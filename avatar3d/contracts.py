"""版本化、与Blender和Qt无关的渲染请求。"""
from dataclasses import dataclass,asdict,fields
import math

SCHEMA=1
ACTIONS={'neutral':'自然站姿','idle':'轻缓待机（循环）','explain':'单手讲解','bend':'屈肘讲解（技术姿态）','wave':'挥手','hold':'持牌姿势','turntable':'三视角检查'}

@dataclass(frozen=True)
class RenderSpec:
    model_sha256:str
    action:str='neutral'
    duration:float=3
    width:int=480
    fps:int=24
    azimuth:float=0
    schema:int=SCHEMA
    audio_sha256:str|None=None
    framing:str='full'

    def validate(self):
        if self.schema not in (1,2):raise ValueError('请求版本不支持，请使用相应版本转换器。')
        if len(self.model_sha256)!=64 or any(c not in '0123456789abcdef' for c in self.model_sha256):raise ValueError('模型标识无效。')
        if self.action not in ACTIONS:raise ValueError('动作不存在。')
        if self.width not in (320,480,720,1080) or self.fps not in (12,24,30):raise ValueError('不支持的尺寸／帧率。')
        if not isinstance(self.duration,(int,float)) or not math.isfinite(self.duration) or not .5<=self.duration<=30:raise ValueError('时长须为0.5—30秒。')
        if not isinstance(self.azimuth,(int,float)) or not math.isfinite(self.azimuth) or not -180<=self.azimuth<=180:raise ValueError('视角超出范围。')
        if self.framing not in ('full','bust'):raise ValueError('构图无效。')
        if self.schema==1 and (self.audio_sha256 is not None or self.framing!='full'):raise ValueError('音频或半身构图需要第二版请求。')
        if self.audio_sha256 is not None:
            if not isinstance(self.audio_sha256,str) or len(self.audio_sha256)!=64 or any(c not in '0123456789abcdef' for c in self.audio_sha256):raise ValueError('音频标识无效。')
            if self.action not in ('idle','explain'):raise ValueError('口播请使用轻缓待机或单手讲解。')
        return self

    def to_dict(self):
        value=asdict(self.validate())
        if self.schema==1:
            value.pop('audio_sha256');value.pop('framing')
        return value

    @classmethod
    def from_dict(cls,value):return cls(**value).validate()

    @classmethod
    def from_request(cls,value):
        return cls.from_dict({field.name:value[field.name] for field in fields(cls) if field.name in value})
