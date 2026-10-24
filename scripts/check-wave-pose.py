"""Run with Blender: verify wave palm, elbow, endpoints and repeatability on VRM rigs."""
import argparse,json,math,sys
from pathlib import Path
import bpy
from mathutils import Matrix,Vector

p=argparse.ArgumentParser();p.add_argument('--addon',required=True);p.add_argument('--output',required=True);p.add_argument('--model',action='append',required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'avatar3d'))
sys.path.insert(0,a.addon)
from wave_pose import WavePose
bpy.ops.preferences.addon_enable(module='io_scene_vrm')
reports=[]
for path in a.model:
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.vrm(filepath=path)
    arm=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
    e=arm.data.vrm_addon_extension
    bones={str(k.value):v.node.bone_name for k,v in e.vrm1.humanoid.human_bones.human_bone_name_to_human_bone().items()}
    bpy.context.view_layer.update();pose=WavePose(arm,bones)
    sign=1 if pose.rest['rightUpperArm'].translation.x>pose.rest['hips'].translation.x else -1
    def sample(i):
        for b in arm.pose.bones:b.matrix_basis=Matrix.Identity(4)
        bpy.context.view_layer.update()
        result=pose.apply(i/89*3,3,sign)
        result['rotations']=[(arm.matrix_world@arm.pose.bones[bones['right'+suffix]].matrix).to_quaternion().copy() for suffix in ('UpperArm','LowerArm','Hand')]
        return result
    samples=[sample(i) for i in range(90)]
    def angle(q,r):
        rad=q.rotation_difference(r).angle
        return math.degrees(min(rad,math.tau-rad))
    peak=min(s['palm_forward_dot'] for s in samples if s['weight']>.999)
    elbow=[s['elbow_flex_degrees'] for s in samples]
    step=max(angle(q,r) for x,y in zip(samples,samples[1:]) for q,r in zip(x['rotations'],y['rotations']))
    closure=max(angle(q,r) for q,r in zip(samples[0]['rotations'],samples[-1]['rotations']))
    replay=max(angle(q,r) for i in (0,23,45,66,89) for q,r in zip(samples[i]['rotations'],sample(i)['rotations']))
    assert peak>.98,(path,'palm',peak)
    assert min(elbow)>2 and max(elbow)<155,(path,'elbow',min(elbow),max(elbow))
    assert step<25,(path,'frame rotation jump',step)
    assert closure<.1 and replay<.1,(path,'closure/replay',closure,replay)
    reports.append({'model':path,'frames':90,'fps':30,'palm_forward_min_dot_at_hold':peak,'elbow_min_max_degrees':[min(elbow),max(elbow)],'max_frame_rotation_degrees':step,'endpoint_error_degrees':closure,'replay_error_degrees':replay,'passed':True})
Path(a.output).write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf-8')
print('WAVE_POSE_CHECKS_PASSED',flush=True)
