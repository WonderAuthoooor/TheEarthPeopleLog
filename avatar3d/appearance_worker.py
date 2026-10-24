"""Blender衣领对照：原资产只读、变化白名单、导出重导入后渲染。"""
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from avatar3d.appearance_study import study_spec
from avatar3d.models import digest, atomic_json
from avatar3d.natural_pose import NaturalPose
from avatar3d.wave_pose import WavePose
from avatar3d.rig_audit import audit_vrm


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def snapshot(arm):
    """分开记录坐标与拓扑/蒙皮，白名单内也不允许改权重。"""
    meshes = {}
    for obj in arm.children_recursive:
        if obj.type != 'MESH':
            continue
        data = obj.data
        geometry = [list(v.co) for v in data.vertices]
        shapes = [] if not data.shape_keys else [
            (key.name, [list(v.co) for v in key.data]) for key in data.shape_keys.key_blocks]
        meshes[obj.name] = {
            'geometry': fingerprint([geometry, shapes]),
            'binding': fingerprint({
                'faces': [list(p.vertices) for p in data.polygons],
                'face_materials': [p.material_index for p in data.polygons],
                'uv': [[list(loop.uv) for loop in layer.data] for layer in data.uv_layers],
                'groups': [g.name for g in obj.vertex_groups],
                'weights': [[(g.group, g.weight) for g in v.groups] for v in data.vertices],
                'materials': [(s.material.name if s.material else None) for s in obj.material_slots],
                'transform': [list(row) for row in obj.matrix_world],
            }),
        }
    bones = [(b.name, b.parent.name if b.parent else None,
              [list(row) for row in b.matrix_local]) for b in arm.data.bones]
    return {'meshes': meshes, 'skeleton': fingerprint(bones)}


def check_changes(before, after, targets, topology_targets=()):
    if before['skeleton'] != after['skeleton'] or before['meshes'].keys() != after['meshes'].keys():
        raise ValueError('骨架或网格列表发生非预期变化。')
    changed = []
    for name, prior in before['meshes'].items():
        current = after['meshes'][name]
        if prior['binding'] != current['binding'] and name not in topology_targets:
            raise ValueError('拓扑／蒙皮／材质引用被改变：' + name)
        if prior['geometry'] != current['geometry']:
            changed.append(name)
    if set(changed) != set(targets):
        raise ValueError('实际变化不等于白名单：' + repr(changed))
    return changed


def load_model(path):
    for obj in tuple(bpy.context.scene.objects):
        if obj.type not in ('CAMERA', 'LIGHT'):
            bpy.data.objects.remove(obj, do_unlink=True)
    if bpy.ops.import_scene.vrm(filepath=str(path)) != {'FINISHED'}:
        raise RuntimeError('VRM导入失败。')
    arm = next(o for o in bpy.context.scene.objects if o.type == 'ARMATURE')
    arm.data.vrm_addon_extension.spring_bone1.enable_animation = False
    bpy.context.view_layer.update()
    return arm


