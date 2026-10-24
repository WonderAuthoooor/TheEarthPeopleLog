"""Blender中检查两种基础动作的跨模型连续性、复播和足部固定。"""
import argparse
import json
import math
import sys
import types
from pathlib import Path
import bpy
from mathutils import Matrix

parser = argparse.ArgumentParser()
parser.add_argument('--addon', required=True)
parser.add_argument('--output', required=True)
parser.add_argument('--model', action='append', required=True)
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
package = types.ModuleType('avatar_pose_check')
package.__path__ = [str(Path(__file__).resolve().parents[1] / 'avatar3d')]
sys.modules['avatar_pose_check'] = package
from avatar_pose_check.natural_pose import NaturalPose
sys.path.insert(0, args.addon)
bpy.ops.preferences.addon_enable(module='io_scene_vrm')


def angle(a, b):
    delta = a.rotation_difference(b).normalized()
    return math.degrees(2 * math.atan2(math.sqrt(delta.x**2 + delta.y**2 + delta.z**2), abs(delta.w)))


reports = []
for path in args.model:
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.vrm(filepath=path)
    arm = next(obj for obj in bpy.context.scene.objects if obj.type == 'ARMATURE')
    ext = arm.data.vrm_addon_extension
    bones = {str(k.value): v.node.bone_name for k, v in ext.vrm1.humanoid.human_bones.human_bone_name_to_human_bone().items()}
    bpy.context.view_layer.update()
    pose = NaturalPose(arm, bones)
    feet = {side: (arm.matrix_world @ arm.pose.bones[bones[side + 'Foot']].matrix).translation.copy() for side in ('left', 'right')}

    def at(action, time):
        for bone in arm.pose.bones:
            bone.rotation_mode = 'QUATERNION';bone.matrix_basis = Matrix.Identity(4)
        bpy.context.view_layer.update()
        diagnostics = pose.apply(action, time, 4)
        rotations = {key: (arm.matrix_world @ arm.pose.bones[bones[key]].matrix).to_quaternion().copy() for key in pose.keyed}
        shift = max(((arm.matrix_world @ arm.pose.bones[bones[side + 'Foot']].matrix).translation - feet[side]).length for side in feet)
        return diagnostics, rotations, shift

    for action in ('idle', 'explain'):
        samples = [at(action, i / 30) for i in range(121)]
        maximum = max(angle(a[1][key], b[1][key]) for a, b in zip(samples, samples[1:]) for key in a[1])
        closure = max(angle(samples[0][1][key], samples[-1][1][key]) for key in samples[0][1])
        excursion = max(angle(samples[0][1][key], item[1][key]) for item in samples for key in item[1])
        replay_samples = {i: at(action, i / 30) for i in (0, 33, 67, 119)}
        replay = max(angle(samples[i][1][key], replay_samples[i][1][key]) for i in replay_samples for key in samples[i][1])
        foot_shift = max(item[2] for item in samples)
        elbows = [item[0]['arms'][side]['elbow_degrees'] for item in samples for side in ('left', 'right')]
        palm = min((item[0]['arms']['right']['palm_up_dot'] for item in samples if item[0]['gesture'] > .999), default=None)
        assert maximum < 15, (path, action, 'rotation step', maximum)
        assert excursion > (.2 if action == 'idle' else 45), (path, action, 'motion absent', excursion)
        assert closure < .1 and replay < .1, (path, action, closure, replay)
        assert foot_shift < 1e-6, (path, action, 'foot shift', foot_shift)
        assert min(elbows) > 2 and max(elbows) < 135, (path, action, elbows)
        assert palm is None or palm > .9, (path, action, 'palm', palm)
        assert all(item[0]['blink_available'] for item in samples)
        reports.append({'model': path, 'action': action, 'frames': 120, 'fps': 30,
                        'max_rotation_step_degrees': maximum, 'endpoint_error_degrees': closure,
                        'motion_excursion_degrees': excursion,
                        'replay_error_degrees': replay, 'foot_shift_m': foot_shift,
                        'elbow_min_max_degrees': [min(elbows), max(elbows)], 'hold_palm_up_dot': palm,
                        'blink_available': True, 'passed': True})
        print(path, action, 'passed', flush=True)
Path(args.output).write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding='utf-8')
print('NATURAL_POSE_CHECKS_PASSED', flush=True)
