"""独立三维角色入口，配置与旧二维工坊分离。"""
from pathlib import Path
import sys,argparse
ROOT=Path(__file__).resolve().parent
if not getattr(sys,'frozen',False):sys.path[:0]=[str(ROOT/'.runtime/python'),str(ROOT)]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--workspace',type=Path);parser.add_argument('--runtime',type=Path)
    parser.add_argument('--smoke',type=Path,help=argparse.SUPPRESS)
    parser.add_argument('--smoke-exchange',action='store_true',help=argparse.SUPPRESS)
    parser.add_argument('--smoke-export',action='store_true',help=argparse.SUPPRESS)
    parser.add_argument('--smoke-preview',action='store_true',help=argparse.SUPPRESS)
    parser.add_argument('--smoke-audio',type=Path,help=argparse.SUPPRESS)
    parser.add_argument('--smoke-model',type=Path,help=argparse.SUPPRESS)
    parser.add_argument('--smoke-project',type=Path,help=argparse.SUPPRESS)
    parser.add_argument('--smoke-live',type=Path,help=argparse.SUPPRESS)
    parser.add_argument('--smoke-action',choices=('wave','idle','explain'),default='wave',help=argparse.SUPPRESS);args=parser.parse_args()
    if args.smoke_export and (not args.smoke or args.smoke_exchange):parser.error('smoke-export requires smoke and cannot combine with smoke-exchange')
    if args.smoke_preview and (not args.smoke or args.smoke_exchange):parser.error('smoke-preview requires smoke and cannot combine with smoke-exchange')
    if args.smoke_audio and (not args.smoke_export or args.smoke_action not in ('idle','explain')):parser.error('smoke-audio requires smoke-export and idle/explain')
    if args.smoke_model and not args.smoke:parser.error('smoke-model requires smoke')
    if args.smoke_project and (not args.smoke or args.smoke_export or args.smoke_exchange or args.smoke_preview or args.smoke_audio):parser.error('smoke-project requires smoke and a separate workspace')
    if args.smoke_live and (not args.smoke or args.smoke_project or args.smoke_export or args.smoke_exchange or args.smoke_preview or args.smoke_audio or args.smoke_model):parser.error('smoke-live requires smoke and a separate workspace')
    from PySide6.QtWidgets import QApplication,QMessageBox
    from PySide6.QtCore import QLockFile
    from avatar3d.app import Window
    app=QApplication(sys.argv)
    workspace=(args.workspace or Path.home()/'Documents/地球三维角色工坊').resolve();workspace.mkdir(parents=True,exist_ok=True)
    lock=QLockFile(str(workspace/'app.lock'));lock.setStaleLockTime(0)
    if not lock.tryLock(100):QMessageBox.warning(None,'工作区已打开','请切回已打开的三维角色工坊；同一工作区只允许运行一个实例。');return 2
    try:
        runtime=args.runtime or ROOT/'.runtime/avatar3d/runtime.json'
        window=Window(workspace,runtime,args.smoke_model or Path(__file__).parent/'avatar3d/assets/Seed-san.vrm',None if args.smoke_project or args.smoke_live else args.smoke,args.smoke_exchange,args.smoke_export,args.smoke_preview,args.smoke_action,args.smoke_audio)
        window.show()
        if args.smoke_project:
            from avatar3d.speech_smoke import start
            start(window,args.smoke_project,args.smoke)
        if args.smoke_live:
            from avatar3d.live_smoke import start
            start(window,args.smoke_live,args.smoke)
        return app.exec()
    except Exception as exc:QMessageBox.critical(None,'三维工坊无法启动',str(exc));return 1
    finally:lock.unlock()

if __name__=='__main__':raise SystemExit(main())
