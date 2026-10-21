"""渲染器无关的语义姿势。方向用模型世界坐标，骨段长由模型保持。"""
import math

def arm_targets(action,t,duration,side,sign):
    if action not in ('neutral','bend','wave','hold','turntable'):raise ValueError('动作不存在')
    upper=(sign*.12,0,-1);lower=(sign*.05,-.04,-1)
    desired_upper,desired_lower=upper,lower
    if action=='bend' and side=='right':desired_upper=(sign*.25,0,-1);desired_lower=(-sign*.6,-.6,.4)
    elif action=='wave' and side=='right':desired_upper=(sign*.8,0,-.4);desired_lower=(sign*(.12+.22*math.sin(t*6)),-.05,1)
    elif action=='hold':desired_upper=(sign*.3,-.1,-1);desired_lower=(-sign*.5,-.7,.25)
    linear=max(0,min(1,t/.35,(duration-t)/.35));weight=linear*linear*(3-2*linear)
    def blend(a,b):return tuple(x*(1-weight)+y*weight for x,y in zip(a,b))
    return blend(upper,desired_upper),blend(lower,desired_lower)
