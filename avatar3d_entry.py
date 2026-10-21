"""独立三维角色入口，配置与旧二维工坊分离。"""
from pathlib import Path
import sys,argparse
ROOT=Path(__file__).resolve().parent
if not getattr(sys,'frozen',False):sys.path[:0]=[str(ROOT/'.runtime/python'),str(ROOT)]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--workspace',type=Path);parser.add_argument('--runtime',type=Path)
    parser.add_argument('--smoke',type=Path,help=argparse.SUPPRESS)
    parser.add_argument('--smoke-exchange',action='store_true',help=argparse.SUPPRESS);args=parser.parse_args()
    from PySide6.QtWidgets import QApplication,QMessageBox
    from PySide6.QtCore import QLockFile
    from avatar3d.app import Window
    app=QApplication(sys.argv)
    workspace=(args.workspace or Path.home()/'Documents/地球三维角色工坊').resolve();workspace.mkdir(parents=True,exist_ok=True)
    lock=QLockFile(str(workspace/'app.lock'));lock.setStaleLockTime(0)
    if not lock.tryLock(100):QMessageBox.warning(None,'工作区已打开','请切回已打开的三维角色工坊；同一工作区只允许运行一个实例。');return 2
    try:
        runtime=args.runtime or ROOT/'.runtime/avatar3d/runtime.json'
        window=Window(workspace,runtime,Path(__file__).parent/'avatar3d/assets/Seed-san.vrm',args.smoke,args.smoke_exchange)
        window.show();return app.exec()
    except Exception as exc:QMessageBox.critical(None,'三维工坊无法启动',str(exc));return 1
    finally:lock.unlock()

if __name__=='__main__':raise SystemExit(main())
