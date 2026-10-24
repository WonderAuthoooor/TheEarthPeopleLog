"""只发布已通过构建校验的动作资产；不改用户场景或覆盖其他资产。"""
from pathlib import Path
import json
import os
import shutil
import uuid

from .models import digest


def deploy_animation(report, install):
    report, install = Path(report).resolve(), Path(install).resolve()
    build = json.loads(report.read_text(encoding='utf-8'))
    source = Path(build.get('modFile', '')).resolve()
    if (build.get('passed') is not True or source.suffix != '.warudo' or
            not source.is_relative_to(report.parent) or source.stat().st_size == 0 or
            digest(source) != build.get('modSha256')):
        raise ValueError('动作构建报告无效或文件已损坏。')
    data = install / 'Warudo_Data/StreamingAssets'
    if not (install / 'Warudo.exe').is_file() or not data.is_dir():
        raise ValueError('Warudo安装目录无效。')
    folder = data / 'CharacterAnimations'
    folder.mkdir(exist_ok=True)
    target = folder / source.name
    reused = target.exists()
    if reused:
        if digest(target) != build['modSha256']:
            raise FileExistsError('同名动作已存在但内容不同，保留原文件。')
    else:
        temporary = folder / (source.name + '.' + uuid.uuid4().hex + '.partial')
        try:
            shutil.copyfile(source, temporary)
            if digest(temporary) != build['modSha256']:
                raise ValueError('复制期间动作文件变化。')
            # CreateNew语义：即便预检查后出现同名文件也不能覆盖。
            os.link(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
    return {'schema': 1, 'installed_file': str(target), 'sha256': build['modSha256'],
            'mod_name': build.get('modName'), 'reused': reused, 'warudo_playback': 'pending'}
