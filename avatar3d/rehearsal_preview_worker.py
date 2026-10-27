"""Blender子进程：只读取已烘焙曲线，逐帧产生可恢复的派生图片。"""
from pathlib import Path
import json
import os
import sys

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from avatar3d.models import atomic_json, digest
from avatar3d.rehearsal_preview import source_info


def main():
    job = json.loads(Path(sys.argv[sys.argv.index('--') + 1]).read_text(encoding='utf-8'))
    folder = Path(job['output'])
    settings = json.loads((folder / 'preview-request.json').read_text(encoding='utf-8'))
    verified = source_info(settings['source'])
    if any(settings[k] != v for k, v in verified.items()):
        raise ValueError('源母版在启动前发生变化。')
    sys.path.insert(0, job['addon'])
    bpy.ops.preferences.addon_enable(module='io_scene_vrm')
    bpy.ops.wm.open_mainfile(filepath=str(Path(settings['source']) / 'scene.blend'), use_scripts=False)
    scene = bpy.context.scene
    if scene.frame_end != settings['frames'] or scene.render.fps != settings['fps']:
        raise ValueError('工程时间线与请求不一致。')
    scene.render.engine = settings['engine']
    if settings['quality'] == 'motion':
        scene.display.shading.light = 'STUDIO'
        scene.display.shading.color_type = 'SINGLE'
        scene.display.shading.single_color = (0.65, 0.65, 0.65)
        scene.display.shading.show_shadows = True
        scene.display.shading.show_cavity = True
        scene.display.shading.show_specular_highlight = False
        scene.display.render_aa = '8'
    else:
        scene.eevee.taa_render_samples = settings['samples']
    scene.render.use_persistent_data = True
    scene.render.resolution_x = settings['width']
    scene.render.resolution_y = settings['height']
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.film_transparent = True
    frames = folder / 'frames'
    for index in job['pending']:
        scene.frame_set(index + 1)
        destination = frames / f'{index:05d}.png'
        partial = frames / f'{index:05d}.partial.png'
        scene.render.filepath = str(partial)
        bpy.ops.render.render(write_still=True)
        os.replace(partial, destination)
        destination.with_suffix('.sha256').write_text(digest(destination), encoding='ascii')
        atomic_json(folder / 'progress.json', {'last_frame': index, 'total': settings['frames']})
    # 不保存工程：灯光采样和预览设置仅作用于本进程。
    if digest(Path(settings['source']) / 'scene.blend') != settings['master_sha256']:
        raise ValueError('母版被外部修改。')


if __name__ == '__main__':
    main()
