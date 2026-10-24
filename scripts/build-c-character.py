"""从已校验基础VRM制作C外观初稿；每次使用新输出目录。"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from avatar3d.backend import Runtime, launch_external
from avatar3d.models import digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--recipe', type=Path, default=ROOT/'design/avatars/2026-10-20-concepts/c-build-recipe.json')
    parser.add_argument('--runtime', type=Path, default=ROOT/'.runtime/avatar3d/runtime.json')
    args = parser.parse_args()
    source, output = args.source.resolve(), args.output.resolve()
    recipe = json.loads(args.recipe.read_text(encoding='utf-8'))
    if output.exists():
        raise ValueError('输出目录已存在；请指定新的版本目录，保留旧稿。')
    if digest(source) != recipe['source_sha256']:
        raise ValueError('基础模型与配方来源校验不一致。')
    runtime = Runtime.load(args.runtime)
    logs = ROOT/'.runtime/avatar3d/character-builds'
    logs.mkdir(parents=True, exist_ok=True)
    log_path = logs/(str(time.time_ns())+'.log')
    command = [str(runtime.blender), '--background', '--factory-startup', '--disable-autoexec',
               '--python-exit-code', '23', '--python', str(ROOT/'avatar3d/character_build.py'), '--',
               '--source', str(source), '--recipe', str(args.recipe.resolve()), '--addon', str(runtime.addon), '--output', str(output)]
    env = dict(os.environ)
    env['BLENDER_USER_CONFIG'] = str(logs/'blender-config')
    env['BLENDER_USER_SCRIPTS'] = str(logs/'blender-scripts')
    with log_path.open('wb') as log:
        child = launch_external(command, env, log)
        try:
            code = child.wait(timeout=1800)
        except (KeyboardInterrupt, subprocess.TimeoutExpired):
            child.terminate()
            try: child.wait(timeout=10)
            except subprocess.TimeoutExpired: child.kill(); child.wait()
            raise
    if code:
        raise RuntimeError(f'制作失败({code})，保留诊断：{log_path}')
    manifest = json.loads((output/'complete.json').read_text(encoding='utf-8'))
    for name, expected in manifest['files'].items():
        if Path(name).name != name or digest(output/name) != expected:
            raise RuntimeError('输出文件校验失败：'+name)
    print(json.dumps({'stage': 'appearance_draft', 'output': str(output), 'log': str(log_path)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
