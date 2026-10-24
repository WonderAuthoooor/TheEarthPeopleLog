"""Blender中检查C肩领修复模型的实际蒙皮、动作连续性和复播。"""
import argparse
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Matrix

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from avatar3d.models import digest
from avatar3d.natural_pose import NaturalPose
from avatar3d.wave_pose import WavePose
from avatar3d.shoulder_repair import skin_coverage


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--addon', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    if args.output.exists():
        raise FileExistsError('报告已存在。')
    source_hash = digest(args.model)
    sys.path.insert(0, str(args.addon))
    bpy.ops.preferences.addon_enable(module='io_scene_vrm')
    bpy.ops.import_scene.vrm(filepath=str(args.model))
    arm = next(o for o in bpy.context.scene.objects if o.type == 'ARMATURE')
    ext = arm.data.vrm_addon_extension
    ext.spring_bone1.enable_animation = False
    bones = {str(k.value): v.node.bone_name for k, v in ext.vrm1.humanoid.human_bones.human_bone_name_to_human_bone().items()}
    bpy.context.view_layer.update()
    pose, wave = NaturalPose(arm, bones), WavePose(arm, bones)
    meshes = [bpy.data.objects[name] for name in ('C_BlackHighNeck', 'C_TailoredJacket')]
    coverage = skin_coverage(arm, meshes[0])
    if coverage['uncovered']:
        raise ValueError('重导入后颈根遮盖检查失败。')
    for obj in meshes:
        for vertex in obj.data.vertices:
            weights = [g.weight for g in vertex.groups]
            if not weights or abs(sum(weights) - 1) > 1e-4 or any(not math.isfinite(w) or w < 0 for w in weights):
                raise ValueError('重导入后蒙皮权重无效。')

    posed_coverage = {}

    def sample(action, time):
        for bone in arm.pose.bones:
            bone.rotation_mode = 'QUATERNION'
            bone.matrix_basis = Matrix.Identity(4)
        bpy.context.view_layer.update()
        pose.apply('idle' if action == 'wave' else action, 0 if action == 'wave' else time, 3)
        if action == 'wave':
            wave.apply(time, 3, pose.signs['right'])
        if abs(time * 2 - round(time * 2)) < 1e-6:
            check = skin_coverage(arm, meshes[0], evaluated=True)
            if check['uncovered']:
                raise ValueError(f'{action}@{time}颈根遮盖失败：{check}')
            posed_coverage[f'{action}@{time:.2f}'] = check
        graph = bpy.context.evaluated_depsgraph_get()
        points = []
        for obj in meshes:
            evaluated = obj.evaluated_get(graph)
            mesh = evaluated.to_mesh()
            try:
                points.extend(evaluated.matrix_world @ v.co for v in mesh.vertices)
            finally:
                evaluated.to_mesh_clear()
        if any(not math.isfinite(v) for point in points for v in point):
            raise ValueError('动作产生非有限顶点坐标。')
        return points

    reports = []
    for action in ('idle', 'explain', 'wave'):
        first = previous = sample(action, 0)
        maximum = excursion = 0
        saved = {}
        for i in range(1, 91):
            current = sample(action, i / 30)
            maximum = max(maximum, max((a - b).length for a, b in zip(previous, current)))
            excursion = max(excursion, max((a - b).length for a, b in zip(first, current)))
            if i in (30, 60):
                saved[i] = current
            previous = current
        closure = max((a - b).length for a, b in zip(first, previous))
        replay = max((a - b).length for i, points in saved.items() for a, b in zip(points, sample(action, i / 30)))
        if maximum > .1 or closure > 1e-4 or replay > 1e-5:
            raise ValueError(f'{action}服装连续性／复播失败：{maximum}, {closure}, {replay}')
        if excursion < (.0005 if action == 'idle' else .05):
            raise ValueError('服装没有随骨骼产生预期运动。')
        reports.append({'action': action, 'fps': 30, 'samples': 91,
                        'max_vertex_step_m': maximum, 'motion_excursion_m': excursion,
                        'endpoint_error_m': closure, 'replay_error_m': replay})
        print('PASSED', action, flush=True)
    if digest(args.model) != source_hash:
        raise ValueError('检查期间源模型变化。')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({'model_sha256': source_hash, 'coverage_after_reimport': coverage,
        'skin_weights_valid': True, 'deformation': reports, 'posed_coverage': posed_coverage,
        'full_collision_verified': False,
        'warudo_verified': False}, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
