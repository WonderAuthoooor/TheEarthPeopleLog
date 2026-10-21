"""Independent packaged city GUI/worker: no studio, avatar or scoring dependency."""
from pathlib import Path
import os,sys,time,json,subprocess
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'.runtime/python'));sys.path.insert(0,str(ROOT))
from pipeline import core
from globe_app import __version__
folder=ROOT/'.runtime'/('globe-independent-'+str(time.time_ns()));folder.mkdir()
app=ROOT/'dist/globe'/__version__/'EarthPeopleLogGlobe';exe=app/'EarthPeopleLogGlobe.exe'
assert not (app/'_internal/pipeline/assets/mascots').exists()
assert not (app/'_internal/studio').exists()
env=dict(os.environ);env['PATH']=str(Path(env['WINDIR'])/'System32')+os.pathsep+env['WINDIR']
for key in ('PYTHONHOME','PYTHONPATH','VIRTUAL_ENV','EARTHLOG_PYTHON','EARTHLOG_FFMPEG','QT_PLUGIN_PATH'):env.pop(key,None)

def call(args,success=True):
    p=subprocess.run([str(exe),*map(str,args)],env=env,creationflags=subprocess.CREATE_NO_WINDOW,timeout=130)
    assert (p.returncode==0)==success,p.returncode

ledger=core.fingerprint(ROOT/'state/score-ledger.json')
call(['--workspace',folder/'workspace','--check-export',folder/'dialog.json'])
d=json.loads((folder/'dialog.json').read_text(encoding='utf-8'))
assert d['output'] and not d['avatar_fields'] and not d['coordinate_fields'] and d['city_count']>=1252,d
assert d['config']['target']['name'].startswith('日本 · 东京 ·'),d
assert d['config']['origin']['name'].endswith('伦敦'),d
assert not any(d['config']['text_options'].values()),d
assert d['config']['style']=='rubberhose',d
assert not (folder/'workspace/workspace.sqlite').exists()
outputs=[d['output']];cases={}
for mode in ('intro','default-hand','no-hand','labelled','classic','cancel','legacy'):
    run=folder/mode;run.mkdir()
    config={'mode':'intro','style':'rubberhose','width':320,'duration':1,'fps':12,'show_hand':mode!='no-hand',
            'target':{'name':'英国 · 伦敦 · 测试现场','city_name':'英国 · 伦敦','lat':51.5,'lon':-.12}}
    if mode=='classic':config.update(mode='transition',style='classic')
    if mode=='labelled':config.update(mode='transition',text_options={k:True for k in ('title','subtitle','status','location','nearby','footer')})
    if mode=='intro':config['hand']=str(app/'_internal/pipeline/assets/hands/robot.svg')
    if mode=='legacy':config['score_status']='pending';config['mascot']='not-installed.svg'
    request={'config':config,'output_root':str(run/'outputs'),'progress_file':str(run/'progress.json'),
             'result_file':str(run/'result.json'),'cancel_file':str(run/'cancel')}
    if mode=='cancel':(run/'cancel').touch()
    core.save_json(run/'request.json',request)
    call(['--animation',run/'request.json'],mode not in ('cancel','legacy'))
    result=json.loads((run/'result.json').read_text(encoding='utf-8'))
    if mode=='legacy':
        assert result['status']=='failed' and '旧版' in result['error'],result;continue
    if mode=='cancel':
        assert result['status']=='cancelled' and not list((run/'outputs').rglob('*.part.*'));continue
    out=Path(result['output']);outputs.append(str(out));cases[mode]=str(out);m=json.loads((out/'manifest.json').read_text(encoding='utf-8'))
    assert m['status']=='succeeded' and m['metadata']['width']==320
    assert abs(m['metadata']['duration']-1)<.1
    assert not any('mascot' in k or 'score' in k for k in m['config'])
    assert all(m['config']['text_options'].values()) if mode=='labelled' else not any(m['config']['text_options'].values())
    if mode in ('no-hand','labelled','classic'):assert not list((out/'components').iterdir())
    else:assert (out/'components/hand.svg').read_bytes()==(app/'_internal/pipeline/assets/hands'/('robot.svg' if mode=='intro' else 'rubber_glove.svg')).read_bytes()
assert core.fingerprint(ROOT/'state/score-ledger.json')==ledger
core.save_json(folder/'report.json',{'at':core.now(),'version':__version__,'outputs':outputs,'cases':cases,'checks':[
    'independent packaged GUI and QProcess actual city transition','1252 cities and separate detailed caption',
    'no coordinate/avatar/score UI fields','no studio or mascot assets packaged','intro hand replacement','bundled retro glove','retro camera export and classic fallback',
    'default text-free output and opt-in labelled output','intro without hand assets','explicit legacy config error','cancel removes partial video','formal ledger unchanged',
    'no studio database created','development paths removed']})
print(folder/'report.json')
