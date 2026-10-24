"""研发CLI：在独立Unity工程配置完成后部署固定SDK，不替代真实导入验证。"""
from pathlib import Path
import argparse
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / '.runtime/python'), str(ROOT)]
from avatar3d.warudo_sdk import stage_sdk

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--editor', type=Path, required=True)
    args = parser.parse_args()
    print(stage_sdk(args.project, args.editor))
