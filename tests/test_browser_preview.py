"""实编解码检查预览缓存、取消和有界备用动画，不依赖浏览器GUI。"""
from pathlib import Path
import json
import sys
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / '.runtime/python'), str(ROOT)]
import av
from PIL import Image, ImageDraw
from avatar3d.browser_preview import prepare
from avatar3d.models import atomic_json, digest


class PreviewTests(unittest.TestCase):
    def setUp(self):
        test_root = ROOT / '.runtime/avatar3d-tests'
        test_root.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=test_root)
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)

    def source(self, count=15, still=False):
        path = self.folder / '动作预览.mp4'
        with av.open(str(path), 'w') as output:
            stream = output.add_stream('libx264', rate=30)
            stream.width, stream.height, stream.pix_fmt = 64, 96, 'yuv420p'
            for index in range(count):
                image = Image.new('RGB', (64, 96), '#28323f')
                ImageDraw.Draw(image).rectangle((0, 20, 10 if still else 10 + index % 50, 70), fill='#ffbc68')
                frame = av.VideoFrame.from_image(image)
                frame.pts = index
                for packet in stream.encode(frame):output.mux(packet)
            for packet in stream.encode():output.mux(packet)
        atomic_json(self.folder / 'complete.json', {'frames': count, 'files': {'动作预览.mp4': digest(path)}})
        return digest(path)

    def test_real_decode_cache_and_corruption_rebuild_preserve_original(self):
        original = self.source()
        page = prepare(self.folder)
        record = json.loads((page.parent / 'complete.json').read_text(encoding='utf-8'))
        self.assertEqual(record['frames'], 15)
        self.assertEqual(record['fallback_duration_ms'], 500)
        mtime = page.stat().st_mtime_ns
        self.assertEqual(prepare(self.folder), page)
        self.assertEqual(page.stat().st_mtime_ns, mtime)
        (page.parent / 'preview.webm').write_bytes(b'broken')
        prepare(self.folder)
        with av.open(str(page.parent / 'preview.webm')) as video:
            self.assertEqual(sum(1 for _ in video.decode(video=0)), 15)
        self.assertEqual(digest(self.folder / '动作预览.mp4'), original)

    def test_long_video_preserves_full_video_but_bounds_fallback(self):
        self.source(100)
        page = prepare(self.folder)
        self.assertIn('前3秒', page.read_text(encoding='utf-8'))
        record = json.loads((page.parent / 'complete.json').read_text(encoding='utf-8'))
        self.assertEqual(record['frames'], 100)
        self.assertEqual(record['fallback_duration_ms'], 3000)

    def test_cancel_during_encode_leaves_no_complete_cache_and_can_retry(self):
        original = self.source()
        cancel = threading.Event()
        with self.assertRaises(InterruptedError):
            prepare(self.folder, cancel, lambda _: cancel.set())
        self.assertFalse((self.folder / '.browser-preview.lock').exists())
        self.assertFalse((self.folder / 'browser-preview/complete.json').exists())
        self.assertEqual(digest(self.folder / '动作预览.mp4'), original)
        self.assertTrue(prepare(self.folder).is_file())

    def test_source_hash_and_frame_mismatch_rejected(self):
        self.source()
        record = json.loads((self.folder / 'complete.json').read_text(encoding='utf-8'))
        record['frames'] = 16
        atomic_json(self.folder / 'complete.json', record)
        with self.assertRaisesRegex(ValueError, '帧数'):prepare(self.folder)
        (self.folder / '动作预览.mp4').write_bytes(b'corrupt')
        with self.assertRaisesRegex(ValueError, '哈希'):prepare(self.folder)

    def test_static_animation_can_be_collapsed_by_webp(self):
        self.source(still=True)
        self.assertTrue(prepare(self.folder).is_file())


if __name__ == '__main__':unittest.main()
