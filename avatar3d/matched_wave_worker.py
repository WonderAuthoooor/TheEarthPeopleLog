"""以当前模型待机为基线烘焙挥手，保持肩部及未挥手侧。"""
from pathlib import Path
import json
import math
import sys

import bpy
from mathutils import Matrix

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from avatar3d.models import atomic_json, digest
from avatar3d.rehearsal_pose import RehearsalPose


def main():
    job = json.loads(Path(sys.argv[sys.argv.index('--') + 1]).read_text(encoding='utf-8'))
    source, out = Path(job['source']), Path(job['output'])
    if digest(source / 'scene.blend') != job['source_sha256']:
        raise ValueError('待机母版发生变化。')
    sys.path.insert(0, job['addon'])
    bpy.ops.preferences.addon_enable(module='io_scene_vrm')
    bpy.ops.wm.open_mainfile(filepath=str(source / 'scene.blend'), use_scripts=False)
    scene = bpy.context.scene
    arm, = [obj for obj in scene.objects if obj.type == 'ARMATURE']
    bones = job['bones']
    scene.frame_set(1)
    expected = {b.name: b.rotation_quaternion.copy() for b in arm.pose.bones}
    arm.animation_data_clear()
    for obj in scene.objects:
        if obj.type == 'MESH' and obj.data.shape_keys:
            obj.data.shape_keys.animation_data_clear()
    for b in arm.pose.bones:
        b.rotation_mode = 'QUATERNION'
        b.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
    plan = {'duration': 3, 'idle_period': 3, 'fade': .35,
            'gestures': [{'action': 'wave', 'start': 0, 'duration': 3}]}
    pose = RehearsalPose(arm, bones, plan)
    checks = []
    first = None
    for index in range(90):
        scene.frame_set(index + 1)
        checks.append(pose.apply(index * 3 / 89, index + 1))
        now = {b.name: b.rotation_quaternion.copy() for b in arm.pose.bones}
        if first is None:
            first = now
    def angle(a, b):
        v = math.degrees(a.rotation_difference(b).angle)
        return min(v, 360 - v)
    start_error = max(angle(first[n], q) for n, q in expected.items())
    end_error = max(angle(first[n], q) for n, q in now.items())
    if start_error > .01 or end_error > .01 or max(x['unmasked_error_radians'] for x in checks) > .0001:
        raise ValueError('挥手起止未对齐当前待机或修改了遮罩外部位。')
    if max(x['max_step_degrees'] for x in checks) > 30:
        raise ValueError('逐帧骨骼出现明显跳变。')
    scene.frame_start, scene.frame_end, scene.render.fps = 1, 90, 30
    scene.frame_set(1)
    # 保存完整原材质母版；诊断渲染设置只在保存之后改变。
    bpy.ops.wm.save_as_mainfile(filepath=str(out / 'scene.blend'))
    atomic_json(out / 'entry-checks.json', {'start_idle_error_degrees': start_error,
        'end_idle_error_degrees': end_error, 'frames': 90, 'checks': checks})
    scene.render.engine = 'BLENDER_WORKBENCH'
    scene.display.shading.light = 'STUDIO'
    scene.display.shading.color_type = 'SINGLE'
    scene.display.shading.single_color = (.65, .65, .65)
    scene.display.shading.show_cavity = True
    scene.display.shading.show_shadows = True
    scene.display.render_aa = '8'
    scene.render.resolution_x, scene.render.resolution_y = 320, 480
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    for index in range(90):
        scene.frame_set(index + 1)
        scene.render.filepath = str(out / 'frames' / f'{index:05d}.png')
        bpy.ops.render.render(write_still=True)
    if digest(source / 'scene.blend') != job['source_sha256']:
        raise ValueError('处理期间待机母版被改变。')


if __name__ == '__main__':
    main()
