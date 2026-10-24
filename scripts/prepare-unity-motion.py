"""研发CLI：离线准备独立Unity动作转换工程，不启动编辑器。"""
from pathlib import Path
import argparse
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / '.runtime/python'), str(ROOT)]
from avatar3d.unity_project import prepare_project


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exchange', type=Path, required=True, help='已完成且校验通过的动作交换包')
    parser.add_argument('--output', type=Path, required=True, help='新的独立工程目录，不覆盖已有文件')
    parser.add_argument('--sdk', type=Path, default=ROOT / '.runtime/warudo-sdk/0.14.5.1/Warudo-Mod-Tool-0.14.5.1.tgz')
    args = parser.parse_args()
    print(prepare_project(args.exchange, args.output, args.sdk))
