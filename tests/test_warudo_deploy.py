"""动作部署的来源校验、重复使用和同名保护；不运行Warudo。"""
from pathlib import Path
import json
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from avatar3d.models import atomic_json, digest
from avatar3d.warudo_deploy import deploy_animation


class DeployTests(unittest.TestCase):
    def fixture(self, root):
        root = Path(root); source = root / 'build'; source.mkdir()
        mod = source / 'AvatarLabWave.warudo'; mod.write_bytes(b'fixture-build')
        report = source / 'report.json'
        atomic_json(report, {'passed': True, 'modFile': str(mod), 'modSha256': digest(mod), 'modName': mod.stem})
        install = root / 'warudo'; install.mkdir(); (install / 'Warudo.exe').touch()
        (install / 'Warudo_Data/StreamingAssets').mkdir(parents=True)
        return report, mod, install

    def test_copy_and_identical_reuse_preserve_user_scene(self):
        with tempfile.TemporaryDirectory(dir=ROOT / '.runtime') as tmp:
            report, mod, install = self.fixture(tmp)
            scene = install / 'scene.json'; scene.write_text('user-scene')
            first = deploy_animation(report, install); second = deploy_animation(report, install)
            self.assertFalse(first['reused']); self.assertTrue(second['reused'])
            self.assertEqual(digest(first['installed_file']), digest(mod))
            self.assertEqual(first['warudo_playback'], 'pending')
            self.assertEqual(scene.read_text(), 'user-scene')

    def test_conflicting_target_is_not_overwritten(self):
        with tempfile.TemporaryDirectory(dir=ROOT / '.runtime') as tmp:
            report, mod, install = self.fixture(tmp)
            target = Path(deploy_animation(report, install)['installed_file']); target.write_bytes(b'user-asset')
            with self.assertRaises(FileExistsError): deploy_animation(report, install)
            self.assertEqual(target.read_bytes(), b'user-asset')

    def test_tampered_or_failed_build_does_not_create_asset_folder(self):
        with tempfile.TemporaryDirectory(dir=ROOT / '.runtime') as tmp:
            report, mod, install = self.fixture(tmp)
            mod.write_bytes(b'corrupt')
            with self.assertRaises(ValueError): deploy_animation(report, install)
            self.assertFalse((install / 'Warudo_Data/StreamingAssets/CharacterAnimations').exists())
            data = json.loads(report.read_text()); data['passed'] = False; atomic_json(report, data)
            with self.assertRaises(ValueError): deploy_animation(report, install)


if __name__ == '__main__': unittest.main()
