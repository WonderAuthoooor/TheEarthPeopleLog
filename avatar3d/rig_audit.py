"""检查VRM1表情和弹簧骨骼引用；结构通过不等于实际观感通过。"""
import json
import math
import struct
from pathlib import Path

from .models import inspect_vrm


def audit_document(doc):
    nodes = doc.get('nodes', [])
    meshes = doc.get('meshes', [])
    extensions = doc.get('extensions', {})
    vrm = extensions.get('VRMC_vrm')
    if not vrm:
        raise ValueError('此检查要求VRM 1.0。')

    def index(value, items, label):
        if type(value) is not int or not 0 <= value < len(items):
            raise ValueError(label + '引用越界。')
        return items[value]

    def finite(value, label, low=None, high=None):
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError(label + '不是有限数。')
        if low is not None and value < low or high is not None and value > high:
            raise ValueError(label + '超出范围。')

    expressions = {}
    for kind in ('preset', 'custom'):
        for name, expression in vrm.get('expressions', {}).get(kind, {}).items():
            binds = expression.get('morphTargetBinds', [])
            for bind in binds:
                node = index(bind.get('node'), nodes, '表情节点')
                mesh = index(node.get('mesh'), meshes, '表情网格')
                for primitive in mesh.get('primitives', []):
                    index(bind.get('index'), primitive.get('targets', []), '表情形态键')
                if not mesh.get('primitives'):
                    raise ValueError('表情网格没有图元。')
                finite(bind.get('weight'), '表情权重', 0, 1)
            expressions[kind + '/' + name] = len(binds)

    physics = extensions.get('VRMC_springBone', {})
    colliders = physics.get('colliders', [])
    groups = physics.get('colliderGroups', [])
    for collider in colliders:
        index(collider.get('node'), nodes, '碰撞体骨骼')
        for shape in collider.get('shape', {}).values():
            finite(shape.get('radius', 0), '碰撞体半径', 0)
            for field in ('offset', 'tail'):
                if field in shape:
                    if len(shape[field]) != 3:
                        raise ValueError('碰撞体坐标必须三维。')
                    for value in shape[field]:
                        finite(value, '碰撞体坐标')
    for group in groups:
        for reference in group.get('colliders', []):
            index(reference, colliders, '碰撞体组')
    joint_count = 0
    for spring in physics.get('springs', []):
        if 'center' in spring:
            index(spring['center'], nodes, '弹簧中心')
        for reference in spring.get('colliderGroups', []):
            index(reference, groups, '弹簧碰撞体组')
        previous = None
        joints = spring.get('joints', [])
        if len(joints) < 2:
            raise ValueError('弹簧链不足两个关节。')
        for joint in joints:
            node = index(joint.get('node'), nodes, '弹簧关节')
            if previous is not None and joint['node'] not in previous.get('children', []):
                raise ValueError('弹簧关节不是连续父子链。')
            previous = node
            for field in ('hitRadius', 'stiffness', 'gravityPower'):
                finite(joint.get(field, 0), field, 0)
            finite(joint.get('dragForce', 0.5), 'dragForce', 0, 1)
            direction = joint.get('gravityDir', [0, -1, 0])
            if len(direction) != 3:
                raise ValueError('重力方向必须三维。')
            for value in direction:
                finite(value, '重力方向')
        joint_count += len(joints)
    return {'expression_bind_counts': expressions, 'spring_chains': len(physics.get('springs', [])),
            'spring_joints': joint_count, 'colliders': len(colliders), 'collider_groups': len(groups),
            'structure_valid': True, 'visual_accepted': False}


def audit_vrm(path):
    info = inspect_vrm(path)
    with Path(path).open('rb') as stream:
        header = stream.read(20)
        length = struct.unpack_from('<I', header, 12)[0]
        document = json.loads(stream.read(length).decode('utf-8'))
    return audit_document(document) | {'sha256': info['sha256'], 'humanoid_bones': len(info['bones'])}
