"""在仓库根目录执行；复核本轮GUI真实输出与最终构建哈希。"""
from pathlib import Path
import sys,json,shutil
ROOT=Path.cwd();sys.path[:0]=[str(ROOT/'.runtime/python'),str(ROOT)]
import av
from avatar3d.models import digest,atomic_json
base=ROOT/'.runtime/avatar3d-tests/speech-ui-017'
evidence=ROOT/'state/verification/2026-10-24-speech-ui-017'
result=[]
for kind in ('source','frozen'):
    raw=base/(kind+'-result')/'project-gui-result.json'
    record=json.loads(raw.read_text(encoding='utf-8'))
    assert record['error']=='' and record['steps']==5,record
    outputs=[json.loads((Path(p)/'complete.json').read_text(encoding='utf-8')) for p in record['outputs']]
    assert len(outputs[0]['segments'])==1
    assert outputs[1]['segments'][0]['reused'] and not outputs[1]['segments'][1]['reused']
    assert all(s['reused'] for s in outputs[2]['segments'])
    assert outputs[2]['segments'][0]['id']==outputs[1]['segments'][1]['id']
    jobs=[]
    for segment in outputs[1]['segments']:
        folder=Path(segment['folder'])
        complete=json.loads((folder/'complete.json').read_text(encoding='utf-8'))
        assert all(digest(folder/name)==sha for name,sha in complete['files'].items())
        count=0
        with av.open(str(folder/'角色透明.mov')) as media:
            for frame in media.decode(video=0):
                assert abs(float(frame.pts*frame.time_base)-count/30)<1e-6
                alpha=frame.to_ndarray(format='rgba')[:,:,3]
                assert alpha.min()==0 and alpha.max()>245
                count+=1
        assert count==15
        jobs.append({'id':segment['job_id'],'frames':count,'fps':30,'alpha_pts_hashes':True})
    shutil.copyfile(raw,evidence/(kind+'-gui.json'))
    shutil.copyfile(base/(kind+'-result')/'window.png',evidence/(kind+'-layout.png'))
    result.append({'kind':kind,'jobs':jobs,'selected_then_all_then_reorder':True})
bundle=ROOT/'dist/avatar3d/0.1.7/EarthPeopleLogAvatar3D'
manifest=json.loads((bundle/'build-manifest.json').read_text(encoding='utf-8'))
assert manifest['version']=='0.1.7' and digest(bundle/'EarthPeopleLogAvatar3D.exe')==manifest['exe_sha256']
assert all(digest(ROOT/path)==sha for path,sha in manifest['source_hashes'].items())
shutil.copyfile(bundle/'build-manifest.json',evidence/'build-manifest.json')
atomic_json(evidence/'verified.json',{'gui':result,'build_hashes_match':True,
            'note':'合成测试音；原生浏览器和剪映人工验证未进行。'})
print('verified source/frozen 4 real C clips, build hashes and incremental UI workflow')
