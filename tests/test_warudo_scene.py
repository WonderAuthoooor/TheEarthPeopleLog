import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from avatar3d.models import atomic_json, digest
from avatar3d.warudo_blueprints import CHARACTER, KEY_NODE, PLAY_NODE, build_graph
from avatar3d.warudo_scene import CAMERA, compose_scene, revise_gestures, value, set_value, animation_resource, install_scene


def fixture():
    def inputs(**kwargs):
        return {k: {'value': json.dumps(v), 'properties': {'hidden': False}} for k, v in kwargs.items()}
    role = {'id': 'role', 'name': '角色1', 'typeId': CHARACTER,
            'dataInputs': inputs(Source='character://data/Characters/old.vrm',
                DefaultIdleAnimation='old-wave', TrackingEnabled=False, TrackingAssetIds=[], TrackingGraphIds=[],
                BreathingEnabled=True, SwayingEnabled=True)}
    camera = {'id': 'camera', 'typeId': CAMERA, 'dataInputs': inputs(TransparentBackground=False,
        SpoutOutput=False, UseChromaKey=False, RenderCharacters=True, RenderEnvironment=True,
        RenderProps=True, RenderScreen=True, FieldOfView=35)}
    key = {'id': 'reference', 'typeId': KEY_NODE, 'dataInputs': inputs(Keystroke={'value': 1},
        RequireCtrl=False, RequireAlt=True, RequireShift=False, RequireMeta=False),
        'flowOutputs': {'Exit': {'key': 'Exit', 'properties': {'label': 'EXIT'}}}}
    expression = {'id': 'expression', 'nodes': {'reference': key}, 'flowConnections': [],
                  'properties': {'dataInputs': {'Variables': {'value': '[]'}}}}
    scene = {'name': 'Original', 'appVersion': '0.15.1', 'assets': [role, camera], 'graphs': [expression],
             'plugins': {'preserve': 'original'}, 'graphHierarchy': {'children': []}}
    wave = build_graph(scene, 'role')
    play = next(n for n in wave['nodes'].values() if n['typeId'] == PLAY_NODE)
    play['dataInputs']['MaskedBodyParts'] = {'value': '[]', 'typeKind': 'EnumArray',
        'properties': {'hidden': True}, 'type': 'Warudo.Plugins.Core.Assets.Character.CharacterAsset+AnimationMaskedBodyPart[]'}
    set_value(play, 'Animation', 'character-animation://data/CharacterAnimations/old.warudo')
    scene['graphs'].append(wave)
    scene['graphHierarchy']['children'] = [{'key': wave['id'], 'children': None}]
    return scene


RESOURCES = {a: f'character-animation://data/CharacterAnimations/{a}.warudo' for a in ('idle', 'wave', 'explain')}


