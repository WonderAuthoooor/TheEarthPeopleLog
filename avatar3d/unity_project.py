"""从已校验交换包准备独立Unity工程；不启动编辑器或宣称运行通过。"""
from pathlib import Path
import json
import math
import shutil

from .models import REQUIRED, atomic_json, digest
from .motion_exchange import verify_exchange

EDITOR_VERSION = '2021.3.45f2'
SDK_FILENAME = 'Warudo-Mod-Tool-0.14.5.1.tgz'
SDK_SHA256 = '9e3f85a4b1cdc88fda9996afab73c04937e336b5108c66e61dc5b634f6a63dc3'
FBX_ASSET = 'Assets/AvatarBridge/Input/animation.fbx'


def bone_bindings(source):
    """VRM语义名转Unity枚举名；实际HumanTrait名称在编辑器中查询。"""
    if not isinstance(source, dict) or any(not source.get(name) for name in REQUIRED):
        raise ValueError('交换包缺少必要人形骨骼。')
    # 两个VRM版本的拇指名称不同，必须整组转换，不能丢掉近腕关节。
    mapping = {}
    for side in ('left', 'right'):
        if source.get(side + 'ThumbMetacarpal'):
            mapping.update({side + 'ThumbMetacarpal': side + 'ThumbProximal',
                            side + 'ThumbProximal': side + 'ThumbIntermediate',
                            side + 'ThumbDistal': side + 'ThumbDistal'})
    allowed = set(REQUIRED) | {'chest', 'upperChest', 'neck', 'jaw', 'leftEye', 'rightEye',
                              'leftShoulder', 'rightShoulder', 'leftToes', 'rightToes'}
    for side in ('left', 'right'):
        for finger in ('Thumb', 'Index', 'Middle', 'Ring', 'Little'):
            allowed.update(side + finger + segment for segment in ('Proximal', 'Intermediate', 'Distal'))
        allowed.add(side + 'ThumbMetacarpal')
    bindings = []
    for semantic, bone in source.items():
        if not bone:
            continue
        if semantic not in allowed or not isinstance(bone, str):
            raise ValueError(f'不支持的骨骼映射：{semantic}')
        target = mapping.get(semantic, semantic)
        bindings.append({'humanBone': target[0].upper() + target[1:], 'sourceBone': bone})
    if (len({b['sourceBone'] for b in bindings}) != len(bindings) or
            len({b['humanBone'] for b in bindings}) != len(bindings)):
        raise ValueError('骨骼映射重复。')
    return bindings


def exchange_request(exchange):
    """准备工程和复用构建工程使用同一来源／时序校验。"""
    exchange = Path(exchange).resolve()
    record = verify_exchange(exchange)
    manifest = json.loads((exchange / 'manifest.json').read_text(encoding='utf-8'))
    fps, frames = manifest.get('fps'), manifest.get('frames')
    if (manifest.get('schema') != 1 or type(fps) is not int or not 1 <= fps <= 120 or
            type(frames) is not int or not 2 <= frames <= 21601 or
            manifest.get('validation', {}).get('blender_fbx_roundtrip') != 'passed' or
            manifest.get('model_sha256') != record['files']['character.vrm'] or
            manifest.get('source_blend_sha256') != record['files']['source.blend']):
        raise ValueError('交换包来源、帧率或帧数不一致。')
    duration = manifest.get('clip_key_range_seconds')
    if (not isinstance(duration, (int, float)) or not math.isfinite(duration) or
            not math.isclose(duration, (frames - 1) / fps, abs_tol=1e-6)):
        raise ValueError('动作关键帧时间范围不一致。')
    roundtrip = json.loads((exchange / 'roundtrip.json').read_text(encoding='utf-8'))
    if roundtrip.get('passed') is not True:
        raise ValueError('交换包FBX往返验证未通过。')
    bindings = bone_bindings(manifest.get('source_bones'))
    action = manifest.get('action_id', 'wave')  # 兼容早期挥手交换包。
    if action not in ('neutral', 'idle', 'explain', 'bend', 'wave', 'hold', 'turntable'):
        raise ValueError('未知动作标识，不能构建动作包。')
    if type(manifest.get('loop', False)) is not bool:
        raise ValueError('循环标识必须是布尔值。')
    if manifest.get('loop') and (roundtrip.get('loop_closed') is not True or
                                roundtrip.get('checked_frames') != frames):
        raise ValueError('循环动作缺少完整周期闭合验证。')
    return {'schema': 1, 'editorVersion': EDITOR_VERSION, 'fbxAsset': FBX_ASSET,
            'fbxSha256': record['files']['animation.fbx'], 'fps': fps, 'frames': frames,
            'duration': duration, 'loop': manifest.get('loop') is True, 'actionId': action,
            'modelSha256': manifest['model_sha256'], 'bindings': bindings}


