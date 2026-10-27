"""有声预览编码与真实音视频时间轴检查；CLI和桌面共用。"""
from pathlib import Path
import os
import time
from .backend import launch_external


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

