"""构建入口损坏输入／子进程失败／超时不得产生成功返回。"""
from pathlib import Path
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from avatar3d.models import atomic_json, digest
spec = importlib.util.spec_from_file_location('warudo_build_cli', ROOT / 'scripts/build-warudo-animation.py')
cli = importlib.util.module_from_spec(spec); spec.loader.exec_module(cli)


class BuildCliTests(unittest.TestCase):
    def fixture(self, root):
        root = Path(root); project = root / 'project'; editor = root / 'Unity.exe'; editor.touch()
        folder = project / 'Assets/AvatarBridge/Runs/test'; folder.mkdir(parents=True)
        clip = folder / 'Animation.anim'; clip.write_bytes(b'fixture')
        report = project / 'AvatarBridge/Runs/test/report.json'; report.parent.mkdir(parents=True)
        atomic_json(report, {'passed': True, 'editorVersion': '2021.3.45f2',
            'clipAsset': clip.relative_to(project).as_posix(), 'clipSha256': digest(clip)})
        builder = project / 'Assets/AvatarBridge/Editor/WarudoAnimationBuilder.cs'
        builder.parent.mkdir(parents=True); builder.touch()
        return project, editor, report, clip

    def test_corrupt_clip_stops_before_editor_launch(self):
        with tempfile.TemporaryDirectory(dir=ROOT / '.runtime') as tmp:
            project, editor, report, clip = self.fixture(tmp); clip.write_bytes(b'corrupt')
            with patch.object(cli.subprocess, 'Popen') as launch:
                with self.assertRaises(ValueError): cli.build(project, editor, report)
                launch.assert_not_called()

    def test_failed_editor_and_timeout_cannot_return_success(self):
        with tempfile.TemporaryDirectory(dir=ROOT / '.runtime') as tmp:
            project, editor, report, clip = self.fixture(tmp)
            child = Mock(); child.wait.return_value = 1
            with patch.object(cli.subprocess, 'Popen', return_value=child):
                with self.assertRaises(RuntimeError): cli.build(project, editor, report)
            child.wait.side_effect = [subprocess.TimeoutExpired('Unity', 1), 1]
            with patch.object(cli.subprocess, 'Popen', return_value=child):
                with self.assertRaises(subprocess.TimeoutExpired): cli.build(project, editor, report, 1)
            child.terminate.assert_called_once()
            self.assertFalse(list(project.rglob('*.warudo')))


if __name__ == '__main__': unittest.main()
