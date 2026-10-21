"""Durability and ownership checks. No external requests or paid APIs."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import shutil
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".runtime" / "python"))
sys.path.insert(0, str(ROOT))
from studio.storage import Workspace, lease, read_json
from pipeline import core


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / ".runtime")
        self.root = Path(self.temp.name)
        self.store = Workspace(self.root / "中文 空格 工作区")
        self.doc = self.store.create()

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_double_open_preserves_first_owner(self):
        with self.assertRaises(core.PipelineError):
            Workspace(self.store.root)
        self.doc["job"]["title"] = "仍可保存"
        self.store.save(self.doc)
        self.assertEqual(self.store.load(self.doc["project_id"])["job"]["title"], "仍可保存")

    def test_atomic_save_failure_keeps_revision_and_disk(self):
        old = copy.deepcopy(self.doc)
        self.doc["job"]["title"] = "未保存修改"
        actual = core.save_json
        def full(path, data):
            if Path(path).name == "project.json":
                raise OSError("simulated disk full")
            return actual(path, data)
        with patch("studio.storage.core.save_json", side_effect=full):
            with self.assertRaises(OSError):
                self.store.save(self.doc)
        self.assertEqual(self.doc["revision"], old["revision"])
        self.assertEqual(self.store.load(old["project_id"]), old)

    def test_external_revision_conflict(self):
        stale = copy.deepcopy(self.doc)
        self.store.save(self.doc)
        with self.assertRaises(core.PipelineError):
            self.store.save(stale)

    def test_corrupt_document_retains_recovery_snapshot(self):
        self.store.save(self.doc)
        folder = self.store.path(self.doc["project_id"])
        (folder / "project.json").write_text("broken", encoding="utf-8")
        with self.assertRaises(core.PipelineError):
            self.store.load(self.doc["project_id"])
        snapshot = read_json(folder / "snapshots" / "r000001.json")
        self.assertEqual(snapshot["project_id"], self.doc["project_id"])
        self.assertTrue(self.store.list_projects()[0][3])
        restored = self.store.restore(folder / "snapshots" / "r000001.json")
        self.assertEqual(self.store.load(restored["project_id"])["job"]["title"], snapshot["job"]["title"])
        self.assertTrue(list((folder / "snapshots").glob("before-restore-*.json")))

    def test_migration_copies_assets_and_preserves_source(self):
        folder, job = core.new_job(self.root / "old")
        original = self.root / "原始 图.png"
        original.write_bytes(b"original bytes")
        job["comments"] = [{"image": str(original), "url": "", "translation": "", "start": 1, "end": 2}]
        core.save_job(folder, job)
        before = core.fingerprint(folder / "job.json")
        migrated = self.store.migrate(folder)
        copied = self.store.path(migrated["project_id"]) / migrated["job"]["comments"][0]["image"]
        self.assertEqual(copied.read_bytes(), original.read_bytes())
        self.assertEqual(core.fingerprint(folder / "job.json"), before)

    def task(self):
        self.doc["job"]["source_url"] = "https://x.com/example/status/123"
        self.store.save(self.doc)
        return self.store.enqueue(self.doc, "download")

    def test_deduplicates_queue_and_freezes_input(self):
        task = self.task()
        self.assertEqual(task, self.store.enqueue(self.doc, "download"))
        self.doc["job"]["title"] = "之后编辑"
        self.store.save(self.doc)
        snapshot = core.load_job(self.store.runs / task)
        self.assertNotEqual(snapshot["title"], self.doc["job"]["title"])

    def test_recovery_uses_os_lease_not_age(self):
        task = self.task()
        self.store.update_task(task, state="RUNNING")
        with lease(self.store.runs / task / ".worker.lock"):
            self.store.reconcile()
            self.assertEqual(self.store.tasks()[0]["state"], "RUNNING")
        self.store.reconcile()
        self.assertEqual(self.store.tasks()[0]["state"], "INTERRUPTED")
        self.store.retry(task)
        self.assertEqual(self.store.tasks()[0]["state"], "QUEUED")

    def test_cancel_queued_and_completed_receipt_recovery(self):
        task = self.task()
        self.store.cancel(task)
        self.assertEqual(self.store.tasks()[0]["state"], "CANCELLED")
        self.store.retry(task)
        self.store.update_task(task, state="RUNNING")
        core.save_json(self.store.runs / task / "result.json", {"state": "SUCCEEDED", "output": "test.mp4", "message": "receipt"})
        self.store.reconcile()
        self.assertEqual(self.store.tasks()[0]["state"], "SUCCEEDED")

    def test_ids_cannot_escape_workspace(self):
        with self.assertRaises(core.PipelineError):
            self.store.path("../../other")

    def test_workspace_move_rebases_queued_snapshot(self):
        task = self.task()
        old_root = self.store.root
        self.store.close()
        moved = self.root / "移动后的 工作区"
        shutil.move(str(old_root), str(moved))
        self.store = Workspace(moved)
        request = read_json(self.store.runs / task / "request.json")
        self.assertEqual(Path(request["project_dir"]), self.store.path(self.doc["project_id"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
