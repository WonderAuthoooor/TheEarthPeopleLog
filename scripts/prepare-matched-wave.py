"""从同模型完整待机任务制作起止一致的挥手；复用动作混合和媒体编码。"""
from pathlib import Path
import argparse
import json
import os
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / '.runtime/python'), str(ROOT)]
from avatar3d.backend import Runtime, launch_external
from avatar3d.models import atomic_json, digest
from avatar3d.motion_exchange import inspect_source, SOURCE_FILES
from avatar3d.service import encode


def prepare(source, out, runtime):
    source, record, spec, report = inspect_source(source)
    if spec.action != 'idle' or spec.fps != 30 or spec.duration != 3:
        raise ValueError('当前修正仅支持同模型3秒30fps待机基线。')
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    (out / 'frames').mkdir()
    request = spec.to_dict() | {'action': 'wave'}
    atomic_json(out / 'request.json', request)
    atomic_json(out / 'scene-report.json', report)
    job = {'source': str(source), 'source_sha256': record['files']['scene.blend'],
           'output': str(out), 'addon': str(runtime.addon), 'bones': report['humanoid_bones']}
    atomic_json(out / 'worker-request.json', job)
    command = [str(runtime.blender), '--background', '--factory-startup', '--disable-autoexec',
               '--python-exit-code', '23', '--python', str(ROOT / 'avatar3d/matched_wave_worker.py'),
               '--', str(out / 'worker-request.json')]
    env = dict(os.environ)
    temporary = out / 'blender-temp'
    temporary.mkdir()
    env.update(TEMP=str(temporary), TMP=str(temporary), BLENDER_USER_CONFIG=str(out / 'blender-config'),
               BLENDER_USER_SCRIPTS=str(out / 'blender-scripts'))
    with (out / 'blender.log').open('wb') as log:
        process = launch_external(command, env, log)
        started = time.monotonic()
        try:
            while process.poll() is None:
                if time.monotonic() - started > 300:
                    raise TimeoutError('匹配动作烘焙超时。')
                time.sleep(.25)
            if process.returncode:
                raise RuntimeError('动作修正失败，查看blender.log。')
        finally:
            if process.poll() is None:
                process.terminate()
                try: process.wait(10)
                except subprocess.TimeoutExpired: process.kill(); process.wait()
    files = sorted((out / 'frames').glob('*.png'))
    if [p.name for p in files] != [f'{i:05d}.png' for i in range(90)]:
        raise ValueError('90帧诊断图不完整。')
    encode(files, out, 30, threading.Event(), lambda _: None)
    atomic_json(out / 'complete.json', {'schema': 1, 'job_id': 'matched-wave',
        'model_sha256': spec.model_sha256, 'action': 'wave', 'frames': 90, 'fps': 30,
        'diagnostic_quality': 'clay motion preview', 'source_idle_sha256': record['files']['scene.blend'],
        'files': {name: digest(out / name) for name in SOURCE_FILES}})
    inspect_source(out)
    return out


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--runtime', type=Path, default=ROOT / '.runtime/avatar3d/runtime.json')
    args = parser.parse_args()
    print(prepare(args.source, args.output, Runtime.load(args.runtime)), flush=True)
