"""从已有排练母版生成完整播放预览；--resume安全复用已校验帧。"""
from pathlib import Path
import argparse
import json
import math
import os
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / '.runtime/python'), str(ROOT)]
from avatar3d.backend import Runtime, launch_external
from avatar3d.models import atomic_json, digest
from avatar3d.rehearsal_preview import output_settings, reusable_frames, source_info
from avatar3d.service import encode


def run(args):
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        raise ValueError('超时秒数必须为有限正数。')
    source = source_info(args.source)
    settings = output_settings(source, args.width, args.samples, args.quality)
    runtime = Runtime.load(args.runtime)
    out = args.output.resolve()
    # 派生内容不能放进源母版中，保证源完成清单始终有效。
    if out == args.source.resolve() or args.source.resolve() in out.parents:
        raise ValueError('预览输出需使用源母版之外的独立目录。')
    if not args.resume:
        out.mkdir(parents=True, exist_ok=False)
        atomic_json(out / 'preview-request.json', settings)
    elif not out.is_dir():
        raise ValueError('没有可继续的预览目录。')
    lock = out / '.preview.lock'
    with lock.open('x', encoding='ascii') as handle:
        handle.write(str(os.getpid()))
    try:
        good = reusable_frames(out, settings)
        pending = [i for i in range(settings['frames']) if i not in good]
        print(f'REUSE {len(good)} / {settings["frames"]}', flush=True)
        (out / 'frames').mkdir(exist_ok=True)
        # 重建开始即取消旧完成标记，不留下过期成功状态。
        (out / 'preview-complete.json').unlink(missing_ok=True)
        job = {'output': str(out), 'addon': str(runtime.addon), 'pending': pending}
        atomic_json(out / 'worker-request.json', job)
        if pending:
            env = dict(os.environ)
            temporary = out / 'blender-temp'
            temporary.mkdir(exist_ok=True)
            env.update(TEMP=str(temporary), TMP=str(temporary),
                       BLENDER_USER_CONFIG=str(out / 'blender-config'),
                       BLENDER_USER_SCRIPTS=str(out / 'blender-scripts'))
            command = [str(runtime.blender), '--background', '--factory-startup', '--disable-autoexec',
                       '--python-exit-code', '23', '--python',
                       str(ROOT / 'avatar3d/rehearsal_preview_worker.py'), '--', str(out / 'worker-request.json')]
            with (out / 'blender.log').open('ab') as log:
                process = launch_external(command, env, log)
                started = time.monotonic()
                try:
                    while process.poll() is None:
                        if time.monotonic() - started > args.timeout:
                            raise TimeoutError('渲染超时；已完成帧保留，使用--resume继续。')
                        time.sleep(.25)
                    if process.returncode:
                        raise RuntimeError('预览渲染失败，详见blender.log；可继续未完成帧。')
                finally:
                    if process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            process.kill(); process.wait()
        good = reusable_frames(out, settings)
        if len(good) != settings['frames']:
            raise ValueError('渲染帧未完整通过检查，不生成视频完成标记。')
        files = [out / 'frames' / f'{i:05d}.png' for i in range(settings['frames'])]
        encode(files, out, settings['fps'], threading.Event(), lambda _: None)
        # 独立验证解码后的实际PTS和时长，不仅比较容器标称信息。
        import av
        for name in ('动作预览.mp4', '角色透明.mov'):
            with av.open(str(out / name)) as media:
                count = 0
                for i, frame in enumerate(media.decode(video=0)):
                    if abs(float(frame.pts * frame.time_base) - i / settings['fps']) > 1e-5:
                        raise ValueError('视频时间线不连续。')
                    count += 1
                if count != settings['frames']:
                    raise ValueError('视频帧数不符。')
        # VP9用于内置浏览器；复用现有流式兼容预览生成器。
        from avatar3d.browser_preview import prepare
        prepare(out, complete={'frames': len(files), 'files': {'动作预览.mp4': digest(out / '动作预览.mp4')}})
        # 通用预览说明面向正式彩色素材，本派生页应准确标注素模用途。
        label = '素模动作检查' if args.quality == 'motion' else '卡通材质预览'
        plan = json.loads((args.source / 'request.json').read_text(encoding='utf-8'))['rehearsal']
        buttons = ''.join(f'<button data-time="{max(0, clip["start"]-.5)}">'
                          f'{clip["start"]:g}秒 · {"挥手" if clip["action"] == "wave" else "讲解"}</button>'
                          for clip in plan['gestures'])
        purpose = ('仅检查肩肘、手腕与动作衔接，不代表最终肤色、衣服、头发或眼睛效果。'
                   if args.quality == 'motion' else '减少渲染采样的检查预览，不代表最终成片质量。')
        page = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>连续排练预览</title>
<style>body{background:#18232b;color:#eef4f7;font:17px system-ui;max-width:900px;margin:24px auto;padding:0 20px}video{max-width:100%;height:70vh;background:#303d46}button{padding:8px;margin:5px}p{line-height:1.6}a{color:#8eddd0}</style>
<h1>连续排练 · LABEL</h1><p>DURATION秒／30fps完整动作，无声。PURPOSE原彩色母版未修改。</p>
<video id="v" controls loop muted playsinline preload="metadata" poster="browser-preview/poster.jpg"><source src="browser-preview/preview.webm" type="video/webm"><source src="动作预览.mp4" type="video/mp4"></video>
<p>BUTTONS<button id="slow">切换0.5倍／正常速度</button></p>
<p id="status">点击播放。服饰穿模仍待后续服装调整；此视频不验证Warudo或摄像头跟随。</p>
<p><a href="动作预览.mp4">打开MP4</a> · <a href="browser-preview/fallback.webp">前3秒备用动画（不含完整手势）</a></p>
<script>const v=document.getElementById('v');document.querySelectorAll('[data-time]').forEach(b=>b.onclick=()=>{v.currentTime=Math.min(+b.dataset.time,v.duration||0);v.play().catch(()=>{});});document.getElementById('slow').onclick=()=>v.playbackRate=v.playbackRate===1?.5:1;v.onerror=()=>document.getElementById('status').textContent='播放失败，请尝试下方MP4文件。';</script></html>'''
        (out / '预览.html').write_text(page.replace('LABEL', label).replace('DURATION', str(settings['duration']))
                                    .replace('PURPOSE', purpose).replace('BUTTONS', buttons), encoding='utf-8')
        if source_info(args.source) != source:
            raise ValueError('源文件在预览生成期间改变。')
        names = ('预览.html', '动作预览.mp4', '角色透明.mov', 'browser-preview/preview.webm',
                 'browser-preview/fallback.webp', 'browser-preview/poster.jpg')
        atomic_json(out / 'preview-complete.json', dict(settings, verified_frames=len(files),
                    reused_frames=len(files)-len(pending), files={n: digest(out / n) for n in names},
                    visual_acceptance='pending', warudo='not tested'))
        print('COMPLETE', out, flush=True)
    finally:
        lock.unlink(missing_ok=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'runtime', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--quality', choices=('motion', 'material'), default='motion')
    parser.add_argument('--width', type=int, default=320)
    parser.add_argument('--samples', type=int, default=2)
    parser.add_argument('--timeout', type=float, default=1800)
    parser.add_argument('--resume', action='store_true')
    run(parser.parse_args())
