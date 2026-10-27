"""直播基础素材打包／校验／预检／恢复；不会启动Warudo或采集设备。"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from avatar3d.live_package import create_package, verify_package, plan_restore, restore_package
from avatar3d.models import atomic_json
from avatar3d.live_diagnostics import inspect_scene


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='command', required=True)
    pack = subs.add_parser('pack')
    for name in ('prepared', 'install', 'output'):
        pack.add_argument('--'+name, type=Path, required=True)
    for command in ('verify', 'plan', 'restore'):
        child = subs.add_parser(command)
        child.add_argument('--package', type=Path, required=True)
        if command != 'verify': child.add_argument('--install', type=Path, required=True)
    diagnostic = subs.add_parser('diagnose')
    diagnostic.add_argument('--scene', type=Path, required=True)
    diagnostic.add_argument('--install', type=Path, required=True)
    diagnostic.add_argument('--package', type=Path)
    parser.add_argument('--report', type=Path, help='可选JSON报告，须放在新路径')
    args = parser.parse_args()
    if args.report and args.report.exists():
        parser.error('报告路径已存在，请选择新文件。')
    try:
        if args.command == 'pack': result = create_package(args.prepared, args.install, args.output)
        elif args.command == 'verify': result = verify_package(args.package)
        elif args.command == 'plan': result = plan_restore(args.package, args.install)
        elif args.command == 'diagnose': result = inspect_scene(args.scene, args.install, args.package)
        else: result = restore_package(args.package, args.install)
        if args.report: atomic_json(args.report, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if result.get('can_restore') is False or result.get('configuration_ok') is False else 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print('未完成：'+str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
