"""从本地口播生成VRM基础口型、透明素材和有声审阅页；输出目录必须全新。"""
from pathlib import Path
import argparse
import json
import math
import os
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / '.runtime/python'), str(ROOT)]
from avatar3d.audio_mouth import decode, envelope, validate_track, write_wav, REVISION
from avatar3d.backend import Runtime, BlenderBackend, launch_external
from avatar3d.contracts import RenderSpec
from avatar3d.models import atomic_json, digest, inspect_vrm
from avatar3d.service import encode
from avatar3d.browser_preview import prepare


def command(args, folder, cancel):
    with (folder/'audio-encode.log').open('ab') as log:
        process = launch_external(args, os.environ, log)
        started = time.monotonic()
        try:
            while process.poll() is None:
                if cancel.is_set():raise InterruptedError('已取消有声预览编码。')
                if time.monotonic()-started > 180:raise TimeoutError('有声预览编码超时。')
                time.sleep(.1)
            if process.returncode:raise RuntimeError('有声预览编码失败，见audio-encode.log。')
        finally:
            if process.poll() is None:
                process.terminate()
                try:process.wait(5)
                except Exception:process.kill();process.wait(5)


def sound_previews(folder, fps, total, cancel):
    import av
    import imageio_ffmpeg
    executable = imageio_ffmpeg.get_ffmpeg_exe()
    for suffix, video, audio in [('mp4',['-c:v','copy'],['-c:a','aac','-b:a','128k']),
                                  ('webm',['-c:v','libvpx-vp9','-crf','30','-b:v','0','-deadline','realtime','-cpu-used','6'],['-c:a','libopus','-b:a','96k'])]:
        target = folder/f'有声预览.{suffix}'
        command([executable,'-nostdin','-n','-v','error','-i',str(folder/'动作预览.mp4'),
                 '-i',str(folder/'口播.wav'),'-map','0:v:0','-map','1:a:0',*video,*audio,
                 '-t',str(total/fps),str(target)],folder,cancel)
        with av.open(str(target)) as media:
            count=0
            for index,frame in enumerate(media.decode(video=0)):
                if cancel.is_set():raise InterruptedError('已取消视频验证。')
                if abs(float(frame.time)-index/fps) > .002:raise ValueError('有声视频时间轴不匹配。')
                count+=1
            if count!=total:raise ValueError('有声预览帧数不匹配。')
        with av.open(str(target)) as media:
            first, end = None, 0
            for frame in media.decode(audio=0):
                if cancel.is_set():raise InterruptedError('已取消音频验证。')
                start = float(frame.time)
                if first is None:first=start
                end = start + frame.samples/frame.sample_rate
            if first is None or abs(first)>.03 or abs(end-total/fps)>.08:
                raise ValueError('有声预览音频起点或长度异常。')


def run(model, audio, output, runtime, fps=24, width=480, action='idle', cancel=None):
    cancel = cancel or threading.Event()
    model, audio, output = (Path(p).resolve() for p in (model,audio,output))
    if output.exists():raise FileExistsError('输出目录已存在，请使用新目录；不会覆盖旧素材。')
    if action not in ('idle','explain'):raise ValueError('口播小样仅支持待机或单手讲解。')
    info = inspect_vrm(model)
    model_hash, audio_hash = digest(model), digest(audio)
    runtime = Runtime.load(runtime)
    samples = decode(audio,cancel)
    track = validate_track(envelope(samples))
    # 末帧晚于收口时间，且末尾音频补静音，保证剪映从0对齐。
    total = max(math.ceil(.5*fps),math.ceil(track['times'][-1]*fps)+1)
    spec = RenderSpec(model_hash,action,total/fps,width,fps).validate()
    if digest(audio)!=audio_hash:raise ValueError('音频读取期间发生变化。')
    output.mkdir(parents=True,exist_ok=False)
    try:
        atomic_json(output/'mouth-track.json',track)
        write_wav(output/'口播.wav',samples,spec.duration)
        atomic_json(output/'model-metadata.json',info)
        request = spec.to_dict() | {'model':str(model),'sample':False,'framing':'bust',
                   'mouth_track':str(output/'mouth-track.json'),
                   'mouth_track_sha256':digest(output/'mouth-track.json')}
        atomic_json(output/'request.json',request)
        last=[-1]
        def progress(value):
            if value//10!=last[0]:last[0]=value//10;print(f'口播渲染 {value}%',flush=True)
        frames = BlenderBackend(runtime).render(request,output,cancel,progress)
        encode(frames,output,fps,cancel,progress)
        sound_previews(output,fps,len(frames),cancel)
        if digest(model)!=model_hash or digest(audio)!=audio_hash:raise ValueError('源文件生成期间发生变化。')
        # 派生生成接受已校验的内存清单，最终完成标记最后写入。
        files = ('角色透明.mov','动作预览.mp4','姿势预览.png','scene.blend','口播.wav',
                 '有声预览.mp4','有声预览.webm','mouth-track.json','mouth-pose-checks.json')
        record = {'schema':1,'frames':len(frames),'fps':fps,'duration':spec.duration,
                  'model_sha256':model_hash,'source_audio':str(audio),'source_audio_sha256':audio_hash,
                  'method':REVISION,'phoneme_alignment':False,'action':action,'framing':'bust',
                  'transparent_video_audio':False,'runtime_verified':False,
                  'files':{name:digest(output/name) for name in files}}
        prepare(output,cancel,complete=record)
        page = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>C口播基础口型</title>
<style>body{max-width:900px;margin:32px auto;background:#18232b;color:#eef4f7;font:18px system-ui;padding:20px}video{max-width:100%;max-height:72vh}a{color:#8eddd0}p{line-height:1.7}</style>
<h1>C角色 · 口播与动作叠加</h1><p>点击播放并开启声音。当前为音量驱动的平滑开合，不是逐字音素匹配。沿用原版脸型及肩领修复；外观未重做。</p>
<video controls playsinline preload="metadata" poster="browser-preview/poster.jpg"><source src="有声预览.webm" type="video/webm"><source src="有声预览.mp4" type="video/mp4"></video>
<p>剪映：角色透明.mov放上层，口播.wav放音轨，两者从同一时刻开始。透明MOV自身静音；WAV末尾含收口静音。棋盘有声预览仅供检查。</p>
<p><a href="有声预览.mp4">有声MP4</a> · <a href="角色透明.mov">透明MOV</a> · <a href="口播.wav">配套音频</a> · <a href="browser-preview/index.html">静音备用动画</a></p>
<p>检查停顿能否闭嘴、讲话开合是否平滑、眨眼和讲解是否互不干扰；最终自然度与剪映音画同步仍待人工验收。</p></html>'''
        (output/'预览.html').write_text(page,encoding='utf-8')
        record['files']['预览.html']=digest(output/'预览.html')
        atomic_json(output/'complete.json',record)
        return output/'预览.html'
    except BaseException:
        (output/'complete.json').unlink(missing_ok=True)
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model',required=True,type=Path)
    parser.add_argument('--audio',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--runtime',type=Path,default=ROOT/'.runtime/avatar3d/runtime.json')
    parser.add_argument('--fps',type=int,choices=(12,24,30),default=24)
    parser.add_argument('--width',type=int,choices=(320,480,720,1080),default=480)
    parser.add_argument('--action',choices=('idle','explain'),default='idle')
    args=parser.parse_args()
    print(run(args.model,args.audio,args.output,args.runtime,args.fps,args.width,args.action))
