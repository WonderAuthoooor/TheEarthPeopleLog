"""分段口播研发入口；与桌面程序共用工作区排他锁和渲染服务。"""
from pathlib import Path
import argparse
import json
import signal
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'.runtime/python'), str(ROOT)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--project', type=Path, required=True)
    commands = parser.add_subparsers(dest='command', required=True)
    init = commands.add_parser('init', help='按空行分段建项目，文本文件须UTF-8')
    init.add_argument('--model', type=Path, required=True)
    init.add_argument('--text', type=Path, required=True)
    init.add_argument('--width', type=int, default=480, choices=(320,480,720,1080))
    init.add_argument('--fps', type=int, default=30, choices=(12,24,30))
    bind = commands.add_parser('bind', help='把当前段落文本与本地配音绑定')
    bind.add_argument('--segment', required=True)
    bind.add_argument('--audio', type=Path, required=True)
    edit = commands.add_parser('edit', help='改文本后旧配音标为过期；动作可单独改')
    edit.add_argument('--segment', required=True)
    edit.add_argument('--text', type=Path)
    edit.add_argument('--action', choices=('idle','explain'))
    reorder = commands.add_parser('reorder', help='给出全部段落编号，保持编号不变')
    reorder.add_argument('ids', nargs='+')
    add = commands.add_parser('add', help='追加一段；--after可指定插入位置')
    add.add_argument('--text', type=Path, required=True)
    add.add_argument('--after')
    remove = commands.add_parser('remove', help='删除一段引用，保留旧素材和文档历史')
    remove.add_argument('--segment', required=True)
    commands.add_parser('plan', help='检查配音与帧时间线，不渲染')
    render = commands.add_parser('render', help='只生成缺失或变化段，Ctrl+C取消')
    render.add_argument('--runtime', type=Path, default=ROOT/'.runtime/avatar3d/runtime.json')
    args = parser.parse_args()
    from PySide6.QtCore import QCoreApplication, QLockFile
    from avatar3d import speech_project as speech
    from avatar3d.models import atomic_json, import_model
    app = QCoreApplication.instance() or QCoreApplication([])
    workspace = args.workspace.resolve(); workspace.mkdir(parents=True, exist_ok=True)
    args.project = args.project.resolve()
    if not args.project.is_relative_to(workspace):raise ValueError('项目文件须位于工作区内，以保证编辑与渲染受同一排他锁保护。')
    lock = QLockFile(str(workspace/'app.lock')); lock.setStaleLockTime(0)
    if not lock.tryLock(100):raise ValueError('工作区正被桌面程序或其他任务使用，请关闭后再运行。')
    cancel = threading.Event()
    previous = signal.signal(signal.SIGINT, lambda *_: cancel.set())
    try:
        if args.command == 'init':
            if args.project.exists():raise ValueError('项目已存在，不覆盖。')
            text = args.text.read_text(encoding='utf-8-sig')
            model = import_model(workspace, args.model)
            project = speech.create(model['sha256'], text, args.width, args.fps)
        else:
            project = speech.validate(json.loads(args.project.read_text(encoding='utf-8')))
        if args.command == 'bind':
            project = speech.bind_audio(project, args.segment, workspace, args.audio, cancel)
        elif args.command == 'edit':
            segment = next((s for s in project['segments'] if s['id'] == args.segment), None)
            if segment is None:raise ValueError('段落不存在。')
            if args.text:segment['text'] = args.text.read_text(encoding='utf-8-sig').strip()
            if args.action:segment['action'] = args.action
        elif args.command == 'reorder':
            old = {s['id']:s for s in project['segments']}
            if len(args.ids) != len(old) or set(args.ids) != set(old):raise ValueError('必须且只能给出全部编号一次。')
            project['segments'] = [old[i] for i in args.ids]
        elif args.command == 'add':
            import uuid
            ids = [s['id'] for s in project['segments']]
            if args.after and args.after not in ids:raise ValueError('插入位置的段落不存在。')
            index = ids.index(args.after)+1 if args.after else len(ids)
            project['segments'].insert(index, {'id':uuid.uuid4().hex[:12], 'action':'idle',
                                              'text':args.text.read_text(encoding='utf-8-sig').strip()})
        elif args.command == 'remove':
            if args.segment not in [s['id'] for s in project['segments']]:raise ValueError('段落不存在。')
            project['segments'] = [s for s in project['segments'] if s['id'] != args.segment]
        if args.command in ('init','bind','edit','reorder','add','remove'):
            speech.validate(project)
            # 每次编辑保留旧文档；渲染计划另外有不可变副本。
            if args.project.exists():
                old = json.loads(args.project.read_text(encoding='utf-8'))
                atomic_json(args.project.parent/'revisions'/(speech.fingerprint(old)+'.json'), old)
            atomic_json(args.project, project)
        if args.command == 'render':
            from avatar3d.backend import Runtime, BlenderBackend
            from avatar3d.service import RenderService
            service = RenderService(workspace, BlenderBackend(Runtime.load(args.runtime)))
            # 已持有同一工作区锁，可安全处理上次异常退出任务。
            service.jobs.recover()
            output = speech.render_project(args.project, service, speech.engine_signature(args.runtime), cancel, print)
            print(str(output))
        else:print(json.dumps(speech.plan(project, workspace), ensure_ascii=False, indent=2))
    finally:
        signal.signal(signal.SIGINT, previous)
        lock.unlock()


if __name__ == '__main__':
    try:main()
    except Exception as exc:
        print(f'失败：{exc}', file=sys.stderr)
        raise SystemExit(1)
