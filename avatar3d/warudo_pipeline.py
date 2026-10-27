"""复用已配置SDK的研发工程，逐次构建且恢复输入；不改Warudo用户场景。"""
from contextlib import contextmanager
from pathlib import Path
import json
import os
import shutil
import subprocess

from .backend import launch_external
from .models import atomic_json, digest
from .unity_project import EDITOR_VERSION, FBX_ASSET, SDK_SHA256, exchange_request
from .warudo_build import build

ROOT = Path(__file__).resolve().parents[1]
INPUTS = ('AvatarBridge/request.json', 'AvatarBridge/build-request.json', FBX_ASSET,
          FBX_ASSET + '.meta', 'Assets/AvatarBridge/Editor/AvatarBridge.cs',
          'Assets/AvatarBridge/Editor/WarudoAnimationBuilder.cs', 'Assets/AvatarBridge/ExportSettings.asset')


@contextmanager
def preserved_inputs(project, output):
    """CreateNew锁防止重复调度；备份保留供中断诊断，失败也恢复原输入。"""
    project, output = Path(project), Path(output)
    lock = project / 'AvatarBridge/pipeline.lock'
    with lock.open('x', encoding='utf-8') as file:
        file.write(str(output.resolve()))
    originals = {}
    try:
        # Unity运行时持有此文件；宁可拒绝，也不在正在打开的工程中替换FBX。
        if (project / 'Temp/UnityLockfile').exists():
            raise RuntimeError('Unity工程仍有会话锁，请正常关闭该工程后重试；不自动删除锁。')
        for name in INPUTS:
            target = project / name
            original = output / 'input-backup' / name
            if target.exists():
                original.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(target, original)
                originals[name] = digest(original)
                if digest(target) != originals[name]:
                    raise RuntimeError('备份期间工程输入变化。')
            else:
                originals[name] = None
        atomic_json(output / 'input-before.json', originals)
        yield
    finally:
        try:
            for name, sha in originals.items():
                target = project / name
                if sha is None:
                    target.unlink(missing_ok=True)
                else:
                    shutil.copyfile(output / 'input-backup' / name, target)
                    if digest(target) != sha:
                        raise RuntimeError('工程输入恢复校验失败：' + name)
            if originals:
                atomic_json(output / 'input-restored.json', {'restored': True, 'files': originals})
        finally:
            lock.unlink(missing_ok=True)


def convert(exchange, project, editor, output, timeout=600):
    exchange, project, editor, output = (Path(p).resolve() for p in (exchange, project, editor, output))
    request = exchange_request(exchange)
    if not editor.is_file():
        raise ValueError('Unity编辑器不存在。')
    if output == project or project in output.parents or output == exchange or exchange in output.parents:
        raise ValueError('输出目录须独立于转换工程和输入交换包。')
    preparation = json.loads((project / 'prepare-complete.json').read_text(encoding='utf-8'))
    sdk = json.loads((project / 'AvatarBridge/sdk-staged.json').read_text(encoding='utf-8'))
    if preparation.get('editor_version') != EDITOR_VERSION or sdk.get('sdk_sha256') != SDK_SHA256:
        raise ValueError('请使用本工具准备并已配置固定SDK的独立工程。')
    output.mkdir(parents=True, exist_ok=False)
    try:
        with preserved_inputs(project, output):
            shutil.copyfile(exchange / 'animation.fbx', project / FBX_ASSET)
            # FBX importer的.meta含前一个模型的HumanDescription/skeleton。
            # 输入与meta均已备份；重建当前模型导入设置，结束后一起恢复。
            (project / (FBX_ASSET + '.meta')).unlink(missing_ok=True)
            for name in ('AvatarBridge.cs', 'WarudoAnimationBuilder.cs'):
                shutil.copyfile(Path(__file__).parent / 'unity' / name,
                                project / 'Assets/AvatarBridge/Editor' / name)
            atomic_json(project / 'AvatarBridge/request.json', request)
            runs = project / 'AvatarBridge/Runs'
            before = set(runs.glob('*/report.json'))
            env = os.environ.copy()
            env['UPM_CACHE_ROOT'] = str(ROOT / '.runtime/unity-upm-cache')
            with (output / 'unity-import.log').open('wb') as log:
                process = launch_external([str(editor), '-batchmode', '-nographics', '-projectPath', str(project),
                    '-executeMethod', 'AvatarLab.Editor.AvatarBridge.RunBatch', '-logFile',
                    str(output / 'unity-editor.log')], env, log)
                try:
                    code = process.wait(timeout)
                except BaseException:
                    process.terminate()
                    try: process.wait(10)
                    except subprocess.TimeoutExpired: process.kill(); process.wait(10)
                    raise
            reports = set(runs.glob('*/report.json')) - before
            if code != 0 or len(reports) != 1:
                raise RuntimeError(f'Unity动作导入失败（{code}），日志保留在{output}')
            report = reports.pop()
            imported = json.loads(report.read_text(encoding='utf-8'))
            if (imported.get('passed') is not True or imported.get('actionId') != request['actionId'] or
                    imported.get('loop') != request['loop'] or imported.get('fbxSha256') != request['fbxSha256'] or
                    imported.get('modelSha256') != request['modelSha256']):
                raise ValueError('Unity结果与当前动作请求不一致。')
            shutil.copyfile(report, output / 'unity-report.json')
            builds = project / 'AvatarBridge/Builds'
            before_build = set(builds.glob('*/report.json'))
            mod = build(project, editor, report, timeout)
            results = set(builds.glob('*/report.json')) - before_build
            if len(results) != 1:
                raise RuntimeError('未找到唯一的本次构建报告。')
            build_report = results.pop()
            built = json.loads(build_report.read_text(encoding='utf-8'))
            if built.get('actionId') != request['actionId'] or built.get('loop') != request['loop']:
                raise ValueError('构建结果动作类型或循环标识不匹配。')
            shutil.copyfile(mod, output / mod.name)
            if digest(output / mod.name) != built['modSha256']:
                raise ValueError('动作包复制校验失败。')
            shutil.copyfile(build_report, output / 'build-report.json')
        atomic_json(output / 'complete.json', {
            'schema': 1, 'action': request['actionId'], 'loop': request['loop'],
            'source_exchange': str(exchange), 'source_sha256': digest(exchange / 'exchange-complete.json'),
            'build_report': str(build_report), 'mod': mod.name, 'mod_sha256': built['modSha256'],
            'inputs_restored': True, 'warudo_playback': 'pending'})
        return output
    except BaseException as error:
        atomic_json(output / 'error.json', {'error': str(error), 'passed': False})
        raise
