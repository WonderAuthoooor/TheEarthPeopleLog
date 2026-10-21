"""Real media processing with a mocked TTS response; no paid requests."""
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".runtime/python"))
sys.path.insert(0, str(ROOT))
from pipeline.core import import_asset, new_job, render, run_media, save_job, read_srt, PipelineError
from pipeline.providers import generate_voice

qa = ROOT / ".pipeline/qa"
audio = qa / "test-response.mp3"
run_media(["-i", qa / "test-tone.wav", "-c:a", "libmp3lame", audio])
directory, data = new_job()
data.update(title="接口返回模拟测试", video=import_asset(directory, qa / "source.mp4"),
            script="技术测试，不是实际口播。", duration=6, narration_start=1)
save_job(directory, data)
with patch("pipeline.providers.post_json", return_value={"data": {"audio": audio.read_bytes().hex()}, "extra_info": {"usage_characters": 10}}):
    generate_voice(directory, data, key="MOCK-ONLY", voice_id="mock-voice")
data["narration_start"] = 3
output = render(directory, data, resolution=540)
assert read_srt(output / "subtitles.srt")[0]["start"] == 3
data["script"] = "changed manuscript"
try:
    render(directory, data, resolution=540)
except PipelineError as exc:
    assert "口播稿或配音已改变" in str(exc)
else:
    raise AssertionError("Old generated subtitles must be rejected after script changes")
print("Mock TTS -> real audio assembly -> 540 render -> shifted subtitles -> stale subtitle rejection: OK")
