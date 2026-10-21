"""Independent location-animation executable and worker entry."""
from pathlib import Path
import argparse
import sys

ROOT=Path(__file__).resolve().parent
if not getattr(sys,'frozen',False):sys.path.insert(0,str(ROOT/'.runtime/python'))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--workspace',type=Path)
    parser.add_argument('--animation',type=Path)
    parser.add_argument('--doctor',type=Path)
    parser.add_argument('--check-export',type=Path,help=argparse.SUPPRESS)
    args=parser.parse_args()
    if args.animation:
        from pipeline.globe import execute_request
        return execute_request(args.animation)
    if args.doctor:
        from pipeline import core
        from globe_app import __version__
        core.save_json(args.doctor,{'product':'EarthPeopleLogGlobe','version':__version__,
            'frozen':bool(getattr(sys,'frozen',False)),'ffmpeg':core.ffmpeg_exe(),
            'workspace_separate':True,'avatar_required':False})
        return 0
    from PySide6.QtWidgets import QApplication,QMessageBox
    app=QApplication.instance() or QApplication(sys.argv)
    try:
        from globe_app.app import launch
        return launch(app,args.workspace or Path.home()/'Documents'/'地球地点动画',args.check_export)
    except Exception as exc:
        QMessageBox.critical(None,'地点动画未能启动',str(exc)+'\n已有素材和工作室项目不会被覆盖。')
        return 1


if __name__=='__main__':raise SystemExit(main())
