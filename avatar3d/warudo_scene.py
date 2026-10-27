"""从已保存场景生成独立直播接续副本；不操作运行器、不启动摄像头。"""
from pathlib import Path
import copy
import json
import os
import re
import uuid

from .models import atomic_json, digest, inspect_vrm
from .warudo_blueprints import CHARACTER, PLAY_NODE, KEY_NODE, build_graph

CAMERA = '6a05ecf3-1501-4cab-b9d7-84131b881a29'
SUPPORTED_ASSETS = {CHARACTER, CAMERA, '778ab65f-8e11-44f1-ad85-28b7a12429f1',
                    '3b082c9c-fd34-41cb-82b6-2045a371dc83', '8aa033fb-9386-4d04-bec1-2ec67028f326'}
GESTURE_PARTS = [('RightArm', 6), ('RightFingers', 8)]


def value(entity, key):
    raw = entity['dataInputs'][key]['value']
    return json.loads(raw) if raw is not None else None


def set_value(entity, key, new):
    if key not in entity.get('dataInputs', {}):
        raise ValueError('场景缺少已验证的字段：' + key)
    entity['dataInputs'][key]['value'] = json.dumps(new, ensure_ascii=False)


def arms_only(node, template):
    """当前两个单手动作只接管右臂／右手指，左侧始终保留待机。"""
    port = template['dataInputs'].get('MaskedBodyParts')
    if not port or port.get('typeKind') != 'EnumArray':
        raise ValueError('缺少原生身体遮罩字段，不能猜测新版本格式。')
    node['dataInputs']['MaskedBodyParts'] = copy.deepcopy(port)
    set_value(node, 'MaskedBodyParts', [dict(label=label, value=number, description=None, icon=None)
                                     for label, number in GESTURE_PARTS])
    node['dataInputs']['MaskedBodyParts']['properties']['hidden'] = False
    set_value(node, 'Masked', True)


def animation_resource(report_path, install, action):
    report_path = Path(report_path)
    report = json.loads(report_path.read_text(encoding='utf-8'))
    source = Path(report.get('modFile', ''))
    name = report.get('modName', '')
    if (report.get('passed') is not True or report.get('editorVersion') != '2021.3.45f2' or
            not re.fullmatch('AvatarLab' + action.capitalize() + '[0-9a-f]{12}', name) or
            source.name != name + '.warudo' or report.get('actionId', 'wave') != action or
            report.get('loop', False) is not (action == 'idle')):
        raise ValueError('动作构建报告类型／名称／循环标识无效：' + action)
    installed = Path(install) / 'Warudo_Data/StreamingAssets/CharacterAnimations' / source.name
    if not installed.is_file() or digest(installed) != report.get('modSha256'):
        raise ValueError('已安装动作缺失或哈希不一致：' + action)
    return 'character-animation://data/CharacterAnimations/' + installed.name, {
        'file': str(installed), 'sha256': report['modSha256'], 'build_report_sha256': digest(report_path)}


def _wave_binding(scene, character_id):
    candidates = []
    for graph in scene['graphs']:
        for link in graph['flowConnections']:
            key = graph['nodes'].get(link['outputNode'], {})
            play = graph['nodes'].get(link['inputNode'], {})
            if key.get('typeId') != KEY_NODE or play.get('typeId') != PLAY_NODE:
                continue
            if (link['outputPort'] == 'Exit' and link['inputPort'] == 'Enter' and
                    value(key, 'Keystroke').get('value') == 66 and
                    value(key, 'RequireCtrl') is True and value(key, 'RequireAlt') is True and
                    value(key, 'RequireShift') is False and value(key, 'RequireMeta') is False and
                    value(play, 'Character').get('id') == character_id):
                candidates.append((graph, play))
    if len(candidates) != 1:
        raise ValueError('需要唯一已保存的Ctrl＋Alt＋F8→角色单次动画绑定。')
    return candidates[0]


def _append_hierarchy(tree, anchor, ident):
    for child in tree.get('children') or []:
        if child['key'] == anchor:
            tree['children'].append({'collapsed': False, 'key': ident, 'children': None})
            return True
        if _append_hierarchy(child, anchor, ident):
            return True
    return False


