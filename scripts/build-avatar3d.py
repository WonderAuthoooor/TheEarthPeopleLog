"""三维工作流独立打包；Blender与插件保持项目内可替换的外部运行环境。"""
from pathlib import Path
import sys,os,json,hashlib
from datetime import datetime
ROOT=Path(__file__).resolve().parent.parent
sys.path[:0]=[str(ROOT/'.runtime/python'),str(ROOT)]
os.environ['PYINSTALLER_CONFIG_DIR']=str(ROOT/'.runtime/pyinstaller-cache')
import PyInstaller.__main__
from avatar3d import __version__
from avatar3d.models import digest

if __name__=='__main__':
    inputs=[ROOT/'avatar3d_entry.py']+[p for p in (ROOT/'avatar3d').rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    hashes={str(p.relative_to(ROOT)):digest(p) for p in inputs}
    dist=ROOT/'dist/avatar3d'/__version__;build=ROOT/'build/avatar3d'/__version__
    args=[str(ROOT/'avatar3d_entry.py'),'--name','EarthPeopleLogAvatar3D','--onedir','--windowed','--clean','--noconfirm',
          '--icon',str(ROOT/'avatar3d/assets/app-icon.ico'),'--paths',str(ROOT/'.runtime/python'),'--paths',str(ROOT),
          '--distpath',str(dist),'--workpath',str(build),'--specpath',str(build),
          '--collect-all','av','--collect-all','imageio_ffmpeg','--add-data',str(ROOT/'avatar3d')+';avatar3d',
          '--add-data',str(ROOT/'.runtime/avatar-notices')+';licenses']
    for module in ('studio','globe_app','avatar_app','pipeline','mediapipe','yt_dlp','tkinter','matplotlib','IPython','pytest','PyQt5','PyQt6'):
        args+=['--exclude-module',module]
    PyInstaller.__main__.run(args)
    assert hashes=={str(p.relative_to(ROOT)):digest(p) for p in inputs},'构建期间源文件变化'
    folder=dist/'EarthPeopleLogAvatar3D'
    (folder/'build-manifest.json').write_text(json.dumps({'product':'EarthPeopleLogAvatar3D','version':__version__,
        'built_at':datetime.now().astimezone().isoformat(),'source_hashes':hashes,'exe_sha256':digest(folder/'EarthPeopleLogAvatar3D.exe'),
        'runtime':'项目内.runtime/avatar3d；快捷入口传入独立配置；未嵌入EXE',
        'scope':'三维导入与离线姿势／渲染验证；不是已完成C角色／直播运行器'},ensure_ascii=False,indent=2),encoding='utf-8')
    print(folder)
