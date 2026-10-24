"""按需生成浏览器派生预览；流式视频、有界备用动画，不修改渲染母版。"""
from pathlib import Path
import json
import os
import tempfile
import threading

from .models import atomic_json, digest

REVISION = 1
FILES = ('preview.webm', 'fallback.webp', 'poster.jpg', 'index.html')


def _check_cancel(cancel):
    if cancel.is_set():
        raise InterruptedError('已取消兼容预览；原始成品保留。')


def _page(short):
    label = '前3秒备用动画（完整视频见上方）' if short else '完整备用动画'
    return '''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>角色动作预览</title><style>
body{background:#18232b;color:#eef4f7;font:17px system-ui;margin:24px auto;max-width:720px;padding:0 20px}
video,img{display:block;max-width:100%;max-height:72vh;margin:16px auto;background:#303d46}
a{color:#8eddd0}summary,button{cursor:pointer}p{line-height:1.6}</style>
<h1>角色动作预览</h1><p id="status">预览已准备。点击播放；若不能播放，可展开下方备用动画。</p>
<video id="video" controls loop muted playsinline preload="metadata" poster="poster.jpg">
<source src="preview.webm" type="video/webm; codecs=vp9">
<source src="../动作预览.mp4" type="video/mp4"></video>
<details id="fallback"><summary>''' + label + '''</summary><img src="fallback.webp" alt="动作备用动画"></details>
<p>这是棋盘背景的检查预览。剪映合成请使用原始透明 MOV。</p>
<p><a href="../动作预览.mp4">原始 MP4</a> · <a href="../角色透明.mov">透明 MOV</a></p>
<script>const v=document.getElementById('video'),s=document.getElementById('status');
v.addEventListener('playing',()=>s.textContent='正在播放完整动作。');
v.addEventListener('error',()=>{s.textContent='此浏览器无法播放视频，已展开备用动画。';
document.getElementById('fallback').open=true;});</script></html>'''


def prepare(folder, cancel=None, progress=lambda _: None, *, complete=None):
    """返回经过校验的本地HTML；缓存损坏可重建，取消／失败不影响complete.json。"""
    import av
    from PIL import Image

    folder = Path(folder).resolve()
    cancel = cancel or threading.Event()
    _check_cancel(cancel)
    if complete is None:
        complete = json.loads((folder / 'complete.json').read_text(encoding='utf-8'))
    source = folder / '动作预览.mp4'
    source_hash = digest(source)
    if source_hash != complete['files']['动作预览.mp4']:
        raise ValueError('原预览文件哈希不一致，不能生成兼容预览。')
    expected = complete['frames']
    if not isinstance(expected, int) or not 2 <= expected <= 900:
        raise ValueError('预览只支持已完成的2—900帧动画。')
    target = folder / 'browser-preview'
    manifest = target / 'complete.json'
    try:
        cached = json.loads(manifest.read_text(encoding='utf-8'))
        if (cached['revision'] == REVISION and cached['source_sha256'] == source_hash
                and cached['frames'] == expected and set(cached['files']) == set(FILES)
                and all(digest(target / name) == sha for name, sha in cached['files'].items())):
            progress(100)
            return target / 'index.html'
    except (OSError, ValueError, KeyError, TypeError):
        pass
    lock_path = folder / '.browser-preview.lock'
    try:
        lock = lock_path.open('x', encoding='utf-8')
    except FileExistsError:
        raise ValueError('此任务的兼容预览正在生成；如上次异常退出，请检查并移除.browser-preview.lock后重试。') from None
    try:
        with lock:
            lock.write(str(os.getpid()))
        with tempfile.TemporaryDirectory(prefix='.browser-preview-', dir=folder) as temporary:
            staging = Path(temporary)
            fallback = []
            durations = []
            count = 0
            with av.open(str(source)) as original:
                stream = original.streams.video[0]
                fps = stream.average_rate
                if fps not in (12, 24, 30):
                    raise ValueError('预览帧率不受支持。')
                # VP9最多480宽；备用动画最多320宽、3秒，内存不随完整导出时长增长。
                scale = min(1, 480 / stream.width, 720 / stream.height)
                width = max(2, int(stream.width * scale) // 2 * 2)
                height = max(2, int(stream.height * scale) // 2 * 2)
                with av.open(str(staging / 'preview.webm'), 'w', format='webm') as output:
                    video = output.add_stream('libvpx-vp9', rate=fps)
                    video.width, video.height, video.pix_fmt = width, height, 'yuv420p'
                    video.options = {'crf': '30', 'b': '0', 'deadline': 'realtime', 'cpu-used': '6'}
                    for index, decoded in enumerate(original.decode(video=0)):
                        _check_cancel(cancel)
                        if index >= expected:
                            raise ValueError('原视频实际帧数超过完成清单。')
                        picture = decoded.to_image().resize((width, height), Image.Resampling.LANCZOS)
                        if index < int(fps * 3):
                            backup = picture.copy()
                            backup.thumbnail((320, 480), Image.Resampling.LANCZOS)
                            fallback.append(backup)
                            durations.append(round((index + 1) * 1000 / fps) - round(index * 1000 / fps))
                        if index == expected // 2:
                            picture.save(staging / 'poster.jpg', quality=90)
                        frame = av.VideoFrame.from_image(picture)
                        frame.pts = index
                        for packet in video.encode(frame):
                            output.mux(packet)
                        count += 1
                        progress(round(count / expected * 75))
                    for packet in video.encode():
                        output.mux(packet)
            if count != expected:
                raise ValueError('原视频实际帧数与完成清单不符。')
            _check_cancel(cancel)
            fallback[0].save(staging / 'fallback.webp', save_all=True, append_images=fallback[1:],
                             duration=durations, loop=0, quality=80, method=2)
            fallback.clear()
            progress(85)
            with av.open(str(staging / 'preview.webm')) as encoded:
                verified = 0
                for frame in encoded.decode(video=0):
                    _check_cancel(cancel)
                    verified += 1
                if verified != expected:
                    raise ValueError('兼容视频解码帧数不完整。')
            # WebP可合并相同画面，按总时长验证，不误判静止片段丢帧。
            with Image.open(staging / 'fallback.webp') as animated:
                duration = 0
                for index in range(animated.n_frames):
                    _check_cancel(cancel)
                    animated.seek(index)
                    animated.load()
                    duration += animated.info.get('duration', 0)
                if animated.n_frames > 1 and duration != sum(durations):
                    raise ValueError('备用动画时长校验失败。')
            (staging / 'index.html').write_text(_page(count > int(fps * 3)), encoding='utf-8')
            result = {'revision': REVISION, 'source_sha256': source_hash, 'frames': count,
                      'fps': float(fps), 'size': [width, height], 'fallback_duration_ms': sum(durations),
                      'native_browser_playback': 'not verified',
                      'files': {name: digest(staging / name) for name in FILES}}
            _check_cancel(cancel)
            if digest(source) != source_hash:
                raise ValueError('生成过程中原视频被修改，预览未发布。')
            target.mkdir(exist_ok=True)
            manifest.unlink(missing_ok=True)
            for name in FILES:
                os.replace(staging / name, target / name)
            atomic_json(manifest, result)
            progress(100)
            return target / 'index.html'
    finally:
        lock_path.unlink(missing_ok=True)
