"""可复现的头身分层与局部五官驱动，不依赖地球动画。"""
from pathlib import Path
import json
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from .actions import pose_at
from .action_art import ActionArt

ASSETS = Path(__file__).parent / "assets" / "c-v01"


def soft_mask(size, feather=7):
    mask = Image.new("L", size)
    ImageDraw.Draw(mask).rounded_rectangle((2, 2, size[0]-3, size[1]-3), radius=14, fill=255)
    return mask.filter(ImageFilter.GaussianBlur(feather))


class Rig:
    def __init__(self, assets=ASSETS, scale=1.0):
        self.config = json.loads((assets / "model.json").read_text(encoding="utf-8"))
        self.scale = scale
        self.canvas = (round(1024*scale),round(1536*scale))
        def resized(image):
            return image.resize(self.canvas,Image.Resampling.LANCZOS)
        def scaled(box):
            return tuple(round(v*scale) for v in box)
        self.body = Image.open(assets / self.config["body"]).convert("RGBA")
        self.head = Image.open(assets / self.config["head"]).convert("RGBA")
        blink = Image.open(assets / self.config["blink"]).convert("RGBA")
        self.eyes = []
        for eye in self.config["eyes"]:
            box = scaled(eye["target"])
            size = (box[2]-box[0], box[3]-box[1])
            self.eyes.append((box, blink.crop(eye["source"]).resize(size, Image.Resampling.LANCZOS), soft_mask(size,max(1,7*scale))))
        box = self.config["mouth"]
        self.mouth = Image.open(assets / self.config["talk"]).convert("RGBA").crop(box)
        self.mouth_box = scaled(box)
        self.mouth = self.mouth.resize((self.mouth_box[2]-self.mouth_box[0],self.mouth_box[3]-self.mouth_box[1]),Image.Resampling.LANCZOS)
        self.mouth_mask = soft_mask(self.mouth.size,max(1,6*scale))
        self.body,self.head = resized(self.body),resized(self.head)
        self.art=ActionArt(scale)
        self.body=self.art.body(pose_at('idle'))

    @staticmethod
    def blink_at(t):
        # 周期由固定表定义，不随机；预览与导出一致。
        centers = (1.45, 4.8, 8.2, 11.6)
        phase = t % 14
        return max(max(0.0, 1-abs(phase-c)/0.105) for c in centers)

    def frame(self, t, size=(720, 1080), mouth=0.0, turn=0.0, blink=None, breath=True,
              blink_left=None,blink_right=None,pitch=0.0,roll=0.0,lean=0.0,pose=None,score='待评'):
        head = self.head.copy()
        speech=self.mouth
        if pose is not None:
            head,speech=self.art.expression(head,pose.expressions,self.mouth)
            roll+=pose.roll;lean+=pose.lean
            mouth=max(mouth,pose.mouth_floor)
        blink = self.blink_at(t) if blink is None else min(1, max(0, blink))
        for (box,patch,mask),closure in zip(self.eyes,(blink_left,blink_right)):
            closure = blink if closure is None else min(1,max(0,closure))
            if pose is not None:closure=max(closure,pose.blink_floor)
            if closure > 0:
                head.paste(patch,box[:2],mask.point(lambda v:int(v*closure)))
        if mouth > 0.08:
            # 音量只控制开合程度，不声称逐字／音素对齐。
            box = self.mouth_box
            openness = min(1.0, max(0.0, mouth))
            h = speech.height
            # 压缩口腔的目标区间；上下皮肤带连接到固定边缘。
            # 原先用同一逆缩放公式外推上下边界，低开合时会读到图外，
            # 得到透明黑色横条。此处所有源坐标都在原图内且单调。
            mesh = []
            source_knots = (0,round(h*.24),round(h*.71),h)
            center = h*.47
            compression = .4+.6*openness
            target_knots = (0,round(center+(source_knots[1]-center)*compression),
                            round(center+(source_knots[2]-center)*compression),h)
            for y0,y1,sy0,sy1 in zip(target_knots,target_knots[1:],source_knots,source_knots[1:]):
                mesh.append(((0, y0, speech.width, y1), (0, sy0, 0, sy1, speech.width, sy1, speech.width, sy0)))
            patch = speech.transform(speech.size, Image.Transform.MESH, mesh, Image.Resampling.BICUBIC)
            head.paste(patch, box[:2], self.mouth_mask)
        # 表情只更换面部颜色，脸部的覆盖范围由基础头部决定。
        head.putalpha(self.head.getchannel("A"))
        # 只有小幅伪透视。新侧面的真实遮挡细节未制作。
        yaw = min(1.0, max(-1.0, turn))
        if abs(yaw) > .001:
            mesh = []
            for yi in range(16):
                y,y1 = round(yi*self.canvas[1]/16),round((yi+1)*self.canvas[1]/16)
                for xi in range(16):
                    x,x1 = round(xi*self.canvas[0]/16),round((xi+1)*self.canvas[0]/16)
                    def src(px, py):
                        influence = max(0, 1-((py/self.scale-470)/420)**2)
                        return (px-yaw*20*self.scale*influence*(1-((px/self.scale-512)/550)**2), py+yaw*(px-512*self.scale)*.012*influence)
                    mesh.append(((x,y,x1,y1), sum((src(a,b) for a,b in ((x,y),(x,y1),(x1,y1),(x1,y))), ())))
            head = head.transform(head.size, Image.Transform.MESH, mesh, Image.Resampling.BICUBIC)
        body = self.art.body(pose,score) if pose is not None else self.body.copy()
        inhale = math.sin(t*2*math.pi/4.2) if breath else 0
        body = body.transform(body.size, Image.Transform.AFFINE, (1, 0, 0, 0, 1-.0025*inhale, 3.4*inhale*self.scale), Image.Resampling.BICUBIC)
        head = head.resize(tuple(round(v*self.config["head_scale"]) for v in self.canvas), Image.Resampling.LANCZOS)
        head = head.rotate(-yaw*1.25-min(1,max(-1,roll))*5, Image.Resampling.BICUBIC, center=(256*self.scale,398*self.scale))
        offset = self.config["head_offset"]
        # 点头仅作几像素位移；没有把单张正面图称作真正三维俯仰。
        body.alpha_composite(head, (round((offset[0]+yaw*2)*self.scale),
                                   round((offset[1]-inhale*1.5+min(1,max(-1,pitch))*4)*self.scale)))
        if abs(lean)>.001:
            body = body.rotate(-min(1,max(-1,lean))*2.5,Image.Resampling.BICUBIC,
                               center=(512*self.scale,1160*self.scale))
        return body.resize(tuple(size), Image.Resampling.LANCZOS)


