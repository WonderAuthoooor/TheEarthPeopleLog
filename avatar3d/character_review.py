"""验证自有制作产物，生成VRM1派生与360度检查帧。仅接受制作完成清单。"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import sys

import bpy
from mathutils import Matrix, Vector


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--folder',required=True)
    p.add_argument('--addon',required=True)
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    folder=Path(args.folder).resolve()
    manifest=json.loads((folder/'complete.json').read_text(encoding='utf-8'))
    source=folder/'C-appearance.blend'
    if digest(source)!=manifest['files']['C-appearance.blend']:
        raise ValueError('自有Blender制作产物校验不一致')
    output=folder/'review'
    output.mkdir(exist_ok=False)
    sys.path.insert(0,str(Path(args.addon).resolve()))
    bpy.ops.preferences.addon_enable(module='io_scene_vrm')
    bpy.ops.wm.open_mainfile(filepath=str(source),use_scripts=False)
    scene=bpy.context.scene
    arm=next(o for o in scene.objects if o.type=='ARMATURE')
    ext=arm.data.vrm_addon_extension
    old_bones={b.bone:b.node.bone_name for b in ext.vrm0.humanoid.human_bones}
    saved_pose={b.name:b.matrix_basis.copy() for b in arm.pose.bones}
    for bone in arm.pose.bones:bone.matrix_basis=Matrix.Identity(4)
    bpy.context.view_layer.update()
    ext.spec_version='1.0'
    mapping={str(k.value):v for k,v in ext.vrm1.humanoid.human_bones.human_bone_name_to_human_bone().items()}
    for name,bone in old_bones.items():
        if name.endswith('ThumbProximal'):name=name.replace('ThumbProximal','ThumbMetacarpal')
        elif name.endswith('ThumbIntermediate'):name=name.replace('ThumbIntermediate','ThumbProximal')
        if name in mapping:mapping[name].node.bone_name=bone
    bpy.ops.vrm.assign_vrm1_expressions_from_vrm0(armature_object_name=arm.name)
    meta=ext.vrm1.meta
    meta.vrm_name='C Correspondent - appearance draft'
    meta.version='0.1.4-draft'
    meta.authors.clear()
    meta.authors.add().value='VRoid Project (CC0 beta base)'
    meta.authors.add().value='C character project (adaptation)'
    meta.references.add().value='https://vroid.pixiv.help/hc/en-us/articles/4402614652569'
    meta.copyright_information='Historical VRoid beta base: CC0. New adaptation: local project draft; no public release license assigned.'
    meta.other_license_url=''
    meta.avatar_permission='onlyAuthor'
    meta.commercial_usage='personalProfit'
    meta.credit_notation='unnecessary'
    meta.modification='allowModification'
    meta.allow_redistribution=False
    meta.allow_political_or_religious_usage=True
    bpy.context.view_layer.objects.active=arm
    bpy.ops.object.select_all(action='DESELECT')
    for obj in {arm,*arm.children_recursive}:obj.select_set(True)
    result=bpy.ops.export_scene.vrm(filepath=str(output/'C-character.vrm'),armature_object_name=arm.name,export_only_selections=True)
    if result!={'FINISHED'}:raise RuntimeError('VRM1导出失败:'+str(result))
    for bone in arm.pose.bones:bone.matrix_basis=saved_pose[bone.name]
    bpy.context.view_layer.update()
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(output/'C-character.blend'))
    report={'vrm_sha256':digest(output/'C-character.vrm'),'blend_sha256':digest(output/'C-character.blend'),
            'source_blend_sha256':digest(source),'stage':'appearance_draft_not_approved',
            'vrm_version':'1.0','spring_physics':'not_migrated_or_verified',
            'expression_conversion':'VRM addon assign_vrm1_expressions_from_vrm0',
            'manual_acceptance':False,'frames':48,'fps':12}
    (output/'export-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    frames=output/'frames';frames.mkdir()
    scene.render.resolution_x=480;scene.render.resolution_y=720
    scene.eevee.taa_render_samples=16
    camera=scene.camera;camera.data.ortho_scale=1.99
    target=Vector((0,0,.91))
    for i in range(48):
        a=math.tau*i/48
        camera.location=target+Vector((3*math.sin(a),-3*math.cos(a),.02))
        camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
        scene.render.filepath=str(frames/f'{i:04}.png')
        bpy.ops.render.render(write_still=True)
    (output/'frames-complete.json').write_text(json.dumps({'files':{f.name:digest(f) for f in sorted(frames.glob('*.png'))}},indent=2),encoding='utf-8')


if __name__=='__main__':main()
