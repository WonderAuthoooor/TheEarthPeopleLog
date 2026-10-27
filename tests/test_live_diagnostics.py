import copy
import json
from pathlib import Path
import tempfile
import unittest

from avatar3d.live_diagnostics import inspect_scene
from avatar3d.models import atomic_json, digest
from avatar3d.warudo_scene import compose_scene, set_value
from avatar3d.warudo_blueprints import PLAY_NODE
from tests.test_warudo_scene import fixture, RESOURCES


class LiveDiagnosticTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root/'Warudo.exe').write_bytes(b'marker')
        self.data = self.root/'Warudo_Data/StreamingAssets'
        for folder in ('Scenes', 'Characters', 'CharacterAnimations'):
            (self.data/folder).mkdir(parents=True)
        for name in ('idle', 'wave', 'explain'):
            (self.data/'CharacterAnimations'/f'{name}.warudo').write_bytes(name.encode())
        (self.data/'Characters/C.vrm').write_bytes(b'model')
        self.scene = compose_scene(fixture(), 'Live_v002', 'character://data/Characters/C.vrm', RESOURCES)
        for a in self.scene['assets']: a['active'] = True
        self.scene['assets'][0]['dataInputs']['Enabled'] = {'value': 'true'}
        for g in self.scene['graphs']: g['enabled'] = True
        self.path = self.data/'Scenes/Live_v002.json'

    def check(self):
        atomic_json(self.path,self.scene); before=digest(self.path)
        result=inspect_scene(self.path,self.root)
        self.assertEqual(before,digest(self.path))
        return result

    def codes(self):
        return {f['code'] for f in self.check()['findings']}

    def plays(self):
        return [n for g in self.scene['graphs'] for n in g['nodes'].values() if n['typeId']==PLAY_NODE]

    def test_valid_config_never_certifies_camera_or_obs(self):
        result=self.check()
        self.assertTrue(result['configuration_ok'], result['findings'])
        self.assertFalse(result['runtime_verified'])
        self.assertEqual({f['level'] for f in result['findings']},{'pending'})

    def test_old_double_arm_mask_and_unmasked_detected(self):
        play=self.plays()[0]
        set_value(play,'MaskedBodyParts',[{'value':5},{'value':6},{'value':7},{'value':8}])
        self.assertIn('gesture_mask',self.codes())
        set_value(play,'Masked',False)
        self.assertIn('gesture_mask',self.codes())

    def test_disabled_graph_and_duplicate_hotkey(self):
        self.scene['graphs'][1]['enabled']=False
        self.assertIn('gesture_binding',self.codes())
        self.scene['graphs'][1]['enabled']=True
        self.scene['graphs'].append(copy.deepcopy(self.scene['graphs'][1]))
        self.assertIn('duplicate_hotkey',self.codes())

    def test_wrong_character_missing_resource_and_null_action(self):
        set_value(self.plays()[0],'Character',{'id':'missing'})
        (self.data/'CharacterAnimations/wave.warudo').unlink()
        self.assertTrue({'gesture_character','resource_missing'} <= self.codes())
        set_value(self.plays()[0],'Animation',None)
        self.assertIn('gesture_resource',self.codes())

    def test_tracking_reference_and_camera_do_not_touch_devices(self):
        set_value(self.scene['assets'][0],'TrackingEnabled',True)
        set_value(self.scene['assets'][0],'TrackingAssetIds',['missing-camera'])
        set_value(self.scene['assets'][1],'TransparentBackground',False)
        self.assertTrue({'tracking_reference','camera_output'} <= self.codes())

    def test_invalid_numeric_and_missing_field(self):
        set_value(self.plays()[0],'Speed',float('nan'))
        del self.plays()[0]['dataInputs']['Masked']
        self.assertTrue({'gesture_parameter','field'} <= self.codes())

    def test_unsafe_resource_and_unsupported_scene_rejected(self):
        set_value(self.scene['assets'][0],'Source','character://data/Characters/../secret.vrm')
        with self.assertRaises(ValueError):self.check()
        self.scene['appVersion']='future'
        with self.assertRaises(ValueError):self.check()

    def test_ui_background_diagnostic(self):
        import os
        os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
        import time
        from PySide6.QtWidgets import QApplication
        from avatar3d.live_ui import LivePanel
        from avatar3d.live_package import create_package
        atomic_json(self.path,self.scene)
        prepared=self.root/'prepared';prepared.mkdir()
        assets={}
        for folder in ('Characters','CharacterAnimations'):
            for p in (self.data/folder).iterdir():assets[p.name]={'file':str(p),'sha256':digest(p)}
        atomic_json(prepared/'complete.json',{'scene_file':self.path.name,'scene_sha256':digest(self.path),'assets':assets})
        package=self.root/'package';create_package(prepared,self.root,package)
        # 改变用户保存的镜头，仍可诊断而不强行覆盖恢复原版本。
        set_value(self.scene['assets'][1],'FieldOfView',40);atomic_json(self.path,self.scene)
        app=QApplication.instance() or QApplication([])
        panel=LivePanel(self.root);self.addCleanup(panel.close)
        panel.package.setText(str(package));panel.install.setText(str(self.root))
        panel.start('diagnose',self.path)
        deadline=time.monotonic()+10
        while (panel.busy or panel.worker.isRunning()) and time.monotonic()<deadline:
            app.processEvents();time.sleep(.01)
        app.processEvents()
        self.assertFalse(panel.busy)
        self.assertTrue(panel.diagnostic['configuration_ok'],panel.report.toPlainText())
        self.assertIn('基线不同',panel.report.toPlainText())
        self.assertFalse(panel.restore.isEnabled())
        self.assertEqual(json.loads(self.path.read_text(encoding='utf-8'))['assets'][1]['dataInputs']['FieldOfView']['value'],'40')