class Envelope:
    """从本地音频解码单声道RMS包络；静音闭嘴，最多180秒。"""
    def __init__(self, path, fps=30):
        import av
        self.fps = fps
        samples = []
        count = 0
        with av.open(str(path)) as container:
            if not container.streams.audio:
                raise ValueError("所选文件没有音轨。")
            resampler = av.AudioResampler(format="fltp", layout="mono", rate=16000)
            for frame in container.decode(audio=0):
                for out in resampler.resample(frame):
                    a = out.to_ndarray().ravel()
                    count += len(a)
                    if count > 16000*180:
                        raise ValueError("试验版一次处理最多180秒音频，请先截取口播片段。")
                    samples.append(a)
            for out in resampler.resample(None):
                samples.append(out.to_ndarray().ravel())
        if not samples:
            raise ValueError("音频为空或不能解码。")
        data = np.concatenate(samples)
        self.duration = len(data)/16000
        n = math.ceil(self.duration*fps)
        rms = np.array([float(np.sqrt(np.mean(data[round(i*16000/fps):min(len(data),round((i+1)*16000/fps))]**2))) for i in range(n)])
        peak = max(.015, float(np.percentile(rms, 95)))
        values = np.clip((rms-.004)/(peak-.004), 0, 1)
        last = 0.0
        self.values = []
        for v in values:
            last += (float(v)-last)*(.8 if v > last else .55)
            self.values.append(last if v > .025 else 0.0)

    def at(self, t):
        i = int(t*self.fps)
        return self.values[i] if 0 <= i < len(self.values) else 0.0


def checker(image):
    bg = Image.new("RGBA", image.size, "#293139")
    draw = ImageDraw.Draw(bg)
    for y in range(0, image.height, 28):
        for x in range(0, image.width, 28):
            if (x//28+y//28)%2:
                draw.rectangle((x,y,x+27,y+27), fill="#343d45")
    bg.alpha_composite(image)
    return bg.convert("RGB")