class SceneTests(unittest.TestCase):
    def test_revision_preserves_saved_camera_model_expressions_and_idle(self):
        source = compose_scene(fixture(), 'Live_v001', 'character://data/Characters/C.vrm', RESOURCES)
        # 模拟旧版双臂遮罩和过渡参数，避免测试只覆盖新版生成器自身。
        for graph in source['graphs']:
            for node in graph['nodes'].values():
                if node['typeId'] == PLAY_NODE:
                    set_value(node, 'MaskedBodyParts', [{'label': 'LeftArm', 'value': 5},
                              {'label': 'RightArm', 'value': 6}])
                    set_value(node, 'TransitionTime', .2)
        before = copy.deepcopy(source)
        new_uri = 'character-animation://data/CharacterAnimations/AvatarLabWave0123456789ab.warudo'
        repaired = revise_gestures(source, 'Live_v002', new_uri)
        self.assertEqual(source, before)
        for key in ('assets', 'plugins', 'graphHierarchy'):
            self.assertEqual(repaired[key], source[key])
        self.assertEqual(repaired['graphs'][0], source['graphs'][0])
        for graph in repaired['graphs']:
            for node in graph['nodes'].values():
                if node['typeId'] == PLAY_NODE:
                    self.assertEqual({p['value'] for p in value(node, 'MaskedBodyParts')}, {6, 8})
        plays = [n for g in repaired['graphs'] for n in g['nodes'].values() if n['typeId'] == PLAY_NODE]
        self.assertEqual(sum(value(n, 'Animation') == new_uri for n in plays), 1)
        self.assertEqual(sum(value(n, 'Animation') == RESOURCES['explain'] for n in plays), 1)

    def test_revision_rejects_tracking_ambiguous_binding_and_resource_traversal(self):
        source = compose_scene(fixture(), 'Live_v001', 'character://data/Characters/C.vrm', RESOURCES)
        uri = 'character-animation://data/CharacterAnimations/AvatarLabWave0123456789ab.warudo'
        tracking = copy.deepcopy(source); set_value(tracking['assets'][0], 'TrackingEnabled', True)
        duplicate = copy.deepcopy(source); duplicate['graphs'].append(copy.deepcopy(duplicate['graphs'][1]))
        for invalid in (tracking, duplicate):
            with self.assertRaises(ValueError): revise_gestures(invalid, 'Live_v002', uri)
        for bad in ('../evil', 'character-animation://data/../secret.warudo'):
            with self.assertRaises(ValueError): revise_gestures(source, 'Live_v002', bad)

    def test_scene_prepares_c_idle_outputs_and_head_free_hands_without_mutating_source(self):
        source = fixture(); before = copy.deepcopy(source)
        scene = compose_scene(source, 'Live_v001', 'character://data/Characters/C.vrm', RESOURCES)
        self.assertEqual(source, before)
        self.assertEqual(scene['plugins'], source['plugins'])
        self.assertEqual(scene['graphs'][0], source['graphs'][0])
        role, camera = scene['assets']
        self.assertEqual(value(role, 'Source'), 'character://data/Characters/C.vrm')
        self.assertEqual(value(role, 'DefaultIdleAnimation'), RESOURCES['idle'])
        self.assertFalse(value(role, 'TrackingEnabled'))
        self.assertTrue(value(camera, 'TransparentBackground')); self.assertTrue(value(camera, 'SpoutOutput'))
        self.assertFalse(value(camera, 'RenderEnvironment'))
        self.assertEqual(value(camera, 'FieldOfView'), 35)
        self.assertEqual(len(scene['graphHierarchy']['children']), 2)
        plays = [n for g in scene['graphs'] for n in g['nodes'].values() if n['typeId'] == PLAY_NODE]
        self.assertEqual(len(plays), 2)
        for node in plays:
            self.assertTrue(value(node, 'Masked'))
            self.assertEqual({x['value'] for x in value(node, 'MaskedBodyParts')}, {6, 8})
            self.assertEqual(value(node, 'TransitionTime'), .35)
            self.assertFalse(value(node, 'Additive'))

    def test_conflict_unknown_version_missing_hierarchy_and_tracking_are_rejected(self):
        source = fixture()
        variants = []
        x = copy.deepcopy(source); x['appVersion'] = 'future'; variants.append(x)
        x = copy.deepcopy(source); x['graphHierarchy']['children'] = []; variants.append(x)
        x = copy.deepcopy(source); set_value(x['assets'][0], 'TrackingEnabled', True); variants.append(x)
        x = copy.deepcopy(source); x['assets'].append({'typeId': 'tracker'}); variants.append(x)
        x = copy.deepcopy(source); x['graphs'].append(build_graph(x, 'role', 'explain')); variants.append(x)
        for scene in variants:
            with self.assertRaises(ValueError): compose_scene(scene, 'Live_v001', 'character://data/Characters/C.vrm', RESOURCES)
        for name in ('Original', '../Other', ''):
            with self.assertRaises(ValueError): compose_scene(source, name, 'c', RESOURCES)

    def test_installed_asset_hash_and_loop_type_must_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); path = root / 'Warudo_Data/StreamingAssets/CharacterAnimations/AvatarLabIdle0123456789ab.warudo'
            path.parent.mkdir(parents=True); path.write_bytes(b'mod')
            report = root / 'report.json'
            data = dict(passed=True, editorVersion='2021.3.45f2', modName=path.stem,
                        modFile=str(path), modSha256=digest(path), actionId='idle', loop=True)
            atomic_json(report, data)
            uri, _ = animation_resource(report, root, 'idle')
            self.assertTrue(uri.endswith(path.name))
            data['loop'] = False; atomic_json(report, data)
            with self.assertRaises(ValueError): animation_resource(report, root, 'idle')
            data['loop'] = True; atomic_json(report, data); path.write_bytes(b'changed')
            with self.assertRaises(ValueError): animation_resource(report, root, 'idle')

    def test_install_is_create_new_reuses_identical_and_checks_dependency_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); install = root / 'Warudo'; bundle = root / 'bundle'
            scenes = install / 'Warudo_Data/StreamingAssets/Scenes'; scenes.mkdir(parents=True)
            (install / 'Warudo.exe').touch(); bundle.mkdir()
            dep = scenes.parent / 'character.vrm'; dep.write_bytes(b'vrm')
            source = bundle / 'Live_v001.json'; atomic_json(source, {'scene': 'prepared'})
            record = {'scene_file': source.name, 'scene_sha256': digest(source),
                      'assets': {'model': {'file': str(dep), 'sha256': digest(dep)}}}
            atomic_json(bundle / 'complete.json', record)
            target = install_scene(bundle, install)
            self.assertEqual(digest(target), record['scene_sha256'])
            self.assertEqual(install_scene(bundle, install), target)
            target.write_bytes(b'user-scene')
            with self.assertRaises(FileExistsError): install_scene(bundle, install)
            self.assertEqual(target.read_bytes(), b'user-scene')
            dep.write_bytes(b'new-model')
            with self.assertRaises(ValueError): install_scene(bundle, install)
            self.assertEqual(list(scenes.glob('*.partial')), [])


if __name__ == '__main__': unittest.main()
