"""C驱动检查：导出并重导入VRM，检查基础表情和固定步长头发物理。"""
import argparse
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Matrix, Quaternion, Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from avatar3d.models import digest, atomic_json
from avatar3d.rig_audit import audit_vrm

REQUIRED = ('happy', 'angry', 'sad', 'relaxed', 'surprised',
            'aa', 'ih', 'ou', 'ee', 'oh', 'blink', 'blinkLeft', 'blinkRight')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-review', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--addon', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    source = args.source_review.resolve() / 'C-character.blend'
    report = json.loads((args.source_review / 'export-report.json').read_text(encoding='utf-8'))
    if digest(source) != report['blend_sha256']:
        raise ValueError('自有源工程哈希不一致。')
    output = args.output.resolve()
    output.mkdir(exist_ok=False)
    sys.path.insert(0, str(args.addon.resolve()))
    bpy.ops.preferences.addon_enable(module='io_scene_vrm')
    bpy.ops.wm.open_mainfile(filepath=str(source), use_scripts=False)
    scene = bpy.context.scene
    arm = next(o for o in scene.objects if o.type == 'ARMATURE')
    ext = arm.data.vrm_addon_extension
    if not ext.is_vrm1():
        raise ValueError('源工程必须为VRM1。')
    neutral_pose = {b.name: b.matrix_basis.copy() for b in arm.pose.bones}
    physics = ext.spring_bone1
    # 插件可能已经迁移；仅保留头发，删除已拆除帽子／抽绳的旧动态链。
    bpy.ops.vrm.assign_spring_bone1_from_vrm0(armature_object_name=arm.name)
    removed = []
    for i in reversed(range(len(physics.springs))):
        spring = physics.springs[i]
        names = [j.node.bone_name for j in spring.joints]
        if not names or not all(name.startswith('HairJoint-') for name in names):
            removed.append(spring.vrm_name)
            physics.springs.remove(i)
    if not physics.springs:
        raise ValueError('没有可用头发链。')
    for i, spring in enumerate(physics.springs):
        spring.vrm_name = f'C_Hair_{i + 1:02}'
    physics.enable_animation = False
    expressions = ext.vrm1.expressions.all_name_to_expression_dict()
    for name in REQUIRED:
        if name not in expressions or not expressions[name].morph_target_binds:
            raise ValueError('基础表情缺失：' + name)
    ext.vrm1.meta.version = '0.1.5-rig-draft'
    for bone in arm.pose.bones:
        bone.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
    bpy.ops.object.select_all(action='DESELECT')
    for obj in {arm, *arm.children_recursive}:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = arm
    vrm = output / 'C-character.vrm'
    if bpy.ops.export_scene.vrm(filepath=str(vrm), armature_object_name=arm.name,
                                export_only_selections=True) != {'FINISHED'}:
        raise RuntimeError('角色导出失败。')
    audit = audit_vrm(vrm)
    for bone in arm.pose.bones:
        bone.matrix_basis = neutral_pose[bone.name]
    bpy.context.view_layer.update()
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(output / 'C-character.blend'))
    # 实际样片使用重新导入的VRM，检查导出时是否丢失表情和物理。
    for obj in tuple({arm, *arm.children_recursive}):
        bpy.data.objects.remove(obj, do_unlink=True)
    if bpy.ops.import_scene.vrm(filepath=str(vrm)) != {'FINISHED'}:
        raise RuntimeError('派生模型无法重新导入。')
    arm = next(o for o in scene.objects if o.type == 'ARMATURE')
    ext = arm.data.vrm_addon_extension
    physics = ext.spring_bone1
    physics.enable_animation = False
    for bone in arm.pose.bones:
        bone.matrix_basis = neutral_pose.get(bone.name, Matrix.Identity(4))
    bpy.context.view_layer.update()
    baseline = {b.name: b.matrix_basis.copy() for b in arm.pose.bones}
    expressions = ext.vrm1.expressions.all_name_to_expression_dict()
    meshes = [o for o in arm.children_recursive if o.type == 'MESH']

    def expression(weights):
        for obj in meshes:
            if obj.data.shape_keys:
                for key in obj.data.shape_keys.key_blocks:
                    key.value = 0
        for name, weight in weights.items():
            for bind in expressions[name].morph_target_binds:
                obj = bpy.data.objects.get(bind.node.mesh_object_name)
                if not obj or not obj.data.shape_keys or bind.index not in obj.data.shape_keys.key_blocks:
                    raise ValueError('重导入表情绑定无效：' + name)
                key = obj.data.shape_keys.key_blocks[bind.index]
                key.value = min(1, key.value + weight * bind.weight)
        bpy.context.view_layer.update()

    head_name = ext.vrm1.humanoid.human_bones.head.node.bone_name
    head = arm.pose.bones[head_name]
    target = arm.matrix_world @ head.head + Vector((0, -.03, .055))
    camera = scene.camera
    camera.data.ortho_scale = .58
    camera.location = target + Vector((0, -3, 0))
    camera.rotation_euler = (target - camera.location).to_track_quat('-Z', 'Y').to_euler()
    scene.render.resolution_x = 480
    scene.render.resolution_y = 600
    scene.eevee.taa_render_samples = 16
    stills = output / 'expressions'; stills.mkdir()
    expression({})
    face = bpy.data.objects.get(expressions['aa'].morph_target_binds[0].node.mesh_object_name)

    def evaluated_vertices():
        evaluated = face.evaluated_get(bpy.context.evaluated_depsgraph_get())
        mesh = evaluated.to_mesh()
        points = [v.co.copy() for v in mesh.vertices]
        evaluated.to_mesh_clear()
        return points

    neutral_vertices = evaluated_vertices()
    samples = [('neutral', {})] + [(name, {name: 1.0}) for name in REQUIRED]
    samples += [('blink_aa', {'blink': 1, 'aa': .6}), ('happy_aa', {'happy': .5, 'aa': .6})]
    deltas = {}
    for name, weights in samples:
        expression(weights)
        moved = evaluated_vertices()
        delta = max((a - b).length for a, b in zip(neutral_vertices, moved))
        if name != 'neutral' and delta < 1e-5:
            raise ValueError('表情绑定未产生实际变形：' + name)
        deltas[name] = delta
        scene.render.filepath = str(stills / (name + '.png'))
        bpy.ops.render.render(write_still=True)
    expression({})
    from io_scene_vrm.editor.spring_bone1.handler import update_pose_bone_rotations
    joint_names = sorted({j.node.bone_name for spring in physics.springs for j in spring.joints})
    frames = output / 'frames'; frames.mkdir()

    def simulate(render):
        physics.enable_animation = False
        for bone in arm.pose.bones:
            bone.rotation_mode = 'QUATERNION'
            bone.matrix_basis = baseline[bone.name]
        bpy.context.view_layer.update()
        # 开关仅重置tail初始化标记；中心空间和惯性位置也必须重置。
        for spring in physics.springs:
            spring.animation_state.use_center_space = False
            center = arm.pose.bones.get(spring.center.bone_name)
            spring.animation_state.previous_center_world_translation = (
                arm.matrix_world @ center.matrix).translation if center else (0, 0, 0)
            for joint in spring.joints:
                joint.animation_state.initialized_as_tail = False
                joint.animation_state.previous_world_translation = (0, 0, 0)
                joint.animation_state.current_world_translation = (0, 0, 0)
        physics.enable_animation = True
        bpy.context.view_layer.update()
        states = []
        # 60Hz固定步长，半秒预滚，3秒样片；复播从相同状态开始。
        for step in range(30 + 180):
            t = max(0, step - 30) / 60
            head.rotation_mode = 'QUATERNION'
            head.rotation_quaternion = baseline[head.name].to_quaternion() @ Quaternion((0, 1, 0), .18 * math.sin(math.tau * t / 3))
            bpy.context.view_layer.update()
            update_pose_bone_rotations(bpy.context, 1 / 60)
            bpy.context.view_layer.update()
            if step >= 30 and (step - 30) % 5 == 0:
                values = [float(v) for name in joint_names for row in arm.pose.bones[name].matrix_basis for v in row]
                if not all(math.isfinite(v) for v in values):
                    raise ValueError('物理模拟产生非有限变换。')
                states.append(values)
                if render:
                    blink = max(0, 1 - abs(t - 1.3) / .12)
                    mouth = .55 * max(0, math.sin(math.tau * t * 1.5))
                    expression({'blink': blink, 'aa': mouth})
                    scene.render.filepath = str(frames / f'{len(states)-1:04}.png')
                    bpy.ops.render.render(write_still=True)
        physics.enable_animation = False
        return states

    # Blender单帧渲染也可能触发frame_change_pre；避免与手动60Hz推进重复积分。
    from io_scene_vrm.editor.spring_bone1 import handler as spring_handler
    callbacks = bpy.app.handlers.frame_change_pre
    callback_index = callbacks.index(spring_handler.frame_change_pre) if spring_handler.frame_change_pre in callbacks else None
    if callback_index is not None:
        callbacks.remove(spring_handler.frame_change_pre)
    try:
        first = simulate(True)
        expression({})
        second = simulate(False)
    finally:
        if callback_index is not None:
            callbacks.insert(callback_index, spring_handler.frame_change_pre)
    replay_error = max(abs(a-b) for ra, rb in zip(first, second) for a, b in zip(ra, rb))
    if replay_error > 1e-5:
        raise ValueError('固定步长复播偏差超阈值：' + str(replay_error))
    movement = max(abs(a-b) for row in first for a, b in zip(first[0], row))
    if movement < 1e-5:
        raise ValueError('头发链没有产生独立运动。')
    report = {'source_blend_sha256': digest(source), 'script_sha256': digest(Path(__file__)),
              'vrm_sha256': digest(vrm), 'blend_sha256': digest(output / 'C-character.blend'),
              'audit': audit, 'removed_legacy_springs': removed, 'expression_vertex_delta_m': deltas,
              'simulation': {'frames': len(first), 'fps': 12, 'step_hz': 60, 'preroll_steps': 30,
                             'repeat_max_error': replay_error, 'hair_transform_variation': movement},
              'sample_mouth': 'procedural_aa_not_audio_lipsync', 'visual_accepted': False,
              'target_clients_verified': False}
    atomic_json(output / 'rig-report.json', report)
    atomic_json(output / 'frames-complete.json', {'files': {f.name: digest(f) for f in sorted(frames.glob('*.png'))}})


if __name__ == '__main__':
    main()
