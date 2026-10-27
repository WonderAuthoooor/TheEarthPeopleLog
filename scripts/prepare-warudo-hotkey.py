"""Prepare a standalone Warudo 0.15.1 one-shot hotkey graph; never edit a scene."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / '.runtime/python'), str(ROOT)]
from avatar3d.warudo_blueprints import KEY_NODE, PLAY_NODE, CHARACTER, PRESETS, build_graph

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", type=Path, required=True)
    parser.add_argument("--character-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--action", choices=tuple(PRESETS), default="wave")
    args = parser.parse_args()
    scene = json.loads(args.scene.read_text(encoding="utf-8-sig"))
    graph = build_graph(scene, args.character_id, args.action)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as file:
        json.dump(graph, file, ensure_ascii=False, indent=2)
        file.write("\n")
    print(args.output)
    print("Prepared only. Import in Warudo, choose Animation, then verify playback.")


if __name__ == "__main__":
    main()

