"""Exercise the real frozen quick GUI and two QProcess worker exports."""
from pathlib import Path
import os
import subprocess
import sys
import time
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".runtime" / "python"))
sys.path.insert(0, str(ROOT))
from studio import __version__
from studio.storage import Workspace, read_json
from pipeline import core
from check_quick import prepare, verify_outputs

folder = ROOT / ".runtime" / ("quick-frozen-" + __version__ + "-" + str(time.time_ns()))
folder.mkdir()
workspace = folder / "快速切片 工作区"
project_id = prepare(workspace)
store = Workspace(workspace)
doc = store.load(project_id)
doc["job"]["quick_clips"] = [["快速片段A · 技术测试", "0", "3", "技术测试，图表口径待核查", "先确认数字说的是什么。", "1"],
                              ["快速片段B · 技术测试", "3", "6", "技术测试，图表口径待核查", "演示片段，不作为事实结论。", "4"]]
store.save(doc)
store.close()
exe = ROOT / "dist" / __version__ / "EarthPeopleLogStudio" / "EarthPeopleLogStudio.exe"
env = dict(os.environ)
env["PATH"] = str(Path(env["WINDIR"]) / "System32") + os.pathsep + env["WINDIR"]
for key in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "EARTHLOG_PYTHON", "EARTHLOG_FFMPEG", "QT_PLUGIN_PATH"):
    env.pop(key, None)
subprocess.run([str(exe), "--workspace", str(workspace), "--check-ui-export", str(folder / "batch.json"), "--check-quick-batch"],
               check=True, env=env, timeout=130, creationflags=subprocess.CREATE_NO_WINDOW)
report = read_json(folder / "batch.json")
assert len(report["tasks"]) == 2, report
outputs = [verify_outputs(row, 3) for row in report["tasks"]]
subprocess.run([str(exe), "--workspace", str(workspace), "--screenshot", str(folder / "quick-frozen.png")],
               check=True, env=env, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
core.save_json(folder / "report.json", {"at": core.now(), "version": __version__, "outputs": [str(p) for p in outputs],
                                       "checks": ["frozen quick GUI submission", "two actual 1080p exports", "original audio track", "covers and posting copy", "development paths removed"]})
print(folder / "report.json")
