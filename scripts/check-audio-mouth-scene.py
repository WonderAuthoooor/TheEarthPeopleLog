"""用Blender重开本项目已完成口播工程，核对实际嘴形曲线、眨眼及复播。"""
from pathlib import Path
import json
import sys
import math

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import bpy
from avatar3d.models import digest,atomic_json
from avatar3d.audio_mouth import at
from avatar3d.mouth_pose import MouthPose


def main():
    folder=Path(sys.argv[sys.argv.index('--')+1]).resolve()
    output=Path(sys.argv[sys.argv.index('--')+2]).resolve()
    record=json.loads((folder/'complete.json').read_text(encoding='utf-8'))
    request=json.loads((folder/'request.json').read_text(encoding='utf-8'))
    if digest(folder/'scene.blend')!=record['files']['scene.blend']:raise ValueError('工程哈希不匹配。')
    runtime=json.loads((ROOT/'.runtime/avatar3d/runtime.json').read_text(encoding='utf-8'))
    sys.path.insert(0,runtime['addon'])
    bpy.ops.preferences.addon_enable(module='io_scene_vrm')
    bpy.ops.wm.open_mainfile(filepath=str(folder/'scene.blend'),use_scripts=False)
    arm=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
    track=json.loads((folder/'mouth-track.json').read_text(encoding='utf-8'))
    pose=MouthPose(arm,track)
    scene=bpy.context.scene
    error=0.;blink_values=[];weights=[]
    expr=arm.data.vrm_addon_extension.vrm1.expressions.all_name_to_expression_dict()
    blink=expr['blink'].morph_target_binds[0]
    blink_key=bpy.data.objects[blink.node.mesh_object_name].data.shape_keys.key_blocks[blink.index]
    for index in range(record['frames']):
        scene.frame_set(index+1);bpy.context.view_layer.update()
        expected=at(track,index/record['fps'])
        weights.append(expected);blink_values.append(blink_key.value)
        for key,weight in pose.bindings.values():
            error=max(error,abs(key.value-min(1.,expected*weight)))
    if error>1e-5 or max(weights)<.05 or weights[-1]!=0:raise ValueError('保存工程口型曲线异常。')
    if max(blink_values)<.5:raise ValueError('眨眼叠加没有保留。')
    peak=max(range(len(weights)),key=weights.__getitem__)+1
    scene.frame_set(peak);bpy.context.view_layer.update()
    mesh=bpy.data.objects[next(iter(pose.bindings))[0]]
    def vertices():
        evaluated=mesh.evaluated_get(bpy.context.evaluated_depsgraph_get())
        return [v.co.copy() for v in evaluated.data.vertices]
    spoken=vertices()
    for key,_ in pose.bindings.values():key.value=0.
    bpy.context.view_layer.update();closed=vertices()
    deformation=max((a-b).length for a,b in zip(spoken,closed))
    scene.frame_set(1);scene.frame_set(peak);bpy.context.view_layer.update();replay=vertices()
    replay_error=max((a-b).length for a,b in zip(spoken,replay))
    if not math.isfinite(deformation) or deformation<1e-5 or replay_error>1e-6:
        raise ValueError('实际口部变形／复播失败。')
    if digest(request['model'])!=record['model_sha256']:raise ValueError('源模型发生修改。')
    atomic_json(output,{'frames':record['frames'],'fps':record['fps'],'binding_error':error,
                       'max_aa':max(weights),'final_aa':weights[-1],'max_blink':max(blink_values),
                       'mouth_vertex_delta':deformation,'replay_vertex_error':replay_error,
                       'source_unchanged':True,'manual_sync_verified':False})


if __name__=='__main__':main()
