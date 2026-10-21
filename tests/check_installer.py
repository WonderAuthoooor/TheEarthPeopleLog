"""Install/uninstall only into this repository's disposable QA directory."""
from pathlib import Path
import subprocess
import time
import sys
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".runtime" / "python"))
sys.path.insert(0, str(ROOT))
from pipeline import core
from studio.storage import read_json
from studio import __version__

if __name__ == "__main__":
    folder = (ROOT / ".runtime" / f"installer-qa-{__version__}" / "app").resolve()
    assert folder.is_relative_to((ROOT / ".runtime" / f"installer-qa-{__version__}").resolve())
    installer = ROOT / "dist" / f"EarthPeopleLogStudio-{__version__}-Setup.exe"
    subprocess.run([str(installer), "/S", "/TEST", "/D=" + str(folder)], check=True, timeout=120)
    exe = folder / "EarthPeopleLogStudio.exe"
    assert exe.is_file() and (folder / "test-install.marker").exists()
    subprocess.run([str(exe), "--doctor", str(folder.parent / "installed-doctor.json")], check=True, timeout=30)
    assert read_json(folder.parent / "installed-doctor.json")["frozen"]
    sentinel = folder / "用户工作区" / "不能删除.txt"
    sentinel.parent.mkdir(exist_ok=True)
    sentinel.write_text("test-user-data", encoding="utf-8")
    subprocess.run([str(folder / "Uninstall.exe"), "/S"], check=True, timeout=60)
    deadline = time.monotonic() + 30
    while exe.exists() and time.monotonic() < deadline:
        time.sleep(.1)
    assert not exe.exists(), "uninstall did not remove installed program"
    assert sentinel.read_text(encoding="utf-8") == "test-user-data"
    core.save_json(folder.parent / "report.json", {"at": core.now(), "test_mode": "无注册表写入/快捷方式创建，仅项目内安装目录", "installer_sha256": core.fingerprint(installer), "checks": ["silent install", "installed frozen runtime", "uninstall exact packaged files", "user workspace preserved"]})
    print(folder.parent / "report.json")
