"""Blender排练适配：循环待机为底层，右臂手势四元数混合；头躯干不被接管。"""
import math
from mathutils import Matrix
from .natural_pose import NaturalPose
from .wave_pose import WavePose
from .rehearsal import validate,sample


class RehearsalPose:
    def __init__(self,arm,bones,plan):
        self.arm,self.bones,self.plan=arm,bones,validate(plan)
        self.natural=NaturalPose(arm,bones);self.wave=WavePose(arm,bones)
        self.previous=None

    def reset(self):
        import bpy
        for bone in self.arm.pose.bones:bone.matrix_basis=Matrix.Identity(4)
        bpy.context.view_layer.update()

    def apply(self,time,keyframe):
        import bpy
        self.reset()
        self.natural.apply('idle',time%self.plan['idle_period'],self.plan['idle_period'])
        base={b.name:b.rotation_quaternion.copy() for b in self.arm.pose.bones}
        blink=[(key,key.value) for key,_ in self.natural.blink_keys]
        clip,local,weight=sample(self.plan,time)
        masked=[]
        if clip and weight>0:
            self.reset()
            if clip['action']=='wave':
                self.wave.apply(local,clip['duration'],self.natural.signs['right'])
                keys=['rightUpperArm','rightLowerArm','rightHand']
            else:
                self.natural.apply('explain',local,clip['duration'])
                keys=[k for k in self.bones if k.startswith('right') and
                      any(s in k for s in ('Arm','Hand','Thumb','Index','Middle','Ring','Little'))]
            masked=[self.bones[k] for k in keys if self.bones[k] in base]
            overlay={name:self.arm.pose.bones[name].rotation_quaternion.copy() for name in masked}
        for bone in self.arm.pose.bones:
            bone.rotation_quaternion=base[bone.name].slerp(overlay[bone.name],weight) if bone.name in masked else base[bone.name]
            bone.keyframe_insert('rotation_quaternion',frame=keyframe)
        for key,value in blink:key.value=value;key.keyframe_insert('value',frame=keyframe)
        bpy.context.view_layer.update()
        now={b.name:b.rotation_quaternion.copy() for b in self.arm.pose.bones}
        angles=[math.degrees(q.rotation_difference(self.previous[name]).angle) for name,q in now.items()] if self.previous else []
        delta=max((min(a,360-a) for a in angles),default=0)
        protected=max((now[n].rotation_difference(q).angle for n,q in base.items() if n not in masked),default=0)
        self.previous=now
        return {'frame':keyframe,'seconds':time,'gesture':clip['action'] if clip else 'idle',
                'weight':weight,'max_step_degrees':delta,'unmasked_error_radians':protected}
