"""为已完成的角色渲染准备兼容预览，与桌面应用共用实现。"""
from pathlib import Path
import argparse
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / '.runtime/python'), str(ROOT)]
from avatar3d.browser_preview import prepare
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path)
    print(prepare(parser.parse_args().folder))
