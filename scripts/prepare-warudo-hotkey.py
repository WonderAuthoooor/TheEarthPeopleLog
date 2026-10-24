"""Prepare a standalone Warudo 0.15.1 one-shot hotkey graph; never edit a scene."""
from __future__ import annotations
import argparse
import copy
import json
from pathlib import Path
from uuid import uuid4

KEY_NODE = "d341c82e-d6d2-4910-bdb6-2f9719470619"
PLAY_NODE = "3c8f47ba-5430-4061-8506-19812b4d2ec0"
CHARACTER = "726ab674-a550-474e-8b92-66526a5ad55e"


def uid():
    return str(uuid4())


def port(key, value, type_name, kind="Value", order=0):
    return {"key": key, "type": type_name, "typeKind": kind,
            "value": json.dumps(value, ensure_ascii=False), "defaultValue": None,
            "properties": {"transient": False, "typeProperties": None,
                           "order": order, "hidden": False, "disabled": False,
                           "label": key, "description": None,
                           "sectionTitle": None, "sectionHidden": False}}


def build_graph(scene, character_id):
    """Clone only the verified key-node shape; use fresh IDs and native one-shot node."""
    characters = {asset["id"]: asset for asset in scene["assets"]}
    if character_id not in characters or characters[character_id]["typeId"] != CHARACTER:
        raise ValueError("Character ID is not a character asset in the supplied scene")
    nodes = [n for g in scene["graphs"] for n in g["nodes"].values()]
    key_nodes = [n for n in nodes if n["typeId"] == KEY_NODE]
    if not key_nodes:
        raise ValueError("No native keystroke node available as schema reference")
    for n in key_nodes:
        d = n["dataInputs"]
        if (json.loads(d["Keystroke"]["value"])["value"] == 66
                and all(json.loads(d[k]["value"]) == v for k, v in
                        {"RequireCtrl": True, "RequireAlt": True,
                         "RequireShift": False, "RequireMeta": False}.items())):
            raise ValueError("Ctrl+Alt+F8 is already assigned in the saved scene")
    key = copy.deepcopy(key_nodes[0])
    key.update(id=uid(), x=0.0, y=0.0)
    key["dataInputs"]["Keystroke"]["value"] = json.dumps(
        {"label": "F8", "value": 66, "description": None, "icon": None})
    for name, value in {"RequireCtrl": True, "RequireAlt": True,
                        "RequireShift": False, "RequireMeta": False}.items():
        key["dataInputs"][name]["value"] = json.dumps(value)
    flow = copy.deepcopy(key["flowOutputs"]["Exit"])
    enter = copy.deepcopy(flow)
    enter["key"] = "Enter"
    enter["properties"]["label"] = "ENTER"
    done = copy.deepcopy(flow)
    done["key"] = "OnAnimationEnd"
    done["properties"]["label"] = "ON_ANIMATION_END"
    data = {
        "Character": port("Character", {"id": character_id,
            "name": characters[character_id]["name"]},
            "Warudo.Plugins.Core.Assets.Character.CharacterAsset", "Asset", 13),
        # Let the native resource picker resolve the installed animation once.
        # A filename is not a verified Warudo resource URI.
        "Animation": port("Animation", None, "string", order=17),
        "TransitionTime": port("TransitionTime", 0.2, "float", order=23),
        "Weight": port("Weight", 1.0, "float", order=28),
        "Speed": port("Speed", 1.0, "float", order=33),
        "Masked": port("Masked", False, "bool", order=38),
        "Additive": port("Additive", False, "bool", order=70),
    }
    play = {"typeId": PLAY_NODE, "name": "PLAY_CHARACTER_ONE_SHOT_ANIMATION",
            "id": uid(), "version": 0, "x": 480.0, "y": 0.0,
            "dataInputs": data, "dataOutputs": {}, "triggers": {},
            "flowInputs": {"Enter": enter},
            "flowOutputs": {"Exit": flow, "OnAnimationEnd": done}}
    graph = {"id": uid(), "name": "AvatarLab｜单次挥手｜Ctrl+Alt+F8",
             "enabled": True, "order": 0, "group": None,
             "panningX": 0.0, "panningY": 0.0, "scaling": 1.0,
             "nodes": {key["id"]: key, play["id"]: play},
             "dataConnections": [], "flowConnections": [{
                 "outputNode": key["id"], "inputNode": play["id"],
                 "outputPort": "Exit", "inputPort": "Enter"}]}
    properties = copy.deepcopy(scene["graphs"][0]["properties"])
    properties["id"] = uid()
    properties["dataInputs"]["Variables"]["value"] = "[]"
    graph["properties"] = properties
    return graph


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", type=Path, required=True)
    parser.add_argument("--character-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    scene = json.loads(args.scene.read_text(encoding="utf-8-sig"))
    graph = build_graph(scene, args.character_id)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as file:
        json.dump(graph, file, ensure_ascii=False, indent=2)
        file.write("\n")
    print(args.output)
    print("Prepared only. Import in Warudo, choose Animation, then verify playback.")


if __name__ == "__main__":
    main()

