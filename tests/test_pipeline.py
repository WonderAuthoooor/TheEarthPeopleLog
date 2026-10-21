"""Offline regression checks. No network/API spending or publishing."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".runtime" / "python"))
sys.path.insert(0, str(ROOT))
from pipeline import core, providers


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / ".runtime")
        self.base = Path(self.temp.name)
        self.directory, self.data = core.new_job(self.base)

    def tearDown(self):
        self.temp.cleanup()

    def test_lock_conflict_preserves_other_owner(self):
        with core.job_lock(self.directory):
            before = (self.directory / ".running.lock").read_bytes()
            with self.assertRaises(core.PipelineError):
                with core.job_lock(self.directory): pass
            self.assertEqual((self.directory / ".running.lock").read_bytes(), before)
        self.assertFalse((self.directory / ".running.lock").exists())

    def test_exception_releases_own_lock(self):
        with self.assertRaises(RuntimeError):
            with core.job_lock(self.directory): raise RuntimeError("test")
        self.assertFalse((self.directory / ".running.lock").exists())

    def test_revision_rejects_stale_writer(self):
        stale = copy.deepcopy(self.data)
        self.data["title"] = "最新稿件"
        core.save_job(self.directory, self.data)
        stale["title"] = "旧窗口稿件"
        with self.assertRaises(core.PipelineError): core.save_job(self.directory, stale)
        self.assertEqual(core.load_job(self.directory)["title"], "最新稿件")

    def test_content_import_deduplicates_and_preserves_original(self):
        original = self.base / "原文件 含空格.png"
        original.write_bytes(b"same image bytes")
        first = core.import_asset(self.directory, original)
        second = core.import_asset(self.directory, original)
        self.assertEqual(first, second)
        self.assertEqual(original.read_bytes(), b"same image bytes")
        self.assertEqual(len(list((self.directory / "assets").iterdir())), 1)

    def test_x_url_rejects_other_hosts_and_credentials(self):
        for url in ("http://x.com/a/status/123", "https://x.com.evil.test/a/status/123",
                    "https://x.com@evil.test/a/status/123", "https://a:pass@x.com/a/status/123",
                    "https://127.0.0.1/a/status/123", "https://x.com/search?q=robot"):
            with self.assertRaises(core.PipelineError): core.validate_x_url(url)
        self.assertEqual(core.validate_x_url("https://x.com/test/status/123?s=20"), ("https://x.com/test/status/123", "123"))

    def test_score_pending_and_rules(self):
        self.assertIsNone(core.score_value({"status": "pending"}))
        dims = dict.fromkeys(core.DIMENSIONS, 2)
        self.assertEqual(core.score_value({"status": "scored", "dimensions": dims, "reason": "虚构测试"}), 5)
        dims["life"] = True
        with self.assertRaises(core.PipelineError):
            core.score_value({"status": "scored", "dimensions": dims, "reason": "x"})

    def test_srt_roundtrip_and_invalid_timestamps(self):
        path = self.base / "中文字幕.srt"
        cues = [{"start": 1.2, "end": 3.45, "text": "第一行\n第二行"}]
        core.write_srt(path, cues)
        self.assertEqual(core.read_srt(path), cues)
        path.write_text("1\n00:00:02,000 --> 00:00:01,000\n倒序", encoding="utf-8")
        with self.assertRaises(core.PipelineError): core.read_srt(path)

    def test_estimated_captions_cover_timeline(self):
        cues = core.estimated_cues("这是第一句话。\n这是第二句话，有一点停顿。", 3, 20)
        self.assertEqual(cues[0]["start"], 3)
        self.assertEqual(cues[-1]["end"], 20)
        self.assertTrue(all(a["end"] == b["start"] for a, b in zip(cues, cues[1:])))

    def test_ass_does_not_interpret_user_override_tags(self):
        path = self.base / "test.ass"
        core.make_ass(path, [{"start": 0, "end": 1, "text": r"{\pos(0,0)}字幕"}])
        text = path.read_text(encoding="utf-8-sig")
        self.assertNotIn(r"{\pos(0,0)}", text)

    @patch("pipeline.core.probe")
    def test_trim_and_voice_validation(self, probe):
        self.data["video"] = "test.mp4"
        probe.return_value = {"duration": 10, "has_video": True, "has_audio": True}
        self.data["duration"] = 20
        with self.assertRaises(core.PipelineError): core.validate_job(self.directory, self.data)
        self.data["duration"] = 10
        self.data["narration_audio"] = "voice.mp3"
        with self.assertRaises(core.PipelineError): core.validate_job(self.directory, self.data)
        self.data["duration"] = float("nan")
        with self.assertRaises(core.PipelineError): core.validate_job(self.directory, self.data)

    @patch("pipeline.providers.post_json")
    def test_missing_inputs_never_call_paid_service(self, post):
        with self.assertRaises(core.PipelineError): providers.generate_voice(self.directory, self.data)
        with self.assertRaises(core.PipelineError): providers.generate_writing(self.directory, self.data)
        post.assert_not_called()

    @patch("pipeline.providers.post_json")
    def test_writing_cache_and_key_not_serialized(self, post):
        self.data["facts"] = "虚构测试材料，不发布"
        post.return_value = {"choices": [{"message": {"content": "测试建议"}, "finish_reason": "stop"}], "usage": {"total_tokens": 1}}
        self.assertEqual(providers.generate_writing(self.directory, self.data, "SECRET-TEST"), "测试建议")
        self.assertEqual(providers.generate_writing(self.directory, self.data, "SECRET-TEST"), "测试建议")
        self.assertEqual(post.call_count, 1)
        self.assertNotIn("SECRET-TEST", (self.directory / "job.json").read_text(encoding="utf-8"))

    @patch("pipeline.providers.post_json")
    @patch("pipeline.providers.probe", return_value={"duration": 1})
    @patch("pipeline.core.run_media")
    def test_tts_partial_retry_only_regenerates_changed_paragraph(self, run, probe, post):
        def fake_media(args, **kwargs): Path(args[-1]).write_bytes(b"assembled")
        run.side_effect = fake_media
        post.return_value = {"data": {"audio": b"dummy-audio".hex()}, "extra_info": {"usage_characters": 4}}
        self.data["script"] = "第一段\n第二段"
        providers.generate_voice(self.directory, self.data, "SECRET", voice_id="test")
        self.assertEqual(post.call_count, 2)
        self.data["script"] = "第一段\n修改第二段"
        providers.generate_voice(self.directory, self.data, "SECRET", voice_id="test")
        self.assertEqual(post.call_count, 3)
        self.assertNotIn("SECRET", (self.directory / "job.json").read_text(encoding="utf-8"))

    @patch("pipeline.core.probe")
    def test_overlapping_comment_images_are_rejected(self, probe):
        probe.return_value = {"duration": 30, "has_video": True, "has_audio": True}
        self.data["video"] = "source.mp4"
        image = self.base / "screenshot.png"
        image.write_bytes(b"placeholder")
        ref = core.import_asset(self.directory, image)
        self.data["comments"] = [{"image": ref, "start": 5, "end": 10}, {"image": ref, "start": 9, "end": 12}]
        with self.assertRaises(core.PipelineError): core.validate_job(self.directory, self.data)

    @patch("pipeline.core.probe")
    def test_script_cannot_start_at_output_end(self, probe):
        probe.return_value = {"duration": 30, "has_video": True, "has_audio": True}
        self.data.update(video="source.mp4", script="测试稿", narration_start=30)
        with self.assertRaises(core.PipelineError): core.validate_job(self.directory, self.data)


if __name__ == "__main__": unittest.main()
