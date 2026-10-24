"""可复用的离线音量口型；不是语音识别或音素对齐。"""
from pathlib import Path
import math
import wave

REVISION = 'rms-mouth-v1'
RATE = 16000
HZ = 100


def envelope(samples, rate=RATE):
    import numpy as np
    data = np.asarray(samples, dtype=np.float64)
    if data.ndim != 1 or not len(data) or not np.isfinite(data).all():
        raise ValueError('音频必须是非空、有限的单声道采样。')
    if rate < HZ:raise ValueError('采样率过低。')
    # 固定100Hz分析，视频帧率变化不改变平滑时常。
    count = math.ceil(len(data) * HZ / rate)
    rms = np.array([np.sqrt(np.mean(data[round(i*rate/HZ):min(len(data),round((i+1)*rate/HZ))] ** 2))
                    for i in range(count)])
    peak = max(.03, float(np.percentile(rms, 95)))
    target = np.clip((rms - .006) / (peak - .006), 0, 1) * .72
    last = 0.
    values = []
    for value in target:
        tau = .025 if value > last else .045
        last += (float(value) - last) * (1 - math.exp(-1/HZ/tau))
        values.append(0. if last < .002 else last)
    # 时间戳指向分析窗中心；结尾平滑收口，素材会保留这段尾静音。
    times = [0.] + [(i+.5)/HZ for i in range(count)] + [len(data)/rate + .15]
    return {'revision': REVISION, 'hz': HZ, 'audio_duration': len(data)/rate,
            'times': times, 'values': [0.] + values + [0.]}


def validate_track(track):
    if track.get('revision') != REVISION:raise ValueError('不支持的口型曲线版本。')
    times, values = track['times'], track['values']
    if not 2 <= len(times) <= 3100 or len(times) != len(values):raise ValueError('口型曲线长度无效。')
    if times[0] != 0 or not all(math.isfinite(t) and 0 <= t <= 30 for t in times):
        raise ValueError('口型时间无效。')
    if any(a >= b for a,b in zip(times,times[1:])):raise ValueError('口型时间必须递增。')
    if not all(math.isfinite(v) and 0 <= v <= 1 for v in values):raise ValueError('口型权重无效。')
    if values[0] != 0 or values[-1] != 0:raise ValueError('口型须闭嘴开始并闭嘴结束。')
    return track


def at(track, seconds):
    import bisect
    times, values = track['times'], track['values']
    if not math.isfinite(seconds):raise ValueError('采样时间无效。')
    if seconds <= 0 or seconds >= times[-1]:return 0.
    right = bisect.bisect_right(times, seconds)
    left = right - 1
    fraction = (seconds-times[left])/(times[right]-times[left])
    return values[left] + fraction*(values[right]-values[left])


def decode(path, cancel):
    """解码后从0开始；拒绝时间轴跳变，不静默压缩停顿。"""
    import av
    import numpy as np
    chunks, count, expected = [], 0, None
    with av.open(str(path)) as container:
        if not container.streams.audio:raise ValueError('所选文件没有音轨。')
        resampler = av.AudioResampler(format='fltp', layout='mono', rate=RATE)
        def collect(frame):
            nonlocal count, expected
            if cancel.is_set():raise InterruptedError('已取消音频解码。')
            if frame.pts is not None:
                start = float(frame.pts * frame.time_base)
                if expected is not None and abs(start-expected) > .002:
                    raise ValueError('音频时间戳不连续，请先导出连续WAV再使用。')
                expected = start + frame.samples/RATE
            data = frame.to_ndarray().ravel()
            count += len(data)
            if count > RATE*29.75:raise ValueError('当前小样支持最多29.75秒口播，请先截取短段。')
            chunks.append(data)
        for frame in container.decode(audio=0):
            for out in resampler.resample(frame):collect(out)
        for out in resampler.resample(None):collect(out)
    if count < RATE*.25:raise ValueError('音频不足0.25秒。')
    data = np.concatenate(chunks)
    if not np.isfinite(data).all():raise ValueError('音频含无效采样。')
    return data


def write_wav(path, samples, duration):
    import numpy as np
    total = round(duration*RATE)
    if total < len(samples):raise ValueError('不能截断口播音频。')
    data = np.zeros(total, dtype='<i2')
    data[:len(samples)] = np.rint(np.clip(samples, -1, 1)*32767).astype('<i2')
    with wave.open(str(Path(path)), 'wb') as output:
        output.setnchannels(1);output.setsampwidth(2);output.setframerate(RATE)
        output.writeframes(data.tobytes())
