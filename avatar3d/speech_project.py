"""分段口播项目；文本/音频绑定、不可变计划与可恢复的局部渲染。

调用者持有工作区 app.lock；本模块不操作外部编辑器或调用配音服务。
"""
from pathlib import Path
import copy
import hashlib
import html
import json
import re
import threading
import uuid

from .audio_assets import import_audio, load_audio, output_duration
from .contracts import RenderSpec
from .models import atomic_json, digest


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


def text_hash(text):
    return fingerprint(text.strip())


def validate(project, allow_draft=False):
    if project.get('schema') != 1:raise ValueError('不支持的口播项目版本。')
    segments = project.get('segments')
    if not isinstance(segments, list) or not 1 <= len(segments) <= 200:
        raise ValueError('项目须有1—200个段落。')
    ids = set()
    for segment in segments:
        ident = segment.get('id', '')
        if not isinstance(ident, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', ident) or ident in ids:
            raise ValueError('段落编号无效或重复。')
        ids.add(ident)
        text = segment.get('text')
        if not isinstance(text, str) or not (0 if allow_draft else 1) <= len(text.strip()) <= 4000:
            raise ValueError('每段文本须有1—4000个字符。')
        if segment.get('action') not in ('idle', 'explain'):raise ValueError('口播动作仅支持待机／讲解。')
    settings = project.get('settings', {})
    if set(settings) != {'model_sha256', 'width', 'fps', 'azimuth', 'framing'}:
        raise ValueError('项目渲染设置不完整。')
    RenderSpec(**settings, schema=2, action='idle').validate()
    return project


def create(model_sha256, text, width=480, fps=30, framing='bust'):
    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text.strip()) if p.strip()]
    return validate({'schema': 1, 'settings': {'model_sha256': model_sha256, 'width': width,
                     'fps': fps, 'azimuth': 0, 'framing': framing},
                     'segments': [{'id': uuid.uuid4().hex[:12], 'text': p, 'action': 'idle'} for p in paragraphs]})


def bind_audio(project, ident, workspace, source, cancel=None):
    result = copy.deepcopy(validate(project, allow_draft=True))
    segment = next((s for s in result['segments'] if s['id'] == ident), None)
    if segment is None:raise ValueError('段落不存在。')
    if not segment['text'].strip():raise ValueError('请先填写本段文本，再绑定对应配音。')
    info = import_audio(workspace, source, cancel)
    segment['audio'] = {'sha256': info['source_sha256'], 'text_sha256': text_hash(segment['text'])}
    return result


def plan(project, workspace):
    """帧为累计时间基准；不从字符数猜音频时长。缺音频时不猜后续起点。"""
    project = copy.deepcopy(validate(project))
    fps = project['settings']['fps']
    rows, cursor = [], 0
    for segment in project['segments']:
        row = {'id': segment['id'], 'text': segment['text'], 'status': 'ready'}
        audio = segment.get('audio', {})
        if not audio.get('sha256'):
            row.update(status='missing_audio', error='尚未绑定本段配音。')
        elif audio.get('text_sha256') != text_hash(segment['text']):
            row.update(status='stale_audio', error='文本已改变，请为当前文本重新绑定配音。')
        else:
            try:
                info = load_audio(workspace, audio['sha256'])
                spec = RenderSpec(**project['settings'], schema=2, action=segment['action'],
                                  audio_sha256=audio['sha256'], duration=output_duration(info, fps))
                row.update(request=spec.to_dict(), frames=round(spec.duration * fps),
                           audio_duration=info['audio_duration'])
            except (OSError, ValueError, KeyError, TypeError) as exc:
                row.update(status='invalid_audio', error=str(exc))
        row['start_frame'] = cursor
        if row['status'] != 'ready' or cursor is None:
            cursor = None
        else:
            cursor += row['frames']
        row['end_frame'] = cursor
        rows.append(row)
    return {'schema': 1, 'project_sha256': fingerprint(project), 'project': project,
            'fps': fps, 'frames': cursor, 'ready': all(r['status'] == 'ready' for r in rows), 'segments': rows}


