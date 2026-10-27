"""生成30秒三动作排练及可编辑母版；不改模型或Warudo，不更新桌面入口。"""
from pathlib import Path
import sys,json,threading,argparse
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'.runtime/python'),str(ROOT)]
from avatar3d.backend import Runtime,BlenderBackend
from avatar3d.models import digest,atomic_json,inspect_vrm
from avatar3d.contracts import RenderSpec
from avatar3d.service import encode
from avatar3d.rehearsal import DEFAULT,validate

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('model','runtime','output'):parser.add_argument('--'+key,type=Path,required=True)
    parser.add_argument('--plan',type=Path);parser.add_argument('--keyframes-only',action='store_true');args=parser.parse_args()
    plan=validate(json.loads(args.plan.read_text(encoding='utf-8')) if args.plan else DEFAULT)
    info=inspect_vrm(args.model);out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    request=RenderSpec(info['sha256'],'idle',plan['duration'],320,30).to_dict()|{'model':str(args.model.resolve()),'rehearsal':plan}
    if args.keyframes_only:
        times={0,plan['duration']-1/30}
        for clip in plan['gestures']:
            times.update((clip['start'],clip['start']+clip['duration']/2,clip['start']+clip['duration']))
        request['rehearsal_render_frames']=sorted({min(round(t*30),round(plan['duration']*30)-1) for t in times})
    atomic_json(out/'request.json',request);cancel=threading.Event()
    frames=BlenderBackend(Runtime.load(args.runtime)).render(request,out,cancel,lambda n:print(n,flush=True),timeout=3600)
    if not args.keyframes_only:encode(frames,out,30,cancel,lambda n:None)
    checks=json.loads((out/'rehearsal-checks.json').read_text(encoding='utf-8'))
    if max(x['unmasked_error_radians'] for x in checks)>1e-4:raise ValueError('手势影响了遮罩外骨骼。')
    for name in ('request.json','scene.blend','rehearsal-checks.json')+(() if args.keyframes_only else ('角色透明.mov','动作预览.mp4')):
        if not (out/name).is_file():raise ValueError('缺少排练成品：'+name)
    content=''.join(f'<figure><img width="240" src="frames/{p.name}"><figcaption>{int(p.stem)/30:.2f}秒</figcaption></figure>' for p in frames) if args.keyframes_only else '<video controls loop src="动作预览.mp4"></video>'
    (out/'预览.html').write_text('<meta charset="utf-8"><title>C三动作连续排练</title><style>body{background:#172129;color:#eee;font:18px sans-serif;margin:32px}video{height:75vh;max-width:100%}main{display:flex;flex-wrap:wrap}figure{margin:12px}img{background:#34434b}</style><h1>C角色 · 连续排练母版</h1><p>仅离线混合，不是摄像头跟随测试。'+('下方是关键姿态图；900帧母版已保存，尚未渲染整段视频。' if args.keyframes_only else '完整30fps无声视频。')+'</p><main>'+content+'</main>',encoding='utf-8')
    atomic_json(out/'rehearsal-complete.json',{'schema':1,'baked_frames':len(checks),'rendered_frames':len(frames),'video_rendered':not args.keyframes_only,'fps':30,'model_sha256':info['sha256'],
        'max_step_degrees':max(x['max_step_degrees'] for x in checks),'unmasked_error_radians':max(x['unmasked_error_radians'] for x in checks),
        'files':{p.relative_to(out).as_posix():digest(p) for p in [*out.iterdir(),*frames] if p.is_file() and p.suffix in ('.png','.mov','.mp4','.blend','.json','.html')},
        'warudo_mixing':'not tested','clothing_clipping':'deferred T035'})
    print('COMPLETE',out,flush=True)
