import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from avatar3d.models import atomic_json, digest
from avatar3d.live_package import create_package, verify_package, plan_restore, restore_package, _publish


class LivePackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.install = self.root / 'old-install'
        self.data = self.install / 'Warudo_Data/StreamingAssets'
        (self.data / 'Scenes').mkdir(parents=True)
        (self.install / 'Warudo.exe').write_bytes(b'test-marker')
        self.prepared = self.root / 'prepared'; self.prepared.mkdir()
        self.sources = {'Characters/C.vrm': b'model', 'CharacterAnimations/Wave.warudo': b'action'}
        assets = {}
        for i, (name, content) in enumerate(self.sources.items()):
            path = self.data / name; path.parent.mkdir(exist_ok=True); path.write_bytes(content)
            assets[str(i)] = {'file': str(path), 'sha256': digest(path)}
        self.scene = {'appVersion': '0.15.1', 'name': 'C_Live', 'nested': {
            'model': json.dumps('character://data/Characters/C.vrm'),
            'action': json.dumps('character-animation://data/CharacterAnimations/Wave.warudo')}}
        self.scene_path = self.data / 'Scenes/C_Live.json'
        atomic_json(self.scene_path, self.scene)
        atomic_json(self.prepared / 'complete.json', {'scene_file': 'C_Live.json',
                    'scene_sha256': digest(self.scene_path), 'assets': assets})
        self.package = self.root / 'package'
        create_package(self.prepared, self.install, self.package)

    def target(self):
        target = self.root / 'new-install'
        (target / 'Warudo_Data/StreamingAssets').mkdir(parents=True, exist_ok=True)
        (target / 'Warudo.exe').write_bytes(b'marker')
        return target

    def edit_manifest(self, edit):
        path = self.package / 'manifest.json'
        manifest = json.loads(path.read_text(encoding='utf-8'))
        edit(manifest)
        atomic_json(path, manifest)

    def test_portable_restore_after_source_removed_and_repeated_restore(self):
        target = self.target()
        # 搬移后不依赖原绝对目录；原素材内容也不作为恢复来源。
        moved = self.root / 'moved'; self.package.rename(moved)
        self.scene_path.unlink()
        self.assertNotIn(str(self.install), (moved / 'manifest.json').read_text(encoding='utf-8'))
        plan = plan_restore(moved, target)
        self.assertTrue(plan['can_restore'])
        self.assertEqual(plan['items'][-1]['path'], 'Scenes/C_Live.json')
        self.assertEqual(restore_package(moved, target)['added'], 3)
        self.assertEqual(restore_package(moved, target)['reused'], 3)

    def test_conflict_preflight_writes_nothing_and_preserves_user_scene(self):
        target = self.target(); scene = target / 'Warudo_Data/StreamingAssets/Scenes/C_Live.json'
        scene.parent.mkdir(); scene.write_text('user-changes', encoding='utf-8')
        self.assertFalse(plan_restore(self.package, target)['can_restore'])
        with self.assertRaises(FileExistsError): restore_package(self.package, target)
        self.assertEqual(scene.read_text(), 'user-changes')
        self.assertFalse((target / 'Warudo_Data/StreamingAssets/Characters').exists())

    def test_corrupt_dependency_rejected_before_writing(self):
        target = self.target()
        (self.package / 'payload/Characters/C.vrm').write_bytes(b'broken')
        with self.assertRaises(ValueError): restore_package(self.package, target)
        self.assertEqual(list((target / 'Warudo_Data/StreamingAssets').iterdir()), [])

    def test_dependency_reference_not_in_manifest_rejected(self):
        path = self.package / 'payload/Scenes/C_Live.json'
        scene = copy.deepcopy(self.scene); scene['extra'] = 'character-animation://data/CharacterAnimations/Other.warudo'
        atomic_json(path, scene)
        def edit(m):
            row = next(x for x in m['files'] if x['path'].startswith('Scenes/'))
            row.update(size=path.stat().st_size, sha256=digest(path))
        self.edit_manifest(edit)
        with self.assertRaises(ValueError): verify_package(self.package)

    def test_path_traversal_and_duplicate_paths_rejected(self):
        original = (self.package / 'manifest.json').read_bytes()
        for bad in ('../escape.json', 'Scenes/../escape.json', 'Scenes/C.json:ads', '/Scenes/C.json', 'Scenes/CON.json'):
            (self.package / 'manifest.json').write_bytes(original)
            self.edit_manifest(lambda m: m['files'][0].update(path=bad))
            with self.assertRaises(ValueError): verify_package(self.package)
        (self.package / 'manifest.json').write_bytes(original)
        self.edit_manifest(lambda m: m['files'].append(m['files'][0]))
        with self.assertRaises(ValueError): verify_package(self.package)

    def test_failure_rolls_back_only_own_files_and_preserves_reused(self):
        target = self.target(); data = target / 'Warudo_Data/StreamingAssets'
        model = data / 'Characters/C.vrm'; model.parent.mkdir(); model.write_bytes(b'model')
        def fail_scene(source, dest, sha):
            if dest.suffix == '.json': raise OSError('injected-write-failure')
            _publish(source, dest, sha)
        with patch('avatar3d.live_package._publish', side_effect=fail_scene):
            with self.assertRaises(OSError): restore_package(self.package, target)
        self.assertEqual(model.read_bytes(), b'model')
        self.assertFalse((data / 'CharacterAnimations/Wave.warudo').exists())
        self.assertFalse((data / 'Scenes/C_Live.json').exists())
        self.assertFalse(list(data.rglob('*.partial')))

    def test_late_conflict_preserves_external_file(self):
        target = self.target(); data = target / 'Warudo_Data/StreamingAssets'
        def race(source, dest, sha):
            if dest.suffix == '.json': dest.write_bytes(b'concurrent-user-save')
            _publish(source, dest, sha)
        with patch('avatar3d.live_package._publish', side_effect=race):
            with self.assertRaises(FileExistsError): restore_package(self.package, target)
        self.assertEqual((data / 'Scenes/C_Live.json').read_bytes(), b'concurrent-user-save')
        self.assertFalse((data / 'Characters/C.vrm').exists())
        self.assertFalse(list(data.rglob('*.partial')))

    def test_changed_installed_scene_is_not_packaged_as_baseline(self):
        self.scene_path.write_text('{}', encoding='utf-8')
        with self.assertRaises(ValueError): create_package(self.prepared, self.install, self.root / 'new-pack')
        self.assertFalse((self.root / 'new-pack').exists())


if __name__ == '__main__': unittest.main()
