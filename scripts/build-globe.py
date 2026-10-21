"""Build the independent globe application without studio or avatar assets."""
from pathlib import Path
import sys,os,zipfile
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'.runtime/python'));sys.path.insert(0,str(ROOT))
os.environ['PYINSTALLER_CONFIG_DIR']=str(ROOT/'.runtime/pyinstaller-cache')
import PyInstaller.__main__
from pipeline import core
from globe_app import __version__

if __name__=='__main__':
    paths=[ROOT/'globe_entry.py']
    paths.extend(p for folder in ('globe_app','pipeline') for p in (ROOT/folder).rglob('*')
                 if p.is_file() and p.suffix in ('.py','.json','.svg','.ico','.png','.md') and 'mascots' not in p.parts)
    hashes={str(p.relative_to(ROOT)):core.fingerprint(p) for p in sorted(paths)}
    notices=ROOT/'.runtime/globe-notices';notices.mkdir(exist_ok=True)
    dependencies=[]
    for wheel in sorted((ROOT/'.runtime/wheels').glob('*.whl')):
        dependencies.append({'build_archive':wheel.name,'sha256':core.fingerprint(wheel)})
        with zipfile.ZipFile(wheel) as z:
            for name in z.namelist():
                if not name.endswith('/') and '.dist-info/' in name and any(v in name.lower() for v in ('license','copying','notice')):
                    dst=notices/wheel.stem/name;dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(z.read(name))
    core.save_json(notices/'build-inputs.json',dependencies)
    (notices/'说明.txt').write_text('内部测试版。Qt动态链接，依赖许可证见子目录。FFmpeg由imageio-ffmpeg提供，含GPL组件；对外分发前完成源码与许可证义务和干净机器验收。\nFFmpeg: https://github.com/BtbN/FFmpeg-Builds\nQt: https://code.qt.io/qt/pyside-setup.git\n',encoding='utf-8')
    build=ROOT/'build/globe'/__version__;dist=ROOT/'dist/globe'/__version__
    args=[str(ROOT/'globe_entry.py'),'--name','EarthPeopleLogGlobe','--onedir','--windowed','--clean','--noconfirm',
          '--icon',str(ROOT/'globe_app/assets/app-icon.ico'),'--paths',str(ROOT/'.runtime/python'),'--paths',str(ROOT),
          '--distpath',str(dist),'--workpath',str(build),'--specpath',str(build),
          '--collect-all','av','--collect-all','imageio_ffmpeg','--add-data',str(ROOT/'globe_app/assets')+';globe_app/assets',
          '--add-data',str(notices)+';licenses']
    for name in ('ne_110m_land.geojson','locations.json','locations-source.json','NOTICE.md','hands'):
        args+=['--add-data',str(ROOT/'pipeline/assets'/name)+';pipeline/assets'+('/hands' if name=='hands' else '')]
    for name in ('studio','yt_dlp','tkinter','numpy','matplotlib','IPython','pytest','PyQt5','PyQt6'):
        args+=['--exclude-module',name]
    PyInstaller.__main__.run(args)
    assert hashes=={str(p.relative_to(ROOT)):core.fingerprint(p) for p in sorted(paths)},'Source changed during build'
    folder=dist/'EarthPeopleLogGlobe'
    assert not (folder/'_internal/pipeline/assets/mascots').exists()
    core.save_json(folder/'build-manifest.json',{'product':'EarthPeopleLogGlobe','version':__version__,'built_at':core.now(),
        'exe_sha256':core.fingerprint(folder/'EarthPeopleLogGlobe.exe'),'source_hashes':hashes,'build_inputs':dependencies,
        'excluded':['studio','avatar runtime','mascot assets','yt_dlp']})
    print(folder)
