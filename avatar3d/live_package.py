"""本地直播素材包：自包含依赖、哈希预检、仅新增恢复，不启动运行器。"""
from datetime import datetime
from pathlib import Path, PurePosixPath
import json
import os
import re
import shutil
import uuid

from .models import atomic_json, digest

SCHEMA = 1
KINDS = {'Scenes': '.json', 'Characters': '.vrm', 'CharacterAnimations': '.warudo'}
RESOURCE = re.compile(r'(character|character-animation)://data/([^\s"\\]+)')


def _relative(value):
    if not isinstance(value, str) or '\\' in value or ':' in value:
        raise ValueError('素材包路径无效。')
    parts = PurePosixPath(value).parts
    if len(parts) != 2 or parts[0] not in KINDS:
        raise ValueError('素材必须位于Scenes、Characters或CharacterAnimations。')
    name = parts[1]
    if (value != '/'.join(parts) or not re.fullmatch(r'[A-Za-z0-9_-]+\.[A-Za-z]+', name)
            or Path(name).suffix != KINDS[parts[0]]
            or name.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL',
                *('COM'+str(n) for n in range(1,10)), *('LPT'+str(n) for n in range(1,10))}):
        raise ValueError('素材文件名或扩展名无效。')
    return value


def _contained(root, relative):
    root = Path(root).resolve()
    path = root / _relative(relative)
    # 拒绝符号链接／目录联接将恢复写入重定向到包或目标以外。
    if not path.resolve().is_relative_to(root):
        raise ValueError('素材路径越出指定目录。')
    if path.is_symlink() or path.parent.is_symlink():
        raise ValueError('素材路径不能是符号链接。')
    return path


def _load_json(path):
    path = Path(path)
    if path.stat().st_size > 32 * 1024 * 1024:
        raise ValueError('JSON文件过大。')
    return json.loads(path.read_text(encoding='utf-8-sig'))


def _scene_dependencies(scene):
    """检查嵌套端口中的本地角色资源；拒绝未支持的外部依赖。"""
    found = set()
    def walk(item):
        if isinstance(item, dict):
            for v in item.values(): walk(v)
        elif isinstance(item, list):
            for v in item: walk(v)
        elif isinstance(item, str):
            # 原生dataInputs.value本身又是一层JSON。
            if item[:1] in ('"', '[', '{'):
                try:
                    decoded = json.loads(item)
                except ValueError:
                    pass
                else:
                    if decoded != item:
                        walk(decoded)
                        return
            matches = list(RESOURCE.finditer(item))
            for match in matches:
                relative = _relative(match.group(2))
                expected = 'Characters' if match.group(1) == 'character' else 'CharacterAnimations'
                if relative.split('/')[0] != expected:
                    raise ValueError('场景资源类型与目录不一致。')
                found.add(relative)
            if ('://data/' in item and not matches) or 'file://' in item or re.match(r'^[A-Za-z]:[\\/]', item):
                raise ValueError('场景含未打包的外部资源，只支持当前基础直播场景。')
    walk(scene)
    return found


def verify_package(package):
    package = Path(package).resolve()
    manifest = _load_json(package / 'manifest.json')
    if manifest.get('schema') != SCHEMA or manifest.get('warudo_version') != '0.15.1':
        raise ValueError('不支持的素材包格式或Warudo场景版本。')
    entries = manifest.get('files')
    if not isinstance(entries, list) or not 2 <= len(entries) <= 64:
        raise ValueError('素材包文件清单无效。')
    paths = set()
    for entry in entries:
        relative = _relative(entry['path'])
        if relative.casefold() in paths:
            raise ValueError('素材包存在重复路径。')
        paths.add(relative.casefold())
        path = _contained(package / 'payload', relative)
        size = entry.get('size')
        if (type(size) is not int or not 0 < size <= 512*1024*1024
                or not re.fullmatch(r'[0-9a-f]{64}', entry.get('sha256', ''))
                or not path.is_file() or path.stat().st_size != size or digest(path) != entry['sha256']):
            raise ValueError('素材缺失或内容校验失败：' + relative)
    scene_path = _relative(manifest['scene'])
    if not scene_path.startswith('Scenes/') or scene_path.casefold() not in paths:
        raise ValueError('素材包缺少指定场景。')
    scenes = [e for e in entries if e['path'].startswith('Scenes/')]
    if len(scenes) != 1:
        raise ValueError('每个素材包只包含一个场景。')
    scene = _load_json(_contained(package / 'payload', scene_path))
    if scene.get('appVersion') != manifest['warudo_version']:
        raise ValueError('场景版本与素材包不一致。')
    dependencies = _scene_dependencies(scene)
    if dependencies != {e['path'] for e in entries if not e['path'].startswith('Scenes/')}:
        raise ValueError('场景引用与素材包依赖不一致。')
    return manifest


