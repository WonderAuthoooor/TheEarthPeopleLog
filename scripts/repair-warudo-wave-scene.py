"""生成挥手修正场景副本，不覆盖用户场景；可选仅新增安装。"""
from pathlib import Path
import argparse
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / '.runtime/python'), str(ROOT)]
from avatar3d.warudo_scene import prepare_revision, install_scene

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'install', 'wave-report', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--name', default='AvatarLab_C_Live_v002')
    parser.add_argument('--install-copy', action='store_true')
    args = parser.parse_args()
    bundle = prepare_revision(args.source, args.install, args.wave_report, args.output, args.name)
    print(install_scene(bundle, args.install) if args.install_copy else bundle)
