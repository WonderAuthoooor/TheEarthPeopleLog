"""复核本轮真实交付；不等同于Warudo人工观感验收。"""
from pathlib import Path
import json,sys,shutil
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'.runtime/python'),str(ROOT)]
import av
from avatar3d.models import digest,atomic_json
from avatar3d.motion_exchange import verify_exchange
base=ROOT/'工作素材/虚拟形象/20261025_直播基础动作'
evidence=Path(__file__).parent
records=[]
delivery=json.loads((base/'delivery.json').read_text(encoding='utf-8'))
assert delivery['scenes_unchanged']
for item in delivery['actions']:
    action=item['action'];loop=action=='idle'
    folder=base/'离线动作-v002'/action
    complete=json.loads((folder/'complete.json').read_text(encoding='utf-8'))
    assert all(digest(folder/name)==sha for name,sha in complete['files'].items())
    counts={}
    for name in ('角色透明.mov','动作预览.mp4','browser-preview/preview.webm'):
        path=folder/name
        if not path.exists() and name.endswith('webm'):
            candidates=list((folder/'browser-preview').glob('*.webm'))
            assert len(candidates)==1,candidates
            path=candidates[0]
        count=0
        with av.open(str(path)) as media:
            for frame in media.decode(video=0):
                assert abs(float(frame.pts*frame.time_base)-count/30)<.0011
                if name.endswith('mov'):
                    alpha=frame.to_ndarray(format='rgba')[:,:,3]
                    assert alpha.min()==0 and alpha.max()>245
                count+=1
        assert count==90,(name,count)
        counts[name]=count
    exchange=base/'交换包'/action
    verify_exchange(exchange)
    roundtrip=json.loads((exchange/'roundtrip.json').read_text(encoding='utf-8'))
    assert roundtrip['passed'] and roundtrip['checked_frames']==(91 if loop else 90)
    build=base/'Warudo构建-v002'/action
    imported=json.loads((build/'unity-report.json').read_text(encoding='utf-8'))
    built=json.loads((build/'build-report.json').read_text(encoding='utf-8'))
    assert imported['passed'] and built['passed'] and imported['loop']==loop and built['loop']==loop
    assert imported['actionId']==action and built['actionId']==action
    assert abs(imported['actualDuration']-(3 if loop else 89/30))<1e-5
    assert imported['mappedBones']==54 and imported['frameRate']==30
    assert json.loads((build/'input-restored.json').read_text(encoding='utf-8'))['restored']
    installation=item['installation']
    assert digest(installation['installed_file'])==installation['sha256']==built['modSha256']
    assert digest(build/Path(installation['installed_file']).name)==built['modSha256']
    for src,name in ((exchange/'roundtrip.json','roundtrip'),(build/'unity-report.json','unity'),(build/'build-report.json','build'),(build/'input-restored.json','restored')):
        shutil.copyfile(src,evidence/(action+'-'+name+'.json'))
    shutil.copyfile(folder/'姿势预览.png',evidence/(action+'.png'))
    records.append({'action':action,'video_frames':counts,'fps':30,'loop':loop,'mod':built['modName'],'mapped_bones':imported['mappedBones'],'clip_seconds':imported['actualDuration'],'alpha_pts_hashes':True,'input_restored':True})
shutil.copyfile(base/'delivery.json',evidence/'delivery.json')
atomic_json(evidence/'verified.json',{'actions':records,'scenes_unchanged':True,'model_sha256':delivery['model_sha256'],'warudo_manual':'pending','camera_obs':'pending','desktop_rebuilt':False})
print(json.dumps(records,ensure_ascii=False))
