"""生成两种C基础动作的独立审阅素材；默认低帧率草稿，成品可选24/30fps。"""
from pathlib import Path
import argparse
import json
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / '.runtime/python'), str(ROOT)]
from avatar3d.backend import Runtime, BlenderBackend
from avatar3d.contracts import RenderSpec
from avatar3d.models import atomic_json, digest, inspect_vrm
from avatar3d.service import encode
from avatar3d.browser_preview import prepare
from avatar3d.natural_motion import REVISION


def run(model, output, runtime, fps=12, duration=3, width=320):
    model, output = Path(model).resolve(), Path(output).resolve()
    info = inspect_vrm(model)
    source_hash = digest(model)
    RenderSpec(source_hash, 'idle', duration, width, fps).validate()
    output.mkdir(parents=True, exist_ok=False)
    backend = BlenderBackend(Runtime.load(runtime))
    cancel = threading.Event()
    reports = []
    for action in ('idle', 'explain'):
        folder = output / action
        folder.mkdir()
        request = RenderSpec(source_hash, action, duration, width, fps).to_dict() | {'model': str(model), 'sample': False}
        atomic_json(folder / 'request.json', request)
        last = [-1]
        def progress(value):
            bucket = value // 10
            if bucket != last[0]:
                last[0] = bucket
                print(action, value, flush=True)
        frames = backend.render(request, folder, cancel, progress)
        encode(frames, folder, fps, cancel, progress)
        record = {'schema': 1, 'job_id': action, 'model_sha256': source_hash, 'action': action,
                  'frames': len(frames), 'fps': fps, 'motion_revision': REVISION, 'sample_only': False,
                  'files': {name: digest(folder / name) for name in ('角色透明.mov', '动作预览.mp4', '姿势预览.png', 'scene.blend')}}
        atomic_json(folder / 'complete.json', record)
        page = prepare(folder)
        reports.append({'action': action, 'preview': str(page.relative_to(output)), 'record': record})
    if digest(model) != source_hash:raise ValueError('源模型在审阅生成期间发生变化。')
    atomic_json(output / 'complete.json', {'source': str(model), 'source_sha256': source_hash,
                                         'motion_revision': REVISION, 'fps': fps, 'actions': reports,
                                         'appearance_changed': False, 'warudo_verified': False})
    sections = ''.join(f'<section><h2>{title}</h2><iframe src="{action}/browser-preview/index.html" title="{title}"></iframe></section>'
                       for action, title in [('idle', '轻缓待机 · 可循环'), ('explain', '单手讲解 · 起手、保持、收手')])
    (output / '预览.html').write_text('''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<title>C基础动作审阅</title><style>body{background:#18232b;color:#eee;font:17px system-ui;margin:28px}main{display:flex;flex-wrap:wrap;gap:24px}section{flex:1;min-width:320px}iframe{width:100%;height:950px;border:0}p{line-height:1.7}</style>
<h1>C基础动作 · 第一版</h1>''' + f'<p>{duration}秒／{fps}fps。当前外观保持不变；技术样片不代表动作美术或直播验收。'+
    ('这是12fps草稿，仅先检查姿态与衔接，最终流畅度需24/30fps素材。' if fps == 12 else '')+
    '</p><p>本版为上身呼吸、微动、眨眼及讲解。脚部固定；尚未加入重心移动、足部IK、语音口型或头发物理烘焙。</p><main>'+sections+'</main></html>', encoding='utf-8')
    print(output / '预览.html', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--runtime', type=Path, default=ROOT / '.runtime/avatar3d/runtime.json')
    parser.add_argument('--fps', type=int, choices=(12,24,30), default=12)
    parser.add_argument('--duration', type=float, default=3)
    parser.add_argument('--width', type=int, choices=(320,480,720,1080), default=320)
    args = parser.parse_args()
    run(args.model, args.output, args.runtime, args.fps, args.duration, args.width)