def engine_signature(runtime_file):
    """保守失效：源码、运行配置和运行器二进制/插件源码变化均不复用旧渲染。"""
    from .backend import Runtime
    runtime = Runtime.load(runtime_file)
    package = Path(__file__).parent
    sources = {p.name: digest(p) for p in sorted(package.glob('*.py'))}
    addon = {p.relative_to(runtime.addon).as_posix(): digest(p)
             for p in sorted((runtime.addon/'io_scene_vrm').rglob('*.py'))}
    return fingerprint({'sources': sources, 'addon': addon, 'blender': digest(runtime.blender),
                        'runtime': digest(runtime_file), 'lock': digest(package/'assets/runtime-lock.json')})


def _stamp(seconds):
    ms = round(seconds * 1000)
    hours, ms = divmod(ms, 3600000)
    minutes, ms = divmod(ms, 60000)
    seconds, ms = divmod(ms, 1000)
    return f'{hours:02}:{minutes:02}:{seconds:02},{ms:03}'


def write_editing_files(folder, planned, results):
    """逐段素材引用与段落字幕草稿，不合并/重编码完整长视频。"""
    folder = Path(folder)
    cues, cards = [], []
    for index, (row, result) in enumerate(zip(planned['segments'], results), 1):
        start = row['start_frame'] / planned['fps']
        end = row['end_frame'] / planned['fps']
        # 字幕结束在配音结束，不覆盖每段收口尾静音；没有逐字对齐的假承诺。
        text = ' '.join(row['text'].split())
        cues.append(f'{index}\n{_stamp(start)} --> {_stamp(start + row["audio_duration"])}\n{text}\n')
        media = Path(result['folder'])
        cards.append(f'<section><h2>{index}. {html.escape(row["id"])}</h2>'
                     f'<p>{start:.3f}—{end:.3f}秒 · {html.escape(text)}</p>'
                     f'<video controls preload="none" width="240" poster="{(media/"姿势预览.png").as_uri()}">'
                     f'<source src="{(media/"有声预览.webm").as_uri()}" type="video/webm">'
                     f'<source src="{(media/"有声预览.mp4").as_uri()}" type="video/mp4"></video>'
                     f'<p><a href="{(media/"角色透明.mov").as_uri()}">透明MOV（静音）</a> · '
                     f'<a href="{(media/"口播.wav").as_uri()}">配套WAV</a></p></section>')
    (folder/'段落字幕草稿.srt').write_text('\n'.join(cues), encoding='utf-8-sig')
    (folder/'剪辑说明.txt').write_text('按timeline.json的start_frame/fps放置各段MOV和WAV，二者同起点。\n'
        '每段包含收口尾静音，按完整视频时长首尾相接；不要单独裁去音频尾静音。\n'
        '字幕为整段时长草稿，需要在剪映拆句校对，不是逐字识别或强制对齐。\n'
        '本目录引用工作区素材；迁移时须一起保留jobs成品目录。段间动作会重新起势，尚无跨段动作混合。\n', encoding='utf-8')
    (folder/'预览.html').write_text('<!doctype html><meta charset="utf-8"><title>分段口播审阅</title>'
        '<style>body{background:#19232b;color:#eee;font:16px sans-serif;margin:32px}section{display:inline-block;'
        'vertical-align:top;width:300px;margin:12px;padding:16px;background:#293844}a{color:#8fe1db}p{overflow-wrap:anywhere}</style>'
        '<h1>分段口播审阅</h1><p>独立有声短片；段落字幕为草稿，剪辑时间以timeline.json帧位置为准。</p>' + ''.join(cards), encoding='utf-8')


