"""Portable documents and a durable, single-owner execution queue.

Workers never write the editor document or database. Immutable run inputs and
atomic receipts allow reconciliation after the UI is interrupted.
"""
from __future__ import annotations
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import uuid
from contextlib import contextmanager
from pipeline import core


@contextmanager
def lease(path):
    """An OS-held byte lock; automatically released when its owner exits."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    stream = path.open("a+b")
    try:
        # Reading an already locked byte itself raises EACCES on Windows.
        if os.fstat(stream.fileno()).st_size == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (OSError, IOError):
        stream.close()
        raise core.PipelineError("此工作区或任务正在另一个进程中使用。")
    try:
        yield
    finally:
        stream.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream, fcntl.LOCK_UN)
        stream.close()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


class Workspace:
    def __init__(self, root):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.guard = lease(self.root / ".studio.lock")
        self.guard.__enter__()
        try:
            self.projects = self.root / "projects"
            self.projects.mkdir(exist_ok=True)
            self.runs = self.root / "runs"
            self.runs.mkdir(exist_ok=True)
            self.db = sqlite3.connect(self.root / "workspace.sqlite")
            self.db.row_factory = sqlite3.Row
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.execute("PRAGMA synchronous=FULL")
            version = self.db.execute("PRAGMA user_version").fetchone()[0]
            if version > 1:
                raise core.PipelineError("工作区由更新版本创建，请使用对应版本；未改写数据。")
            self.db.execute("""CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY, project_id TEXT NOT NULL, revision INTEGER,
                kind TEXT NOT NULL, state TEXT NOT NULL, digest TEXT,
                created_at TEXT, updated_at TEXT, progress REAL DEFAULT 0,
                message TEXT DEFAULT '', output TEXT DEFAULT '')""")
            self.db.execute("PRAGMA user_version=1")
            self.db.commit()
            self.relocate_if_needed()
        except Exception:
            if hasattr(self, "db"):
                self.db.close()
            self.guard.__exit__(None, None, None)
            raise

    def close(self):
        self.db.close()
        self.guard.__exit__(None, None, None)

    def path(self, project_id):
        if not isinstance(project_id, str) or not all(c in "0123456789abcdef-" for c in project_id) or len(project_id) != 36:
            raise core.PipelineError("项目编号无效。")
        return self.projects / project_id

    def create(self):
        project_id = str(uuid.uuid4())
        folder = self.path(project_id)
        folder.mkdir()
        # Obtain defaults from the established schema without changing old jobs.
        old_dir, job = core.new_job(folder / ".seed")
        shutil.rmtree(folder / ".seed")
        job.pop("revision", None)
        document = {"schema_version": 2, "project_id": project_id, "revision": 0,
                    "created_at": core.now(), "updated_at": core.now(), "job": job}
        self.save(document)
        return document

    def load(self, project_id):
        try:
            document = read_json(self.path(project_id) / "project.json")
            if document.get("schema_version") != 2 or document.get("project_id") != project_id or not isinstance(document.get("job"), dict):
                raise ValueError("schema")
            return document
        except (OSError, ValueError) as exc:
            raise core.PipelineError("项目文件损坏或版本不兼容。原文件已保留，可从项目目录 snapshots 恢复。") from exc

    def save(self, document):
        folder = self.path(document["project_id"])
        target = folder / "project.json"
        if target.exists():
            previous = read_json(target)
            if previous["revision"] != document["revision"]:
                raise core.PipelineError("项目被外部程序更新，请重新打开后再编辑。当前修改尚未保存。")
            core.save_json(folder / "snapshots" / f"r{previous['revision']:06}.json", previous)
        candidate = copy.deepcopy(document)
        candidate["revision"] += 1
        candidate["updated_at"] = core.now()
        core.save_json(target, candidate)
        document.update(candidate)
        core.save_json(self.root / "recent.json", {"project_id": document["project_id"]})

    def list_projects(self):
        rows = []
        for folder in self.projects.iterdir():
            if not folder.is_dir():
                continue
            try:
                d = self.load(folder.name)
                rows.append((d["updated_at"], d["project_id"], d["job"]["title"], ""))
            except core.PipelineError:
                rows.append(("", folder.name, "文件损坏 · 点击查看恢复提示", str(folder)))
        return sorted(rows, reverse=True)

    def restore(self, snapshot):
        document = read_json(snapshot)
        if document.get("schema_version") != 2 or not isinstance(document.get("job"), dict):
            raise core.PipelineError("这不是受支持的项目快照。")
        folder = self.path(document["project_id"])
        if not folder.is_dir():
            raise core.PipelineError("该快照所属项目不在当前工作区。请先切换工作区。")
        target = folder / "project.json"
        old_revision = document["revision"]
        if target.exists():
            backup = folder / "snapshots" / ("before-restore-" + uuid.uuid4().hex[:12] + ".json")
            backup.parent.mkdir(exist_ok=True)
            shutil.copyfile(target, backup)
            try:
                old_revision = max(old_revision, read_json(target).get("revision", 0))
            except ValueError:
                pass
        document["revision"] = old_revision + 1
        document["updated_at"] = core.now()
        core.save_json(target, document)
        return document

    def relocate_if_needed(self):
        marker = self.root / "workspace.json"
        previous = read_json(marker).get("root") if marker.exists() else None
        if previous and Path(previous) != self.root:
            old_root = Path(previous)
            # Do not clone a live writer. Windows locks are checked, not timestamps.
            if old_root.exists():
                with lease(old_root / ".studio.lock"):
                    for task in self.tasks():
                        if task["state"] == "RUNNING":
                            with lease(old_root / "runs" / task["id"] / ".worker.lock"):
                                pass
            def rebase(value):
                if isinstance(value, dict):
                    return {k: rebase(v) for k, v in value.items()}
                if isinstance(value, list):
                    return [rebase(v) for v in value]
                if isinstance(value, str):
                    try:
                        path = Path(value)
                        if path.is_absolute() and path.is_relative_to(old_root):
                            return str(self.root / path.relative_to(old_root))
                    except (ValueError, OSError):
                        pass
                return value
            for run in self.runs.iterdir():
                for name in ("job.json", "request.json", "result.json"):
                    path = run / name
                    if path.exists():
                        core.save_json(path, rebase(read_json(path)))
            for task in self.tasks():
                if task["output"]:
                    self.update_task(task["id"], output=rebase(task["output"]))
            core.save_json(self.root / "relocation.json", {"at": core.now(), "previous_root": previous, "root": str(self.root)})
        core.save_json(marker, {"schema_version": 1, "root": str(self.root), "updated_at": core.now()})

    def migrate(self, old_folder):
        """Copy a legacy job and every referenced file; originals remain intact."""
        old_folder = Path(old_folder).resolve()
        job = core.load_job(old_folder)
        document = self.create()
        folder = self.path(document["project_id"])
        migrated = copy.deepcopy(job)
        manifest = []
        references = [(migrated, k) for k in ("video", "narration_audio", "subtitle_file") if migrated.get(k)]
        references += [(c, "image") for c in migrated.get("comments", [])]
        for owner, key in references:
            original = core.asset_path(old_folder, owner[key])
            owner[key] = core.import_asset(folder, original)
            manifest.append({"original": str(original), "asset": owner[key], "sha256": core.fingerprint(original)})
        migrated.pop("last_output", None)
        migrated.pop("revision", None)
        # Generated SRT becomes an explicitly imported timing file; preserve origin.
        migrated["steps"] = {}
        document["job"] = migrated
        core.save_json(folder / "legacy-job.json", job)
        core.save_json(folder / "migration.json", {"at": core.now(), "source": str(old_folder), "files": manifest})
        self.save(document)
        return document

    def enqueue(self, document, kind="render", resolution=1080):
        job = copy.deepcopy(document["job"])
        folder = self.path(document["project_id"])
        if kind == "render":
            core.validate_job(folder, job)
        elif kind == "download":
            core.validate_x_url(job.get("source_url", ""))
        else:
            raise core.PipelineError("不支持的任务类型。")
        for key in ("video", "narration_audio", "subtitle_file"):
            if job.get(key):
                job[key] = str(core.asset_path(folder, job[key]))
        for comment in job.get("comments", []):
            comment["image"] = str(core.asset_path(folder, comment["image"]))
        job["revision"] = 0
        job.pop("last_output", None)
        # Hash source bytes as well as settings. Original files are immutable in UI.
        hashes = {key: core.fingerprint(job[key]) for key in ("video", "narration_audio", "subtitle_file") if job.get(key)}
        hashes["comments"] = [core.fingerprint(c["image"]) for c in job.get("comments", [])]
        settings = {k: v for k, v in job.items() if k not in ("updated_at", "created_at", "revision", "steps", "quick_clips")}
        # PyInstaller stores modules inside its archive, not as loose .py files.
        renderer_source = Path(sys.executable) if getattr(sys, "frozen", False) else Path(core.__file__)
        renderer = core.fingerprint(renderer_source)
        digest = hashlib.sha256(json.dumps([kind, resolution, settings, hashes, renderer], sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        active = self.db.execute("SELECT id FROM tasks WHERE project_id=? AND kind=? AND digest=? AND state IN ('QUEUED','RUNNING')", (document["project_id"], kind, digest)).fetchone()
        if active:
            return active["id"]
        if kind == "render":
            for cached in self.db.execute("SELECT id,output FROM tasks WHERE project_id=? AND digest=? AND state='SUCCEEDED'", (document["project_id"], digest)):
                try:
                    output = Path(cached["output"])
                    receipt = read_json(output / "review.json")
                    hashes = receipt["output_hashes"]
                    if hashes and all((output / name).is_file() and core.fingerprint(output / name) == sha for name, sha in hashes.items()):
                        return cached["id"]
                except (OSError, ValueError, KeyError):
                    pass
        task_id = str(uuid.uuid4())
        run = self.runs / task_id
        run.mkdir()
        core.save_job(run, job)
        core.save_json(run / "request.json", {"kind": kind, "resolution": resolution, "project_id": document["project_id"], "project_dir": str(folder), "revision": document["revision"]})
        self.db.execute("INSERT INTO tasks(id,project_id,revision,kind,state,digest,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)", (task_id, document["project_id"], document["revision"], kind, "QUEUED", digest, core.now(), core.now()))
        self.db.commit()
        return task_id

    def tasks(self):
        return [dict(row) for row in self.db.execute("SELECT * FROM tasks ORDER BY created_at DESC, rowid DESC")]

    def update_task(self, task_id, **fields):
        if not set(fields) <= {"state", "progress", "message", "output"}:
            raise ValueError("Invalid task fields")
        fields["updated_at"] = core.now()
        self.db.execute("UPDATE tasks SET " + ",".join(k + "=?" for k in fields) + " WHERE id=?", (*fields.values(), task_id))
        self.db.commit()

    def cancel(self, task_id):
        row = self.db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if row and row["state"] == "QUEUED":
            self.update_task(task_id, state="CANCELLED", message="已取消，项目已保留")
        elif row and row["state"] == "RUNNING":
            core.save_json(self.runs / task_id / "cancel.json", {"at": core.now()})

    def reconcile(self):
        for row in self.tasks():
            if row["state"] != "RUNNING":
                continue
            run = self.runs / row["id"]
            receipt = run / "result.json"
            if receipt.exists():
                result = read_json(receipt)
                self.update_task(row["id"], state=result["state"], message=result.get("message", ""), output=result.get("output", ""), progress=100 if result["state"] == "SUCCEEDED" else 0)
            else:
                try:
                    with lease(run / ".worker.lock"):
                        self.update_task(row["id"], state="INTERRUPTED", message="运行进程已结束；可按原快照重新执行。本地导出不产生API费用。")
                except core.PipelineError:
                    progress = run / "progress.json"
                    if progress.exists():
                        try:
                            event = read_json(progress)
                            self.update_task(row["id"], message=event["message"], progress=event["progress"])
                        except (ValueError, OSError, KeyError):
                            pass

    def retry(self, task_id):
        row = self.db.execute("SELECT state FROM tasks WHERE id=?", (task_id,)).fetchone()
        if not row or row["state"] not in ("INTERRUPTED", "FAILED", "CANCELLED"):
            raise core.PipelineError("只有已停止的任务可以重新执行。")
        run = self.runs / task_id
        with lease(run / ".worker.lock"):
            for name in ("cancel.json", "result.json", ".running.lock"):
                (run / name).unlink(missing_ok=True)
        self.update_task(task_id, state="QUEUED", progress=0, message="按原快照重新排队")
