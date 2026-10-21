"""项目自己的已完成场景→FBX→重导入；独立Blender进程，不开启文件脚本。"""
from pathlib import Path
import hashlib
import json
import math
import sys


def main():
    import bpy
    request = json.loads(Path(sys.argv[sys.argv.index('--') + 1]).read_text(encoding='utf-8'))
    source = Path(request['source'])
    if hashlib.sha256(source.read_bytes()).hexdigest() != request['source_sha256']:
        raise ValueError('源工程哈希不一致。')
    bpy.ops.wm.open_mainfile(filepath=str(source), load_ui=False, use_scripts=False)
    scene = bpy.context.scene
    rigs = [obj for obj in scene.objects if obj.type == 'ARMATURE']
    if len(rigs) != 1:
        raise ValueError('动作交换要求单个人形骨架。')
    rig = rigs[0]
    if not rig.animation_data or not rig.animation_data.action:
        raise ValueError('源工程没有已烘焙动作。')
    if scene.render.fps != request['fps'] or scene.frame_end - scene.frame_start + 1 != request['frames']:
        raise ValueError('源工程时间范围与任务不一致。')
    bones = {key: value for key, value in request['bones'].items() if value and value in rig.pose.bones}
    if not {'hips', 'head', 'leftFoot', 'rightFoot', 'rightHand'} <= bones.keys():
        raise ValueError('人形骨骼映射不完整。')
    frames = list(range(scene.frame_start, scene.frame_end + 1))

    def snapshot(arm, frame):
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        # 世界坐标的头／尾验证方向，能发现单位、轴向、左右手和重定向偏差。
        return {key: (arm.matrix_world @ arm.pose.bones[name].head,
                      arm.matrix_world @ arm.pose.bones[name].tail,
                      ((arm.matrix_world @ arm.pose.bones[name].matrix) @
                       (arm.matrix_world @ arm.data.bones[name].matrix_local).inverted()).to_quaternion())
                for key, name in bones.items()}

    original = {frame: snapshot(rig, frame) for frame in frames}
    source_fps = scene.render.fps / scene.render.fps_base
    scene.frame_set(scene.frame_start)
    bpy.ops.object.select_all(action='DESELECT')
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    # 骨架独立FBX没有蒙皮BindPose，导入器可能把首帧误当休息姿势。
    # 附带绑定网格保留BindPose；材质仍由独立VRM提供，不用FBX外观作验收。
    meshes = [obj for obj in scene.objects if obj.type == 'MESH' and
              any(mod.type == 'ARMATURE' and mod.object == rig for mod in obj.modifiers)]
    if not meshes:
        raise ValueError('缺少用于保留绑定姿势的蒙皮网格。')
    for mesh in meshes:
        mesh.select_set(True)
    output = Path(request['output'])
    result = bpy.ops.export_scene.fbx(
        filepath=str(output / 'animation.fbx'), use_selection=True, object_types={'ARMATURE', 'MESH'},
        use_mesh_modifiers=False, path_mode='STRIP',
        add_leaf_bones=False, use_armature_deform_only=False, armature_nodetype='NULL',
        axis_forward='-Z', axis_up='Y', global_scale=1, apply_unit_scale=True,
        bake_anim=True, bake_anim_use_all_bones=True, bake_anim_use_nla_strips=False,
        bake_anim_use_all_actions=False, bake_anim_force_startend_keying=True,
        bake_anim_step=1, bake_anim_simplify_factor=0)
    if result != {'FINISHED'}:
        raise RuntimeError('FBX导出没有完成。')
    # 不修改母版；在内存里移除原场景后重导入，所有帧均对照。
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    # Blender导入默认额外偏移一帧；验证同一时间的姿势时必须显式归零。
    bpy.ops.import_scene.fbx(filepath=str(output / 'animation.fbx'), automatic_bone_orientation=False,
                             anim_offset=0.0)
    imported = [obj for obj in scene.objects if obj.type == 'ARMATURE']
    if len(imported) != 1:
        raise ValueError('FBX重导入未得到唯一骨架。')
    restored = imported[0]
    if not restored.animation_data or not restored.animation_data.action:
        raise ValueError('FBX重导入丢失动作。')
    missing = [name for name in bones.values() if name not in restored.pose.bones]
    if missing:
        raise ValueError('FBX重导入丢失骨骼：' + ', '.join(missing))
    max_head_error = max_tail_error = 0.0
    # FBX缺少末端骨时重建尾长可能不同，验证头位置和骨段方向；不把尾长差误判为动作错误。
    max_angle = max_rotation_error = 0.0
    frame_errors = []
    for frame in frames:
        current = snapshot(restored, frame)
        frame_error = 0.0
        for key, (head, tail, rotation) in original[frame].items():
            new_head, new_tail, new_rotation = current[key]
            max_head_error = max(max_head_error, (head - new_head).length)
            frame_error = max(frame_error, (head - new_head).length)
            max_tail_error = max(max_tail_error, (tail - new_tail).length)
            old_direction, new_direction = tail - head, new_tail - new_head
            if old_direction.length > 1e-7 and new_direction.length > 1e-7:
                max_angle = max(max_angle, math.degrees(old_direction.angle(new_direction)))
            angle = rotation.rotation_difference(new_rotation).angle
            max_rotation_error = max(max_rotation_error, math.degrees(min(angle, 2 * math.pi - angle)))
        frame_errors.append({'frame': frame, 'max_head_error_m': frame_error})
    imported_range = list(restored.animation_data.action.frame_range)
    timing_ok = (abs(scene.render.fps / scene.render.fps_base - source_fps) < 1e-6 and
                 abs(imported_range[0] - frames[0]) < 1e-4 and
                 abs(imported_range[1] - frames[-1]) < 1e-4)
    report = {'schema': 1, 'blender_version': bpy.app.version_string,
              'checked_frames': len(frames), 'checked_bones': len(bones),
              'source_fps': source_fps, 'reimport_fps': scene.render.fps / scene.render.fps_base,
              'reimport_key_range': imported_range, 'timing_passed': timing_ok,
              'frame_errors': frame_errors,
              'max_head_position_error_m': max_head_error,
              'max_tail_position_error_m': max_tail_error,
              'max_direction_error_degrees': max_angle,
              'max_deformation_rotation_error_degrees': max_rotation_error,
              'position_tolerance_m': .001, 'direction_tolerance_degrees': .1,
              'tail_length_note': '无叶骨FBX会重建末端尾长；不用于重建角色网格，头位置、方向及相对休息姿势的旋转单独检查',
              'passed': timing_ok and max_head_error < .001 and max_angle < .1 and max_rotation_error < .1,
              'scope': 'Blender FBX往返，不代表Unity Humanoid或Warudo已验证'}
    (output / 'roundtrip.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    if not report['passed']:
        raise ValueError('FBX往返的姿势／坐标偏差超出阈值。')


if __name__ == '__main__':
    main()
