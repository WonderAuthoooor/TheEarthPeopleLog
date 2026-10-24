"""SDK本地展开拒绝越界／链接／覆盖；不运行外部SDK。"""
from pathlib import Path
import io
import json
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from avatar3d.models import digest
from avatar3d.warudo_sdk import extract_sdk, stage_sdk
from avatar3d.unity_project import SDK_FILENAME


class SdkExtractionTests(unittest.TestCase):
    def archive(self, root, extra=None):
        archive = Path(root) / 'test.tgz'
        with tarfile.open(archive, 'w:gz') as tar:
            data = json.dumps({'name': 'app.warudo.modtool', 'version': '0.14.5'}).encode()
            member = tarfile.TarInfo('./package.json'); member.size = len(data)
            tar.addfile(member, io.BytesIO(data))
            if extra:
                tar.addfile(extra, io.BytesIO(b''))
        return archive

    def test_extracts_root_layout_and_does_not_overwrite(self):
        with tempfile.TemporaryDirectory(dir=ROOT / '.runtime') as tmp:
            archive = self.archive(tmp); target = Path(tmp) / 'sdk'
            with patch('avatar3d.warudo_sdk.SDK_SHA256', digest(archive)):
                hashes = extract_sdk(archive, target)
                self.assertEqual(hashes['package.json'], digest(target / 'package.json'))
                with self.assertRaises(FileExistsError): extract_sdk(archive, target)

    def test_checksum_mismatch_rejects_before_writing(self):
        with tempfile.TemporaryDirectory(dir=ROOT / '.runtime') as tmp:
            archive = self.archive(tmp); target = Path(tmp) / 'sdk'
            with self.assertRaises(ValueError): extract_sdk(archive, target)
            self.assertFalse(target.exists())

    def test_traversal_absolute_windows_paths_links_and_duplicates_are_rejected(self):
        for name in ('../outside', '/outside', 'C:/outside', 'bad\\outside', './PACKAGE.JSON', './link'):
            with self.subTest(name=name), tempfile.TemporaryDirectory(dir=ROOT / '.runtime') as tmp:
                member = tarfile.TarInfo(name)
                if name.endswith('link'): member.type = tarfile.SYMTYPE; member.linkname = '../outside'
                archive = self.archive(tmp, member); target = Path(tmp) / 'sdk'
                with patch('avatar3d.warudo_sdk.SDK_SHA256', digest(archive)):
                    with self.assertRaises(ValueError): extract_sdk(archive, target)
                self.assertFalse(target.exists())

    def test_stage_requires_config_and_keeps_manifest_backup(self):
        with tempfile.TemporaryDirectory(dir=ROOT / '.runtime') as tmp:
            root = Path(tmp); project = root / 'project'; project.mkdir()
            for folder in ('AvatarBridge', 'LocalPackages', 'Packages'): (project / folder).mkdir()
            (project / 'prepare-complete.json').write_text(json.dumps({'editor_version': '2021.3.45f2'}))
            settings = project / 'AvatarBridge/sdk-settings.txt'; settings.write_text('editor=Unity6')
            manifest = project / 'Packages/manifest.json'; original = {'dependencies': {}, 'test_field': True}
            manifest.write_text(json.dumps(original))
            editor = root / 'Editor/Unity.exe'; editor.parent.mkdir(); editor.write_bytes(b'fixture')
            builtin = editor.parent / 'Data/Resources/PackageManager/BuiltInPackages/com.unity.modules.audio'
            builtin.mkdir(parents=True); (builtin / 'package.json').write_text('{"version":"1.0.0"}')
            archive = self.archive(root); (project / 'LocalPackages' / SDK_FILENAME).write_bytes(archive.read_bytes())
            with self.assertRaises(ValueError): stage_sdk(project, editor)
            self.assertEqual(json.loads(manifest.read_text()), original)
            settings.write_text('editor=2021.3.45f2\napi=NET_Unity_4_8\nassemblyVersionValidation=False\n')
            with patch('avatar3d.warudo_sdk.SDK_SHA256', digest(archive)):
                stage_sdk(project, editor)
            result = json.loads(manifest.read_text())
            self.assertTrue(result['test_field'])
            self.assertEqual(result['dependencies']['com.unity.timeline'], '1.7.6')
            self.assertEqual(json.loads((project / 'AvatarBridge/pre-sdk-manifest.json').read_text()), original)
            self.assertTrue((project / 'Assets/AvatarBridge/Editor/WarudoAnimationBuilder.cs').exists())
            self.assertEqual(json.loads((project / 'AvatarBridge/sdk-staged.json').read_text())['warudo_build'], 'pending')


if __name__ == '__main__': unittest.main()
