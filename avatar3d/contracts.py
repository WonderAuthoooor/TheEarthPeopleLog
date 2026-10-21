"""版本化、与Blender和Qt无关的渲染请求。"""
from dataclasses import dataclass,asdict
import math

SCHEMA=1
ACTIONS={'neutral':'自然站姿','bend':'屈肘讲解','wave':'挥手','hold':'持牌姿势','turntable':'三视角检查'}

@dataclass(frozen=True)
class RenderSpec:
    model_sha256:str
    action:str='neutral'
    duration:float=3
    width:int=480
    fps:int=24
    azimuth:float=0
    schema:int=SCHEMA

    def validate(self):
        if self.schema!=SCHEMA:raise ValueError('请求版本不支持，请使用相应版本转换器。')
        if len(self.model_sha256)!=64 or any(c not in '0123456789abcdef' for c in self.model_sha256):raise ValueError('模型标识无效。')
        if self.action not in ACTIONS:raise ValueError('动作不存在。')
        if self.width not in (320,480,720,1080) or self.fps not in (12,24,30):raise ValueError('不支持的尺寸／帧率。')
        if not isinstance(self.duration,(int,float)) or not math.isfinite(self.duration) or not .5<=self.duration<=30:raise ValueError('时长须为0.5—30秒。')
        if not isinstance(self.azimuth,(int,float)) or not math.isfinite(self.azimuth) or not -180<=self.azimuth<=180:raise ValueError('视角超出范围。')
        return self

    def to_dict(self):return asdict(self.validate())

    @classmethod
    def from_dict(cls,value):return cls(**value).validate()
