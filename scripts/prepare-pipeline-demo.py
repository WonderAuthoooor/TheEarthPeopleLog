"""Prepare an editable internal task using the user's existing local video."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".runtime" / "python"))
sys.path.insert(0, str(ROOT))
from pipeline.core import ROOT, import_asset, new_job, render, save_job, save_json


def main():
    source = ROOT / "工作素材" / "20261018  中国贫困人数变化" / "angeloinchina-2111423703263379903-01.mp4"
    if not source.is_file():
        raise SystemExit("The expected local sample is missing; use the GUI to import your own video.")
    directory, data = new_job()
    data.update(title="先核对口径，再看这张图", duration=8, narration_start=0,
                video=import_asset(directory, source),
                source_url="https://x.com/angeloinchina/status/2111423703263379903",
                source_note="用户提供视频 / 原帖与统计来源待核查",
                facts="已读取本地文件：1080×1080，约44.74秒，有音轨。图中数据来源、极端贫困标准、年份口径尚未核实。原帖URL由文件名推断，待打开确认。",
                script="内部测试：先核对数据来源，再讨论图表结论。")
    data["score"]["reason"] = "来源与统计口径待核查，不作结论"
    save_job(directory, data)
    output = render(directory, data)
    save_json(ROOT / ".pipeline/recent.json", {"job": str(directory.relative_to(ROOT))})
    save_json(ROOT / ".pipeline/demo.json", {"job": str(directory), "output": str(output)})
    print("DEMO_JOB=" + str(directory))
    print("DEMO_OUTPUT=" + str(output))


if __name__ == "__main__": main()