def render_project(project_file, service, engine, cancel=None, progress=lambda _: None, segment_ids=None):
    """同项目缓存已完成任务；取消/崩溃后再次执行只补缺段。"""
    cancel = cancel or threading.Event()
    project_file = Path(project_file).resolve()
    project = json.loads(project_file.read_text(encoding='utf-8'))
    if segment_ids is not None:
        validate(project, allow_draft=True)
        selected = set(segment_ids)
        if not selected or not selected.issubset({s['id'] for s in project['segments']}):
            raise ValueError('导出段落不存在。')
        project['segments'] = [s for s in project['segments'] if s['id'] in selected]
    planned = plan(project, service.workspace)
    if not planned['ready']:raise ValueError('有段落缺少、损坏或过期的配音；请先查看plan。')
    # 项目可跨工作区使用，缓存不能跨工作区借用同名任务。
    workspace_id = str(Path(service.workspace).resolve())
    cache_file = project_file.with_name(project_file.stem + '.render-cache.json')
    cache = json.loads(cache_file.read_text(encoding='utf-8')) if cache_file.exists() else {}
    if cache.get('workspace') != workspace_id:cache = {'workspace': workspace_id, 'entries': {}}
    folder = project_file.parent/'runs'/uuid.uuid4().hex
    folder.mkdir(parents=True, exist_ok=False)
    atomic_json(folder/'plan.json', planned)
    results = []
    try:
        for index, row in enumerate(planned['segments'], 1):
            if cancel.is_set():raise InterruptedError('已取消分段口播。')
            spec = RenderSpec.from_dict(row['request'])
            key = fingerprint({'request': row['request'], 'engine': engine})
            ident = cache['entries'].get(key)
            reusable = False
            if ident:
                try:
                    job = service.jobs.get(ident)
                    if job['request'] != row['request']:raise ValueError('缓存请求不一致。')
                    if job['status'] == 'complete':
                        media = service.completed_folder(ident)
                        reusable = True
                    elif job['status'] != 'queued':ident = None
                except (OSError, ValueError, KeyError):ident = None
            if not reusable:
                if not ident:ident = service.jobs.add(spec)
                cache['entries'][key] = ident
                atomic_json(cache_file, cache)
                progress(f'第{index}/{len(planned["segments"])}段：生成')
                media = service.run(ident, cancel, lambda value:progress(f'第{index}/{len(planned["segments"])}段：{value}%'))
            else:progress(f'{row["id"]}：复用已校验成品')
            results.append({'id': row['id'], 'job_id': ident, 'folder': str(media.resolve()), 'reused': reusable,
                            'start_frame': row['start_frame'], 'end_frame': row['end_frame'], 'fps': planned['fps']})
        if cancel.is_set():raise InterruptedError('已取消分段口播。')
        atomic_json(folder/'timeline.json', {'schema': 1, 'fps': planned['fps'], 'frames': planned['frames'], 'segments': results})
        write_editing_files(folder, planned, results)
        atomic_json(folder/'complete.json', {'schema': 1, 'project_sha256': planned['project_sha256'], 'engine': engine,
                    'segments': results, 'files': {name: digest(folder/name) for name in
                        ('plan.json', 'timeline.json', '段落字幕草稿.srt', '剪辑说明.txt', '预览.html')}})
        return folder
    except BaseException as exc:
        atomic_json(folder/'error.json', {'error': str(exc), 'completed_segments': results})
        raise


def save_draft(path, project, expected=None):
    """持工作区锁调用；检测外部修改，先归档上一版再原子保存。"""
    validate(project, allow_draft=True)
    path = Path(path)
    if path.exists():
        previous = json.loads(path.read_text(encoding='utf-8'))
        if fingerprint(previous) != expected:raise ValueError('项目文件已被其他程序修改，请先重新打开；当前编辑仍保留在窗口。')
        if previous == project:return expected
        atomic_json(path.parent/'revisions'/(fingerprint(previous)+'.json'), previous)
    elif expected is not None:raise ValueError('项目文件已被移走，当前编辑仍保留在窗口。')
    atomic_json(path, project)
    return fingerprint(project)
