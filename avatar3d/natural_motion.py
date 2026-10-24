"""无模型依赖的基础动作时间曲线；以比例而非骨段长度定义。"""
import math

REVISION = 'upper-body-v1'
ACTIONS = ('idle', 'explain')


def smooth(value):
    value = max(0.0, min(1.0, value))
    return value ** 3 * (value * (value * 6 - 15) + 10)


def sample(action, time, duration):
    if action not in ACTIONS or not math.isfinite(duration) or duration <= 0 or not math.isfinite(time):
        raise ValueError('基础动作或时间参数无效。')
    phase = max(0.0, min(1.0, time / duration))
    gesture = smooth(phase / .24) * smooth((1 - phase) / .28) if action == 'explain' else 0.0
    # 不改髋部位置，不在没有足部IK时伪造重心位移。
    breath = .5 - .5 * math.cos(math.tau * phase)
    sway = math.sin(math.tau * phase)
    blink = 0.0
    if duration >= 2:
        distance = abs(time - duration * .38)
        half_width = min(.13, duration * .05)
        blink = smooth(1 - distance / half_width)
    return {'phase': phase, 'gesture': gesture, 'breath': breath, 'sway': sway, 'blink': blink,
            'head_nod': gesture * math.sin(phase * math.tau),
            'emphasis': gesture * math.sin(phase * math.tau * 2)}
