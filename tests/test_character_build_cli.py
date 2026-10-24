"""制作入口必须在启动昂贵渲染前拒绝来源错误和已有输出。"""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT=Path(__file__).resolve().parents[1]


class CharacterBuildSafetyTests(unittest.TestCase):
    def invoke(self, source, output):
        return subprocess.run([sys.executable,'-X','utf8',str(ROOT/'scripts/build-c-character.py'),
                               '--source',str(source),'--output',str(output)],
                              cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=15)

    def test_existing_output_preserved_before_source_or_renderer_access(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory);marker=folder/'keep.txt';marker.write_text('original')
            result=self.invoke(folder/'missing.vrm',folder)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('输出目录已存在',result.stderr)
            self.assertEqual(marker.read_text(),'original')
            self.assertEqual(list(folder.iterdir()),[marker])

    def test_wrong_source_hash_does_not_create_output(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory);source=folder/'wrong.vrm';source.write_bytes(b'not approved source')
            output=folder/'new-result'
            result=self.invoke(source,output)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('来源校验不一致',result.stderr)
            self.assertFalse(output.exists())


if __name__=='__main__':unittest.main()
