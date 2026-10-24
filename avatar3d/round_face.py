"""C角色的圆润脸型空间变换；Basis与全部表情使用同一映射。"""
import math


def smooth(value):
    value = max(0., min(1., value))
    return value * value * (3 - 2 * value)


def rounded_point(point, eyes, strength):
    x, y, z = point
    if not all(math.isfinite(v) for v in (*point, strength, *(v for eye in eyes for v in eye))):
        raise ValueError('脸型参数必须为有限数。')
    if len(eyes) != 2 or not 0 <= strength <= 1.25:
        raise ValueError('脸型配方需要两个眼部中心及0—1.25强度。')
    if strength == 0:
        return x, y, z
    center_x = sum(eye[0] for eye in eyes) / 2
    eye_z = sum(eye[2] for eye in eyes) / 2
    local_x = x - center_x
    front = smooth((-.025 - y) / .035)
    face = 1 - smooth((abs(local_x) - .072) / .023)
    cheek = math.exp(-((z - (eye_z - .052)) / .048) ** 2)
    cheek *= front * face * (1 - smooth((z - (eye_z - .004)) / .03))
    chin = smooth((eye_z - .018 - z) / .100) * front * face
    new_x = x + local_x * .105 * strength * cheek
    # 固定现有颈部接口时，下巴提升最多9.5毫米，避免强版本叠进颈部。
    new_z = z + min(.013 * strength, .0095) * chin * (1 - .18 * min(1, abs(local_x) / .08))
    new_y = y - .003 * strength * cheek * math.exp(-((abs(local_x) - .04) / .030) ** 2)
    # 眼部中心取可见虹膜，避免用位于眼球内部的骨骼枢轴误移眼位。
    for ex, _, ez in eyes:
        weight = math.exp(-((x - ex) / .028) ** 4 - ((z - ez) / .025) ** 4) * front
        new_x += (x - ex) * .06 * strength * weight
        new_z += (z - ez) * .08 * strength * weight
    return new_x, new_y, new_z


def apply_round_face(arm, strength):
    import bpy
    from mathutils import Vector
    face = bpy.data.objects.get('Face')
    if face is None or face not in arm.children_recursive or not face.data.shape_keys:
        raise ValueError('当前角色缺少带表情的Face网格。')
    iris_slots = {i for i, material in enumerate(face.data.materials) if material and 'EyeIris' in material.name}
    indices = {i for poly in face.data.polygons if poly.material_index in iris_slots for i in poly.vertices}
    basis = face.data.shape_keys.key_blocks[0]
    points = [face.matrix_world @ basis.data[i].co for i in indices]
    eyes = []
    for sign in (-1, 1):
        selected = [p for p in points if sign * p.x > 0]
        if not selected:
            raise ValueError('无法确定两个虹膜中心。')
        eyes.append(tuple(sum(p[k] for p in selected) / len(selected) for k in range(3)))
    inverse = face.matrix_world.inverted()
    old_basis = [face.matrix_world @ vertex.co for vertex in basis.data]
    max_shift = 0
    key_shifts = {}
    for key in face.data.shape_keys.key_blocks:
        original = [face.matrix_world @ vertex.co for vertex in key.data]
        changed = [Vector(rounded_point(point, eyes, strength)) for point in original]
        shift = max((a - b).length for a, b in zip(original, changed))
        max_shift = max(max_shift, shift)
        key_shifts[key.name] = shift
        for vertex, point in zip(key.data, changed):
            vertex.co = inverse @ point
    # 显式同步基础网格，不对共享Basis再次应用变换。
    for vertex, point in zip(face.data.vertices, basis.data):
        vertex.co = point.co
    face.data.update()
    new_basis = [face.matrix_world @ vertex.co for vertex in basis.data]
    if max_shift > .025 or max_shift < .001:
        raise ValueError('脸型改变量超出本轮小范围研究限制。')
    return {'strength': strength, 'eye_centers': eyes, 'shape_keys_transformed': len(key_shifts),
            'key_max_shift_m': key_shifts, 'max_shift_m': max_shift,
            'basis_min_z_before': min(p.z for p in old_basis),
            'basis_min_z_after': min(p.z for p in new_basis),
            'topology_weights_uv_preserved': True}
