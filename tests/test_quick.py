"""Quick-cut boundaries, batch isolation and score scope checks."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".runtime" / "python"))
sys.path.insert(0, str(ROOT))
from studio.storage import Workspace
from studio import quick
from pipeline import core


class QuickChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / ".runtime")
        self.store = Workspace(self.temp.name)
        self.doc = self.store.create()
        self.doc["job"] = quick.defaults(self.doc["job"])
        folder = self.store.path(self.doc["project_id"])
        (folder / "sample.mp4").write_bytes(b"unit-test-placeholder-not-real-video")
        self.doc["job"]["video"] = "sample.mp4"
        self.folder = folder
        self.meta = patch("pipeline.core.probe", return_value={"duration": 60., "width": 1080, "height": 1080, "has_video": True, "has_audio": True})
        self.meta.start()

    def tearDown(self):
        self.meta.stop()
        self.store.close()
        self.temp.cleanup()

    def test_batch_isolation_and_pending_score_scope(self):
        self.doc["job"]["score"] = {"status": "scored", "dimensions": dict.fromkeys(core.DIMENSIONS, 1), "reason": "仅测试"}
        before = copy.deepcopy(self.doc)
        prepared = quick.prepare_batch(self.doc, [["A", "0", "3", "背景A", "观察A", "1"], ["B", "3", "7", "背景B", "观察B", ""]], self.folder)
        self.assertEqual(self.doc, before)
        self.assertEqual([d["job"]["duration"] for d in prepared], [3, 4])
        self.assertTrue(all(d["job"]["score"]["status"] == "pending" for d in prepared))
        self.assertEqual(prepared[0]["job"]["cover_at"], 1)

    def test_invalid_ranges_and_cover_cannot_escape_clip(self):
        for row in (["A", "5", "3", "", "", ""], ["A", "59", "65", "", "", ""], ["A", "0", "3", "", "", "4"], ["A", "NaN", "3", "", "", ""]):
            with self.assertRaises(core.PipelineError):
                quick.prepare_batch(self.doc, [row], self.folder)

    def test_batch_rejects_shared_voice_or_srt(self):
        rows = [["A", "0", "3", "", "", ""], ["B", "3", "6", "", "", ""]]
        self.doc["job"]["subtitle_file"] = "captions.srt"
        with self.assertRaisesRegex(core.PipelineError, "时轴错位"):
            quick.prepare_batch(self.doc, rows, self.folder)

    def test_copy_and_context_limits(self):
        job = self.doc["job"]
        job.update(context="背景", observation="观察内容", source_note="原作者", source_url="https://example.org/source", event_date="2026-10-19")
        text = quick.posting_copy(job)
        self.assertIn("观察：观察内容", text["description"])
        self.assertIn("待评", text["description"])
        self.assertFalse(text["published"])
        job["observation"] = "长" * 53
        with self.assertRaises(core.PipelineError):
            core.validate_job(self.folder, job)


if __name__ == "__main__":
    unittest.main(verbosity=2)