def create_package(prepared, install, output):
    """从已校验准备包快照导出；拒绝把用户后改场景默认为已验基线。"""
    prepared, install, output = map(Path, (prepared, install, output))
    record = _load_json(prepared / 'complete.json')
    data = (install / 'Warudo_Data/StreamingAssets').resolve()
    if not (install / 'Warudo.exe').is_file():
        raise ValueError('Warudo安装目录无效。')
    scene_relative = _relative('Scenes/' + record['scene_file'])
    scene_source = _contained(data, scene_relative)
    if digest(scene_source) != record['scene_sha256']:
        raise ValueError('安装场景已被修改；保留现场，不能冒充原准备基线导出。')
    sources = [(scene_relative, scene_source, record['scene_sha256'])]
    for entry in record['assets'].values():
        source = Path(entry['file']).resolve()
        if not source.is_relative_to(data):
            raise ValueError('依赖不在指定Warudo目录。')
        relative = _relative(source.relative_to(data).as_posix())
        sources.append((relative, source, entry['sha256']))
    if output.exists():
        raise FileExistsError('输出目录已存在，请使用新的素材包目录。')
    # 先核实全部来源；失败时不发布可恢复标记。
    for relative, source, sha in sources:
        if not source.is_file() or digest(source) != sha:
            raise ValueError('来源缺失或已改变：' + relative)
    output.mkdir(parents=True)
    entries = []
    for relative, source, sha in sources:
        target = _contained(output / 'payload', relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        if digest(target) != sha:
            raise ValueError('复制期间来源变化：' + relative)
        entries.append({'path': relative, 'size': target.stat().st_size, 'sha256': sha})
    manifest = {'schema': SCHEMA, 'warudo_version': '0.15.1', 'scene': scene_relative,
                'created_at': datetime.now().astimezone().isoformat(), 'files': entries,
                'native_validation': 'pending', 'scope': '直播基础素材；不含可编辑源工程、软件、摄像头和OBS配置'}
    # 校验临时清单后才发布ready标志；verify同样用于恢复前。
    atomic_json(output / 'manifest.json', manifest)
    try:
        verify_package(output)
    except Exception:
        (output / 'manifest.json').unlink()
        raise
    return manifest


def plan_restore(package, install):
    manifest = verify_package(package)
    install = Path(install)
    data = (install / 'Warudo_Data/StreamingAssets').resolve()
    if not (install / 'Warudo.exe').is_file() or not data.is_dir():
        raise ValueError('请选择已有的Warudo安装目录。')
    items = []
    for entry in manifest['files']:
        target = _contained(data, entry['path'])
        state = 'add'
        if target.exists():
            state = 'reuse' if target.is_file() and digest(target) == entry['sha256'] else 'conflict'
        items.append({**entry, 'action': state})
    # 场景最后落盘，避免先出现引用缺失依赖的场景。
    items.sort(key=lambda e: e['path'].startswith('Scenes/'))
    return {'schema': SCHEMA, 'can_restore': not any(e['action'] == 'conflict' for e in items),
            'scene': manifest['scene'], 'items': items, 'native_validation': 'pending'}


def _publish(source, target, sha):
    temporary = target.with_name(target.name + '.' + uuid.uuid4().hex + '.partial')
    try:
        with source.open('rb') as src, temporary.open('xb') as dst:
            shutil.copyfileobj(src, dst); dst.flush(); os.fsync(dst.fileno())
        if digest(temporary) != sha:
            raise ValueError('复制期间素材包变化。')
        os.link(temporary, target)  # 原子CreateNew：不覆盖预检后创建的文件。
    finally:
        temporary.unlink(missing_ok=True)


def restore_package(package, install):
    package, install = Path(package).resolve(), Path(install).resolve()
    plan = plan_restore(package, install)
    if not plan['can_restore']:
        raise FileExistsError('存在同名不同内容的文件，未写入任何素材。请保留原场景并检查预检报告。')
    data = install / 'Warudo_Data/StreamingAssets'
    created = []
    try:
        for item in plan['items']:
            target = _contained(data, item['path'])
            if item['action'] == 'reuse':
                if digest(target) != item['sha256']:
                    raise ValueError('预检后已安装素材发生变化。')
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target = _contained(data, item['path'])
            _publish(_contained(package / 'payload', item['path']), target, item['sha256'])
            created.append((target, item['sha256']))
        # 最终核实包含复用文件，避免安装过程中外部修改被当作成功。
        for item in plan['items']:
            if digest(_contained(data, item['path'])) != item['sha256']:
                raise ValueError('恢复结束时文件发生变化。')
    except Exception:
        for path, sha in reversed(created):
            # 仅回滚本次新增且仍是本次内容的文件，保留其他人的修改。
            if path.is_file() and digest(path) == sha:
                path.unlink()
        raise
    return {**plan, 'restored': True, 'added': len(created),
            'reused': sum(e['action'] == 'reuse' for e in plan['items'])}
