"""把已校验交换包转为Warudo动作，复用独立工程并恢复输入，不部署场景。"""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / '.runtime/python'), str(ROOT)]
from avatar3d.warudo_pipeline import convert


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('exchange', 'project', 'editor', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--timeout', type=int, default=600)
    args = parser.parse_args()
    if not 30 <= args.timeout <= 1800:
        parser.error('超时须为30—1800秒。')
    print(convert(args.exchange, args.project, args.editor, args.output, args.timeout))
