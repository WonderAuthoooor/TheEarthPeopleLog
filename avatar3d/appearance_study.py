"""受控衣领对照配方。仅改变命名网格，不能套用于任意角色。"""
from dataclasses import dataclass
import math

REVISION = 'c-collar-v1'


@dataclass(frozen=True)
class Variant:
    key: str
    label: str
    meshes: tuple[str, ...]
    anchor: float
    scale: float
    repair_shoulders: bool = False
    face_strength: float = 0

    def transform(self, point):
        x, y, z = point
        if not all(math.isfinite(v) for v in (x, y, z, self.anchor, self.scale)):
            raise ValueError('坐标与配方必须为有限数。')
        if not 0 < self.scale <= 1:
            raise ValueError('本轮只支持缩短衣领。')
        return x, y, self.anchor + (z - self.anchor) * self.scale if z > self.anchor else z


VARIANTS = (
    Variant('A', '原版', (), 0, 1),
    Variant('B', '仅降低黑色内领', ('C_BlackHighNeck',), 1.445, .4),
    Variant('C', '仅降低外套立领', (
        'C_StandingCollar_-1', 'C_StandingCollar_1',
        'C_CollarTrim_-1', 'C_CollarTrim_1'), 1.405, .6),
)

VIEWS = (
    ('full', '全身正面', 0, False, 'idle'),
    ('front', '肩颈正面', 0, True, 'idle'),
    ('side', '肩颈侧面', 65, True, 'idle'),
    ('explain', '讲解时肩颈', 35, True, 'explain'),
)

SHOULDER_VARIANTS = (
    VARIANTS[0],
    Variant('D', '肩领接缝与袖色分界修复',
            ('C_BlackHighNeck', 'C_TailoredJacket'), 0, 1, True),
)
SHOULDER_VIEWS = (
    *VIEWS,
    ('other-side', '肩颈另一侧', -65, True, 'idle'),
    ('wave', '挥手抬臂全身', 0, False, 'wave'),
)

ROUND_VARIANTS = (
    Variant('A', '当前肩领修复版', (), 0, 1),
    Variant('E', '轻度圆润', ('Face',), 0, 1, face_strength=.7),
    Variant('F', '更圆润可爱', ('Face',), 0, 1, face_strength=1.2),
)
ROUND_VIEWS = (
    ('full', '全身比例', 0, False, 'idle'),
    ('front', '正面近景', 0, True, 'idle'),
    ('three-quarter', '三分之四', 35, True, 'idle'),
    ('profile', '侧面', 85, True, 'idle'),
    ('happy', '微笑表情', 0, True, 'happy'),
    ('blink-aa', '闭眼与张嘴', 0, True, 'blink_aa'),
)


def study_spec(name):
    if name == 'collar':
        return VARIANTS, VIEWS, REVISION
    if name == 'shoulder':
        return SHOULDER_VARIANTS, SHOULDER_VIEWS, 'c-shoulder-v3'
    if name == 'rounded':
        return ROUND_VARIANTS, ROUND_VIEWS, 'c-rounded-v2'
    raise ValueError('未知外观对照类型。')


def shoulder_underlayer(point):
    """扩大内搭肩颈过渡圈，保留领口高度与胸腹；坐标单位为米。"""
    x, y, z = point
    if not all(math.isfinite(v) for v in point):
        raise ValueError('无效内搭坐标。')
    influence = max(0., 1. - abs(z - 1.445) / .045)
    # 漏肤位于侧后方；前胸一侧保持原轮廓，避免整圈撑成宽领。
    rear = max(0., min(1., (y + .03) / .05))
    influence *= rear * rear * (3 - 2 * rear)
    return x * (1 + .90 * influence), y * (1 + .04 * influence), z
