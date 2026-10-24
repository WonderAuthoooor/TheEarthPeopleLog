"""研发CLI：复制已校验动作包到用户指定Warudo目录，不改场景。"""
from pathlib import Path
import argparse
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / '.runtime/python'), str(ROOT)]
from avatar3d.models import atomic_json
from avatar3d.warudo_deploy import deploy_animation

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--install', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    if args.receipt.exists(): parser.error('收据已存在，请使用新路径。')
    result = deploy_animation(args.report, args.install)
    atomic_json(args.receipt, result)
    print(result['installed_file'])
