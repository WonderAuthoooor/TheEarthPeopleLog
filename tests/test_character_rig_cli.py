"""昂贵驱动渲染前拒绝覆盖已有结果和不匹配的母版。"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CharacterRigCliTests(unittest.TestCase):
    def invoke(self, source, output):
        return subprocess.run([sys.executable, '-X', 'utf8', str(ROOT / 'scripts/review-c-character.py'),
                               '--source-review', str(source), '--output', str(output)],
                              cwd=ROOT, capture_output=True, text=True, encoding='utf-8', timeout=15)

    def test_existing_result_preserved_before_source_access(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'result'; output.mkdir()
            marker = output / 'keep.txt'; marker.write_text('original')
            result = self.invoke(Path(tmp) / 'missing', output)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('输出目录已存在', result.stderr)
            self.assertEqual(marker.read_text(), 'original')
            self.assertEqual(list(output.iterdir()), [marker])

    def test_modified_source_rejected_without_creating_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'source'; source.mkdir()
            (source / 'export-report.json').write_text(json.dumps({'blend_sha256': '0' * 64}))
            (source / 'C-character.blend').write_bytes(b'modified')
            output = Path(tmp) / 'result'
            result = self.invoke(source, output)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('源工程哈希不一致', result.stderr)
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
