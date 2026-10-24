"""仅用于C初模：切齐袖色边界、扩大内搭肩颈覆盖，不改变人体或骨架。"""
import math

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

from avatar3d.appearance_study import shoulder_underlayer

SEAM_X = .172


def skin_coverage(arm, shirt, evaluated=False):
    """T姿态颈根皮肤采样的径向遮盖检查；不等同动态碰撞检查。"""
    body = next(o for o in arm.children_recursive if o.type == 'MESH' and
                any(m and 'Body_00_SKIN' in m.name for m in o.data.materials))
    if evaluated:
        graph = bpy.context.evaluated_depsgraph_get()
        shirt, body = shirt.evaluated_get(graph), body.evaluated_get(graph)
    points = [shirt.matrix_world @ v.co for v in shirt.data.vertices]
    tree = BVHTree.FromPolygons(points, [tuple(p.vertices) for p in shirt.data.polygons])
    samples = {}
    for face in body.data.polygons:
        if 'Body_00_SKIN' not in body.data.materials[face.material_index].name:
            continue
        vertices = [body.matrix_world @ body.data.vertices[i].co for i in face.vertices]
        points = list(vertices)
        # 检查三角面内部，不能只靠顶点判断覆盖（两层表面之间仍可能露出细缝）。
        for j in range(1, len(vertices) - 1):
            a, b, c = vertices[0], vertices[j], vertices[j + 1]
            points.extend(a * (i / 4) + b * (k / 4) + c * (1 - (i + k) / 4)
                          for i in range(5) for k in range(5 - i))
        for point in points:
            if .03 < abs(point.x) < .145 and 1.42 < point.z < 1.48:
                direction = Vector((point.x, point.y, 0))
                skin_radius = direction.length
                location, _, _, distance = tree.ray_cast(Vector((0, 0, point.z)), direction.normalized(), 1)
                samples[tuple(round(v, 7) for v in point)] = {'covered': location is not None and distance > skin_radius + .0001,
                              'margin': None if location is None else distance - skin_radius}
    if not samples:
        raise ValueError('当前基础网格没有预期的颈根检查区域。')
    return {'samples': len(samples), 'uncovered': sum(not p['covered'] for p in samples.values()),
            'min_margin': min(p['margin'] for p in samples.values() if p['margin'] is not None),
            'uncovered_points': [list(point) for point, value in samples.items() if not value['covered']]}


def repair(arm):
    meshes = {o.name: o for o in arm.children_recursive if o.type == 'MESH'}
    shirt, jacket = (meshes[n] for n in ('C_BlackHighNeck', 'C_TailoredJacket'))
    if shirt.data.shape_keys or jacket.data.shape_keys:
        raise ValueError('此局部修复不支持带形状键的服装；需另建配方。')
    before_coverage = skin_coverage(arm, shirt)
    inverse = shirt.matrix_world.inverted()
    for vertex in shirt.data.vertices:
        vertex.co = inverse @ Vector(shoulder_underlayer(shirt.matrix_world @ vertex.co))
    after_coverage = skin_coverage(arm, shirt)
    if after_coverage['uncovered'] or after_coverage['min_margin'] <= 0:
        raise ValueError('内搭仍未覆盖所检查的颈根皮肤。')

    materials = [m.name for m in jacket.data.materials]
    ivory = next(i for i, name in enumerate(materials) if name.startswith('C_TexturedIvoryCloth'))
    dark = next(i for i, name in enumerate(materials) if name.startswith('C_TexturedDarkSleeves'))
    if len(materials) != 2:
        raise ValueError('外套材质结构不匹配，停止局部修复。')
    matrix = jacket.matrix_world
    if max(abs(matrix[r][c] - (1 if r == c else 0)) for r in range(4) for c in range(4)) > 1e-5:
        raise ValueError('外套变换需为已应用的单位矩阵。')
    original_points = [v.co.copy() for v in jacket.data.vertices]
    original_tree = BVHTree.FromPolygons(original_points, [tuple(p.vertices) for p in jacket.data.polygons])
    original_area = sum(p.area for p in jacket.data.polygons)
    original_count = len(original_points)
    bm = bmesh.new()
    try:
        bm.from_mesh(jacket.data)
        for side in (-1, 1):
            bmesh.ops.bisect_plane(bm, geom=[*bm.verts, *bm.edges, *bm.faces], dist=1e-7,
                plane_co=(side * SEAM_X, 0, 0), plane_no=(1, 0, 0),
                clear_inner=False, clear_outer=False)
        for face in bm.faces:
            face.material_index = dark if abs(face.calc_center_median().x) > SEAM_X else ivory
        layer = bm.verts.layers.deform.active
        if layer is None:
            raise ValueError('外套没有蒙皮数据。')
        for vertex in bm.verts:
            weights = vertex[layer]
            total = sum(weights.values())
            if total <= 0 or any(not math.isfinite(w) or w < 0 for w in weights.values()):
                raise ValueError('切分产生无效蒙皮权重。')
            for key in weights.keys():
                weights[key] /= total
        bm.normal_update()
        bm.to_mesh(jacket.data)
    finally:
        bm.free()
    jacket.data.update()
    max_surface_distance = max(original_tree.find_nearest(v.co)[3] for v in jacket.data.vertices)
    relative_area_error = abs(sum(p.area for p in jacket.data.polygons) - original_area) / original_area
    crossings = 0
    for face in jacket.data.polygons:
        xs = [jacket.data.vertices[i].co.x for i in face.vertices]
        for plane in (-SEAM_X, SEAM_X):
            crossings += min(xs) < plane - 1e-6 and max(xs) > plane + 1e-6
    if max_surface_distance > 1e-5 or relative_area_error > 1e-5 or crossings:
        raise ValueError('袖色切分改变了表面或仍有跨界三角面。')
    return {'coverage_before': before_coverage, 'coverage_after': after_coverage,
            'jacket_vertices_before': original_count, 'jacket_vertices_after': len(jacket.data.vertices),
            'max_surface_distance_m': max_surface_distance, 'relative_area_error': relative_area_error,
            'crossing_faces_after': crossings, 'normalized_skin_weights': True}
