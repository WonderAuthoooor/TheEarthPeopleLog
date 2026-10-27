"""有限的三动作排练时间表；不引入口播编辑或通用时间线。"""
import math
from .natural_motion import smooth

DEFAULT = {'duration':30, 'idle_period':3, 'fade':.3, 'gestures':[
    {'action':'wave','start':3,'duration':3},
    {'action':'explain','start':10,'duration':5},
    {'action':'wave','start':19,'duration':3},
    {'action':'explain','start':25,'duration':3}]}


def validate(plan):
    def number(v):return type(v) in (int,float) and math.isfinite(v)
    if (not number(plan['duration']) or not .5<=plan['duration']<=30
            or not number(plan['idle_period']) or not 2<=plan['idle_period']<=10
            or not number(plan['fade']) or not .1<=plan['fade']<=1):
        raise ValueError('排练时长、待机周期或过渡时间无效。')
    clips=plan['gestures']
    if not isinstance(clips,list) or not 1<=len(clips)<=10:raise ValueError('排练需要1—10段手势。')
    end=0
    for clip in clips:
        start,duration=clip['start'],clip['duration']
        if (clip['action'] not in ('wave','explain') or not number(start) or not number(duration)
                or duration<2*plan['fade'] or start<end or start+duration>plan['duration']):
            raise ValueError('手势必须有序、不重叠、完整落在排练时长内。')
        end=start+duration
    return plan


def sample(plan,time):
    if not math.isfinite(time) or not 0<=time<=plan['duration']:raise ValueError('排练采样时间越界。')
    for clip in plan['gestures']:
        local=time-clip['start']
        if 0<=local<clip['duration']:
            weight=smooth(local/plan['fade'])*smooth((clip['duration']-local)/plan['fade'])
            return clip,local,weight
    return None,0,0


def selected_frames(request):
    total=round(request['duration']*request['fps'])
    frames=request.get('rehearsal_render_frames',list(range(total)))
    if (not request.get('rehearsal') or not isinstance(frames,list) or not frames
            or any(type(i) is not int or not 0<=i<total for i in frames)
            or frames!=sorted(set(frames))):
        raise ValueError('排练渲染帧须有序、唯一且在时间范围内。')
    return frames
