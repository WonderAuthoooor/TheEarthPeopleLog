"""使用固定Unity／SDK构建已校验的人形动作，不编辑运行器场景。"""
from pathlib import Path
import json
import os
import subprocess
import uuid
from .models import atomic_json, digest

ROOT = Path(__file__).resolve().parents[1]


def build(project, editor, report, timeout=600):
    project, editor, report = (Path(p).resolve() for p in (project, editor, report))
    if not editor.is_file() or not report.is_relative_to(project / 'AvatarBridge/Runs'):
        raise ValueError('编辑器或已验证报告路径无效。')
    imported = json.loads(report.read_text(encoding='utf-8'))
    clip = (project / imported.get('clipAsset', '')).resolve()
    if (imported.get('passed') is not True or imported.get('editorVersion') != '2021.3.45f2' or
            not clip.is_relative_to(project / 'Assets/AvatarBridge/Runs') or
            digest(clip) != imported.get('clipSha256')):
        raise ValueError('源动作没有通过Unity导入验证或文件已损坏。')
    if not (project / 'Assets/AvatarBridge/Editor/WarudoAnimationBuilder.cs').is_file():
        raise ValueError('SDK构建脚本未部署。')
    # Unity自行检查工程的真实进程锁；编译失败后遗留的空锁文件不能代表仍在运行。
    atomic_json(project / 'AvatarBridge/build-request.json', {
        'sourceReport': report.relative_to(project).as_posix(),
        'reportSha256': digest(report), 'clipSha256': imported['clipSha256']})
    outputs = project / 'AvatarBridge/Builds'
    before = set(outputs.glob('*/report.json'))
    log = project / ('AvatarBridge/build-' + uuid.uuid4().hex + '.log')
    env = os.environ.copy()
    env['UPM_CACHE_ROOT'] = str(ROOT / '.runtime/unity-upm-cache')
    startup = subprocess.STARTUPINFO() if os.name == 'nt' else None
    if startup:
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = subprocess.SW_HIDE
    process = subprocess.Popen([str(editor), '-batchmode', '-nographics', '-projectPath', str(project),
        '-executeMethod', 'AvatarLab.Editor.WarudoAnimationBuilder.BuildAndExit', '-logFile', str(log)],
        env=env, startupinfo=startup)
    try:
        code = process.wait(timeout)
    except BaseException:
        process.terminate()
        try: process.wait(10)
        except subprocess.TimeoutExpired: process.kill(); process.wait(10)
        raise
    reports = set(outputs.glob('*/report.json')) - before
    if code != 0 or len(reports) != 1:
        raise RuntimeError(f'Unity动作构建失败（{code}），查看{log}')
    completed = json.loads(reports.pop().read_text(encoding='utf-8'))
    mod = Path(completed.get('modFile', '')).resolve()
    if (completed.get('passed') is not True or not mod.is_relative_to(outputs) or
            completed.get('clipSha256') != imported['clipSha256'] or digest(mod) != completed.get('modSha256')):
        raise ValueError('构建报告或动作包校验失败。')
    return mod


