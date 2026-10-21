"""Build in project-local paths. Run using the project's bootstrap Python."""
from pathlib import Path
import sys
import json
import hashlib
import zipfile
import os

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".runtime" / "python"))
sys.path.insert(0, str(ROOT))
os.environ["PYINSTALLER_CONFIG_DIR"] = str(ROOT / ".runtime" / "pyinstaller-cache")
import PyInstaller.__main__
from pipeline import core
from studio import __version__


if __name__ == "__main__":
    import runpy
    runpy.run_path(str(ROOT / "scripts" / "generate-app-icon.py"), run_name="__main__")
    source_paths = [ROOT / "studio_entry.py"]
    for folder in ("pipeline", "studio", "globe_app"):
        source_paths.extend(p for p in (ROOT / folder).rglob("*")
                            if p.is_file() and p.suffix in (".py", ".json", ".svg", ".ico", ".png", ".md"))
    source_hashes = {str(p.relative_to(ROOT)): core.fingerprint(p) for p in sorted(source_paths)}
    import importlib.metadata
    notices = ROOT / ".runtime" / "studio-notices-v02"
    notices.mkdir(exist_ok=True)
    manifest = []
    for wheel in sorted((ROOT / ".runtime" / "wheels").glob("*.whl")):
        manifest.append({"wheel": wheel.name, "sha256": core.fingerprint(wheel)})
        with zipfile.ZipFile(wheel) as package:
            for item in package.namelist():
                if not item.endswith("/") and ".dist-info/" in item and any(word in item.lower() for word in ("license", "copying", "notice")):
                    destination = notices / wheel.stem / item
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(package.read(item))
    core.save_json(notices / "dependencies.json", manifest)
    (notices / "说明.txt").write_text("内部测试版；依赖许可证见各子目录。Qt动态链接，可替换兼容DLL。FFmpeg由imageio-ffmpeg提供，包含GPL组件；二进制构建配置和项目见其许可证/README。对外分发前须完成对应源码与许可证义务、签名及干净机器验收。应用源代码位于本项目studio/与pipeline/。\nFFmpeg upstream: https://github.com/BtbN/FFmpeg-Builds\nQt source: https://code.qt.io/qt/pyside-setup.git\n", encoding="utf-8")
    args = [str(ROOT / "studio_entry.py"), "--name", "EarthPeopleLogStudio", "--onedir", "--windowed", "--noconfirm", "--clean",
            "--icon", str(ROOT / "studio" / "assets" / "app-icon.ico"),
            "--add-data", str(ROOT / "studio" / "assets") + ";studio/assets",
            "--add-data", str(ROOT / "pipeline" / "assets") + ";pipeline/assets",
            "--add-data", str(ROOT / "globe_app" / "assets") + ";globe_app/assets",
            "--paths", str(ROOT / ".runtime" / "python"), "--paths", str(ROOT),
            "--distpath", str(ROOT / "dist" / __version__), "--workpath", str(ROOT / "build" / __version__), "--specpath", str(ROOT / "build" / __version__),
            "--collect-all", "av", "--collect-all", "imageio_ffmpeg", "--collect-all", "yt_dlp",
            "--add-data", str(notices) + ";licenses",
            "--exclude-module", "tkinter", "--exclude-module", "numpy", "--exclude-module", "matplotlib",
            "--exclude-module", "IPython", "--exclude-module", "pytest", "--exclude-module", "PyQt5", "--exclude-module", "PyQt6"]
    PyInstaller.__main__.run(args)
    if source_hashes != {str(p.relative_to(ROOT)): core.fingerprint(p) for p in sorted(source_paths)}:
        raise RuntimeError("构建期间源码或资产发生变化，请在编辑结束后重新构建。")
    destination = ROOT / "dist" / __version__ / "EarthPeopleLogStudio"
    core.save_json(destination / "build-manifest.json", {"version": __version__, "built_at": core.now(), "exe_sha256": core.fingerprint(destination / "EarthPeopleLogStudio.exe"), "dependencies": manifest, "source_hashes": source_hashes})
    print(destination)
