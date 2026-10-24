"""Blender语义骨骼适配，基础待机与单手讲解，不修改角色几何。"""
import math
from mathutils import Vector, Quaternion
from .natural_motion import sample, REVISION
from .wave_pose import frame


class NaturalPose:
    def __init__(self, arm, bones):
        import bpy
        self.arm, self.bones = arm, bones
        self.rest = {key: (arm.matrix_world @ arm.pose.bones[name].matrix).copy()
                     for key, name in bones.items() if name and name in arm.pose.bones}
        required = {'hips', 'spine', 'head'} | {
            side + suffix for side in ('left', 'right') for suffix in
            ('UpperArm', 'LowerArm', 'Hand', 'IndexProximal', 'MiddleProximal', 'LittleProximal')}
        if missing := required - self.rest.keys():
            raise ValueError('基础动作需要人形与掌面骨骼：' + ', '.join(sorted(missing)))
        self.forward = Vector((0, -1, 0))
        self.signs = {}; self.palms = {}; self.hand_frames = {}; self.curls = {}
        for side in ('left', 'right'):
            self.signs[side] = 1 if self.rest[side + 'UpperArm'].translation.x > self.rest['hips'].translation.x else -1
            fingers = (self.rest[side + 'MiddleProximal'].translation - self.rest[side + 'Hand'].translation).normalized()
            palm = fingers.cross(self.rest[side + 'LittleProximal'].translation - self.rest[side + 'IndexProximal'].translation).normalized()
            if palm.z > 0:palm.negate()
            self.palms[side] = palm
            self.hand_frames[side] = frame(fingers, palm)
            self.curls[side] = fingers.cross(palm).normalized()
        self.blink_keys = []
        ext = arm.data.vrm_addon_extension
        if ext.is_vrm1():
            expression = ext.vrm1.expressions.all_name_to_expression_dict().get('blink')
            if expression:
                for bind in expression.morph_target_binds:
                    obj = bpy.data.objects.get(bind.node.mesh_object_name)
                    if obj and obj.data.shape_keys and bind.index in obj.data.shape_keys.key_blocks:
                        self.blink_keys.append((obj.data.shape_keys.key_blocks[bind.index], bind.weight))
        self.keyed = set()

    def rotate_world(self, key, quaternion):
        import bpy
        bone = self.arm.pose.bones[self.bones[key]]
        world = self.arm.matrix_world @ bone.matrix
        changed = quaternion.to_matrix().to_4x4()
        changed.translation = world.translation
        bone.matrix = self.arm.matrix_world.inverted() @ changed
        self.keyed.add(key)
        bpy.context.view_layer.update()

    def rotate_local_axis(self, key, world_axis, degrees):
        if key not in self.rest:return
        bone = self.arm.pose.bones[self.bones[key]]
        axis = self.rest[key].to_quaternion().inverted() @ Vector(world_axis)
        bone.rotation_quaternion = Quaternion(axis, math.radians(degrees))
        self.keyed.add(key)

    def apply(self, action, time, duration, keyframe=None):
        import bpy
        values = sample(action, time, duration)
        self.keyed.clear()
        self.rotate_local_axis('spine', (0, 1, 0), values['sway'] * .45)
        self.rotate_local_axis('chest', (1, 0, 0), values['breath'] * .65)
        self.rotate_local_axis('neck', (0, 1, 0), -values['sway'] * .3)
        self.rotate_local_axis('head', (1, 0, 0), values['breath'] * -.35 + values['head_nod'] * 1.8)
        bpy.context.view_layer.update()
        diagnostics = {}
        for side in ('left', 'right'):
            sign = self.signs[side]
            weight = values['gesture'] if side == 'right' else 0
            upper = Vector((sign * (.18 + .22 * weight), -.18 * weight, -1 + .05 * weight)).normalized()
            theta = .12 + 1.5 * weight + values['emphasis'] * .035 * weight
            lower = Vector((sign * (.08 + .42 * weight), -math.sin(theta), -math.cos(theta))).normalized()
            hinge = upper.cross(lower).normalized()
            for key, direction in ((side + 'UpperArm', upper), (side + 'LowerArm', lower)):
                rest = self.rest[key]
                direction_rest = rest.to_quaternion() @ Vector((0, 1, 0))
                hinge_rest = direction_rest.cross(self.forward).normalized()
                delta = frame(direction, hinge) @ frame(direction_rest, hinge_rest).transposed()
                self.rotate_world(key, (delta @ rest.to_3x3()).to_quaternion())
            hand = side + 'Hand'
            inherited = (self.arm.matrix_world @ self.arm.pose.bones[self.bones[hand]].matrix).to_quaternion()
            desired = (frame(Vector((sign * .45, -1, .12)), Vector((0, -.1, 1)))
                       @ self.hand_frames[side].transposed() @ self.rest[hand].to_3x3()).to_quaternion()
            self.rotate_world(hand, inherited.slerp(desired, weight))
            # 少量弯曲，避免所有手指像硬板；使用休息骨架推导轴，不硬编码本地XYZ。
            for finger in ('Index', 'Middle', 'Ring', 'Little'):
                for segment, angle in (('Proximal', 8), ('Intermediate', 12), ('Distal', 5)):
                    self.rotate_local_axis(side + finger + segment, self.curls[side], angle * (1 - .45 * weight))
            delta = ((self.arm.matrix_world @ self.arm.pose.bones[self.bones[hand]].matrix).to_quaternion()
                     @ self.rest[hand].to_quaternion().inverted())
            diagnostics[side] = {'elbow_degrees': math.degrees(upper.angle(lower)),
                                 'palm_up_dot': (delta @ self.palms[side]).z}
        for key, weight in self.blink_keys:
            key.value = values['blink'] * weight
            if keyframe is not None:key.keyframe_insert('value', frame=keyframe)
        bpy.context.view_layer.update()
        if keyframe is not None:
            for key in sorted(self.keyed):
                self.arm.pose.bones[self.bones[key]].keyframe_insert('rotation_quaternion', frame=keyframe)
        return {'revision': REVISION, **values, 'arms': diagnostics, 'blink_available': bool(self.blink_keys)}
