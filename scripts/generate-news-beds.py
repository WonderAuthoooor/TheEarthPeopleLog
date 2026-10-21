"""Compose three low-density instrumental beds with mathematical oscillators.

No song, recorded sample, artist model, external API or downloaded audio is used.
This is procedural synthesis, not a professional AI music-generation service.
"""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import sys
import wave
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".runtime" / "python"))
sys.path.insert(0, str(ROOT))
import numpy as np
from pipeline.core import ffmpeg_exe, probe

RATE = 44100
LENGTH = 48
SPECS = [
    {"file": "01_日常新闻_轻缓观察", "bpm": 80, "kind": "neutral", "seed": 19101,
     "chords": [[48, 55, 59, 62], [45, 52, 55, 59], [41, 48, 52, 55], [43, 50, 55, 57]],
     "use": "日常新闻口播；温和电钢琴合成音色、低密度和弦和轻脉冲"},
    {"file": "02_科技观察_柔和脉冲", "bpm": 90, "kind": "tech", "seed": 19102,
     "chords": [[50, 57, 60, 64], [46, 53, 57, 60], [53, 60, 64, 67], [48, 55, 60, 62]],
     "use": "科技与产品解说；柔和合成器铺底、稀疏分解音与轻节奏"},
    {"file": "03_轻松点评_温暖留白", "bpm": 84, "kind": "light", "seed": 19103,
     "chords": [[53, 60, 64, 67], [50, 57, 60, 64], [46, 53, 57, 60], [48, 55, 58, 62]],
     "use": "温和幽默点评；短促柔软拨奏、轻切分，不用于伤亡等严肃场景"},
]


