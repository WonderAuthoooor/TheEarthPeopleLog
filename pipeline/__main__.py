"""GUI by default; CLI supports headless render and reproducible QA."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".runtime" / "python"))


def main():
    parser = argparse.ArgumentParser(description="地球人日志视频草稿流水线")
    parser.add_argument("--job", dest="gui_job", type=Path, help="启动界面时打开指定任务")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("doctor", help="检查媒体依赖")
    sub.add_parser("new", help="创建空任务")
    for name in ("render", "download"):
        command = sub.add_parser(name)
        command.add_argument("job", type=Path, help="含job.json的目录")
        if name == "render": command.add_argument("--resolution", type=int, choices=(540, 1080), default=1080)
    args = parser.parse_args()
    from . import core
    try:
        if args.command == "doctor":
            import av, PIL, yt_dlp
            print("Python:", sys.version.split()[0])
            print("FFmpeg:", core.ffmpeg_exe())
            print("PyAV:", av.__version__, "/ Pillow:", PIL.__version__)
            print("中文字体:", core.font(24).getname())
        elif args.command == "new":
            print(core.new_job()[0])
        elif args.command == "render":
            core.render(args.job, core.load_job(args.job), resolution=args.resolution)
        elif args.command == "download":
            core.download_x(args.job, core.load_job(args.job))
        else:
            from .gui import main as gui_main
            gui_main(args.gui_job)
    except core.PipelineError as exc:
        print("处理未完成:", exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
