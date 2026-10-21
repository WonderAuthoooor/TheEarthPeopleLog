"""研发CLI：从本工具已完成的任务制作动作交换包，供双端实测。"""
from pathlib import Path
import argparse
import sys
import threading

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / '.runtime/python'), str(ROOT)]
from avatar3d.backend import Runtime
from avatar3d.motion_exchange import export_exchange


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True, help='本工具生成且有complete.json的任务目录')
    parser.add_argument('--model', type=Path, required=True, help='与源任务哈希一致的VRM')
    parser.add_argument('--output', type=Path, required=True, help='新的输出目录，不覆盖已有文件')
    parser.add_argument('--runtime', type=Path, default=ROOT / '.runtime/avatar3d/runtime.json')
    args = parser.parse_args()
    output = export_exchange(args.source, args.model, args.output, Runtime.load(args.runtime),
                             threading.Event(), lambda value: print(f'{value}%', flush=True))
    print(output)
