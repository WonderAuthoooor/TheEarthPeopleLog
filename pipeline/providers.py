"""Optional MiniMax requests. Keys live only in process memory/environment.

No paid request is made by launch, render, download, or the offline tests.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import urllib.error
import urllib.request

from .core import (PipelineError, asset_path, fingerprint, job_lock, now, probe,
                   save_job, save_json, writing_prompt, number, estimated_cues)

API = "https://api.minimax.cn/v1/"


def post_json(route, body, key):
    key = key or os.environ.get("MINIMAX_API_KEY", "")
    if not key:
        raise PipelineError("请在接口设置中填写MiniMax API Key，或设置MINIMAX_API_KEY环境变量。密钥不会保存到任务。")
    request = urllib.request.Request(API + route, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + key}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=150) as response:
            data = json.load(response)
    except urllib.error.HTTPError as exc:
        raise PipelineError(f"MiniMax请求失败，HTTP {exc.code}。请检查账号、模型和额度；未自动重试。") from None
    except (OSError, ValueError):
        raise PipelineError("MiniMax请求未完成。请先查看平台调用记录；网络失败也可能已产生费用，工具不会自动重试。") from None
    status = data.get("base_resp", {}).get("status_code", 0)
    if status:
        raise PipelineError(f"MiniMax返回错误码 {status}。请在平台检查调用记录。")
    return data


def generate_writing(directory, data, key="", model="MiniMax-M2.7"):
    if not data.get("facts", "").strip():
        raise PipelineError("先填写事实材料；仅有X链接不能让模型知道视频发生了什么。")
    with job_lock(directory):
        prompt = writing_prompt(data)
        if len(prompt) > 20000:
            raise PipelineError("写稿材料超过20000字符，请先精简，避免单次请求过大。")
        digest = hashlib.sha256((model + prompt).encode()).hexdigest()
        path = Path(directory) / "generated" / (digest[:24] + ".txt")
        if path.is_file():
            return path.read_text(encoding="utf-8")
        # Native API remains documented, but is marked deprecated; keep adapter isolated.
        response = post_json("text/chatcompletion_v2", {"model": model, "stream": False,
            "max_completion_tokens": 4096, "messages": [{"role": "user", "content": prompt}]}, key)
        choices = response.get("choices") or []
        if not choices or not choices[0].get("message", {}).get("content") or choices[0].get("finish_reason") == "length":
            raise PipelineError("模型没有返回完整文稿，请检查平台记录后调整模型或材料。")
        result = choices[0]["message"]["content"]
        path.parent.mkdir(exist_ok=True)
        path.write_text(result, encoding="utf-8")
        data["usage"].append({"at": now(), "service": "minimax_text", "model": model,
                              "usage": response.get("usage"), "cost": None})
        data["steps"]["writing"] = {"status": "review", "digest": digest, "at": now()}
        save_job(directory, data)
        return result


def generate_voice(directory, data, key="", model="speech-2.8-turbo",
                   voice_id="", speed=1.0, emotion="", max_chars=1500, log=print):
    if not voice_id:
        raise PipelineError("请填写MiniMax音色ID。剪映“甜美解说”的名字不是MiniMax音色ID。")
    paragraphs = [line.strip() for line in data.get("script", "").splitlines() if line.strip()]
    if not paragraphs:
        raise PipelineError("请先填写口播稿，每行一段。")
    total = sum(len(line) for line in paragraphs)
    if total > max_chars:
        raise PipelineError(f"本次合成{total}字，超过单次{max_chars}字上限。请缩短文稿。")
    if not .5 <= speed <= 2:
        raise PipelineError("语速应在0.5至2之间。")
    offset = number(data["narration_start"], "配音起点", 0, 300)
    with job_lock(directory):
        generated = Path(directory) / "generated"
        generated.mkdir(exist_ok=True)
        paths = []
        cues = []
        cursor = offset
        for i, paragraph in enumerate(paragraphs):
            settings = {"voice_id": voice_id, "speed": speed, "vol": 1, "pitch": 0}
            if emotion:
                settings["emotion"] = emotion
            body = {"model": model, "text": paragraph, "stream": False, "voice_setting": settings,
                    "audio_setting": {"sample_rate": 32000, "bitrate": 128000, "format": "mp3", "channel": 1},
                    "subtitle_enable": False, "output_format": "hex"}
            digest = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
            audio = generated / (digest[:24] + ".mp3")
            receipt = generated / (digest[:24] + ".json")
            cached = False
            if audio.is_file() and receipt.is_file():
                cached = json.loads(receipt.read_text(encoding="utf-8")).get("sha256") == fingerprint(audio)
            if not cached:
                log(f"正在合成第{i+1}/{len(paragraphs)}段（{len(paragraph)}字）…")
                response = post_json("t2a_v2", body, key)
                try:
                    binary = bytes.fromhex(response["data"]["audio"])
                    if not binary:
                        raise ValueError()
                except (KeyError, TypeError, ValueError):
                    raise PipelineError("平台未返回有效音频，请检查调用记录；工具未自动重试。") from None
                audio.write_bytes(binary)
                length = probe(audio)["duration"]
                save_json(receipt, {"at": now(), "sha256": fingerprint(audio), "duration": length,
                    "model": model, "voice_id": voice_id, "usage": response.get("extra_info", {}).get("usage_characters"), "cost": None})
                data["usage"].append({"at": now(), "service": "minimax_tts", "model": model,
                    "characters": response.get("extra_info", {}).get("usage_characters"), "cost": None})
                save_job(directory, data)
            length = probe(audio)["duration"]
            paths.append(audio)
            # Paragraph boundaries use actual generated lengths. Not word alignment.
            cues.extend(estimated_cues(paragraph, cursor, cursor + length))
            cursor += length
        from .core import run_media, write_srt
        assembly_id = hashlib.sha256("".join(fingerprint(p) for p in paths).encode()).hexdigest()[:24]
        audio_output = generated / (assembly_id + ".wav")
        if not audio_output.is_file():
            inputs = []
            for path in paths:
                inputs += ["-i", str(path)]
            graph = "".join(f"[{i}:a]" for i in range(len(paths))) + f"concat=n={len(paths)}:v=0:a=1[a]"
            temporary = audio_output.with_name(assembly_id + ".part.wav")
            run_media([*inputs, "-filter_complex", graph, "-map", "[a]", "-c:a", "pcm_s16le", temporary])
            probe(temporary)
            os.replace(temporary, audio_output)
        subtitle = generated / (assembly_id + f"-{round(float(data['narration_start'])*1000)}.srt")
        write_srt(subtitle, cues)
        data["narration_audio"] = audio_output.relative_to(directory).as_posix()
        data["subtitle_file"] = subtitle.relative_to(directory).as_posix()
        data["steps"]["voice"] = {"status": "done", "at": now(), "timing": "paragraph_estimated",
                                  "model": model, "voice_id": voice_id, "narration_start": offset,
                                  "audio": data["narration_audio"], "subtitle": data["subtitle_file"],
                                  "script_digest": hashlib.sha256(data["script"].encode()).hexdigest()}
        save_job(directory, data)
        return audio_output
