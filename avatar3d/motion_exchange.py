"""把已校验的本地渲染任务转换为可追溯的骨骼动画交换包。"""
from pathlib import Path
import json
import os
import shutil
import subprocess
import time

from .backend import launch_external
from .contracts import RenderSpec
from .models import atomic_json, digest, inspect_vrm

SOURCE_FILES = {'角色透明.mov', '动作预览.mp4', '姿势预览.png', 'scene.blend'}


def inspect_source(folder):
    """只接收现有工具完成的任务结构；不新增任意blend导入入口。"""
    folder = Path(folder).resolve()
    record = json.loads((folder / 'complete.json').read_text(encoding='utf-8'))
    request = json.loads((folder / 'request.json').read_text(encoding='utf-8'))
    spec = RenderSpec.from_dict({key: request[key] for key in (
        'schema', 'model_sha256', 'action', 'duration', 'fps', 'width', 'azimuth')})
    if record.get('schema') != 1 or set(record.get('files', {})) != SOURCE_FILES:
        raise ValueError('源任务完成清单无效，不能导出动作包。')
    if any(digest(folder / name) != sha for name, sha in record['files'].items()):
        raise ValueError('源任务文件损坏，不能导出动作包。')
    if (record.get('model_sha256') != spec.model_sha256 or
            record.get('action') != spec.action or record.get('fps') != spec.fps or
            record.get('frames') != round(spec.duration * spec.fps)):
        raise ValueError('源任务参数与完成清单不一致。')
    report = json.loads((folder / 'scene-report.json').read_text(encoding='utf-8'))
    if report.get('model_sha256') != spec.model_sha256:
        raise ValueError('骨架报告与源模型不一致。')
    return folder, record, spec, report


def verify_exchange(folder):
    folder = Path(folder)
    record = json.loads((folder / 'exchange-complete.json').read_text(encoding='utf-8'))
    required = {'source.blend', 'character.vrm', 'animation.fbx', 'transparent.mov',
                'preview.mp4', 'poster.png', 'model-metadata.json', 'manifest.json',
                'roundtrip.json', '使用说明.txt'}
    if record.get('schema') != 1 or set(record.get('files', {})) != required:
        raise ValueError('动作包完成清单无效。')
    if any(digest(folder / name) != sha for name, sha in record['files'].items()):
        raise ValueError('动作包文件损坏。')
    return record


def export_exchange(source, model, destination, runtime, cancel, progress=lambda _: None, timeout=180):
    source, record, spec, report = inspect_source(source)
    model = Path(model).resolve()
    model_info = inspect_vrm(model)
    if model_info['sha256'] != spec.model_sha256:
        raise ValueError('交换包模型与源任务不匹配。')
    if cancel.is_set():
        raise InterruptedError('已取消动作包导出。')
    destination = Path(destination).resolve()
    # 每次独立新目录，绝不覆盖用户已有包；失败保留诊断但没有成功标记。
    destination.mkdir(parents=True, exist_ok=False)
    progress(5)
    try:
        copies = {'scene.blend': 'source.blend', '角色透明.mov': 'transparent.mov',
                  '动作预览.mp4': 'preview.mp4', '姿势预览.png': 'poster.png'}
        for name, target in copies.items():
            shutil.copyfile(source / name, destination / target)
            if name in record['files'] and digest(destination / target) != record['files'][name]:
                raise ValueError('复制时源文件发生变化。')
        shutil.copyfile(model, destination / 'character.vrm')
        if digest(destination / 'character.vrm') != spec.model_sha256:
            raise ValueError('复制时模型发生变化。')
        atomic_json(destination / 'model-metadata.json', model_info)
        if cancel.is_set():
            raise InterruptedError('已取消动作包导出。')
        request = {'source': str(destination / 'source.blend'),
                   'source_sha256': record['files']['scene.blend'],
                   'output': str(destination), 'bones': report['humanoid_bones'],
                   'fps': spec.fps, 'frames': record['frames']}
        atomic_json(destination / 'exchange-request.json', request)
        worker = Path(__file__).with_name('motion_exchange_worker.py')
        command = [str(runtime.blender), '--background', '--factory-startup', '--disable-autoexec',
                   '--python-exit-code', '23', '--python', str(worker), '--',
                   str(destination / 'exchange-request.json')]
        env = os.environ.copy()
        env['BLENDER_USER_CONFIG'] = str(destination / 'blender-config')
        env['BLENDER_USER_SCRIPTS'] = str(destination / 'blender-scripts')
        with (destination / 'exchange.log').open('wb') as log:
            process = launch_external(command, env, log)
            started = time.monotonic()
            try:
                while process.poll() is None:
                    if cancel.is_set():
                        raise InterruptedError('已取消动作包导出。')
                    if time.monotonic() - started > timeout:
                        raise TimeoutError('动作包导出超时，诊断已保留。')
                    time.sleep(.1)
                if process.returncode:
                    raise RuntimeError(f'动作包转换失败（{process.returncode}），查看exchange.log。')
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(5)
        progress(85)
        roundtrip = json.loads((destination / 'roundtrip.json').read_text(encoding='utf-8'))
        if roundtrip.get('passed') is not True:
            raise ValueError('FBX重导入姿势检查未通过。')
        manifest = {'schema': 1, 'action_id': spec.action, 'asset_version': '0.1.0-technical',
                    'source_job_id': record['job_id'], 'model_sha256': spec.model_sha256,
                    'source_blend_sha256': record['files']['scene.blend'],
                    'fps': spec.fps, 'frames': record['frames'],
                    'sample_count_duration': record['frames'] / spec.fps,
                    'clip_key_range_seconds': (record['frames'] - 1) / spec.fps,
                    'loop': False, 'sample_only': record.get('sample_only', False),
                    'source_bones': report['humanoid_bones'],
                    'includes': '骨骼动画；不包含表情、材质、道具曲线',
                    'validation': {'blender_fbx_roundtrip': 'passed',
                                   'unity_humanoid': 'pending', 'warudo_playback': 'pending',
                                   'obs_alpha': 'pending', 'jianying_composite': 'pending'}}
        atomic_json(destination / 'manifest.json', manifest)
        (destination / '使用说明.txt').write_text(
            '这是技术动作交换包，不是正式C角色或已验收的Warudo成品。\n'
            'character.vrm：运行器角色；source.blend：可编辑源工程；animation.fbx：骨骼动作中转。\n'
            'transparent.mov：透明素材；preview.mp4：棋盘预览。模型作者与使用范围见model-metadata.json。\n'
            'FBX已在Blender重导入检查，Unity／Warudo、OBS与剪映仍需实测。\n'
            'Warudo官方动画Mod流程：匹配版本Unity／SDK→FBX设Humanoid并检查映射→提取Animation Clip→构建Mod。\n'
            '不直接把FBX当作已可播放的.warudo；详见https://docs.warudo.app/docs/modding/character-animation-mod\n'
            '骨骼外的表情／材质另行适配；首末关键帧间隔比采样帧数除帧率短一帧，不据此拉伸动作。\n', encoding='utf-8')
        if cancel.is_set():
            raise InterruptedError('已取消动作包导出。')
        files = set(copies.values()) | {'character.vrm', 'model-metadata.json', 'animation.fbx', 'roundtrip.json', 'manifest.json', '使用说明.txt'}
        atomic_json(destination / 'exchange-complete.json', {
            'schema': 1, 'files': {name: digest(destination / name) for name in sorted(files)}})
        verify_exchange(destination)
        progress(100)
        return destination
    except BaseException:
        (destination / 'exchange-complete.json').unlink(missing_ok=True)
        raise
