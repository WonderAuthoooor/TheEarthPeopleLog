"""任务编排与流式媒体编码；后端可替换，成品须有完成清单。"""
from pathlib import Path
import json,os,traceback
from .jobs import Jobs
from .models import digest,atomic_json

def encode(files,folder,fps,cancel,progress):
    import av,numpy as np
    from PIL import Image,ImageDraw
    folder=Path(folder);containers=[]
    try:
        with Image.open(files[0]) as first:width,height=first.size
        outputs=[]
        for name,codec,pix,options in (('角色透明.partial.mov','prores_ks','yuva444p10le',{'profile':'4','alpha_bits':'16'}),
                                      ('动作预览.partial.mp4','libx264','yuv420p',{'crf':'20','preset':'fast'})):
            c=av.open(str(folder/name),'w');containers.append(c)
            s=c.add_stream(codec,rate=fps);s.width=width;s.height=height;s.pix_fmt=pix;s.options=options
            outputs.append((c,s))
        background=Image.new('RGBA',(width,height),'#293139');draw=ImageDraw.Draw(background)
        for y in range(0,height,24):
            for x in range(0,width,24):
                if (x//24+y//24)%2:draw.rectangle((x,y,x+23,y+23),fill='#343d45')
        for i,path in enumerate(files):
            if cancel.is_set():raise InterruptedError('已取消媒体编码。')
            with Image.open(path) as source:image=source.convert('RGBA')
            if image.size!=(width,height):raise ValueError('帧尺寸不一致。')
            preview=background.copy();preview.alpha_composite(image)
            for (container,stream),picture,format in zip(outputs,(image,preview.convert('RGB')),('rgba','rgb24')):
                frame=av.VideoFrame.from_ndarray(np.asarray(picture),format=format);frame.pts=i
                for packet in stream.encode(frame):container.mux(packet)
            progress(85+round((i+1)/len(files)*14))
        for container,stream in outputs:
            for packet in stream.encode():container.mux(packet)
            container.close()
        containers.clear()
        if cancel.is_set():raise InterruptedError('已取消。')
        # 编码后真实解码，确认帧数和透明通道，没有通过仅凭文件存在判断成功。
        for name in ('角色透明.partial.mov','动作预览.partial.mp4'):
            with av.open(str(folder/name)) as c:
                count=0
                for frame in c.decode(video=0):
                    if cancel.is_set():raise InterruptedError('已取消成品检查。')
                    if name.endswith('mov'):
                        alpha=frame.to_ndarray(format='rgba')[:,:,3]
                        if alpha.min()>0 or alpha.max()<200:raise ValueError('透明通道检查失败。')
                    count+=1
                if count!=len(files):raise ValueError('编码后帧数不完整。')
        os.replace(folder/'角色透明.partial.mov',folder/'角色透明.mov')
        os.replace(folder/'动作预览.partial.mp4',folder/'动作预览.mp4')
        with Image.open(files[len(files)//2]) as image:image.save(folder/'姿势预览.png')
    finally:
        for c in containers:
            try:c.close()
            except Exception:pass

class RenderService:
    def __init__(self,workspace,backend):self.jobs=Jobs(workspace);self.workspace=Path(workspace);self.backend=backend

    def run(self,ident,cancel,progress=lambda _:None):
        spec=self.jobs.claim(ident)
        folder=self.workspace/'jobs'/ident
        try:
            folder.mkdir(parents=True,exist_ok=False)
            model=self.workspace/'models'/(spec.model_sha256+'.vrm')
            info=json.loads(model.with_suffix('.json').read_text(encoding='utf-8'))
            if digest(model)!=spec.model_sha256:raise ValueError('模型被修改或损坏。')
            sample_sha=json.loads((Path(__file__).parent/'assets/runtime-lock.json').read_text(encoding='utf-8'))['sample']['sha256']
            request=spec.to_dict()|{'model':str(model.resolve()),'sample':spec.model_sha256==sample_sha}
            atomic_json(folder/'request.json',request)
            def update(value):self.jobs.progress(ident,value);progress(value)
            if cancel.is_set():raise InterruptedError('任务开始前已取消。')
            files=self.backend.render(request,folder,cancel,update)
            encode(files,folder,spec.fps,cancel,update)
            if cancel.is_set():raise InterruptedError('已取消。')
            atomic_json(folder/'model-metadata.json',info)
            credit=info['metadata'].get('copyrightInformation',info['metadata'].get('author',''))
            (folder/'使用说明.txt').write_text('角色透明.mov用于剪映上层；动作预览.mp4为棋盘预览，不用于透明合成。\n视频静音，无逐字口型／直播信号。scene.blend含本次模型与烘焙动作，原始VRM未修改。\n'+
                ('官方技术测试模型，不是C角色或正式新闻成片。\n' if request['sample'] else '')+
                '模型：'+info['name']+'\n署名：'+str(credit)+'\n使用范围以model-metadata.json、源模型和来源约定为准。\n',encoding='utf-8')
            metadata={'schema':1,'job_id':ident,'model':info['name'],'model_sha256':spec.model_sha256,
                'action':spec.action,'frames':len(files),'fps':spec.fps,'size':[spec.width,spec.width*3//2],
                'credit':info['metadata'].get('copyrightInformation',info['metadata'].get('author','')),
                'sample_only':request['sample'],'output_audio':False,'score_ledger_written':False,
                'files':{name:digest(folder/name) for name in ('角色透明.mov','动作预览.mp4','姿势预览.png','scene.blend')}}
            atomic_json(folder/'complete.json',metadata)
            self.jobs.finish(ident,'complete');progress(100)
            return folder
        except BaseException as exc:
            if folder.exists():
                (folder/'error.txt').write_text(traceback.format_exc(),encoding='utf-8')
                (folder/'complete.json').unlink(missing_ok=True)
            self.jobs.finish(ident,'cancelled' if isinstance(exc,InterruptedError) else 'failed',str(exc))
            raise

    def completed_folder(self,ident):
        if self.jobs.get(ident)['status']!='complete':raise ValueError('任务尚未完成。')
        folder=self.workspace/'jobs'/ident
        record=json.loads((folder/'complete.json').read_text(encoding='utf-8'))
        if record['job_id']!=ident or set(record['files'])!={'角色透明.mov','动作预览.mp4','姿势预览.png','scene.blend'}:
            raise ValueError('成品清单无效。')
        if any(digest(folder/name)!=sha for name,sha in record['files'].items()):raise ValueError('导出文件损坏，不能作为完整成品使用。')
        return folder
