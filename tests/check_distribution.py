"""Standalone executable check with Codex/Python removed from child environment."""
from pathlib import Path
import json
import os
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".runtime" / "python"))
sys.path.insert(0, str(ROOT))
from studio.storage import Workspace, read_json
from studio import __version__
from pipeline import core
EXE = ROOT / "dist" / __version__ / "EarthPeopleLogStudio" / "EarthPeopleLogStudio.exe"


if __name__ == "__main__":
    folder = ROOT / ".runtime" / "distribution-qa"
    folder.mkdir(exist_ok=True)
    env = dict(os.environ)
    env["PATH"] = str(Path(env["WINDIR"]) / "System32") + os.pathsep + env["WINDIR"]
    for key in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "EARTHLOG_PYTHON", "EARTHLOG_FFMPEG", "QT_PLUGIN_PATH"):
        env.pop(key, None)
    flags = subprocess.CREATE_NO_WINDOW
    subprocess.run([str(EXE), "--doctor", str(folder / "doctor.json")], check=True, env=env, timeout=30, creationflags=flags)
    doctor = read_json(folder / "doctor.json")
    assert doctor["frozen"] and Path(doctor["ffmpeg"]).is_relative_to(EXE.parent)
    workspace = ROOT / ".studio"
    store = Workspace(workspace)
    if not store.list_projects():
        doc = store.migrate(ROOT / ".pipeline" / "jobs" / "20261018-55d72b73")
    else:
        doc = store.load(store.list_projects()[0][1])
    task = store.enqueue(doc, resolution=1080)
    row = next(r for r in store.tasks() if r["id"] == task)
    if row["state"] != "SUCCEEDED":
        store.update_task(task, state="RUNNING")
        child = subprocess.run([str(EXE), "--worker", str(store.runs / task)], check=True, env=env, timeout=120, creationflags=flags)
        store.reconcile()
    row = next(r for r in store.tasks() if r["id"] == task)
    assert row["state"] == "SUCCEEDED", row
    metadata = core.probe(Path(row["output"]) / "preview.mp4")
    assert metadata["width"] == 1080 and metadata["height"] == 1920
    store.close()
    subprocess.run([str(EXE), "--workspace", str(workspace), "--screenshot", str(folder / "frozen-workbench.png")], check=True, env=env, timeout=30, creationflags=flags)
    assert (folder / "frozen-workbench.png").stat().st_size > 10000
    subprocess.run([str(EXE), "--workspace", str(workspace), "--check-ui-export", str(folder / "gui-export.json")], check=True, env=env, timeout=120, creationflags=flags)
    gui_task = read_json(folder / "gui-export.json")["task"]
    assert gui_task and gui_task["state"] == "SUCCEEDED", read_json(folder / "gui-export.json")
    core.save_json(folder / "report.json", {"at": core.now(), "environment": "PATH仅Windows系统目录，移除Python/Codex引用；本机仍安装开发工具，不等于干净机器", "doctor": doctor, "output": row["output"], "metadata": metadata, "checks": ["frozen runtime", "bundled FFmpeg", "1080p actual export", "Qt GUI launch/capture/exit"]})
    print(folder / "report.json")
