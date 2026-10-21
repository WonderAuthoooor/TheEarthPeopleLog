"""仅打包角色运行时与原创素材，不带地点／新闻程序。"""
from pathlib import Path
import hashlib
import json
import os
import sys
import zipfile
from datetime import datetime
ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT/".runtime/python"),str(ROOT/".runtime/avatar-live-python"),str(ROOT)]
os.environ["PYINSTALLER_CONFIG_DIR"] = str(ROOT/".runtime/pyinstaller-cache")
import PyInstaller.__main__
from avatar_app import __version__


def fingerprint(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    sources = [ROOT/"avatar_entry.py"]+[p for p in (ROOT/"avatar_app").rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    hashes = {str(p.relative_to(ROOT)):fingerprint(p) for p in sources}
    dist = ROOT/"dist/avatar"/__version__
    build = ROOT/"build/avatar"/__version__
    notices = ROOT/".runtime/avatar-notices"
    notices.mkdir(parents=True,exist_ok=True)
    dependencies = []
    wheels = list((ROOT/".runtime/wheels").glob("*.whl"))+list((ROOT/".runtime/avatar-live-wheels").glob("*.whl"))
    for wheel in sorted(wheels):
        if not any(wheel.name.lower().startswith(name) for name in ("pyside6","shiboken6","pillow-12.3.0","numpy-2.3.5","av-", "mediapipe-0.10.31-","absl_py-","flatbuffers-","sounddevice-","cffi-","pycparser-")):
            continue
        dependencies.append({"archive":wheel.name,"sha256":fingerprint(wheel)})
        with zipfile.ZipFile(wheel) as z:
            for name in z.namelist():
                if not name.endswith("/") and ".dist-info/" in name and any(s in name.lower() for s in ("license","copying","notice")):
                    target = notices/wheel.stem/name
                    target.parent.mkdir(parents=True,exist_ok=True)
                    target.write_bytes(z.read(name))
    (notices/"说明.txt").write_text("内部试验包。Qt动态链接；PyAV／FFmpeg、Qt等许可证见归档。对外分发前补齐对应源码与许可证义务、签名和干净机器验收。\n未采购／集成Live2D SDK，角色为项目内置image_gen生成原画与自定义分层试验驱动。\n",encoding="utf-8")
    args = [str(ROOT/"avatar_entry.py"),"--name","EarthPeopleLogAvatar","--onedir","--windowed","--clean","--noconfirm",
            "--icon",str(ROOT/"avatar_app/assets/app-icon.ico"),"--paths",str(ROOT/".runtime/python"),
            "--paths",str(ROOT/".runtime/avatar-live-python"),"--paths",str(ROOT),
            "--distpath",str(dist),"--workpath",str(build),"--specpath",str(build),
            "--collect-all","av","--collect-all","mediapipe","--add-data",str(ROOT/"avatar_app/assets")+";avatar_app/assets",
            "--add-data",str(notices)+";licenses"]
    for module in ("studio","globe_app","pipeline","yt_dlp","tkinter","matplotlib","IPython","pytest","PyQt5","PyQt6"):
        args += ["--exclude-module",module]
    PyInstaller.__main__.run(args)
    assert hashes == {str(p.relative_to(ROOT)):fingerprint(p) for p in sources},"Source changed during build"
    folder = dist/"EarthPeopleLogAvatar"
    (folder/"build-manifest.json").write_text(json.dumps({"product":"EarthPeopleLogAvatar","version":__version__,
        "built_at":datetime.now().astimezone().isoformat(),"source_hashes":hashes,
        "exe_sha256":fingerprint(folder/"EarthPeopleLogAvatar.exe"),"excluded":["studio","globe_app","pipeline"],"build_inputs":dependencies,
        "scope":"内部试验版，尚未完成对外分发／干净机器验收"},ensure_ascii=False,indent=2),encoding="utf-8")
    print(folder)
