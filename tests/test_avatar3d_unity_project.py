"""动作工程准备的输入完整性、时间保护及不覆盖行为；不伪造Unity执行。"""
from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / '.runtime/python'), str(ROOT)]
from avatar3d.models import REQUIRED, atomic_json, digest
from avatar3d.unity_project import prepare_project, bone_bindings, SDK_FILENAME

TEMP = ROOT / '.runtime/avatar3d-tests'
TEMP.mkdir(parents=True, exist_ok=True)


class UnityProjectTests(unittest.TestCase):
    def fixture(self, root):
        source = root / 'exchange'
        source.mkdir()
        names = {'source.blend', 'character.vrm', 'animation.fbx', 'transparent.mov',
                 'preview.mp4', 'poster.png', 'model-metadata.json', 'manifest.json',
                 'roundtrip.json', '使用说明.txt'}
        for name in names:
            (source / name).write_bytes(name.encode())
        atomic_json(source / 'roundtrip.json', {'passed': True})
        atomic_json(source / 'manifest.json', {
            'schema': 1, 'fps': 12, 'frames': 18, 'clip_key_range_seconds': 17 / 12,
            'model_sha256': digest(source / 'character.vrm'),
            'source_blend_sha256': digest(source / 'source.blend'),
            'source_bones': {name: name for name in REQUIRED}, 'loop': False,
            'validation': {'blender_fbx_roundtrip': 'passed'}})
        self.seal(source)
        sdk = root / SDK_FILENAME
        sdk.write_bytes(b'unit-test-sdk-not-for-unity')
        return source, sdk

    def seal(self, source):
        atomic_json(source / 'exchange-complete.json', {'schema': 1, 'files': {
            name: digest(source / name) for name in (
                'source.blend', 'character.vrm', 'animation.fbx', 'transparent.mov',
                'preview.mp4', 'poster.png', 'model-metadata.json', 'manifest.json',
                'roundtrip.json', '使用说明.txt')}})

    def test_prepare_is_portable_preserves_source_and_does_not_claim_unity_pass(self):
        with tempfile.TemporaryDirectory(dir=TEMP) as tmp:
            root = Path(tmp); source, sdk = self.fixture(root)
            before = digest(source / 'exchange-complete.json')
            with patch('avatar3d.unity_project.SDK_SHA256', digest(sdk)):
                output = prepare_project(source, root / '工程 空格', sdk)
            record = json.loads((output / 'prepare-complete.json').read_text())
            self.assertEqual(record['unity_execution'], 'pending')
            self.assertEqual(record['warudo_playback'], 'pending')
            self.assertTrue(all(digest(output / name) == sha for name, sha in record['files'].items()))
            self.assertEqual(digest(source / 'exchange-complete.json'), before)
            self.assertFalse(list(output.rglob('*.anim')))
            self.assertFalse(list(output.rglob('*.warudo')))
            self.assertEqual((output / 'ProjectSettings/ProjectVersion.txt').read_text(),
                             'm_EditorVersion: 2021.3.45f2\n')

    def test_corrupt_asset_is_rejected_before_output(self):
        with tempfile.TemporaryDirectory(dir=TEMP) as tmp:
            root = Path(tmp); source, sdk = self.fixture(root)
            (source / 'animation.fbx').write_bytes(b'corrupt')
            with self.assertRaises(ValueError): prepare_project(source, root / 'output', sdk)
            self.assertFalse((root / 'output').exists())

    def test_resealed_but_inconsistent_timing_or_model_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=TEMP) as tmp:
            root = Path(tmp); source, sdk = self.fixture(root)
            original = json.loads((source / 'manifest.json').read_text())
            for change in ({'fps': 24}, {'frames': 0}, {'frames': True},
                           {'clip_key_range_seconds': float('nan')}, {'model_sha256': '0' * 64}):
                atomic_json(source / 'manifest.json', {**original, **change}); self.seal(source)
                with self.assertRaises(ValueError): prepare_project(source, root / 'output', sdk)
                self.assertFalse((root / 'output').exists())

    def test_sdk_mismatch_and_existing_destination_do_not_overwrite(self):
        with tempfile.TemporaryDirectory(dir=TEMP) as tmp:
            root = Path(tmp); source, sdk = self.fixture(root)
            output = root / 'output'; output.mkdir()
            (output / 'user.txt').write_text('keep')
            with self.assertRaises(ValueError): prepare_project(source, output, sdk)
            with patch('avatar3d.unity_project.SDK_SHA256', digest(sdk)):
                with self.assertRaises(FileExistsError): prepare_project(source, output, sdk)
                with self.assertRaises(ValueError): prepare_project(source, source / 'nested', sdk)
            self.assertEqual((output / 'user.txt').read_text(), 'keep')

    def test_copy_failure_retains_diagnostics_without_success_marker(self):
        with tempfile.TemporaryDirectory(dir=TEMP) as tmp:
            root = Path(tmp); source, sdk = self.fixture(root)
            with patch('avatar3d.unity_project.SDK_SHA256', digest(sdk)), \
                 patch('avatar3d.unity_project.shutil.copyfile', side_effect=OSError('disk full')):
                with self.assertRaises(OSError): prepare_project(source, root / 'output', sdk)
            self.assertFalse((root / 'output/prepare-complete.json').exists())
            self.assertIn('disk full', (root / 'output/prepare-error.json').read_text())

    def test_vrm_thumb_generations_and_duplicate_required_bones(self):
        base = {name: name for name in REQUIRED}
        v1 = {**base, 'leftThumbMetacarpal': 'thumb.01',
              'leftThumbProximal': 'thumb.02', 'leftThumbDistal': 'thumb.03'}
        mapped = {b['humanBone']: b['sourceBone'] for b in bone_bindings(v1)}
        self.assertEqual([mapped['LeftThumb' + segment] for segment in ('Proximal', 'Intermediate', 'Distal')],
                         ['thumb.01', 'thumb.02', 'thumb.03'])
        v0 = {**base, 'leftThumbProximal': '01', 'leftThumbIntermediate': '02', 'leftThumbDistal': '03'}
        self.assertEqual(len(bone_bindings(v0)), len(base) + 3)
        for invalid in ({**base, 'head': base['hips']}, {**base, 'head': ''}, {**base, 'unknown': 'extra'}):
            with self.assertRaises(ValueError): bone_bindings(invalid)


if __name__ == '__main__': unittest.main()
