"""Blender wave pose with a stable elbow plane and an anatomical palm frame."""
import math
from mathutils import Vector, Matrix


def smooth(x):
    x=max(0.0,min(1.0,x))
    return x*x*x*(x*(x*6-15)+10)


def wave_envelope(t,duration):
    p=max(0.0,min(1.0,t/duration))
    return smooth(p/.28)*smooth((1-p)/.28)


def frame(direction,secondary):
    y=Vector(direction).normalized()
    z=Vector(secondary)-y*Vector(secondary).dot(y)
    if z.length<1e-6:raise ValueError('Degenerate anatomical orientation frame')
    z.normalize();x=y.cross(z).normalized()
    return Matrix((x,y,z)).transposed()


class WavePose:
    def __init__(self,arm,bones):
        self.arm=arm;self.bones=bones
        self.rest={k:(arm.matrix_world@arm.pose.bones[v].matrix).copy()
                   for k,v in bones.items() if v and v in arm.pose.bones}
        required={'rightUpperArm','rightLowerArm','rightHand','rightIndexProximal','rightMiddleProximal','rightLittleProximal'}
        missing=required-self.rest.keys()
        if missing:raise ValueError('挥手需要掌面校准骨骼：'+', '.join(sorted(missing)))
        self.forward=Vector((0,-1,0))
        hand=self.rest['rightHand'].translation
        index=self.rest['rightIndexProximal'].translation
        little=self.rest['rightLittleProximal'].translation
        middle=self.rest['rightMiddleProximal'].translation
        self.fingers=(middle-hand).normalized()
        normal=self.fingers.cross(little-index).normalized()
        # VRM T pose palms point down; choose the normal's anatomical sign.
        if normal.z>0:normal.negate()
        self.palm=normal
        self.hand_frame=frame(self.fingers,normal)

    def set_rotation(self,key,q):
        import bpy
        p=self.arm.pose.bones[self.bones[key]]
        world=self.arm.matrix_world@p.matrix
        changed=q.to_matrix().to_4x4();changed.translation=world.translation
        p.matrix=self.arm.matrix_world.inverted()@changed
        bpy.context.view_layer.update()

    def apply(self,t,duration,sign):
        w=wave_envelope(t,duration)
        upper=Vector((sign*(.12+.58*w),-.12*w,-1+.30*w)).normalized()
        # Sweep through forward space, never linearly interpolate opposite vectors.
        theta=.055+2.80*w
        lower=Vector((sign*.05,-math.sin(theta),-math.cos(theta))).normalized()
        hinge=upper.cross(lower).normalized()
        for key,direction in [('rightUpperArm',upper),('rightLowerArm',lower)]:
            rest=self.rest[key];rest_direction=rest.to_quaternion()@Vector((0,1,0))
            rest_hinge=rest_direction.cross(self.forward).normalized()
            delta=frame(direction,hinge)@frame(rest_direction,rest_hinge).transposed()
            self.set_rotation(key,(delta@rest.to_3x3()).to_quaternion())
        # Neutral inherits forearm roll; raised palm is independently facing the viewer.
        inherited=(self.arm.matrix_world@self.arm.pose.bones[self.bones['rightHand']].matrix).to_quaternion()
        phase=max(0,min(1,(t/duration-.28)/.44))
        swing=math.radians(16)*math.sin(phase*math.tau*2)*smooth(phase/.12)*smooth((1-phase)/.12)
        fingers=Vector((sign*math.sin(swing),-.08,math.cos(swing))).normalized()
        target=(frame(fingers,self.forward)@self.hand_frame.transposed()@self.rest['rightHand'].to_3x3()).to_quaternion()
        self.set_rotation('rightHand',inherited.slerp(target,w))
        world=self.arm.matrix_world@self.arm.pose.bones[self.bones['rightHand']].matrix
        delta=world.to_quaternion()@self.rest['rightHand'].to_quaternion().inverted()
        return {'weight':w,'palm_forward_dot':(delta@self.palm).dot(self.forward),
                'elbow_flex_degrees':math.degrees(upper.angle(lower))}
