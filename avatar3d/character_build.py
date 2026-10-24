"""C角色研发制作入口：固定来源、独立输出、不操作图形界面。

运行在项目便携Blender中。产物是可编辑外观初稿，尚非直播成品。
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import sys

import bpy
import bmesh
from mathutils import Vector, Matrix


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    parser.add_argument('--recipe', required=True)
    parser.add_argument('--addon', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    source = Path(args.source).resolve()
    recipe = json.loads(Path(args.recipe).read_text(encoding='utf-8'))
    if sha(source) != recipe['source_sha256']:
        raise ValueError('基础模型SHA256与已审阅配方不一致')
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(Path(args.addon).resolve()))
    bpy.ops.preferences.addon_enable(module='io_scene_vrm')
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    if bpy.ops.import_scene.vrm(filepath=str(source)) != {'FINISHED'}:
        raise RuntimeError('基础模型导入失败')
    arm = next(o for o in bpy.context.scene.objects if o.type == 'ARMATURE')
    keep = {arm, *arm.children_recursive}
    for obj in list(bpy.context.scene.objects):
        if obj not in keep:
            bpy.data.objects.remove(obj, do_unlink=True)
    bones = {b.bone: b.node.bone_name for b in arm.data.vrm_addon_extension.vrm0.humanoid.human_bones}
    palette = recipe['palette']

    def mat(name, color):
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        ext = m.vrm_addon_extension.mtoon1
        ext.enabled = True
        ext.pbr_metallic_roughness.base_color_factor = (*color, 1)
        ext.double_sided = True
        ext.extensions.vrmc_materials_mtoon.shade_color_factor = tuple(c * .72 for c in color)
        ext.extensions.vrmc_materials_mtoon.shading_toony_factor = .85
        ext.extensions.vrmc_materials_mtoon.outline_width_mode = 'worldCoordinates'
        ext.extensions.vrmc_materials_mtoon.outline_width_factor = .00065
        ext.extensions.vrmc_materials_mtoon.outline_color_factor = (.025, .029, .035)
        return m

    materials = {key: mat('C_' + key, value) for key, value in palette.items()}
    face = bpy.data.objects.get('Face')
    body = bpy.data.objects.get('Body')
    hair = bpy.data.objects.get('Hair001')
    if not all((face, body, hair)):
        raise ValueError('来源模型布局改变，停止自动制作')
    # VRM0 importer leaves a 180-degree object transform on mesh objects.
    # Bake it into all shape keys before spatial tailoring so front/back agree.
    for obj in (face, body, hair):
        obj.data.transform(obj.matrix_world, shape_keys=True)
        obj.matrix_world = Matrix.Identity(4)
        obj.data.update()

    def recolor_texture(m, tint, saturated_only=False):
        import numpy as np
        tex = m.vrm_addon_extension.mtoon1.pbr_metallic_roughness.base_color_texture.index.source
        if not tex:
            raise ValueError('来源材质缺少纹理:' + m.name)
        arr = np.empty(len(tex.pixels), dtype=np.float32)
        tex.pixels.foreach_get(arr)
        pixels = arr.reshape((-1, 4))
        rgb = pixels[:, :3]
        lum = rgb @ np.array([.2126, .7152, .0722], dtype=np.float32)
        mask = (rgb.max(axis=1) - rgb.min(axis=1) > .10) if saturated_only else np.ones(len(rgb), dtype=bool)
        rgb[mask] = np.clip(lum[mask, None] * np.array(tint)[None, :], 0, 1)
        new = bpy.data.images.new('C_' + tex.name, width=tex.size[0], height=tex.size[1], alpha=True)
        new.pixels.foreach_set(arr)
        new.pack()
        m.vrm_addon_extension.mtoon1.pbr_metallic_roughness.base_color_texture.index.source = new
        toon = m.vrm_addon_extension.mtoon1.extensions.vrmc_materials_mtoon
        toon.shade_multiply_texture.index.source = new
        toon.shade_color_factor = (.65,.65,.68)
        return new.name

    changed_textures = []
    for m in hair.data.materials:
        changed_textures.append(recolor_texture(m, (.40, .43, .48)))
        m.vrm_addon_extension.mtoon1.extensions.vrmc_materials_mtoon.shade_color_factor = (.12,.13,.15)
    # Select entire connected hair locks, avoiding a hard color boundary through a strand.
    mint_lock = hair.data.materials[0].copy()
    mint_lock.name = 'C_TexturedMintLocks'
    changed_textures.append(recolor_texture(mint_lock, (2.6,4.2,3.5)))
    hair.data.materials.append(mint_lock)
    links = {v.index:set() for v in hair.data.vertices}
    for edge in hair.data.edges:
        a,b=edge.vertices;links[a].add(b);links[b].add(a)
    islands=[];seen=set()
    for start in links:
        if start in seen:continue
        stack=[start];seen.add(start);island=[]
        while stack:
            idx=stack.pop();island.append(idx)
            for nxt in links[idx]-seen:seen.add(nxt);stack.append(nxt)
        islands.append(island)
    colored=set()
    for island in islands:
        center=sum((hair.data.vertices[i].co for i in island),Vector())/len(island)
        if .035<center.x<.085 and center.y<-.055 and center.z>1.67:
            colored.update(island)
    for poly in hair.data.polygons:
        if all(i in colored for i in poly.vertices):poly.material_index=1
    for m in face.data.materials:
        if 'EyeIris' in m.name:
            changed_textures.append(recolor_texture(m, (.78, 1.04, .96), True))

    # 调整脸型时对所有表情使用同一空间变换，保留原表情的相对位移。
    for block in face.data.shape_keys.key_blocks:
        for v in block.data:
            if v.co.z < 1.61:
                f = max(0, min(1, (1.61 - v.co.z) / .11))
                v.co.x *= 1 - .045 * f
    # Preserve continuous shoulder/sleeve topology and original weights while tailoring.
    jacket = body.copy();jacket.data = body.data.copy();jacket.name='C_TailoredJacket'
    bpy.context.scene.collection.objects.link(jacket)
    tops = next(m for m in body.data.materials if 'Tops' in m.name)
    ivory_cloth=tops.copy();ivory_cloth.name='C_TexturedIvoryCloth'
    dark_cloth=tops.copy();dark_cloth.name='C_TexturedDarkSleeves'
    changed_textures.append(recolor_texture(ivory_cloth,(.83,.85,.86)))
    changed_textures.append(recolor_texture(dark_cloth,(.075,.085,.105)))
    jacket.data.materials.append(ivory_cloth);ivory_idx=len(jacket.data.materials)-1
    jacket.data.materials.append(dark_cloth);dark_idx=len(jacket.data.materials)-1
    bm=bmesh.new();bm.from_mesh(jacket.data)
    remove=[f for f in bm.faces if 'Tops' not in jacket.data.materials[f.material_index].name]
    bmesh.ops.delete(bm,geom=remove,context='FACES')
    # Remove separate hoodie cords and trim islands, retaining the continuous garment.
    components=[];visited=set()
    for first in bm.faces:
        if first in visited:continue
        stack=[first];visited.add(first);component=[]
        while stack:
            f=stack.pop();component.append(f)
            for v in f.verts:
                for neighbor in v.link_faces:
                    if neighbor not in visited:visited.add(neighbor);stack.append(neighbor)
        components.append(component)
    largest=max(components,key=lambda faces:sum(f.calc_area() for f in faces))
    keep_faces=set(largest)
    # The sample's sleeves are separate welded islands; preserve both arm regions.
    for component in components:
        center=sum((f.calc_center_median() for f in component),Vector())/len(component)
        if abs(center.x)>.20 and 1.25<center.z<1.48:
            keep_faces.update(component)
    bmesh.ops.delete(bm,geom=[f for f in bm.faces if f not in keep_faces],context='FACES')
    for x in (-.048,.048):
        bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),dist=.00001,plane_co=(x,0,0),plane_no=(1,0,0))
    remove=[]
    for f in bm.faces:
        c=f.calc_center_median()
        if (abs(c.x)<.0481 and c.y<-.005) or (c.z>1.447 and abs(c.x)<.15):remove.append(f)
        else:f.material_index=dark_idx if abs(c.x)>.172 else ivory_idx
    bmesh.ops.delete(bm,geom=remove,context='FACES')
    for v in bm.verts:
        if abs(v.co.x)<.25 and v.co.z<1.17:
            v.co.z=1.17+(v.co.z-1.17)*recipe['coat_length_scale']
            v.co.x*=1.025
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    bm.to_mesh(jacket.data);bm.free()
    mod=jacket.modifiers.new('TailoredFabricThickness','SOLIDIFY');mod.thickness=.002
    bm=bmesh.new();bm.from_mesh(body.data)
    remove=[]
    for f in bm.faces:
        name=body.data.materials[f.material_index].name;c=f.calc_center_median()
        if 'Tops' in name or ('Body' in name and .97<c.z<1.455 and abs(c.x)<.19):remove.append(f)
    bmesh.ops.delete(bm,geom=remove,context='FACES');bm.to_mesh(body.data);bm.free()

    def skin(obj, fixed=None):
        obj.parent = arm
        mod = obj.modifiers.new('C_HumanoidSkin', 'ARMATURE')
        mod.object = arm
        groups = {}
        def add(name, idx, w):
            if name not in groups:
                groups[name] = obj.vertex_groups.new(name=name)
            groups[name].add([idx], w, 'REPLACE')
        levels = [(1.04, 'hips'), (1.17, 'spine'), (1.28, 'chest'), (1.40, 'upperChest')]
        for v in obj.data.vertices:
            if fixed:
                add(bones[fixed], v.index, 1)
                continue
            z = v.co.z
            if z <= levels[0][0]:
                add(bones['hips'], v.index, 1)
            elif z >= levels[-1][0]:
                add(bones['upperChest'], v.index, 1)
            else:
                for (a, ka), (b, kb) in zip(levels, levels[1:]):
                    if a <= z <= b:
                        t = (z - a) / (b - a)
                        add(bones[ka], v.index, 1 - t)
                        add(bones[kb], v.index, t)
                        break

    created = []
    def mesh(name, verts, faces, material, fixed=None, solid=.002):
        data = bpy.data.meshes.new(name)
        data.from_pydata(verts, [], faces)
        data.update()
        obj = bpy.data.objects.new(name, data)
        bpy.context.scene.collection.objects.link(obj)
        data.materials.append(material)
        for p in data.polygons:
            p.use_smooth = True
        skin(obj, fixed)
        if solid:
            mod = obj.modifiers.new('FabricThickness', 'SOLIDIFY')
            mod.thickness = solid
        created.append(obj)
        return obj

    def shell(name, rings, start, end, material, n=48, fixed=None):
        verts = []
        for z, rx, ry in rings:
            for j in range(n + 1):
                a = start + (end - start) * j / n
                verts.append((rx * math.sin(a), -ry * math.cos(a), z))
        faces = [(i*(n+1)+j, i*(n+1)+j+1, (i+1)*(n+1)+j+1, (i+1)*(n+1)+j)
                 for i in range(len(rings)-1) for j in range(n)]
        return mesh(name, verts, faces, material, fixed)

    def tube(name, points, radius, material, fixed=None):
        # Convert to mesh before skinning so it follows pose and exports as geometry.
        cu = bpy.data.curves.new(name, 'CURVE');cu.dimensions = '3D'
        cu.bevel_depth = radius;cu.bevel_resolution = 2;cu.resolution_u = 12
        sp = cu.splines.new('POLY');sp.points.add(len(points)-1)
        for p, co in zip(sp.points, points): p.co = (*co, 1)
        o = bpy.data.objects.new(name, cu);bpy.context.scene.collection.objects.link(o)
        bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.view_layer.objects.active = o
        bpy.ops.object.convert(target='MESH')
        o.data.materials.append(material);skin(o, fixed);created.append(o)
        return o

    shirt = shell('C_BlackHighNeck', [(1.00,.14,.085),(1.12,.14,.085),(1.29,.16,.095),(1.40,.17,.085),(1.445,.072,.064),(1.49,.064,.064)], 0, math.tau, materials['black'])
    # Front ornaments are fitted to the actual jacket surface, not a guessed flat plane.
    from mathutils.bvhtree import BVHTree
    tree=BVHTree.FromPolygons([v.co for v in jacket.data.vertices],[p.vertices[:] for p in jacket.data.polygons])
    def fitted(x,z,offset=.005):
        hit,_,_,_=tree.ray_cast(Vector((x,-1,z)),Vector((0,1,0)))
        return (x,hit.y-offset if hit else -.135,z)
    for side in (-1,1):
        zs=[.80+i*(1.40-.80)/30 for i in range(31)]
        edge=[fitted(side*.053,z,.003) for z in zs]
        tube('C_MintFrontPiping_'+str(side),edge,.0025,materials['mint'])
        # Raised angular collar, distinct from the sample hoodie.
        collar=[(side*.065,-.067,1.405),(side*.124,-.062,1.478),(side*.077,.025,1.515),(side*.056,.055,1.45)]
        mesh('C_StandingCollar_'+str(side),collar,[(0,1,2,3)],materials['ivory'])
        tube('C_CollarTrim_'+str(side),collar[:3],.0023,materials['mint'])
        # Short shoulder harness strips follow upper chest; no simulated cloth yet.
        vs=[fitted(side*.105,1.26),fitted(side*.123,1.26),fitted(side*.148,1.419),fitted(side*.13,1.419)]
        mesh('C_ShoulderHarness_'+str(side),vs,[(0,1,2,3)],materials['black'],solid=.003)
        buckle=[fitted(side*x,z,.008) for x,z in [(.119,1.365),(.143,1.365),(.146,1.392),(.122,1.392),(.119,1.365)]]
        tube('C_GoldShoulderBuckle_'+str(side),buckle,.002,materials['gold'])
    # Waist belt and signature orbital chest badge.
    shell('C_WaistBelt',[(1.005,.162,.103),(1.036,.162,.103)],0,math.tau,materials['black'])
    tube('C_BeltBuckle',[(-.024,-.106,1.008),(.024,-.106,1.008),(.024,-.106,1.036),(-.024,-.106,1.036),(-.024,-.106,1.008)],.0024,materials['gold'])
    badge_center=Vector((.115,-.112,1.30))
    for tilt in (-.55,.55):
        points=[]
        for i in range(49):
            t=math.tau*i/48;x=.024*math.cos(t);z=.013*math.sin(t)
            points.append(fitted(badge_center.x+x*math.cos(tilt)-z*math.sin(tilt),badge_center.z+x*math.sin(tilt)+z*math.cos(tilt),.008))
        tube('C_OrbitBadge',points,.0014,materials['gold'])
    tube('C_ChestClasp',[(-.048,-.106,1.267),(.048,-.106,1.267)],.004,materials['charcoal'])
    tube('C_ChestDiamond',[(-.015,-.112,1.267),(0,-.112,1.277),(.015,-.112,1.267),(0,-.112,1.257),(-.015,-.112,1.267)],.0015,materials['gold'])
    for side in (-1,1):
        tube('C_Earring_'+str(side),[(side*.105,-.015,1.562),(side*.108,-.018,1.532)],.0015,materials['gold'],'head')

    # Mark provenance on the editable scene; retain the source expressions and spring settings.
    arm['character_id']='correspondent-c'
    arm['asset_stage']='appearance_draft_not_live_ready'
    arm['base_source_sha256']=sha(source)
    arm['recipe_sha256']=sha(args.recipe)
    arm['build_script_sha256']=sha(__file__)
    scene=bpy.context.scene
    scene.render.engine='BLENDER_EEVEE_NEXT';scene.eevee.taa_render_samples=24
    bpy.context.preferences.filepaths.save_version=0
    scene.render.resolution_x=720;scene.render.resolution_y=1080;scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGBA'
    scene.render.film_transparent=True;scene.view_settings.view_transform='Standard'
    world=bpy.data.worlds.new('C_Studio');scene.world=world;world.use_nodes=True
    world.node_tree.nodes['Background'].inputs['Color'].default_value=(.35,.38,.42,1)
    world.node_tree.nodes['Background'].inputs['Strength'].default_value=.65
    for name,loc,energy,size in [('Key',(-2,-3,3.5),200,4),('Fill',(2,-1,2),70,3)]:
        light=bpy.data.objects.new(name,bpy.data.lights.new(name,'AREA'));scene.collection.objects.link(light)
        light.location=loc;light.data.energy=energy;light.data.size=size
        light.rotation_euler=(Vector((0,0,1.2))-light.location).to_track_quat('-Z','Y').to_euler()
    camera=bpy.data.objects.new('Camera',bpy.data.cameras.new('Camera'));scene.collection.objects.link(camera);scene.camera=camera;camera.data.type='ORTHO'
    def camera_at(degrees,portrait=False):
        target=Vector((0,0,1.43 if portrait else .91));a=math.radians(degrees)
        camera.location=target+Vector((3*math.sin(a),-3*math.cos(a),.02))
        camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
        camera.data.ortho_scale=.89 if portrait else 1.98
    def orient(key,direction):
        p=arm.pose.bones[bones[key]];world=arm.matrix_world@p.matrix
        current=world.to_quaternion()@Vector((0,1,0));delta=current.rotation_difference(Vector(direction).normalized())
        changed=delta.to_matrix().to_4x4()@world;changed.translation=world.translation
        p.matrix=arm.matrix_world.inverted()@changed;bpy.context.view_layer.update()
    def pose(mode):
        for p in arm.pose.bones:p.matrix_basis=Matrix.Identity(4)
        bpy.context.view_layer.update()
        for side in ('left','right'):
            sign=1 if arm.data.bones[bones[side+'UpperArm']].head_local.x>0 else -1
            upper=(sign*.14,0,-1);lower=(sign*.035,-.05,-1)
            if mode=='bend' and side=='right':lower=(-sign*.45,-.7,.45)
            if mode=='wave' and side=='right':upper=(sign*.85,0,-.4);lower=(sign*.05,-.1,1)
            orient(side+'UpperArm',upper);orient(side+'LowerArm',lower);orient(side+'Hand',lower)
    pose('neutral');camera_at(0)
    # Save unposed rest asset separately for future skin/VRM work; review scene saves neutral pose.
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'C-appearance.blend'))
    report={'stage':'appearance_draft','source':str(source),'source_sha256':sha(source),'recipe':recipe,
            'blender':bpy.app.version_string,'build_script_sha256':sha(__file__),'created_meshes':len(created)+1,'humanoid_bones':bones,
            'shape_keys':len(face.data.shape_keys.key_blocks),'textures_modified':changed_textures,
            'limitations':['VRM派生与运行器尚未验证','肩袖沿用基础蒙皮，延长衣摆和新增配饰仍需动态精修','发丝尚未设置独立物理骨骼','造型尚未经用户验收']}
    write_json(out/'build-report.json',report)
    for name,angle,portrait,mode in [('front',0,False,'neutral'),('three-quarter',35,True,'neutral'),('side',90,False,'neutral'),('back',180,False,'neutral'),('bend',-25,True,'bend'),('wave',0,True,'wave')]:
        pose(mode);camera_at(angle,portrait);scene.render.filepath=str(out/(name+'.png'));bpy.ops.render.render(write_still=True)
    pose('neutral');camera_at(0)
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'C-appearance.blend'))
    write_json(out/'complete.json',{'files':{p.name:sha(p) for p in out.iterdir() if p.is_file() and p.suffix in ('.blend','.png','.json')}})


if __name__=='__main__':
    main()
