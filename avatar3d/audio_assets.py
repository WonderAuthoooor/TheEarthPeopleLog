"""工作区内的不可变音频快照；入队后不依赖原文件。"""
from pathlib import Path
import json
import math
import os
import tempfile
import threading
from .models import digest,atomic_json
from .audio_mouth import decode,envelope,validate_track,write_wav,REVISION

FILES={'speech.wav','mouth-track.json'}


def load_audio(workspace,ident):
    if not isinstance(ident,str) or len(ident)!=64 or any(c not in '0123456789abcdef' for c in ident):
        raise ValueError('音频标识无效。')
    folder=Path(workspace)/'audio'/ident
    info=json.loads((folder/'complete.json').read_text(encoding='utf-8'))
    if info.get('source_sha256')!=ident or info.get('method')!=REVISION or set(info.get('files',{}))!=FILES:
        raise ValueError('音频快照清单无效。')
    if any(digest(folder/name)!=sha for name,sha in info['files'].items()):raise ValueError('音频快照损坏，请重新导入到新工作区或恢复原文件。')
    track=validate_track(json.loads((folder/'mouth-track.json').read_text(encoding='utf-8')))
    if info.get('audio_duration')!=track['audio_duration']:raise ValueError('音频快照时长不一致。')
    return info


def output_duration(info,fps):
    tail=info['audio_duration']+.15
    return max(math.ceil(.5*fps),math.ceil(tail*fps)+1)/fps


def import_audio(workspace,source,cancel=None):
    cancel=cancel or threading.Event()
    source=Path(source).resolve()
    if cancel.is_set():raise InterruptedError('已取消音频导入。')
    if not source.is_file() or not 1<=source.stat().st_size<=64*1024*1024:raise ValueError('音频文件须非空且不超过64MB。')
    ident=digest(source)
    root=Path(workspace)/'audio';target=root/ident
    if target.exists():return load_audio(workspace,ident)
    data=decode(source,cancel)
    track=validate_track(envelope(data))
    if digest(source)!=ident:raise ValueError('读取期间原音频发生变化，请重新选择。')
    root.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.import-',dir=root) as temporary:
        staging=Path(temporary)
        write_wav(staging/'speech.wav',data,len(data)/16000)
        atomic_json(staging/'mouth-track.json',track)
        info={'schema':1,'source_name':source.name,'source_sha256':ident,'method':REVISION,
              'audio_duration':track['audio_duration'],
              'files':{name:digest(staging/name) for name in FILES}}
        atomic_json(staging/'complete.json',info)
        if cancel.is_set():raise InterruptedError('已取消音频导入。')
        # 工作区应用锁保证单实例；目录发布失败不覆盖已存在的快照。
        if target.exists():return load_audio(workspace,ident)
        for attempt in range(5):
            if cancel.is_set():raise InterruptedError('已取消音频导入。')
            try:
                os.rename(staging,target)
                break
            except FileExistsError:
                return load_audio(workspace,ident)
            except OSError as exc:
                # Windows短暂占用目录时有限重试；持续拒绝仍报错，不覆盖目标。
                if target.exists():return load_audio(workspace,ident)
                if getattr(exc,'winerror',None) not in (5,32,33) or attempt==4:raise
                if cancel.wait(.05 * 2**attempt):raise InterruptedError('已取消音频导入。')
    return load_audio(workspace,ident)
