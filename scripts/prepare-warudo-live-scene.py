"""生成独立C直播接续场景，可选新增安装；不激活场景或采集设备。"""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / '.runtime/python'), str(ROOT)]
from avatar3d.warudo_scene import prepare_scene, install_scene

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('scene', 'install', 'model', 'idle-report', 'explain-report', 'wave-report', 'output'):
        parser.add_argument('--' + key, type=Path, required=True)
    parser.add_argument('--name', default='AvatarLab_C_Live_v002')
    parser.add_argument('--install-copy', action='store_true')
    args = parser.parse_args()
    output = prepare_scene(args.scene, args.install, args.model,
        {key: getattr(args, key + '_report') for key in ('idle', 'explain', 'wave')}, args.output, args.name)
    print(install_scene(output, args.install) if args.install_copy else output)
