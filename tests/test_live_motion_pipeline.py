"""直播动作循环合同、工程恢复和键位共存；真实Unity结果另行记录。"""
import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / '.runtime/python'), str(ROOT), str(ROOT / 'tests')]
from avatar3d.models import atomic_json, digest
from avatar3d.unity_project import exchange_request
from avatar3d.warudo_pipeline import INPUTS, preserved_inputs, convert
from avatar3d.unity_project import SDK_SHA256, FBX_ASSET
import test_avatar3d_unity_project as unity_tests

spec = importlib.util.spec_from_file_location('motion_hotkey', ROOT / 'scripts/prepare-warudo-hotkey.py')
hotkey = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hotkey)


class LiveMotionTests(unittest.TestCase):
    def test_model_switch_discards_stale_importer_then_restores_it_on_editor_failure(self):
        with tempfile.TemporaryDirectory(dir=ROOT / '.runtime') as tmp:
            root = Path(tmp); project = root / 'project'; source = root / 'exchange'
            source.mkdir(); (source / 'animation.fbx').write_bytes(b'new-C-model')
            editor = root / 'Unity.exe'; editor.touch()
            atomic_json(project / 'prepare-complete.json', {'editor_version': '2021.3.45f2'})
            atomic_json(project / 'AvatarBridge/sdk-staged.json', {'sdk_sha256': SDK_SHA256})
            for name in INPUTS:
                target = project / name; target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b'old-Seed-input')
            def launch(*args):
                from unittest.mock import Mock
                self.assertFalse((project / (FBX_ASSET + '.meta')).exists())
                self.assertEqual((project / FBX_ASSET).read_bytes(), b'new-C-model')
                # 模拟Unity为新模型写入导入设置，然后导入失败。
                (project / (FBX_ASSET + '.meta')).write_bytes(b'new-C-importer')
                child = Mock(); child.wait.return_value = 20
                return child
            with patch('avatar3d.warudo_pipeline.exchange_request', return_value={'actionId': 'idle'}), \
                    patch('avatar3d.warudo_pipeline.launch_external', side_effect=launch):
                with self.assertRaisesRegex(RuntimeError, '导入失败'):
                    convert(source, project, editor, root / 'output')
            for name in INPUTS:
                self.assertEqual((project / name).read_bytes(), b'old-Seed-input')
            self.assertFalse((root / 'output/complete.json').exists())
            self.assertTrue((root / 'output/error.json').exists())

    def test_loop_requires_closed_roundtrip_and_preserves_full_period(self):
        with tempfile.TemporaryDirectory(dir=ROOT / '.runtime') as tmp:
            fixture = unity_tests.UnityProjectTests()
            source, _ = fixture.fixture(Path(tmp))
            manifest = json.loads((source / 'manifest.json').read_text())
            manifest.update(action_id='idle', fps=30, frames=91, source_frames=90,
                            clip_key_range_seconds=3.0, loop=True)
            atomic_json(source / 'manifest.json', manifest)
            fixture.seal(source)
            with self.assertRaisesRegex(ValueError, '闭合'):
                exchange_request(source)
            atomic_json(source / 'roundtrip.json', {'passed': True, 'loop_closed': True, 'checked_frames': 91})
            fixture.seal(source)
            request = exchange_request(source)
            self.assertEqual((request['actionId'], request['loop'], request['duration']), ('idle', True, 3.0))
            manifest.update(action_id='explain', loop=False, frames=90, clip_key_range_seconds=89/30)
            atomic_json(source / 'manifest.json', manifest)
            fixture.seal(source)
            request = exchange_request(source)
            self.assertEqual((request['actionId'], request['loop']), ('explain', False))
            self.assertAlmostEqual(request['duration'], 89/30)
            manifest['action_id'] = '../unknown'
            atomic_json(source / 'manifest.json', manifest); fixture.seal(source)
            with self.assertRaisesRegex(ValueError, '未知动作'):
                exchange_request(source)

    def test_failed_conversion_restores_inputs_settings_and_releases_owned_lock(self):
        with tempfile.TemporaryDirectory(dir=ROOT / '.runtime') as tmp:
            root = Path(tmp); project = root / 'project'; output = root / 'output'
            before = {}
            for name in INPUTS[:-1]:
                target = project / name; target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(name.encode()); before[name] = target.read_bytes()
            with self.assertRaisesRegex(RuntimeError, 'simulated'):
                with preserved_inputs(project, output):
                    for name in INPUTS:
                        (project / name).write_bytes(b'changed')
                    raise RuntimeError('simulated editor failure')
            for name, value in before.items():
                self.assertEqual((project / name).read_bytes(), value)
            self.assertFalse((project / INPUTS[-1]).exists())
            self.assertFalse((project / 'AvatarBridge/pipeline.lock').exists())
            self.assertTrue(json.loads((output / 'input-restored.json').read_text())['restored'])

    def test_existing_pipeline_or_unity_lock_prevents_mutation(self):
        with tempfile.TemporaryDirectory(dir=ROOT / '.runtime') as tmp:
            project = Path(tmp) / 'project'; output = Path(tmp) / 'output'
            folder = project / 'AvatarBridge'; folder.mkdir(parents=True)
            lock = folder / 'pipeline.lock'; lock.write_text('other-owner')
            with self.assertRaises(FileExistsError):
                with preserved_inputs(project, output): self.fail('must not enter')
            self.assertEqual(lock.read_text(), 'other-owner')
            lock.unlink()
            unity_lock = project / 'Temp/UnityLockfile'; unity_lock.parent.mkdir(); unity_lock.touch()
            with self.assertRaisesRegex(RuntimeError, '会话锁'):
                with preserved_inputs(project, output): self.fail('must not enter')
            self.assertTrue(unity_lock.exists()); self.assertFalse(lock.exists())

    def test_explain_hotkey_coexists_with_wave_and_rejects_duplicates(self):
        node = {'id': 'key-reference', 'typeId': hotkey.KEY_NODE,
                'dataInputs': {k: {'value': json.dumps(v)} for k, v in {
                    'Keystroke': {'value': 1}, 'RequireCtrl': False, 'RequireAlt': False,
                    'RequireShift': False, 'RequireMeta': False}.items()},
                'flowOutputs': {'Exit': {'key': 'Exit', 'properties': {'label': 'EXIT'}}}}
        scene = {'assets': [{'id': 'c', 'name': '角色1', 'typeId': hotkey.CHARACTER}],
                 'graphs': [{'nodes': {'key-reference': node}, 'properties': {
                     'dataInputs': {'Variables': {'value': '[]'}}}}]}
        original = copy.deepcopy(scene)
        wave = hotkey.build_graph(scene, 'c'); scene['graphs'].append(wave)
        explain = hotkey.build_graph(scene, 'c', 'explain')
        self.assertEqual(scene['graphs'][0], original['graphs'][0])
        nodes = list(explain['nodes'].values())
        key = next(n for n in nodes if n['typeId'] == hotkey.KEY_NODE)
        play = next(n for n in nodes if n['typeId'] == hotkey.PLAY_NODE)
        self.assertEqual(json.loads(key['dataInputs']['Keystroke']['value'])['value'], 67)
        self.assertIsNone(json.loads(play['dataInputs']['Animation']['value']))
        self.assertFalse(set(wave['nodes']) & set(explain['nodes']))
        scene['graphs'].append(explain)
        for action in ('wave', 'explain'):
            with self.assertRaisesRegex(ValueError, 'already assigned'):
                hotkey.build_graph(scene, 'c', action)
        with self.assertRaises(ValueError): hotkey.build_graph(original, 'c', 'idle')
        with self.assertRaises(ValueError): hotkey.build_graph(original, 'missing', 'explain')

    @unittest.skipUnless(os.name == 'nt', 'Windows共享文件锁重试')
    def test_atomic_progress_retry_and_persistent_failure_preserve_previous_data(self):
        import avatar3d.models as models
        with tempfile.TemporaryDirectory(dir=ROOT / '.runtime') as tmp:
            target = Path(tmp) / 'progress.json'; atomic_json(target, {'percent': 1})
            real_replace = models.os.replace
            calls = []
            def transient(source, destination):
                calls.append(1)
                if len(calls) < 3: raise PermissionError('sharing violation')
                return real_replace(source, destination)
            with patch.object(models.os, 'replace', side_effect=transient), patch.object(models.time, 'sleep'):
                atomic_json(target, {'percent': 2})
            self.assertEqual(json.loads(target.read_text())['percent'], 2)
            before = digest(target)
            with patch.object(models.os, 'replace', side_effect=PermissionError('persistent')), \
                    patch.object(models.time, 'sleep'):
                with self.assertRaises(PermissionError): atomic_json(target, {'percent': 3})
            self.assertEqual(digest(target), before)
            self.assertEqual(list(Path(tmp).glob('*.tmp')), [])


if __name__ == '__main__': unittest.main()
