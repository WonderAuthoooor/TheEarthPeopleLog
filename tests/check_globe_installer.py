"""Isolated standalone globe installation/uninstallation, preserving user files."""
from pathlib import Path
import sys,subprocess,time
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'.runtime/python'));sys.path.insert(0,str(ROOT))
from pipeline import core
from globe_app import __version__
if __name__=='__main__':
    parent=ROOT/'.runtime'/('installer-qa-globe-'+__version__);app=parent/'app'
    assert app.resolve().is_relative_to(parent.resolve())
    installer=ROOT/'dist'/f'EarthPeopleLogGlobe-{__version__}-Setup.exe'
    subprocess.run([str(installer),'/S','/TEST','/D='+str(app)],check=True,timeout=120)
    exe=app/'EarthPeopleLogGlobe.exe';assert exe.exists() and (app/'test-install.marker').exists()
    assert core.fingerprint(exe)==core.fingerprint(ROOT/'dist/globe'/__version__/'EarthPeopleLogGlobe/EarthPeopleLogGlobe.exe'), 'Installed executable differs from final build'
    subprocess.run([str(exe),'--doctor',str(parent/'doctor.json')],check=True,timeout=30)
    doctor=__import__('json').loads((parent/'doctor.json').read_text(encoding='utf-8'))
    assert doctor['product']=='EarthPeopleLogGlobe' and doctor['frozen'] and not doctor['avatar_required']
    sentinel=app/'用户素材/保留.txt';sentinel.parent.mkdir(exist_ok=True);sentinel.write_text('keep',encoding='utf-8')
    subprocess.run([str(app/'Uninstall.exe'),'/S'],check=True,timeout=60)
    deadline=time.monotonic()+30
    while exe.exists() and time.monotonic()<deadline:time.sleep(.1)
    assert not exe.exists() and sentinel.read_text(encoding='utf-8')=='keep'
    core.save_json(parent/'report.json',{'at':core.now(),'version':__version__,'installer_sha256':core.fingerprint(installer),
        'checks':['project-local silent install','independent installed EXE doctor and final-build hash','uninstall preserves user files'],
        'test_mode':'no registry or system shortcut writes'})
    print(parent/'report.json')
