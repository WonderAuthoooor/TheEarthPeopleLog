"""独立角色工具入口，与地点／新闻工作台无运行时依赖。"""
from pathlib import Path
import argparse
import sys

ROOT = Path(__file__).resolve().parent
if not getattr(sys,"frozen",False):
    sys.path[:0] = [str(ROOT/".runtime/python"),str(ROOT/".runtime/avatar-live-python")]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace",type=Path)
    parser.add_argument("--render",type=Path,help="本地JSON渲染请求")
    parser.add_argument("--smoke",type=Path,help=argparse.SUPPRESS)
    parser.add_argument("--doctor",type=Path,help=argparse.SUPPRESS)
    parser.add_argument("--check-live",type=Path,help=argparse.SUPPRESS)
    parser.add_argument("--check-actions",type=Path,help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.render:
        import json
        from avatar_app.export import export_clip
        request = json.loads(args.render.read_text(encoding="utf-8"))
        folder = export_clip(**request)
        print(folder)
        return 0
    if args.doctor:
        from avatar_app import __version__
        from avatar_app.rig import Rig
        from avatar_app.export import save_json
        from avatar_app.tracking import MODELS
        from avatar_app.actions import ACTION_NAMES
        import mediapipe
        rig = Rig()
        save_json(args.doctor,{"version":__version__,"frozen":bool(getattr(sys,"frozen",False)),
                  "capabilities":rig.config["capabilities"],"globe_required":False,"studio_required":False,
                  "tracking_backend":"MediaPipe "+mediapipe.__version__,
                  "tracking_models_present":all((MODELS/n).is_file() for n in ("face_landmarker.task","pose_landmarker_lite.task")),
                  "action_presets":ACTION_NAMES,
                  "camera_started":False})
        return 0
    from PySide6.QtWidgets import QApplication,QMessageBox
    from avatar_app.app import Window
    app = QApplication(sys.argv)
    if args.check_actions:
        from avatar_app.selfcheck import check_actions
        return check_actions(app,args.check_actions)
    if args.check_live:
        from avatar_app.selfcheck import check_live
        return check_live(app,args.check_live)
    try:
        window = Window(args.workspace or Path.home()/"Documents"/"地球角色工坊",args.smoke)
    except Exception as exc:
        QMessageBox.critical(None,"角色工坊无法启动",str(exc))
        return 1
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
