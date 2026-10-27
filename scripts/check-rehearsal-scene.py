"""重开已生成的排练母版，独立检查900帧曲线、循环底层和复播。"""
from pathlib import Path
import json,sys,math
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import bpy
from avatar3d.models import digest,atomic_json

folder=Path(sys.argv[sys.argv.index('--')+1]).resolve()
output=Path(sys.argv[sys.argv.index('--')+2]).resolve()
record=json.loads((folder/'rehearsal-complete.json').read_text(encoding='utf-8'))
assert digest(folder/'scene.blend')==record['files']['scene.blend']
runtime=json.loads((ROOT/'.runtime/avatar3d/runtime.json').read_text(encoding='utf-8'))
sys.path.insert(0,runtime['addon']);bpy.ops.preferences.addon_enable(module='io_scene_vrm')
bpy.ops.wm.open_mainfile(filepath=str(folder/'scene.blend'),use_scripts=False)
scene=bpy.context.scene;arm=next(o for o in scene.objects if o.type=='ARMATURE')
bones=json.loads((folder/'scene-report.json').read_text(encoding='utf-8'))['humanoid_bones']
request=json.loads((folder/'request.json').read_text(encoding='utf-8'))
total=round(request['duration']*request['fps']);period=round(request['rehearsal']['idle_period']*request['fps'])
assert scene.frame_end==total and scene.render.fps==30
protected=[v for k,v in bones.items() if v and not (k.startswith('right') and any(s in k for s in ('Arm','Hand','Thumb','Index','Middle','Ring','Little')))]
def angle(a,b):
    value=math.degrees(a.rotation_difference(b).angle)
    return min(value,360-value)
samples=[];max_jump=0;max_cycle_error=0;max_root=0
for index in range(total):
    scene.frame_set(index+1);bpy.context.view_layer.update()
    pose={b.name:b.rotation_quaternion.copy() for b in arm.pose.bones}
    if samples:max_jump=max(max_jump,max(angle(pose[n],q) for n,q in samples[-1].items()))
    if index>=period:max_cycle_error=max(max_cycle_error,max(angle(pose[n],samples[index%period][n]) for n in protected))
    max_root=max(max_root,arm.pose.bones[bones['hips']].location.length)
    samples.append(pose)
replay=0
for index in (total-1,0,450,135,750,299,0):
    scene.frame_set(index+1);bpy.context.view_layer.update()
    replay=max(replay,max(angle(b.rotation_quaternion,samples[index][b.name]) for b in arm.pose.bones))
assert max_cycle_error<.1 and replay<.1 and max_root<1e-6
assert max_jump<30, '骨骼相邻帧跳变超过30度，需返修'
atomic_json(output,{'baked_frames':total,'fps':scene.render.fps,'bone_count':len(samples[0]),
    'max_adjacent_degrees':max_jump,'protected_cycle_error_degrees':max_cycle_error,
    'reverse_seek_replay_error_degrees':replay,'root_translation':max_root,
    'passed':True,'warudo_mixing':'not tested','visual_naturalness':'pending manual review'})
print('REHEARSAL_REPLAY_OK')
