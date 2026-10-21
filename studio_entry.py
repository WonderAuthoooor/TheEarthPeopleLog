"""Development and frozen entry; data lives outside the application directory."""
from pathlib import Path
import argparse
import os
import sys

ROOT = Path(__file__).resolve().parent
if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(ROOT / ".runtime" / "python"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", type=Path)
    parser.add_argument("--animation", type=Path)
    parser.add_argument("--workspace", type=Path)
    parser.add_argument("--screenshot", type=Path)
    parser.add_argument("--doctor", type=Path)
    parser.add_argument("--check-ui-export", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--check-quick-batch", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--check-animation", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.animation:
        from pipeline.globe import execute_request
        return execute_request(args.animation)
    if args.worker:
        from studio.worker import execute
        return execute(args.worker)
    from pipeline import core
    if args.doctor:
        import av, PIL, PySide6
        from studio import __version__
        core.save_json(args.doctor, {"frozen": bool(getattr(sys, "frozen", False)), "version": __version__, "python": sys.version, "qt": PySide6.__version__, "av": av.__version__, "pillow": PIL.__version__, "ffmpeg": core.ffmpeg_exe(), "font": core.font(24).getname()})
        return 0
    config_root = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "EarthPeopleLogStudio"
    # Explicit workspaces (tests/development) do not write global user configuration.
    config_file = config_root / "settings.json"
    workspace = args.workspace
    if workspace is None:
        try:
            import json
            workspace = Path(json.loads(config_file.read_text(encoding="utf-8"))["workspace"])
        except (OSError, ValueError, KeyError):
            workspace = Path.home() / "Documents" / "地球人日志工作区"
    try:
        from studio.app import launch
        next_workspace = launch(workspace, args.screenshot, args.check_ui_export, args.check_quick_batch, args.check_animation)
        if not args.workspace:
            core.save_json(config_file, {"workspace": str(next_workspace or workspace)})
    except Exception as exc:
        # Windowed builds have no console: preserve a visible, actionable error.
        from PySide6.QtWidgets import QApplication, QMessageBox
        app = QApplication.instance() or QApplication([])
        QMessageBox.critical(None, "工作室未能启动", str(exc) + "\n原有项目不会被覆盖。")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