def prepare_project(exchange, destination, sdk):
    exchange, destination, sdk = map(lambda p: Path(p).resolve(), (exchange, destination, sdk))
    request = exchange_request(exchange)
    record = verify_exchange(exchange)
    if sdk.name != SDK_FILENAME or digest(sdk) != SDK_SHA256:
        raise ValueError('SDK不是已缓存的固定版本或文件已损坏。')
    template = Path(__file__).parent / 'unity/AvatarBridge.cs'
    # 不把准备工程放在输入包内，避免污染已完成资产。
    if destination == exchange or exchange in destination.parents:
        raise ValueError('输出工程必须独立于输入交换包。')
    destination.mkdir(parents=True, exist_ok=False)
    try:
        files = {}
        for source, relative, expected in (
            (exchange / 'animation.fbx', FBX_ASSET, record['files']['animation.fbx']),
            (exchange / 'manifest.json', 'AvatarBridge/source-manifest.json', record['files']['manifest.json']),
            (exchange / 'model-metadata.json', 'AvatarBridge/model-metadata.json', record['files']['model-metadata.json']),
            (template, 'Assets/AvatarBridge/Editor/AvatarBridge.cs', digest(template)),
            (template.with_name('WarudoBridge.cs'), 'Assets/AvatarBridge/Editor/WarudoBridge.cs',
             digest(template.with_name('WarudoBridge.cs'))),
            (sdk, 'LocalPackages/' + SDK_FILENAME, SDK_SHA256),
        ):
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            if digest(target) != expected:
                raise ValueError(f'复制期间文件变化：{source.name}')
            files[relative] = expected
        atomic_json(destination / 'AvatarBridge/request.json', request)
        # 先在纯Unity验证人形动作；SDK稍后按官方流程导入，避免依赖下载阻塞骨骼排错。
        atomic_json(destination / 'Packages/manifest.json', {
            'dependencies': {'com.unity.modules.animation': '1.0.0'}})
        settings = destination / 'ProjectSettings/ProjectVersion.txt'
        settings.parent.mkdir(parents=True, exist_ok=True)
        settings.write_text(f'm_EditorVersion: {EDITOR_VERSION}\n', encoding='utf-8')
        (destination / 'README.md').write_text(
            '# 动作转换技术工程\n\n'
            f'仅使用Unity {EDITOR_VERSION}打开。当前只是离线准备，C#尚待真实编译。\n\n'
            '1. 在Unity Hub添加本目录，首次导入完成且Console无编译错误后，选择菜单 '
            'Avatar Bridge / Validate and Extract Animation。每次运行输出独立Runs目录，失败保留诊断。\n'
            '2. 查看AvatarBridge/Runs/<本次ID>/report.json。必须passed=true，且核对本次ID和输入哈希；'
            '旧报告不代表新运行成功。此通过只覆盖Unity人形与时长，不覆盖Warudo播放和视觉观感。\n'
            '3. 接着由研发执行WarudoBridge.ConfigureAndExit配置.NET Framework和Assembly Version Validation，'
            '用scripts/stage-warudo-sdk.py部署固定SDK。本机UPM不能直接读官方tgz根布局，'
            '因此使用校验后本地文件夹引用；SDK依赖首次需要联网。'
            '启动Editor时UPM_CACHE_ROOT使用项目内缓存，不改用户全局配置。\n'
            '4. SDK真实编译通过后，scripts/build-warudo-animation.py接受本次成功的导入报告，'
            '验证输入并调用SDK公开构建入口，输出独立构建报告和.warudo。'
            '也可按官方New Mod／Build Mod手动流程操作，动画须命名Animation并位于Mod目录。'
            '不要把FBX直接改名为.warudo；构建通过不等于Warudo播放与视觉验收通过。\n\n'
            '批处理入口：AvatarLab.Editor.AvatarBridge.RunBatch；准备记录prepare-complete.json不是Unity完成报告。\n'
            '人物仍为技术样例，角色外观使用原VRM；不从参考FBX网格替换正式角色。\n\n'
            '官方依据：https://docs.warudo.app/docs/modding/sdk-installation\n'
            'https://docs.warudo.app/docs/modding/character-animation-mod\n', encoding='utf-8')
        for name in ('AvatarBridge/request.json', 'Packages/manifest.json',
                     'ProjectSettings/ProjectVersion.txt', 'README.md'):
            files[name] = digest(destination / name)
        atomic_json(destination / 'prepare-complete.json', {
            'schema': 1, 'stage': 'prepared_only', 'editor_version': EDITOR_VERSION,
            'source_exchange': str(exchange), 'source_complete_sha256': digest(exchange / 'exchange-complete.json'),
            'sdk_sha256': SDK_SHA256, 'sdk_checksum_scope': '本地缓存固定值，非发布者签名',
            'unity_execution': 'pending', 'warudo_playback': 'pending', 'files': files})
        return destination
    except BaseException as error:
        (destination / 'prepare-complete.json').unlink(missing_ok=True)
        atomic_json(destination / 'prepare-error.json', {'error': str(error), 'stage': 'preparation_failed'})
        raise
