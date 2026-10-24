"""固定项目脚本的Blender进程入口。只导入VRM数据，不打开第三方blend。"""
from pathlib import Path
import sys,json,traceback,math,types
# 冻结目录根还有Python3.12的pyd；不得加入Blender(Python3.11)的模块搜索路径。
# 仅把纯Python协议目录暴露为私有命名空间。
package=types.ModuleType('earthlog_render');package.__path__=[str(Path(__file__).resolve().parent)]
sys.modules['earthlog_render']=package
from earthlog_render.contracts import RenderSpec
from earthlog_render.models import atomic_json
from earthlog_render.motion import arm_targets

def main():
    request=json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text(encoding='utf-8'))
    RenderSpec.from_dict({k:request[k] for k in ('schema','model_sha256','action','duration','fps','width','azimuth')})
    folder=Path(request['folder'])
    sys.path.insert(0,request['addon'])
    import bpy,io_scene_vrm
    from mathutils import Vector,Matrix
    bpy.ops.preferences.addon_enable(module='io_scene_vrm')
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    result=bpy.ops.import_scene.vrm(filepath=request['model'])
    if result!={'FINISHED'}:raise RuntimeError('VRM插件未成功导入。')
    armatures=[o for o in bpy.context.scene.objects if o.type=='ARMATURE']
    if len(armatures)!=1:raise ValueError('当前后端要求模型只有一个人形骨架。')
    arm=armatures[0];ext=arm.data.vrm_addon_extension
    # 插件首次构建材质库可能带回默认场景Cube；只保留角色层级，隔离场景与角色。
    keep={arm,*arm.children_recursive}
    for obj in tuple(scene_obj for scene_obj in bpy.context.scene.objects if scene_obj not in keep):
        bpy.data.objects.remove(obj,do_unlink=True)
    if ext.is_vrm1():
        bones={str(name.value):bone.node.bone_name for name,bone in ext.vrm1.humanoid.human_bones.human_bone_name_to_human_bone().items()}
    else:bones={b.bone:b.node.bone_name for b in ext.vrm0.humanoid.human_bones}
    def bone(key):return arm.pose.bones[bones[key]]
    def position(key):return arm.matrix_world@bone(key).head
    bpy.context.view_layer.update()
    hips=position('hips');head=position('head')
    foot=min(position('leftFoot').z,position('rightFoot').z)
    height=max(.5,head.z-foot+.2)
    # 人形映射给出语义，左右轴方向从实际绑定位置取得，不硬编码骨骼本地轴。
    signs={side:(1 if position(side+'UpperArm').x>hips.x else -1) for side in ('left','right')}
    def orient(key,direction):
        p=bone(key);world=arm.matrix_world@p.matrix
        current=world.to_quaternion()@Vector((0,1,0))
        delta=current.rotation_difference(Vector(direction).normalized())
        changed=delta.to_matrix().to_4x4()@world
        changed.translation=world.translation
        p.matrix=arm.matrix_world.inverted()@changed
        bpy.context.view_layer.update()
    from earthlog_render.wave_pose import WavePose
    wave_pose=WavePose(arm,bones) if request['action']=='wave' else None
    wave_checks=[]
    from earthlog_render.natural_pose import NaturalPose
    natural_pose=NaturalPose(arm,bones) if request['action'] in ('idle','explain') else None
    natural_checks=[]
    mouth_pose=None;mouth_checks=[]
    if request.get('mouth_track'):
        from earthlog_render.models import digest
        from earthlog_render.mouth_pose import MouthPose
        track_path=Path(request['mouth_track'])
        if digest(track_path)!=request['mouth_track_sha256']:raise ValueError('口型曲线与请求快照不一致。')
        mouth_pose=MouthPose(arm,json.loads(track_path.read_text(encoding='utf-8')))
    scene=bpy.context.scene
    scene.render.engine='BLENDER_EEVEE_NEXT';scene.eevee.taa_render_samples=16
    scene.render.resolution_x=request['width'];scene.render.resolution_y=request['width']*3//2;scene.render.resolution_percentage=100
    scene.render.film_transparent=True;scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGBA'
    scene.render.image_settings.color_depth='8';scene.render.fps=request['fps'];scene.view_settings.view_transform='Standard'
    scene.frame_start=1;scene.frame_end=round(request['duration']*request['fps'])
    world=bpy.data.worlds.new('EarthLogStudio');scene.world=world;world.use_nodes=True
    world.node_tree.nodes['Background'].inputs['Color'].default_value=(.5,.5,.5,1)
    world.node_tree.nodes['Background'].inputs['Strength'].default_value=.8
    light=bpy.data.lights.new('SoftKey','AREA');light.energy=180;light.shape='DISK';light.size=4
    light_obj=bpy.data.objects.new('SoftKey',light);scene.collection.objects.link(light_obj)
    light_obj.location=(hips.x-2,-3,head.z+2);light_obj.rotation_euler=(Vector((hips.x,0,head.z))-light_obj.location).to_track_quat('-Z','Y').to_euler()
    camera=bpy.data.objects.new('Camera',bpy.data.cameras.new('Camera'));scene.collection.objects.link(camera);scene.camera=camera
    camera.data.type='ORTHO';camera.data.ortho_scale=height*1.17
    target=Vector((hips.x,hips.y,foot+height*.52))
    if request.get('framing')=='bust':
        camera.data.ortho_scale=height*.50
        target=Vector((hips.x,hips.y,head.z-height*.09))
    elif request.get('framing','full')!='full':raise ValueError('未知构图。')
    def place_camera(degrees):
        a=math.radians(degrees);camera.location=target+Vector((math.sin(a)*height*3,-math.cos(a)*height*3,0))
        camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
    total=round(request['duration']*request['fps'])
    report={'engine':scene.render.engine,'blender':bpy.app.version_string,'humanoid_bones':bones,
        'armature_count':len(armatures),'mesh_count':sum(o.type=='MESH' for o in scene.objects),'height':height,
        'model_sha256':request['model_sha256'],'model_is_sample':request.get('sample',False)}
    atomic_json(folder/'scene-report.json',report)
    for index in range(total):
        t=index/request['fps'];phase=index/max(1,total-1)
        scene.frame_set(index+1)
        for p in arm.pose.bones:
            p.rotation_mode='QUATERNION'
            p.matrix_basis=Matrix.Identity(4)
        bpy.context.view_layer.update()
        action=request['action']
        if natural_pose:
            # 循环不重复最后一帧；单次讲解保留完整收手端点。
            sample_time=t if action=='idle' else phase*request['duration']
            natural_checks.append(natural_pose.apply(action,sample_time,request['duration'],index+1))
        for side in (() if natural_pose else ('left','right')):
            if action=='wave' and side=='right':
                wave_checks.append(wave_pose.apply(phase*request['duration'],request['duration'],signs[side]))
                for suffix in ('UpperArm','LowerArm','Hand'):
                    bone(side+suffix).keyframe_insert('rotation_quaternion',frame=index+1)
                continue
            upper,lower=arm_targets(action,t,request['duration'],side,signs[side])
            orient(side+'UpperArm',upper);orient(side+'LowerArm',lower);orient(side+'Hand',lower)
            for suffix in ('UpperArm','LowerArm','Hand'):
                p=bone(side+suffix)
                p.keyframe_insert('rotation_quaternion',frame=index+1)
        if mouth_pose:
            mouth_checks.append({'frame':index+1,'seconds':t,'aa':mouth_pose.apply(t,index+1)})
            bpy.context.view_layer.update()
        place_camera(request['azimuth']+(90*math.sin(phase*2*math.pi) if action=='turntable' else 0))
        camera.keyframe_insert('location',frame=index+1);camera.keyframe_insert('rotation_euler',frame=index+1)
        scene.render.filepath=str(folder/'frames'/f'{index:05}.png')
        bpy.ops.render.render(write_still=True)
        atomic_json(folder/'progress.json',{'percent':round((index+1)/total*85)})
    # 保存烘焙后的骨骼动作与相机关键帧，作为可复用且可编辑的生成工程。
    if wave_checks:atomic_json(folder/'wave-pose-checks.json',wave_checks)
    if natural_checks:atomic_json(folder/'natural-pose-checks.json',natural_checks)
    if mouth_checks:atomic_json(folder/'mouth-pose-checks.json',mouth_checks)
    scene.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=str(folder/'scene.blend'))

if __name__=='__main__':
    try:main()
    except BaseException:
        traceback.print_exc();raise
