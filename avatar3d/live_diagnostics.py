"""读取已保存的直播场景；仅检查配置，不连接运行器或采集设备。"""
import math
from pathlib import Path

from .live_package import _load_json, _contained, _scene_dependencies, verify_package
from .models import digest
from .warudo_blueprints import CHARACTER, KEY_NODE, PLAY_NODE
from .warudo_scene import CAMERA, value


def inspect_scene(scene_path, install, package=None):
    scene_path, install = Path(scene_path).resolve(), Path(install).resolve()
    before = digest(scene_path)
    scene = _load_json(scene_path)
    if scene.get('appVersion') != '0.15.1':
        raise ValueError('目前仅支持已核实的 Warudo 0.15.1 场景格式。')
    data = install / 'Warudo_Data/StreamingAssets'
    if not (install / 'Warudo.exe').is_file() or not data.is_dir():
        raise ValueError('Warudo 安装目录无效。')
    findings = []

    def add(level, code, message):
        findings.append({'level': level, 'code': code, 'message': message})

    def read(entity, key):
        try:
            return value(entity, key)
        except (KeyError, TypeError, ValueError):
            add('error', 'field', '字段缺失或无法读取：' + key)
            return None

    expected = {}
    if package:
        manifest = verify_package(package)
        expected = {e['path']: e['sha256'] for e in manifest['files']}
        baseline = next(e for e in manifest['files'] if e['path'] == manifest['scene'])
        if before != baseline['sha256']:
            add('notice', 'scene_changed', '保存场景与素材包基线不同；可能是正常设置修改，以下检查当前文件。')
    dependencies = _scene_dependencies(scene)
    for relative in sorted(dependencies):
        target = _contained(data, relative)
        if not target.is_file():
            add('error', 'resource_missing', '找不到引用素材：' + relative)
        elif relative in expected and digest(target) != expected[relative]:
            add('error', 'resource_changed', '引用素材与素材包内容不同：' + relative)
        elif expected and relative not in expected:
            add('warning', 'resource_unverified', '引用了素材包外的资源，适配尚未确认：' + relative)

    roles = [a for a in scene['assets'] if a['typeId'] == CHARACTER]
    cameras = [a for a in scene['assets'] if a['typeId'] == CAMERA]
    if len(roles) != 1 or len(cameras) != 1:
        raise ValueError('当前检查针对单角色、单摄像机直播场景。')
    role, camera = roles[0], cameras[0]
    for entity in (role, camera):
        if entity.get('active') is not True:
            add('error', 'inactive_asset', '角色或摄像机未激活，或缺少激活状态。')
    if read(role, 'Enabled') is not True:
        add('error', 'character_disabled', '角色未启用。')
    for key, prefix in [('Source', 'character://data/Characters/'),
                        ('DefaultIdleAnimation', 'character-animation://data/CharacterAnimations/')]:
        if not str(read(role, key)).startswith(prefix):
            add('error', 'base_resource', '未设置本地角色／待机素材：' + key)
    for key in ('BreathingEnabled', 'SwayingEnabled'):
        if read(role, key) is True:
            add('warning', 'idle_overlay', '内置呼吸或晃动正在叠加；需要检查是否与待机重复。')
    tracking = read(role, 'TrackingEnabled')
    for key, ids in [('TrackingAssetIds', {a['id'] for a in scene['assets']}),
                     ('TrackingGraphIds', {g['id'] for g in scene['graphs']})]:
        refs = read(role, key)
        if not isinstance(refs, list):
            add('error', 'tracking_format', key + ' 格式不受支持。')
        elif any(not isinstance(ref, str) or ref not in ids for ref in refs):
            add('error', 'tracking_reference', '动捕引用缺失：' + key)
    add('pending', 'tracking_runtime', '动捕已开启，跟随、失跟和动作混合须实测。' if tracking is True
        else '动捕未开启；摄像头跟随尚未验证。')

    keys = {}
    bindings = {66: [], 67: []}
    for graph in scene['graphs']:
        if graph.get('enabled') is not True:
            continue
        if graph.get('dataConnections'):
            add('warning', 'dynamic_inputs', '蓝图含动态数据连接；保存参数可能被运行时覆盖，需实际检查。')
        nodes = graph['nodes']
        for node in nodes.values():
            if node.get('typeId') != KEY_NODE:
                continue
            stroke = read(node, 'Keystroke')
            number = stroke.get('value') if isinstance(stroke, dict) else None
            modifiers = tuple(read(node, k) for k in ('RequireCtrl', 'RequireAlt', 'RequireShift', 'RequireMeta'))
            if type(number) is not int or any(type(v) is not bool for v in modifiers):
                add('error', 'key_format', '快捷键格式无效。')
                continue
            chord = (number, *modifiers)
            keys[chord] = keys.get(chord, 0) + 1
            if number not in bindings or modifiers != (True, True, False, False):
                continue
            links = [link for link in graph['flowConnections']
                     if link['outputNode'] == node['id'] and link['outputPort'] == 'Exit']
            for link in links:
                play = nodes.get(link['inputNode'], {})
                if play.get('typeId') == PLAY_NODE and link['inputPort'] == 'Enter':
                    bindings[number].append(play)
                else:
                    add('warning', 'custom_flow', 'F8/F9 连接了自定义流程，当前检查无法验证其行为。')
    if any(count > 1 for count in keys.values()):
        add('error', 'duplicate_hotkey', '多个启用蓝图监听同一快捷键，可能同时触发。')
    for number, plays in bindings.items():
        label = 'Ctrl+Alt+F' + str(number - 58)
        if len(plays) != 1:
            add('error', 'gesture_binding', label + ' 缺少唯一的直接单次动作绑定。')
            continue
        play = plays[0]
        character_ref = read(play, 'Character')
        if not isinstance(character_ref, dict) or character_ref.get('id') != role['id']:
            add('error', 'gesture_character', label + ' 绑定的角色不匹配。')
        if not str(read(play, 'Animation')).startswith('character-animation://data/CharacterAnimations/'):
            add('error', 'gesture_resource', label + ' 未选择本地动作。')
        parts = read(play, 'MaskedBodyParts')
        if (read(play, 'Masked') is not True or not isinstance(parts, list)
                or {str(p.get('value')) for p in parts if isinstance(p, dict)} != {'6', '8'}):
            add('error', 'gesture_mask', label + ' 未限制到右臂与右手指，可能覆盖左臂或脸头跟随。')
        if read(play, 'Additive') is not False:
            add('error', 'gesture_additive', label + ' 当前动作不应开启附加动画。')
        for key in ('TransitionTime', 'Weight', 'Speed'):
            v = read(play, key)
            if type(v) not in (float, int) or not math.isfinite(v) or v <= 0:
                add('error', 'gesture_parameter', label + ' 参数无效：' + key)
            elif (key == 'TransitionTime' and v < .3) or (key != 'TransitionTime' and v != 1):
                add('warning', 'gesture_tuning', label + ' 参数偏离当前已验证基线：' + key)
    for key, wanted in [('TransparentBackground', True), ('SpoutOutput', True),
                         ('UseChromaKey', False), ('RenderCharacters', True), ('RenderEnvironment', False)]:
        if read(camera, key) is not wanted:
            add('warning', 'camera_output', '透明直播输出设置需检查：' + key)
    add('pending', 'obs_runtime', 'OBS 发送者、透明效果与录制仍需实际验证。')
    if digest(scene_path) != before:
        raise ValueError('检查期间场景发生变化，请保存后重新检查。')
    return {'schema': 1, 'scene': str(scene_path), 'name': scene.get('name'),
            'scene_sha256': before, 'configuration_ok': not any(f['level'] == 'error' for f in findings),
            'findings': findings, 'runtime_verified': False,
            'scope': '只读取磁盘上的已保存配置；不代表当前运行场景或设备正常'}


def format_report(report):
    labels = {'error': '需修正', 'warning': '需留意', 'notice': '提示', 'pending': '待实测'}
    return ('场景：' + str(report['name']) + '\n' + report['scope'] + '\n\n' +
            '\n'.join('【' + labels[f['level']] + '】' + f['message'] for f in report['findings']))
