import json
import tempfile
import unittest
from pathlib import Path

from avatar3d.models import atomic_json, digest
from avatar3d.rehearsal import DEFAULT
from avatar3d.rehearsal_preview import source_info, output_settings, reusable_frames


class RehearsalPreviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        (self.source / 'scene.blend').write_bytes(b'test master')
        atomic_json(self.source / 'request.json', {'fps': 30, 'rehearsal': DEFAULT})
        self.record = {'baked_frames': 900, 'files': {
            name: digest(self.source / name) for name in ('request.json', 'scene.blend')}}
        atomic_json(self.source / 'rehearsal-complete.json', self.record)

    def test_master_and_request_tampering_rejected(self):
        self.assertEqual(source_info(self.source)['frames'], 900)
        for name in ('scene.blend', 'request.json'):
            original = (self.source / name).read_bytes()
            (self.source / name).write_bytes(original + b' ')
            with self.assertRaises(ValueError):
                source_info(self.source)
            (self.source / name).write_bytes(original)

    def test_mismatched_baked_count_rejected(self):
        self.record['baked_frames'] = 899
        atomic_json(self.source / 'rehearsal-complete.json', self.record)
        with self.assertRaises(ValueError):
            source_info(self.source)

    def test_reuse_requires_matching_parameters(self):
        settings = output_settings(source_info(self.source))
        atomic_json(self.root / 'preview-request.json', settings)
        for changed in ({'width': 480}, {'master_sha256': 'changed'}, {'quality': 'material'}):
            with self.assertRaises(ValueError):
                reusable_frames(self.root, dict(settings, **changed))

    def test_missing_corrupt_and_empty_frames_rebuilt(self):
        from PIL import Image
        settings = output_settings(source_info(self.source))
        atomic_json(self.root / 'preview-request.json', settings)
        frames = self.root / 'frames'
        frames.mkdir()
        valid = Image.new('RGBA', (320, 480), (0, 0, 0, 0))
        valid.putpixel((100, 100), (200, 200, 200, 255))
        for i in range(5):
            path = frames / f'{i:05d}.png'
            valid.save(path)
            path.with_suffix('.sha256').write_text(digest(path))
        (frames / '00001.sha256').unlink()  # 未完成登记
        (frames / '00002.png').write_bytes(b'broken')  # 哈希不匹配
        blank = frames / '00003.png'
        Image.new('RGBA', (320, 480)).save(blank)
        blank.with_suffix('.sha256').write_text(digest(blank))  # 空帧虽匹配也拒绝
        self.assertEqual(set(reusable_frames(self.root, settings)), {0, 4})

    def test_quality_and_size_are_explicit(self):
        source = source_info(self.source)
        self.assertEqual(output_settings(source)['engine'], 'BLENDER_WORKBENCH')
        self.assertEqual(output_settings(source, quality='material')['engine'], 'BLENDER_EEVEE_NEXT')
        for kwargs in ({'width': 321}, {'samples': 0}, {'quality': 'unknown'}):
            with self.assertRaises(ValueError):
                output_settings(source, **kwargs)


if __name__ == '__main__':
    unittest.main()
