"""固定SDK的本地文件夹部署，避免旧UPM解包根目录和共享缓存问题。"""
from pathlib import Path, PurePosixPath
import json
import shutil
import tarfile

from .models import atomic_json, digest
from .unity_project import EDITOR_VERSION, SDK_FILENAME, SDK_SHA256


def extract_sdk(archive, target):
    archive, target = Path(archive), Path(target).resolve()
    if digest(archive) != SDK_SHA256:
        raise ValueError('SDK校验值不匹配。')
    with tarfile.open(archive, 'r:gz') as package:
        members = package.getmembers()
        if len(members) > 20000 or sum(item.size for item in members) > 512 * 1024 * 1024:
            raise ValueError('SDK展开大小异常。')
        names = set()
        for item in members:
            path = PurePosixPath(item.name)
            resolved = (target / str(path)).resolve()
            if (path.is_absolute() or '..' in path.parts or
                    any(':' in part or '\\' in part for part in path.parts) or
                    (resolved != target and target not in resolved.parents) or
                    not (item.isfile() or item.isdir())):
                raise ValueError('SDK含有越界路径或链接。')
            if item.isfile():
                if str(path).casefold() in names:
                    raise ValueError('SDK包含重名文件。')
                names.add(str(path).casefold())
        target.mkdir(parents=True, exist_ok=False)
        hashes = {}
        for item in members:
            relative = str(PurePosixPath(item.name))
            output = target / relative
            if item.isdir():
                output.mkdir(parents=True, exist_ok=True)
            else:
                output.parent.mkdir(parents=True, exist_ok=True)
                with package.extractfile(item) as source, output.open('xb') as destination:
                    shutil.copyfileobj(source, destination)
                hashes[relative] = digest(output)
    metadata = json.loads((target / 'package.json').read_text(encoding='utf-8'))
    if metadata.get('name') != 'app.warudo.modtool' or metadata.get('version') != '0.14.5':
        raise ValueError('SDK包清单版本不匹配。')
    return hashes


def stage_sdk(project, editor):
    project, editor = Path(project).resolve(), Path(editor).resolve()
    preparation = json.loads((project / 'prepare-complete.json').read_text(encoding='utf-8'))
    settings = (project / 'AvatarBridge/sdk-settings.txt').read_text(encoding='utf-8')
    if (preparation.get('editor_version') != EDITOR_VERSION or
            'editor=' + EDITOR_VERSION not in settings or 'assemblyVersionValidation=False' not in settings or
            not any('api=' + api in settings for api in ('NET_Unity_4_8', 'NET_4_6'))):
        raise ValueError('请先用匹配Editor运行WarudoBridge.ConfigureAndExit配置工程。')
    builtin = editor.parent / 'Data/Resources/PackageManager/BuiltInPackages'
    if not editor.is_file() or not builtin.is_dir():
        raise ValueError('Editor或内置模块目录无效。')
    manifest_path = project / 'Packages/manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    builder = Path(__file__).parent / 'unity/WarudoAnimationBuilder.cs'
    builder_target = project / 'Assets/AvatarBridge/Editor/WarudoAnimationBuilder.cs'
    if builder_target.exists():
        raise FileExistsError('工程已有SDK构建脚本，请保留现有文件并使用新工程。')
    archive = project / 'LocalPackages' / SDK_FILENAME
    target = project / 'LocalPackages/WarudoSDK-0.14.5.1'
    # 解包失败不修改manifest；保留不完整目录供诊断，重试使用新的工程。
    hashes = extract_sdk(archive, target)
    before = project / 'AvatarBridge/pre-sdk-manifest.json'
    if not before.exists():
        atomic_json(before, manifest)
    dependencies = manifest.setdefault('dependencies', {})
    for module in sorted(builtin.glob('com.unity.modules.*/package.json')):
        metadata = json.loads(module.read_text(encoding='utf-8'))
        dependencies[module.parent.name] = metadata['version']
    dependencies.update({'app.warudo.modtool': 'file:../LocalPackages/WarudoSDK-0.14.5.1',
                         'com.unity.ugui': '1.0.0', 'com.unity.textmeshpro': '3.0.6',
                         'com.unity.timeline': '1.7.6'})
    builder_target.parent.mkdir(parents=True, exist_ok=True)
    with builder.open('rb') as source, builder_target.open('xb') as destination:
        shutil.copyfileobj(source, destination)
    atomic_json(manifest_path, manifest)
    atomic_json(project / 'AvatarBridge/sdk-staged.json', {
        'schema': 1, 'sdk_sha256': SDK_SHA256, 'files': hashes,
        'sdk_import': 'pending', 'warudo_build': 'pending'})
    return target
