"""本轮可复核的请求准备／编码后逐帧验收；不启用摄像头。"""
from pathlib import Path
import sys,json,hashlib
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'.runtime/python'),str(ROOT)]
HERE=Path(__file__).resolve().parent
DEST=ROOT/'工作素材/虚拟形象/20261021_C动作库首版'

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

if sys.argv[1]=='prepare':
    HERE.joinpath('all-request.json').write_text(json.dumps(dict(destination=str(DEST),action='all',width=480,fps=24,turn=False),ensure_ascii=False),encoding='utf-8')
    HERE.joinpath('ledger-before.sha256').write_text(digest(ROOT/'state/score-ledger.json'))
    live=HERE/'frozen-live';live.mkdir(exist_ok=True)
    import shutil
    for name in ('portrait.jpg','pose.jpg'):shutil.copy2(ROOT/'state/verification/2026-10-21-avatar-live'/name,live/name)
else:
    import av,numpy as np
    from PIL import Image,ImageDraw,ImageFont
    from avatar_app.actions import ACTION_ORDER,ACTION_NAMES
    folder=sorted(DEST.iterdir())[-1]
    details={};selected={}
    for name in ('角色透明.mov','棋盘预览.mp4'):
        with av.open(str(folder/name)) as video:
            stream=video.streams.video[0];total=0;holes=0
            targets={round((i*2.5+1.25)*24):key for i,key in enumerate(ACTION_ORDER)}
            for index,frame in enumerate(video.decode(video=0)):
                array=frame.to_ndarray(format='rgba' if name.endswith('mov') else 'rgb24')
                if name.endswith('mov'):
                    if int(array[152:160,234:248,3].min())<240:holes+=1
                    assert array[0,0,3]==0
                elif index in targets:selected[targets[index]]=Image.fromarray(array)
                total+=1
            assert total==660,(name,total)
            assert holes==0,(name,holes)
            details[name]={'frames':total,'size':[stream.width,stream.height],'fps':str(stream.average_rate),
                'codec':stream.codec_context.name,'mouth_face_holes':holes,'sha256':digest(folder/name)}
    font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',20)
    board=Image.new('RGB',(960,4*516),'#18252b');draw=ImageDraw.Draw(board)
    for i,key in enumerate(ACTION_ORDER):
        x=i%3*320;y=i//3*516
        board.paste(selected[key].resize((320,480)),(x,y+36))
        draw.text((x+12,y+5),ACTION_NAMES[key],font=font,fill='white')
    board.save(HERE/'final-contact.png');board.save(DEST/'动作一览.png')
    (DEST/'先看这里.txt').write_text('棋盘预览.mp4用于观看动作；角色透明.mov用于剪映上层叠加。\n合集静音，每2.5秒一个动作，共27.5秒。顺序：'+ '、'.join(ACTION_NAMES.values())+'。\n评分待评，仅为技术演示，不对应新闻，不记账。\n',encoding='utf-8')
    manifest=json.loads((ROOT/'dist/avatar/0.3.0/EarthPeopleLogAvatar/build-manifest.json').read_text(encoding='utf-8'))
    assert all(digest(ROOT/path)==sha for path,sha in manifest['source_hashes'].items())
    globe=json.loads((ROOT/'dist/globe/0.2.0/EarthPeopleLogGlobe/build-manifest.json').read_text(encoding='utf-8'))
    assert all(digest(ROOT/path)==sha for path,sha in globe['source_hashes'].items())
    assert digest(ROOT/'state/score-ledger.json')==HERE.joinpath('ledger-before.sha256').read_text()
    report={'sample_folder':str(folder),'encoded_videos':details,'avatar_source_hash_match':True,
        'globe_source_unchanged':True,'ledger_unchanged':True,'camera_started':False,
        'boundaries':['真实摄像头和直播软件未实测','系统全局热键仅模拟注册冲突／消息分发检查','不是完整Live2D模型']}
    HERE.joinpath('verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
