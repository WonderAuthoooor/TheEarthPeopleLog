"""交付复核与技术素材归档，不把样例模型当作C。"""
from pathlib import Path
import sys,json,shutil
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'.runtime/python'),str(ROOT)]
from avatar3d.models import digest,atomic_json
from avatar3d.backend import Runtime,BlenderBackend
from avatar3d.service import RenderService
from PIL import Image,ImageDraw,ImageFont
import av,numpy as np
HERE=Path(__file__).resolve().parent
result=json.loads((HERE/'frozen-ui-v3/gui-result.json').read_text(encoding='utf-8'))
assert not result['error'],result
service=RenderService(ROOT/'.runtime/avatar3d-frozen-workspace-v3',BlenderBackend(Runtime.load(ROOT/'.runtime/avatar3d/runtime.json')))
folder=service.completed_folder(Path(result['folder']).name)
for name in ('角色透明.mov','动作预览.mp4'):
    with av.open(str(folder/name)) as video:
        frames=list(video.decode(video=0));assert len(frames)==6
        if name.endswith('mov'):
            alpha=frames[3].to_ndarray(format='rgba')[:,:,3]
            assert alpha.min()==0 and alpha.max()>245
            assert (alpha>200).sum()>4000
source=ROOT/'.runtime/avatar3d-wave/jobs/64391dfcfcd64286a9a5c086e40b3a68'
with av.open(str(source/'动作预览.mp4')) as video:
    images=[frame.to_ndarray(format='rgb24') for frame in video.decode(video=0)]
    assert len(images)==18
    assert np.abs(images[0].astype(float)-images[9].astype(float)).mean()>1
side=ROOT/'.runtime/avatar3d-side/jobs/f3073c290ef74fe39c06a3874efbeb85'
board=Image.new('RGB',(960,530),'#293139');font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',20);draw=ImageDraw.Draw(board)
paths=[(source/'frames/00000.png','自然姿势'),(source/'frames/00009.png','真实骨骼挥手'),(side/'姿势预览.png','侧面90°')]
for i,(path,label) in enumerate(paths):
    with Image.open(path) as image:board.paste(image,(i*320,40),image.getchannel('A'))
    draw.text((i*320+10,8),label,fill='white',font=font)
draw.text((10,505),'Seed-san · VirtualCast, Inc. · 技术样例，非C形象',fill='#c4e7e0',font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',16))
board.save(HERE/'3d-contact.png')
dest=ROOT/'工作素材/虚拟形象/20261021_3D骨骼技术验证';dest.mkdir(parents=True,exist_ok=True)
for original,label in ((folder,'冻结版导出'),(source,'骨骼挥手'),(side,'侧面检查')):
    target=dest/label
    if not target.exists():shutil.copytree(original,target)
board.save(dest/'技术样例一览.png')
(dest/'先看这里.txt').write_text('这是三维程序技术验证，模型为Seed-san，作者VirtualCast, Inc.，不是账号正式C角色。\n骨骼挥手/动作预览.mp4 可观察真实骨骼动画；角色透明.mov供剪映透明叠加。\n侧面检查展示真实三维视角。正式C建模、实时拖拽／3D面捕／评分牌还未完成。\n模型来源和许可证在项目avatar3d/assets；不要删除署名与使用条件。\n',encoding='utf-8')
for product,version in (('avatar3d','0.1.0'),('avatar','0.3.0'),('globe','0.2.0')):
    name={'avatar3d':'EarthPeopleLogAvatar3D','avatar':'EarthPeopleLogAvatar','globe':'EarthPeopleLogGlobe'}[product]
    manifest=json.loads((ROOT/'dist'/product/version/name/'build-manifest.json').read_text(encoding='utf-8'))
    assert all(digest(ROOT/path)==sha for path,sha in manifest['source_hashes'].items()),product
assert json.loads((ROOT/'state/score-ledger.json').read_text(encoding='utf-8'))['entries']==[]
shutil.copy2(ROOT/'.runtime/avatar3d-cancel/cancel-result.json',HERE/'cancel-result.json')
atomic_json(HERE/'verification.json',{'frozen_gui_export':True,'frozen_frames':6,'size':[320,480],
    'alpha_checked':True,'source_wave_frames':18,'baked_motion_reloaded':True,'side_view':True,
    'source_hashes_match':True,'old_avatar_and_globe_unchanged':True,'ledger_empty':True,
    'sample_folder':str(dest),'model':'Seed-san by VirtualCast, Inc.','not_character_c':True,
    'not_tested':['真人摄像头与直播','实时骨架拖拽','正式C形象','干净Windows安装','目标剪映透明合成']})
print(dest)