def synth(spec):
    rng = np.random.default_rng(spec["seed"])
    canvas = np.zeros((RATE * LENGTH, 2), np.float64)
    beat = 60 / spec["bpm"]
    bar = 4 * beat

    def add(sound, when, gain, pan=0):
        start = int(round(when * RATE))
        if start >= len(canvas):
            return
        sound = sound[:len(canvas) - start]
        canvas[start:start + len(sound), 0] += sound * gain * np.sqrt((1 - pan) / 2)
        canvas[start:start + len(sound), 1] += sound * gain * np.sqrt((1 + pan) / 2)

    def tone(note, seconds, mode="keys"):
        t = np.arange(int(seconds * RATE)) / RATE
        f = 440 * 2 ** ((note - 69) / 12)
        attack = 1 - np.exp(-t / (.30 if mode == "pad" else .014))
        release = np.minimum(1, np.maximum(0, (seconds - t) / (.65 if mode == "pad" else .18)))
        if mode == "pad":
            sound = (np.sin(2 * np.pi * f * t) + .16 * np.sin(2 * np.pi * f * 1.0018 * t)
                     + .10 * np.sin(2 * np.pi * 2 * f * t))
            env = attack * release * (.88 + .12 * np.cos(2 * np.pi * .16 * t))
        elif mode == "bass":
            sound = np.sin(2 * np.pi * f * t) + .13 * np.sin(2 * np.pi * 2 * f * t)
            env = attack * release * np.exp(-t / .9)
        else:
            # Soft electric-key/pluck timbre; no attempt to emulate an artist.
            sound = (np.sin(2 * np.pi * f * t) + .20 * np.sin(2 * np.pi * 2 * f * t)
                     * np.exp(-t * 3) + .045 * np.sin(2 * np.pi * 3 * f * t))
            env = attack * release * np.exp(-t / (.68 if mode == "pluck" else 1.35))
        return sound * env

    bars = int(np.ceil(LENGTH / bar))
    for i in range(bars):
        chord = spec["chords"][(i // 2) % len(spec["chords"])]
        start = i * bar
        # Slow harmonic motion leaves room for narration.
        if i % 2 == 0:
            for n, note in enumerate(chord):
                add(tone(note, 2 * bar + .7, "pad"), start + .015 * n, .052, (n - 1.5) / 3)
        add(tone(chord[0] - 12, 1.5 * beat, "bass"), start, .095)
        if spec["kind"] == "neutral":
            pattern = [(0, 1), (1.5, 2), (3, 3)]
        elif spec["kind"] == "tech":
            pattern = [(0, 0), (1, 2), (2.5, 1), (3.5, 3)]
        else:
            pattern = [(.5, 1), (1.75, 3), (3, 2)]
        for k, (offset, index) in enumerate(pattern):
            when = start + offset * beat + rng.uniform(-.008, .008)
            note = chord[index] + 12
            add(tone(note, 2.2 if spec["kind"] == "neutral" else 1.6,
                     "pluck" if spec["kind"] == "light" else "keys"), max(0, when),
                .073 if spec["kind"] == "neutral" else .063, (-1 if k % 2 else 1) * .24)
        if spec["kind"] != "neutral":
            for off in (0, 2):
                t = np.arange(int(.17 * RATE)) / RATE
                phase = 2 * np.pi * (47 * t + 2.8 * (1 - np.exp(-t * 24)))
                kick = np.sin(phase) * np.exp(-t * 29) * (1 - np.exp(-t * 900))
                add(kick, start + off * beat, .038)
        # Soft filtered noise ticks, quiet enough to stay behind speech.
        if spec["kind"] == "tech":
            t = np.arange(int(.07 * RATE)) / RATE
            noise = rng.normal(0, 1, len(t))
            noise = np.convolve(noise, np.ones(8) / 8, mode="same")
            tick = noise * np.exp(-t * 70) * np.minimum(t / .006, 1)
            for off in (.5, 1.5, 2.5, 3.5):
                add(tick, start + off * beat, .017, .3)

    dry = canvas.copy()
    for delay, gain in ((.137, .12), (.271, .08), (.413, .045)):
        samples = int(delay * RATE)
        canvas[samples:] += dry[:-samples, ::-1] * gain
    canvas -= np.mean(canvas, axis=0)
    # Short smooth entrance and a deliberate tail (not advertised as seamless).
    fade_in = int(.8 * RATE)
    fade_out = int(2.6 * RATE)
    canvas[:fade_in] *= np.sin(np.linspace(0, np.pi / 2, fade_in))[:, None] ** 2
    canvas[-fade_out:] *= np.sin(np.linspace(np.pi / 2, 0, fade_out))[:, None] ** 2
    rms = np.sqrt(np.mean(canvas ** 2))
    gain = min(10 ** (-25 / 20) / rms, .60 / np.max(np.abs(canvas)))
    canvas *= gain
    assert np.isfinite(canvas).all() and np.max(np.abs(canvas)) < .99
    return canvas


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "工作素材" / "配乐" / "20261019_轻缓新闻_v1")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    results = []
    for spec in SPECS:
        wav = args.output / (spec["file"] + ".wav")
        mp3 = wav.with_suffix(".mp3")
        if wav.exists() or mp3.exists():
            raise FileExistsError("已有同名配乐，改用新版本输出目录，避免覆盖试听选择。")
        sound = synth(spec)
        with wave.open(str(wav), "wb") as output:
            output.setnchannels(2)
            output.setsampwidth(2)
            output.setframerate(RATE)
            output.writeframes(np.round(sound * 32767).astype("<i2").tobytes())
        subprocess.run([ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-nostdin", "-i", str(wav),
                        "-codec:a", "libmp3lame", "-b:a", "192k", "-metadata", "title=" + spec["file"],
                        str(mp3)], check=True, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
        meta = probe(mp3)
        assert abs(meta["duration"] - LENGTH) < .15 and meta["has_audio"]
        results.append({**spec, "seconds": LENGTH, "sample_rate": RATE, "channels": 2,
                        "peak_dbfs": round(float(20 * np.log10(np.max(np.abs(sound))))),
                        "rms_dbfs": round(float(20 * np.log10(np.sqrt(np.mean(sound ** 2))))),
                        "wav": wav.name, "mp3": mp3.name,
                        "sha256": hashlib.sha256(mp3.read_bytes()).hexdigest()})
        print(mp3)
    manifest = {"created_at": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
                "method": "本地程序原创编排与振荡器合成，未调用AI音乐API，未使用第三方歌曲或采样",
                "audition": "未人工试听；已完成时长、解码、非静音及峰值检查，听感由用户确认",
                "tracks": results}
    (args.output / "生成记录.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
