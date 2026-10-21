"""Isolated local worker. Atomic result files are the recovery contract."""
import os
from pathlib import Path
import threading
import time
import re
import shutil
from pipeline import core
from .storage import lease, read_json
from .processes import ChildGroup


def execute(run):
    run = Path(run).resolve()
    with lease(run / ".worker.lock"):
        request = read_json(run / "request.json")
        data = core.load_job(run)
        state = {"message": "准备素材", "progress": 1, "heartbeat": core.now(), "pid": os.getpid()}
        done = threading.Event()
        stage = [5, 68]
        def publish():
            state["heartbeat"] = core.now()
            core.save_json(run / "progress.json", dict(state))
        def heartbeat():
            while not done.wait(1):
                try:
                    publish()
                except OSError:
                    pass
        def log(message):
            state["message"] = str(message)
            if "添加字幕" in str(message):
                stage[:] = [72, 24]
            publish()
        def progress(seconds):
            state["progress"] = min(97, stage[0] + stage[1] * seconds / max(.1, float(data["duration"])))
        core.MEDIA_CANCEL = lambda: (run / "cancel.json").exists()
        core.MEDIA_PROGRESS = progress
        publish()
        thread = threading.Thread(target=heartbeat, daemon=True)
        thread.start()
        children = None
        try:
            children = ChildGroup()
            def attach(process):
                children.attach(process)
                state["media_pid"] = process.pid
                publish()
            core.MEDIA_PROCESS = attach
            if core.MEDIA_CANCEL():
                raise core.PipelineError("任务已取消")
            if request["kind"] == "render":
                output = core.render(run, data, log=log, resolution=request["resolution"])
                # Commit a complete package in a readable, unique version folder.
                title = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", data["title"]).strip(" .")[:40] or "地球人日志"
                exports = Path(request["project_dir"]) / "exports"
                exports.mkdir(exist_ok=True)
                name = f"{core.now()[:10].replace('-', '')}_{title}_r{request['revision']:04}_{run.name[:8]}"
                target = exports / name
                staging = exports / ("." + name + ".part")
                if staging.exists():
                    # Only this run's own staging output, never originals or other runs.
                    if staging.resolve().parent != exports.resolve():
                        raise core.PipelineError("导出路径检查失败")
                    shutil.rmtree(staging)
                shutil.copytree(output, staging, ignore=shutil.ignore_patterns("work"))
                core.save_json(staging / "sources-and-shots.json", {"source_url": data.get("source_url"), "source_note": data.get("source_note"), "event_date": data.get("event_date"), "video": data["video"], "clip_start": data["clip_start"], "duration": data["duration"], "layout": data.get("layout", "classic"), "context": data.get("context", ""), "observation": data.get("observation", ""), "cover_at": data.get("cover_at"), "comments": data["comments"], "narration_audio": data.get("narration_audio"), "snapshot": str(run / "job.json"), "revision": request["revision"]})
                report = read_json(staging / "review.json")
                if not all(core.fingerprint(staging / file) == digest for file, digest in report["output_hashes"].items()):
                    raise core.PipelineError("导出包校验失败，未标记为完成")
                if target.exists():
                    # A crash after atomic directory commit can leave a valid package.
                    if not all((target / file).is_file() and core.fingerprint(target / file) == digest for file, digest in report["output_hashes"].items()):
                        raise core.PipelineError("已有同任务导出包内容不同，已保留两个版本以便核查")
                    shutil.rmtree(staging)
                else:
                    staging.rename(target)
                output = target
                result = {"state": "SUCCEEDED", "output": str(output), "message": "草稿已生成 · 内容仍需审核"}
            else:
                # yt-dlp hooks enable cancellation without touching other processes.
                from yt_dlp import YoutubeDL
                original = YoutubeDL.__init__
                def hooked(instance, params=None, *args, **kwargs):
                    params = dict(params or {})
                    def hook(event):
                        if core.MEDIA_CANCEL():
                            raise core.PipelineError("下载已取消")
                        total = event.get("total_bytes") or event.get("total_bytes_estimate") or 0
                        state["progress"] = min(97, 100 * event.get("downloaded_bytes", 0) / total) if total else 5
                    params["progress_hooks"] = [hook]
                    return original(instance, params, *args, **kwargs)
                YoutubeDL.__init__ = hooked
                video = core.download_x(run, data, log=log)
                result = {"state": "SUCCEEDED", "output": str(core.asset_path(run, video)), "message": "视频已取得 · 请导入项目并核查出处", "source_note": data.get("source_note", "")}
            if core.MEDIA_CANCEL():
                result = {"state": "CANCELLED", "message": "已取消；已完成的中间文件保留"}
        except Exception as exc:
            result = {"state": "CANCELLED" if core.MEDIA_CANCEL() else "FAILED", "message": str(exc)[:2500]}
        finally:
            done.set()
            thread.join(timeout=2)
            core.MEDIA_CANCEL = core.MEDIA_PROGRESS = None
            core.MEDIA_PROCESS = None
            if children:
                children.close()
        result.update(completed_at=core.now(), revision=request["revision"], project_id=request["project_id"])
        core.save_json(run / "result.json", result)
        return 0 if result["state"] == "SUCCEEDED" else 1