def compose_scene(source, name, model_uri, animations):
    if source.get('appVersion') != '0.15.1':
        raise ValueError('当前只验证Warudo0.15.1场景格式。')
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{1,63}', name) or name == source.get('name'):
        raise ValueError('请使用新的场景名称（英文字母开头，2—64位）。')
    if any(a['typeId'] not in SUPPORTED_ASSETS for a in source['assets']):
        raise ValueError('源场景含额外资源；请使用独立基础场景，避免复制启用中的采集设备。')
    scene = copy.deepcopy(source)
    characters = [a for a in scene['assets'] if a['typeId'] == CHARACTER]
    cameras = [a for a in scene['assets'] if a['typeId'] == CAMERA]
    if len(characters) != 1 or len(cameras) != 1:
        raise ValueError('需要单角色、单摄像机基础场景。')
    character, camera = characters[0], cameras[0]
    if value(character, 'TrackingAssetIds') or value(character, 'TrackingGraphIds') or value(character, 'TrackingEnabled'):
        raise ValueError('源场景已有动捕配置，请保留现有设置并使用无动捕基础场景。')
    graph, wave = _wave_binding(scene, character['id'])
    # 确认资源地址来自本机原生保存的选择，不把文件名当成任意资源URI。
    if not (value(character, 'Source') or '').startswith('character://data/Characters/') or not (
            value(wave, 'Animation') or '').startswith('character-animation://data/CharacterAnimations/'):
        raise ValueError('源场景资源地址不是已验证的本地资源格式。')
    explain_graph = build_graph(scene, character['id'], 'explain')  # 冲突检测先于任何落盘
    explain = next(n for n in explain_graph['nodes'].values() if n['typeId'] == PLAY_NODE)
    arms_only(explain, wave)
    arms_only(wave, wave)
    set_value(wave, 'Animation', animations['wave'])
    set_value(explain, 'Animation', animations['explain'])
    for node in (wave, explain):
        for key, val in {'TransitionTime': .35, 'Weight': 1.0, 'Speed': 1.0, 'Additive': False}.items():
            set_value(node, key, val)
    for key, val in {'Source': model_uri, 'DefaultIdleAnimation': animations['idle'],
                     'BreathingEnabled': False, 'SwayingEnabled': False}.items():
        set_value(character, key, val)
    for key, val in {'TransparentBackground': True, 'SpoutOutput': True, 'UseChromaKey': False,
                     'RenderCharacters': True, 'RenderEnvironment': False, 'RenderProps': False,
                     'RenderScreen': False}.items():
        set_value(camera, key, val)
    if not _append_hierarchy(scene['graphHierarchy'], graph['id'], explain_graph['id']):
        raise ValueError('原挥手蓝图不在场景目录中，停止生成不完整场景。')
    scene['graphs'].append(explain_graph)
    scene['name'] = name
    scene['selectedAssetId'] = character['id']
    scene['selectedGraphId'] = explain_graph['id']
    return scene


