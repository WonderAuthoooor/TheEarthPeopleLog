"""复核口播成品哈希、时长和实际编码声轨相对于WAV的偏移。"""
from pathlib import Path
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'.runtime/python'),str(ROOT)]
import av
import numpy as np
from avatar3d.models import digest,atomic_json


def audio(path):
    chunks=[];count=0
    with av.open(str(path)) as media:
        resampler=av.AudioResampler(format='fltp',layout='mono',rate=16000)
        for frame in media.decode(audio=0):
            for out in resampler.resample(frame):
                count+=out.samples
                if count>16000*31:raise ValueError('验证音轨超过31秒。')
                chunks.append(out.to_ndarray().ravel())
        for out in resampler.resample(None):chunks.append(out.to_ndarray().ravel())
    return np.concatenate(chunks).astype(np.float64)


def run(folder,output):
    folder=Path(folder)
    record=json.loads((folder/'complete.json').read_text(encoding='utf-8'))
    for name,sha in record['files'].items():
        if digest(folder/name)!=sha:raise ValueError('产物哈希不一致：'+name)
    reference=audio(folder/'口播.wav')[::4]
    results={}
    for name in ('有声预览.mp4','有声预览.webm'):
        data=audio(folder/name)[::4]
        candidates=[]
        for lag in range(-160,161):
            left=max(0,-lag);right=max(0,lag)
            count=min(len(reference)-left,len(data)-right)
            a=reference[left:left+count];b=data[right:right+count]
            energy=float(np.linalg.norm(a)*np.linalg.norm(b))
            if energy<1e-10:raise ValueError('测试声轨静音，无法检查波形同步。')
            candidates.append((float(np.dot(a,b)/energy),lag/4000))
        correlation,offset=max(candidates)
        if correlation<.90 or abs(offset)>.03:raise ValueError('声轨波形或同步异常：'+name)
        results[name]={'correlation':correlation,'offset_seconds':offset}
    atomic_json(output,{'frames':record['frames'],'fps':record['fps'],'duration':record['duration'],
                       'hashes_valid':True,'audio_waveform_checks':results,'human_sync_verified':False})


if __name__=='__main__':run(sys.argv[1],sys.argv[2])
