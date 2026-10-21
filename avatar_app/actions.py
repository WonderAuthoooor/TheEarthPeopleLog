"""可复现的动作姿态、两段臂长约束与可中断过渡；不生成文明分数。"""
from dataclasses import dataclass,field
import math
import time

EXPRESSIONS=("neutral","smile","smirk","think","surprise","resigned","angry")
ACTION_NAMES={"idle":"待机","explain":"讲解","witty":"微笑吐槽","think":"思考",
              "surprise":"惊讶","resigned":"无奈","point":"指向新闻","wave":"挥手","score":"举评分牌",
              "laugh":"大笑","angry":"生气"}
ACTION_ORDER=tuple(ACTION_NAMES)
ROOTS={"left":(185,560),"right":(835,560)}
LENGTH=320.0


def ease(value):
    value=min(1,max(0,value))
    return value*value*(3-2*value)


def angle_mix(a,b,weight):
    delta=(b-a+180)%360-180
    return a+delta*weight


def arm_angles(side,wrist):
    root=ROOTS[side];dx,dy=wrist[0]-root[0],wrist[1]-root[1]
    distance=min(2*LENGTH-.01,max(.1,math.hypot(dx,dy)))
    norm=max(.1,math.hypot(dx,dy));ux,uy=dx/norm,dy/norm
    middle=(root[0]+ux*distance/2,root[1]+uy*distance/2)
    height=math.sqrt(max(0,LENGTH**2-(distance/2)**2))
    options=[(middle[0]-uy*height,middle[1]+ux*height),(middle[0]+uy*height,middle[1]-ux*height)]
    reference=(70,850) if side=="left" else (955,850)
    elbow=min(options,key=lambda p:math.dist(p,reference))
    target=(root[0]+ux*distance,root[1]+uy*distance)
    return math.degrees(math.atan2(elbow[1]-root[1],elbow[0]-root[0])),math.degrees(math.atan2(target[1]-elbow[1],target[0]-elbow[0]))


def joints(side,angles):
    root=ROOTS[side]
    a,b=(math.radians(v) for v in angles)
    elbow=(root[0]+LENGTH*math.cos(a),root[1]+LENGTH*math.sin(a))
    wrist=(elbow[0]+LENGTH*math.cos(b),elbow[1]+LENGTH*math.sin(b))
    return root,elbow,wrist


@dataclass
class Pose:
    angles: dict=field(default_factory=dict)
    hands: dict=field(default_factory=lambda:{"left":"relax","right":"relax"})
    hand_angles: dict=field(default_factory=lambda:{"left":90.0,"right":90.0})
    expressions: dict=field(default_factory=lambda:{"neutral":1.0})
    roll: float=0.0
    lean: float=0.0
    card: float=0.0
    mouth_floor: float=0.0
    blink_floor: float=0.0


def pose_at(action,t=0):
    if action not in ACTION_NAMES:raise ValueError("不支持的动作："+str(action))
    wrists={"left":(125,1190),"right":(895,1190)}
    pose=Pose()
    if action=="explain":
        wrists['right']=(570,900+8*math.sin(t*2.2));pose.hands['right']='open';pose.hand_angles['right']=190
        pose.expressions={'smile':.45,'neutral':.55}
    elif action=="witty":
        pose.expressions={'smirk':1};pose.roll=.15
    elif action=="think":
        wrists['right']=(560,600);pose.hands['right']='point';pose.hand_angles['right']=255
        pose.expressions={'think':1};pose.roll=-.16
    elif action=="surprise":
        wrists={'left':(400,760),'right':(620,760)}
        pose.hands={'left':'open','right':'open'};pose.hand_angles={'left':-120,'right':-60}
        pose.expressions={'surprise':1}
    elif action=="resigned":
        wrists['right']=(650,1030);pose.hands['right']='open';pose.hand_angles['right']=200
        pose.expressions={'resigned':1};pose.roll=-.3;pose.lean=.12
    elif action=="point":
        wrists['right']=(430,730);pose.hands['right']='point';pose.hand_angles['right']=190
    elif action=="wave":
        wrists['right']=(865+4*math.sin(t*3),555)
        pose.hands['right']='open';pose.hand_angles['right']=-90+14*math.sin(t*6)
        pose.expressions={'smile':1}
    elif action=="score":
        wrists={'left':(290,1100),'right':(860,1100)}
        pose.hands={'left':'grip','right':'grip'};pose.hand_angles={'left':20,'right':160};pose.card=1
    elif action=="laugh":
        pose.expressions={'smile':1};pose.mouth_floor=.8+.15*math.sin(t*8)
        pose.blink_floor=.9;pose.lean=.08*math.sin(t*8)
    elif action=="angry":
        pose.expressions={'angry':1};pose.roll=-.12
    pose.angles={side:arm_angles(side,wrists[side]) for side in ROOTS}
    return pose


def blend_pose(a,b,weight):
    weight=min(1,max(0,weight))
    return Pose(angles={side:tuple(angle_mix(x,y,weight) for x,y in zip(a.angles[side],b.angles[side])) for side in ROOTS},
        hands={side:(b.hands[side] if weight>=.5 else a.hands[side]) for side in ROOTS},
        hand_angles={side:angle_mix(a.hand_angles[side],b.hand_angles[side],weight) for side in ROOTS},
        expressions={key:a.expressions.get(key,0)*(1-weight)+b.expressions.get(key,0)*weight for key in EXPRESSIONS},
        roll=a.roll*(1-weight)+b.roll*weight,lean=a.lean*(1-weight)+b.lean*weight,card=a.card*(1-weight)+b.card*weight,
        mouth_floor=a.mouth_floor*(1-weight)+b.mouth_floor*weight,blink_floor=a.blink_floor*(1-weight)+b.blink_floor*weight)


class ActionController:
    def __init__(self,now=None):
        self.action='idle'
        self.since=time.monotonic() if now is None else now
        self.previous=pose_at('idle')

    def sample(self,now=None):
        now=time.monotonic() if now is None else now
        age=max(0,now-self.since)
        return blend_pose(self.previous,pose_at(self.action,age),ease(age/.4))

    def trigger(self,action,now=None):
        if action not in ACTION_NAMES:raise ValueError("不支持的动作")
        now=time.monotonic() if now is None else now
        self.previous=self.sample(now)
        self.action=action;self.since=now


def clip_pose(action,t,duration):
    pose=pose_at(action,t)
    envelope=min(ease(t/.4),ease((duration-t)/.4))
    return blend_pose(pose_at('idle'),pose,envelope)
