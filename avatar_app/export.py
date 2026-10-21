"""独立透明素材导出；每次写入新目录，失败不留下伪成品。"""
from pathlib import Path
import json
import math
import uuid
from datetime import datetime

import av
import numpy as np

from .rig import Rig, Envelope, checker
from .actions import ACTION_NAMES,ACTION_ORDER,clip_pose
from .action_art import validate_score


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name+"."+uuid.uuid4().hex+".tmp")
    try:
        tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)


def export_clip(destination, audio=None, duration=6, fps=30, width=720, turn=True, fixed_turn=0,
                cancel=None, progress=lambda value: None,action='idle',score_text='待评'):
    if action not in ACTION_NAMES and action!='all':raise ValueError('不支持的动作。')
    score_text=validate_score(score_text)
    if action=='all':
        if audio:raise ValueError('动作合集为静音技术预览，请清除音频或导出单动作。')
        duration=len(ACTION_ORDER)*2.5
    if fps not in (24, 30) or width not in (480, 720, 1080):
        raise ValueError("不支持的画布／帧率。")
    if not math.isfinite(duration) or not 1 <= duration <= 180:
        raise ValueError("时长须为1—180秒。")
    env = Envelope(audio, fps) if audio else None
    duration = env.duration if env else duration
    if duration < .1:
        raise ValueError("音频太短。")
    if not math.isfinite(fixed_turn) or not -1 <= fixed_turn <= 1:
        raise ValueError("转头参数超出范围。")
    rig = Rig(scale=width/1024)
    folder = Path(destination) / (datetime.now().strftime("%Y%m%d_%H%M%S")+"_"+uuid.uuid4().hex[:8])
    folder.mkdir(parents=True, exist_ok=False)
    record = {"status":"rendering", "model":rig.config["id"], "audio":str(audio) if audio else None,
              "duration":duration, "fps":fps, "size":[width,width*3//2], "turn":bool(turn),"fixed_turn":fixed_turn,
              "mouth_method":"RMS音量开合；不是音素对齐", "output_audio":False,
              "action":action,"score_display":score_text,"score_ledger_written":False,
              "note":"角色MOV与棋盘预览均静音，剪映中叠回同一口播音轨。"}
    save_json(folder/"request.json", record)
    mov = folder/"character.partial.mov"
    mp4 = folder/"preview.partial.mp4"
    containers = []
    try:
        transparent = av.open(str(mov), "w")
        containers.append(transparent)
        ts = transparent.add_stream("prores_ks", rate=fps)
        ts.width,ts.height = width,width*3//2
        ts.pix_fmt = "yuva444p10le"
        ts.options = {"profile":"4", "alpha_bits":"16"}
        preview = av.open(str(mp4), "w")
        containers.append(preview)
        ps = preview.add_stream("libx264",rate=fps)
        ps.width,ps.height = width,width*3//2
        ps.pix_fmt = "yuv420p"
        ps.options = {"crf":"21", "preset":"fast"}
        total = math.ceil(duration*fps)
        for i in range(total):
            if cancel and cancel.is_set():
                raise InterruptedError("已取消；未生成完整角色素材。")
            t = i/fps
            selected=ACTION_ORDER[min(len(ACTION_ORDER)-1,int(t/2.5))] if action=='all' else action
            local_t=t%2.5 if action=='all' else t
            pose=clip_pose(selected,local_t,2.5 if action=='all' else duration)
            image = rig.frame(t, (width,width*3//2), env.at(t) if env else 0,
                              math.sin(t*2*math.pi/7)*.7 if turn else fixed_turn,pose=pose,score=score_text)
            for container, stream, picture in ((transparent,ts,image),(preview,ps,checker(image))):
                frame = av.VideoFrame.from_ndarray(np.asarray(picture),format="rgba" if picture.mode=="RGBA" else "rgb24")
                frame.pts = i
                for packet in stream.encode(frame):
                    container.mux(packet)
            progress(round((i+1)/total*100))
        for container, stream in ((transparent,ts),(preview,ps)):
            for packet in stream.encode():
                container.mux(packet)
            container.close()
        containers.clear()
        if cancel and cancel.is_set():
            raise InterruptedError("已取消。")
        mov.replace(folder/"角色透明.mov")
        mp4.replace(folder/"棋盘预览.mp4")
        (folder/"剪映使用说明.txt").write_text("角色透明.mov 放在新闻视频上方轨道；棋盘预览.mp4只用于检查，不要用于成片。\n两个视频均静音，将同一口播音频放在音频轨，并对齐到角色素材起点。\n本版为2D分层动作试验，已有表情／手臂预设与入场收回；不是逐字口型或全身动作捕捉。评分牌仅显示人工输入，不写文明账本。\n"+
            ('合集每2.5秒切换一个动作：'+ '、'.join(ACTION_NAMES[k] for k in ACTION_ORDER)+'。\n' if action=='all' else ''),encoding="utf-8")
        record["status"] = "complete"
        save_json(folder/"request.json",record)
        return folder
    except BaseException as exc:
        for container in containers:
            try:
                container.close()
            except Exception:
                pass
        for path in (mov,mp4,folder/"角色透明.mov",folder/"棋盘预览.mp4"):
            path.unlink(missing_ok=True)
        record.update(status="cancelled" if isinstance(exc,InterruptedError) else "failed",error=str(exc))
        save_json(folder/"request.json",record)
        raise