def revise_gestures(source, name, wave_uri):
    """复制已有直播场景，只修手势绑定／遮罩／过渡，保留机位与表情。"""
    if (source.get('appVersion') != '0.15.1' or name == source.get('name') or
            not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{1,63}', name)):
        raise ValueError('需要0.15.1场景和新的有效名称。')
    if not re.fullmatch(r'character-animation://data/CharacterAnimations/AvatarLabWave[0-9a-f]{12}\.warudo', wave_uri):
        raise ValueError('挥手资源地址无效。')
    scene = copy.deepcopy(source)
    characters = [a for a in scene['assets'] if a['typeId'] == CHARACTER]
    if len(characters) != 1:
        raise ValueError('需要单角色场景。')
    character = characters[0]
    if value(character, 'TrackingEnabled') or value(character, 'TrackingAssetIds') or value(character, 'TrackingGraphIds'):
        raise ValueError('场景已有动捕，请保留配置并使用原无动捕副本。')
    _, wave = _wave_binding(scene, character['id'])
    explanations = []
    for graph in scene['graphs']:
        for link in graph['flowConnections']:
            key = graph['nodes'].get(link['outputNode'], {})
            node = graph['nodes'].get(link['inputNode'], {})
            if (key.get('typeId') == KEY_NODE and node.get('typeId') == PLAY_NODE and
                    link['outputPort'] == 'Exit' and link['inputPort'] == 'Enter' and
                    value(key, 'Keystroke').get('value') == 67 and
                    value(key, 'RequireCtrl') is True and value(key, 'RequireAlt') is True and
                    value(key, 'RequireShift') is False and value(key, 'RequireMeta') is False and
                    value(node, 'Character').get('id') == character['id']):
                explanations.append(node)
    if len(explanations) != 1:
        raise ValueError('需要唯一Ctrl＋Alt＋F9讲解绑定。')
    for node in (wave, explanations[0]):
        arms_only(node, wave)
        set_value(node, 'TransitionTime', .35)
    set_value(wave, 'Animation', wave_uri)
    scene['name'] = name
    return scene


def prepare_revision(source_path, install, wave_report, output, name='AvatarLab_C_Live_v002'):
    source_path, install, output = (Path(p).resolve() for p in (source_path, install, output))
    before = digest(source_path)
    source = json.loads(source_path.read_text(encoding='utf-8-sig'))
    wave_uri, wave_asset = animation_resource(wave_report, install, 'wave')
    scene = revise_gestures(source, name, wave_uri)
    character = next(a for a in scene['assets'] if a['typeId'] == CHARACTER)
    _, wave = _wave_binding(scene, character['id'])
    explanation = next(n for g in scene['graphs'] for n in g['nodes'].values()
                       if n['typeId'] == PLAY_NODE and n['id'] != wave['id'])
    assets = {'wave': wave_asset}
    for key, uri, directory in (
            ('model', value(character, 'Source'), 'Characters'),
            ('idle', value(character, 'DefaultIdleAnimation'), 'CharacterAnimations'),
            ('explain', value(explanation, 'Animation'), 'CharacterAnimations')):
        prefix = 'character' if key == 'model' else 'character-animation'
        match = re.fullmatch(prefix + r'://data/' + directory + r'/([A-Za-z0-9_-]+\.(?:vrm|warudo))', uri)
        if not match:
            raise ValueError('场景含未校验的资源地址：' + key)
        path = install / 'Warudo_Data/StreamingAssets' / directory / match[1]
        assets[key] = {'file': str(path), 'sha256': digest(path)}
    if digest(source_path) != before:
        raise ValueError('生成期间源场景改变。')
    output.mkdir(parents=True, exist_ok=False)
    atomic_json(output / (name + '.json'), scene)
    atomic_json(output / 'complete.json', {'schema': 1, 'scene_file': name + '.json',
        'scene_sha256': digest(output / (name + '.json')), 'source_scene': str(source_path),
        'source_scene_sha256': before, 'assets': assets, 'warudo_version': '0.15.1',
        'native_load': 'pending', 'repair': 'matched wave and right-side-only mask'})
    return output


def prepare_scene(source_path, install, model, reports, output, name='AvatarLab_C_Live_v002'):
    source_path, install, model, output = (Path(p).resolve() for p in (source_path, install, model, output))
    before = digest(source_path)
    if not (install / 'Warudo.exe').is_file():
        raise ValueError('Warudo安装目录无效。')
    source = json.loads(source_path.read_text(encoding='utf-8-sig'))
    model_info = inspect_vrm(model)
    installed_model = install / 'Warudo_Data/StreamingAssets/Characters' / model.name
    if digest(installed_model) != model_info['sha256']:
        raise ValueError('模型必须已在Warudo中按同一文件名安装且哈希一致。')
    resources, assets = {}, {'model': {'file': str(installed_model), 'sha256': model_info['sha256']}}
    for action in ('idle', 'explain', 'wave'):
        resources[action], assets[action] = animation_resource(reports[action], install, action)
    scene = compose_scene(source, name, 'character://data/Characters/' + installed_model.name, resources)
    if digest(source_path) != before:
        raise RuntimeError('源场景在准备期间变化，请重新生成。')
    output.mkdir(parents=True, exist_ok=False)
    atomic_json(output / (name + '.json'), scene)
    atomic_json(output / 'complete.json', {'schema': 1, 'scene_file': name + '.json',
        'scene_sha256': digest(output / (name + '.json')), 'source_scene': str(source_path),
        'source_scene_sha256': before, 'assets': assets, 'warudo_version': '0.15.1',
        'native_load': 'pending', 'tracking': 'not_configured', 'obs_capture': 'pending'})
    return output


def install_scene(bundle, install):
    bundle, install = Path(bundle), Path(install)
    record = json.loads((bundle / 'complete.json').read_text(encoding='utf-8'))
    filename = record['scene_file']
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{1,63}\.json', filename):
        raise ValueError('场景文件名无效。')
    source = bundle / filename
    if digest(source) != record['scene_sha256'] or not (install / 'Warudo.exe').is_file():
        raise ValueError('场景包损坏或安装目录错误。')
    # 安装前再检查依赖，防止准备与安装之间资源被替换。
    data = (install / 'Warudo_Data/StreamingAssets').resolve()
    for item in record['assets'].values():
        path = Path(item['file']).resolve()
        if not path.is_relative_to(data) or digest(path) != item['sha256']:
            raise ValueError('安装时发现依赖资源变化。')
    target = data / 'Scenes' / filename
    if target.exists():
        if digest(target) != record['scene_sha256']:
            raise FileExistsError('已有同名场景，保留原文件；请使用新版本名称。')
        return target
    temporary = target.with_name(target.name + '.' + uuid.uuid4().hex + '.partial')
    try:
        with temporary.open('xb') as file:
            file.write(source.read_bytes()); file.flush(); os.fsync(file.fileno())
        if digest(temporary) != record['scene_sha256']:
            raise ValueError('场景复制校验失败。')
        os.link(temporary, target)  # CreateNew，不覆盖在检查后出现的文件。
    finally:
        temporary.unlink(missing_ok=True)
    return target
