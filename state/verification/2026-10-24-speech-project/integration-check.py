from pathlib import Path
import sys,json,subprocess,os
ROOT=Path.cwd();sys.path[:0]=[str(ROOT/'.runtime/python'),str(ROOT)]
import numpy as np
import av
from avatar3d.audio_mouth import write_wav
from avatar3d.models import digest,atomic_json
base=ROOT/'.runtime/avatar3d-tests/speech-project-v1'
workspace=base/'workspace';project=workspace/'projects/demo.json'
evidence=ROOT/'state/verification/2026-10-24-speech-project'
(base/'text.txt').write_text('第一段测试。\n\n第二段测试。',encoding='utf-8')
(base/'edited.txt').write_text('第一段修改后的测试。',encoding='utf-8')
for name,freq in [('a',.15),('b',.18),('c',.22)]:
    n=8000 if name=='c' else 4000
    write_wav(base/(name+'.wav'),np.sin(np.arange(n)*freq)*.2,n/16000)
def cli(*args,fail=False):
    command=[sys.executable,'-X','utf8',str(ROOT/'scripts/avatar-speech-project.py'),
             '--workspace',str(workspace),'--project',str(project),*map(str,args)]
    r=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',timeout=600)
    with (base/'cli.log').open('a',encoding='utf-8') as f:f.write(str(args)+'\n'+r.stdout+r.stderr+'\n')
    if fail:assert r.returncode!=0;return r
    assert r.returncode==0,r.stderr
    return r.stdout
cli('init','--model',ROOT/'工作素材/虚拟形象/C角色/肩领修复-v004/D/C-character.vrm','--text',base/'text.txt','--width',320,'--fps',30)
ids=[s['id'] for s in json.loads(project.read_text(encoding='utf-8'))['segments']]
cli('bind','--segment',ids[0],'--audio',base/'a.wav')
cli('bind','--segment',ids[1],'--audio',base/'b.wav')
def run():
    output=Path(cli('render').strip().splitlines()[-1]);print(output,flush=True)
    return output,json.loads((output/'complete.json').read_text(encoding='utf-8'))
first,f=run()
same,s=run();assert all(r['reused'] for r in s['segments'])
cli('edit','--segment',ids[0],'--text',base/'edited.txt')
p=json.loads(cli('plan'));assert p['segments'][0]['status']=='stale_audio'
cli('render',fail=True)
cli('bind','--segment',ids[0],'--audio',base/'c.wav')
changed,c=run();assert not c['segments'][0]['reused'] and c['segments'][1]['reused']
assert c['segments'][0]['job_id']!=f['segments'][0]['job_id']
assert c['segments'][1]['job_id']==f['segments'][1]['job_id']
assert c['segments'][1]['start_frame']==21
cli('reorder',*reversed(ids));reordered,r=run()
assert all(s['reused'] for s in r['segments']) and r['segments'][1]['start_frame']==15
checks=[]
seen=set()
for record in [f,c]:
    for segment in record['segments']:
        if segment['job_id'] in seen:continue
        seen.add(segment['job_id']);folder=Path(segment['folder'])
        manifest=json.loads((folder/'complete.json').read_text(encoding='utf-8'))
        assert all(digest(folder/name)==sha for name,sha in manifest['files'].items())
        pts=[]
        with av.open(str(folder/'角色透明.mov')) as media:
            for frame in media.decode(video=0):
                alpha=frame.to_ndarray(format='rgba')[:,:,3]
                assert alpha.min()==0 and alpha.max()>245
                pts.append(float(frame.pts*frame.time_base))
        assert len(pts)==manifest['frames'] and all(abs(t-i/30)<1e-6 for i,t in enumerate(pts))
        checks.append({'job_id':segment['job_id'],'frames':len(pts),'fps':30,'alpha_pts_hashes':True})
# CLI编辑历史、增删和不覆盖保护；不再渲染。
cli('add','--text',base/'text.txt','--after',ids[0]);added=json.loads(cli('plan'))
new_id=next(row['id'] for row in added['segments'] if row['id'] not in ids)
assert len(added['segments'])==3 and not added['ready']
cli('remove','--segment',new_id);assert json.loads(cli('plan'))['ready']
assert len(list((project.parent/'revisions').glob('*.json')))>=5
cli('init','--model',ROOT/'avatar3d/assets/Seed-san.vrm','--text',base/'text.txt',fail=True)
from PySide6.QtCore import QCoreApplication,QLockFile
app=QCoreApplication([]);lock=QLockFile(str(workspace/'app.lock'));lock.setStaleLockTime(0)
assert lock.tryLock(100)
try:assert '工作区正被' in cli('plan',fail=True).stderr
finally:lock.unlock()
atomic_json(evidence/'integration.json',{'first':str(first),'repeated':str(same),'changed':str(changed),
           'reordered':str(reordered),'initial_jobs':[x['job_id'] for x in f['segments']],
           'changed_jobs':[x['job_id'] for x in c['segments']],'checks':checks,
           'stale_audio_blocked':True,'lock_rejected':True,'history_add_remove':True,
           'note':'合成测试音，非真实口播；实际C模型Blender及编码链路。'})
print('ALL PASSED',flush=True)
