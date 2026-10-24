"""Blender中检查脸型候选导出后的13项表情是否仍实际变形。"""
import argparse
import json
import math
from pathlib import Path
import sys

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from avatar3d.models import digest

REQUIRED = ('happy', 'angry', 'sad', 'relaxed', 'surprised',
            'aa', 'ih', 'ou', 'ee', 'oh', 'blink', 'blinkLeft', 'blinkRight')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', action='append', type=Path, required=True)
    parser.add_argument('--addon', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    if args.output.exists():
        raise FileExistsError('检查报告已存在。')
    sys.path.insert(0, str(args.addon))
    bpy.ops.preferences.addon_enable(module='io_scene_vrm')
    reports = []
    for model in args.model:
        for obj in tuple(bpy.context.scene.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        source_hash = digest(model)
        bpy.ops.import_scene.vrm(filepath=str(model))
        arm = next(obj for obj in bpy.context.scene.objects if obj.type == 'ARMATURE')
        ext = arm.data.vrm_addon_extension
        ext.spring_bone1.enable_animation = False
        meshes = [obj for obj in arm.children_recursive if obj.type == 'MESH' and obj.data.shape_keys]
        expressions = ext.vrm1.expressions.all_name_to_expression_dict()

        def reset():
            for obj in meshes:
                for key in obj.data.shape_keys.key_blocks:
                    key.value = 0
            bpy.context.view_layer.update()

        def coordinates():
            graph = bpy.context.evaluated_depsgraph_get()
            return {obj.name: [vertex.co.copy() for vertex in obj.evaluated_get(graph).data.vertices] for obj in meshes}

        reset()
        baseline = coordinates()
        shape_keys = {obj.name: len(obj.data.shape_keys.key_blocks) for obj in meshes}
        for obj in meshes:
            for key in obj.data.shape_keys.key_blocks:
                if any(not math.isfinite(value) for vertex in key.data for value in vertex.co):
                    raise ValueError('存在无效的形状键坐标。')
        changes = {}
        for name in REQUIRED:
            reset()
            expr = expressions[name]
            if not expr.morph_target_binds:
                raise ValueError('缺少表情绑定：' + name)
            for bind in expr.morph_target_binds:
                obj = bpy.data.objects[bind.node.mesh_object_name]
                obj.data.shape_keys.key_blocks[bind.index].value += bind.weight
            bpy.context.view_layer.update()
            current = coordinates()
            maximum = max((a - b).length for mesh in baseline
                          for a, b in zip(baseline[mesh], current[mesh]))
            if not 1e-5 < maximum < .15:
                raise ValueError('表情未变形或超出预期范围：' + name)
            changes[name] = maximum
        if digest(model) != source_hash:
            raise ValueError('检查期间模型变化。')
        reports.append({'model': str(model), 'sha256': source_hash, 'shape_keys': shape_keys,
                        'expression_max_displacement_m': changes, 'finite_coordinates': True,
                        'visual_accepted': False, 'warudo_verified': False})
        print('EXPRESSIONS_PASSED', model.parent.name, flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