def main():
    request = json.loads(Path(sys.argv[sys.argv.index('--') + 1]).read_text(encoding='utf-8'))
    variants, views, revision = study_spec(request.get('study', 'collar'))
    source, studio, output = (Path(request[k]) for k in ('source', 'studio', 'output'))
    for key, path in [('source', source), ('studio', studio)]:
        if digest(path) != request[key + '_sha256']:
            raise ValueError('输入哈希不一致：' + key)
    sys.path.insert(0, request['addon'])
    bpy.ops.preferences.addon_enable(module='io_scene_vrm')
    bpy.ops.wm.open_mainfile(filepath=str(studio), use_scripts=False)
    scene = bpy.context.scene
    camera = scene.camera
    camera.animation_data_clear()
    scene.render.resolution_x = 480
    scene.render.resolution_y = 720
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.film_transparent = True
    bpy.context.preferences.filepaths.save_version = 0
    baseline_audit = audit_vrm(source)
    results = []
    camera_settings = {}
    for variant in variants:
        print('VARIANT', variant.key, flush=True)
        folder = output / variant.key
        folder.mkdir(exist_ok=False)
        arm = load_model(source)
        before = snapshot(arm)
        bounds = {}
        repair_report = None
        face_report = None
        posed_coverage = {}
        if variant.repair_shoulders:
            from avatar3d.shoulder_repair import repair
            repair_report = repair(arm)
        if variant.face_strength:
            from avatar3d.round_face import apply_round_face
            face_report = apply_round_face(arm, variant.face_strength)
        for name in (() if variant.repair_shoulders or variant.face_strength else variant.meshes):
            obj = bpy.data.objects.get(name)
            if obj is None or obj.type != 'MESH' or obj not in arm.children_recursive:
                raise ValueError('当前模型缺少受控衣领网格：' + name)
            inverse = obj.matrix_world.inverted()
            old = [(obj.matrix_world @ v.co).z for v in obj.data.vertices]
            collections = [obj.data.vertices]
            if obj.data.shape_keys:
                collections += [key.data for key in obj.data.shape_keys.key_blocks]
            for vertices in collections:
                for vertex in vertices:
                    vertex.co = inverse @ Vector(variant.transform(obj.matrix_world @ vertex.co))
            new = [(obj.matrix_world @ v.co).z for v in obj.data.vertices]
            bounds[name] = {'before_z': [min(old), max(old)], 'after_z': [min(new), max(new)]}
        topology_targets = ('C_TailoredJacket',) if variant.repair_shoulders else ()
        changed = check_changes(before, snapshot(arm), variant.meshes, topology_targets)
        bpy.context.view_layer.update()
        vrm = folder / 'C-character.vrm'
        if variant.key == 'A':
            shutil.copyfile(source, vrm)
        else:
            bpy.ops.object.select_all(action='DESELECT')
            for obj in {arm, *arm.children_recursive}:
                obj.select_set(True)
            bpy.context.view_layer.objects.active = arm
            if bpy.ops.export_scene.vrm(filepath=str(vrm), armature_object_name=arm.name,
                                       export_only_selections=True) != {'FINISHED'}:
                raise RuntimeError('VRM导出失败。')
        bpy.ops.wm.save_as_mainfile(filepath=str(folder / 'C-character.blend'))
        audit = audit_vrm(vrm)
        for key in ('humanoid_bones', 'expression_bind_counts', 'spring_chains', 'spring_joints', 'colliders', 'collider_groups'):
            if audit[key] != baseline_audit[key]:
                raise ValueError('导出后驱动结构变化：' + key)
        arm = load_model(vrm)
        ext = arm.data.vrm_addon_extension
        bones = {str(k.value): v.node.bone_name for k, v in
                 ext.vrm1.humanoid.human_bones.human_bone_name_to_human_bone().items()}
        pose = NaturalPose(arm, bones)
        wave = WavePose(arm, bones)
        foot = min(pose.rest[k].translation.z for k in ('leftFoot', 'rightFoot'))
        height = pose.rest['head'].translation.z - foot + .2
        if not camera_settings:
            camera_settings = {'full_target': [0, 0, foot + height * .52],
                               'close_target': [0, 0, pose.rest['head'].translation.z - .10],
                               'full_scale': height * 1.17, 'close_scale': .72}
            if request.get('study') == 'rounded':
                eyes = [pose.rest[side + 'Eye'].translation for side in ('left', 'right')]
                camera_settings['close_target'] = [0, -.015, sum(p.z for p in eyes) / 2 + .025]
                camera_settings['close_scale'] = .42
        for key, label, degrees, close, action in views:
            for obj in arm.children_recursive:
                if obj.type == 'MESH' and obj.data.shape_keys:
                    for shape in obj.data.shape_keys.key_blocks:
                        shape.value = 0
            for bone in arm.pose.bones:
                bone.rotation_mode = 'QUATERNION'
                bone.matrix_basis = Matrix.Identity(4)
            bpy.context.view_layer.update()
            pose.apply(action if action in ('idle', 'explain') else 'idle', 2 if action == 'explain' else 0, 4)
            if action in ('happy', 'blink_aa'):
                expressions = ext.vrm1.expressions.all_name_to_expression_dict()
                weights = {'happy': .7} if action == 'happy' else {'blink': 1., 'aa': .55}
                for expression_name, weight in weights.items():
                    for bind in expressions[expression_name].morph_target_binds:
                        obj = bpy.data.objects[bind.node.mesh_object_name]
                        obj.data.shape_keys.key_blocks[bind.index].value += weight * bind.weight
                bpy.context.view_layer.update()
            if action == 'wave':
                wave.apply(1.5, 3, pose.signs['right'])
            if variant.repair_shoulders:
                from avatar3d.shoulder_repair import skin_coverage
                coverage = skin_coverage(arm, bpy.data.objects['C_BlackHighNeck'], evaluated=True)
                if coverage['uncovered']:
                    raise ValueError(f'{key}姿态下内搭未覆盖检查区域：{coverage}')
                posed_coverage[key] = coverage
            target = Vector(camera_settings['close_target' if close else 'full_target'])
            camera.data.ortho_scale = camera_settings['close_scale' if close else 'full_scale']
            angle = math.radians(degrees)
            camera.location = target + Vector((5 * math.sin(angle), -5 * math.cos(angle), 0))
            camera.rotation_euler = (target - camera.location).to_track_quat('-Z', 'Y').to_euler()
            scene.render.filepath = str(folder / f'{key}.png')
            bpy.ops.render.render(write_still=True)
            print('RENDERED', variant.key, key, flush=True)
        results.append({'key': variant.key, 'label': variant.label, 'changed_meshes': changed,
                        'bounds': bounds, 'unchanged_geometry_checked': len(before['meshes']) - len(changed),
                        'skeleton_unchanged': True, 'binding_unchanged': not bool(topology_targets),
                        'topology_changed_meshes': list(topology_targets), 'repair_report': repair_report, 'audit': audit,
                        'face_report': face_report,
                        'posed_coverage': posed_coverage,
                        'files': {p.name: digest(p) for p in folder.iterdir() if p.is_file()}})
    if digest(source) != request['source_sha256']:
        raise ValueError('源模型发生变化。')
    atomic_json(output / 'complete.json', {'schema': 1, 'revision': revision,
        'source_sha256': request['source_sha256'], 'camera_settings': camera_settings,
        'variants': results, 'visual_accepted': False, 'target_runtime_verified': False})
    print('COLLAR_STUDY_COMPLETE', flush=True)


if __name__ == '__main__':
    main()
