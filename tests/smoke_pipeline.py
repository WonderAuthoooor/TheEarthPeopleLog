"""Render real files plus clearly labeled synthetic technical test fixtures.

Fixtures are internal QA, not news examples or invented user comments.
"""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".runtime" / "python"))
sys.path.insert(0, str(ROOT))
from pipeline.core import (import_asset, new_job, probe, render, run_media,
                           save_job, write_srt)


def main():
    qa = ROOT / ".pipeline" / "qa"
    qa.mkdir(parents=True, exist_ok=True)
    from PIL import Image, ImageDraw
    from pipeline.core import font
    panel = Image.new("RGB", (900, 160), "#f6f3ea")
    draw = ImageDraw.Draw(panel)
    draw.text((25, 25), "排版测试图片（不是网友评论）", font=font(36), fill="#182a30")
    panel.save(qa / "test-panel.png")
    run_media(["-f", "lavfi", "-i", "testsrc2=size=640x360:rate=30", "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000",
               "-t", "7", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", qa / "source.mp4"])
    run_media(["-f", "lavfi", "-i", "sine=frequency=660:sample_rate=48000", "-t", "2", "-c:a", "pcm_s16le", qa / "test-tone.wav"])
    outputs = []
    for name, source, duration in (("横屏混音测试", qa / "source.mp4", 6),
        ("现有样片兼容测试", ROOT / "content/2026-10-11-ai-si/preview-v1.mp4", 6),
        ("用户素材选段测试", next((ROOT / "工作素材").rglob("*.mp4")), 8)):
        directory, data = new_job()
        data["title"] = name
        data["source_note"] = "内部技术测试 / 原视频未改写"
        data["video"] = import_asset(directory, source)
        data["duration"] = duration
        data["clip_start"] = 0
        data["score"]["reason"] = "仅验证工具；不作事实结论"
        if name == "横屏混音测试":
            data["narration_audio"] = import_asset(directory, qa / "test-tone.wav")
            data["narration_start"] = 2
            data["comments"] = [{"image": import_asset(directory, qa / "test-panel.png"),
                                 "translation": "技术测试：不是网友评论", "url": "", "start": 2, "end": 5}]
            write_srt(qa / "准确字幕.srt", [{"start": 2, "end": 4, "text": "技术测试音，不是口播。"}])
            data["subtitle_file"] = import_asset(directory, qa / "准确字幕.srt")
        elif name == "用户素材选段测试":
            data["script"] = "内部测试：数据来源与统计口径尚未核查。"
        save_job(directory, data)
        output = render(directory, data, resolution=1080)
        # Same inputs must reuse outputs, not re-render or call external services.
        cached = render(directory, data, resolution=1080)
        assert output == cached and data["steps"]["render"]["cached"] is True
        info = probe(output / "preview.mp4")
        assert (info["width"], info["height"]) == (1080, 1920)
        assert info["has_audio"]
        assert abs(info["duration"] - duration) < .2
        run_media(["-ss", 3, "-i", output / "preview.mp4", "-frames:v", "1", output / "check-frame.png"])
        outputs.append({"name": name, "job": str(directory), "output": str(output), "technical": info})
    (qa / "results.json").write_text(json.dumps(outputs, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(outputs, ensure_ascii=False, indent=2))


if __name__ == "__main__": main()
