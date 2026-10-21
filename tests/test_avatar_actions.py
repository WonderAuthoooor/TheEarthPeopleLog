"""动作衔接、脸部透明度、评分和快捷键资源生命周期；不启用真人摄像头。"""
from pathlib import Path
import sys,math,tempfile,unittest,ctypes
from unittest.mock import Mock
ROOT=Path(__file__).resolve().parent.parent
sys.path[:0]=[str(ROOT/'.runtime/python'),str(ROOT/'.runtime/avatar-live-python'),str(ROOT)]
import numpy as np
from avatar_app.actions import ACTION_ORDER,ROOTS,LENGTH,ActionController,pose_at,joints,clip_pose
from avatar_app.action_art import validate_score
from avatar_app.rig import Rig
from avatar_app.export import export_clip
from avatar_app.hotkeys import GlobalHotkeys
from ctypes import wintypes


class ActionTests(unittest.TestCase):
    def test_interrupt_transition_is_continuous_and_lengths_fixed(self):
        controller=ActionController(now=0)
        for index,key in enumerate(ACTION_ORDER):
            now=index*.13
            before=controller.sample(now)
            controller.trigger(key,now)
            after=controller.sample(now)
            self.assertEqual(before,after)
            for t in np.linspace(now,now+.12,7):
                current=controller.sample(float(t))
                for side in ROOTS:
                    a,b,c=joints(side,current.angles[side])
                    self.assertAlmostEqual(math.dist(a,b),LENGTH)
                    self.assertAlmostEqual(math.dist(b,c),LENGTH)
        controller.trigger('idle',now=3)
        for side in ROOTS:
            for actual,expected in zip(controller.sample(4).angles[side],pose_at('idle').angles[side]):
                self.assertAlmostEqual(actual,expected)

    def test_clip_enters_and_returns_idle(self):
        for key in ACTION_ORDER:
            self.assertEqual(clip_pose(key,0,3).angles,pose_at('idle').angles)
            self.assertEqual(clip_pose(key,3,3).angles,pose_at('idle').angles)
        self.assertNotEqual(pose_at('wave',0).hand_angles,pose_at('wave',.2).hand_angles)

    def test_expressions_and_low_mouth_do_not_cut_face(self):
        rig=Rig(scale=360/1024)
        for key in ACTION_ORDER:
            base=np.array(rig.frame(0,(360,540),pose=pose_at(key),blink=0,breath=False))
            for mouth in (.081,.1,1):
                current=np.array(rig.frame(0,(360,540),pose=pose_at(key),mouth=mouth,blink=0,breath=False))
                self.assertTrue(np.array_equal(base[:,:,3],current[:,:,3]),key)
                self.assertGreater(int(current[114:120,175:188,3].min()),240,key)

    def test_score_validation_and_no_ledger_mutation(self):
        ledger=ROOT/'state/score-ledger.json';before=ledger.read_bytes()
        self.assertEqual(validate_score('待评'),'待评')
        for value in np.arange(-5,5.01,.5):self.assertEqual(validate_score(str(value)),f'{value:+.1f}')
        for bad in ('+5.5','-6','0.1','nan','文明进步','1e0'):
            with self.assertRaises(ValueError):validate_score(bad)
        Rig(scale=360/1024).frame(0,(360,540),pose=pose_at('score'),score='+1.5')
        self.assertEqual(before,ledger.read_bytes())

    def test_invalid_action_score_fail_before_writes(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'.runtime/avatar-tests') as tmp:
            for kwargs in ({'action':'missing'},{'score_text':'+8'},{'action':'all','audio':'anything.wav'}):
                with self.assertRaises(ValueError):export_clip(tmp,**kwargs)
            self.assertEqual(list(Path(tmp).iterdir()),[])


class HotkeyTests(unittest.TestCase):
    def test_default_off_conflict_releases_only_owned_keys(self):
        h=GlobalHotkeys(Mock());self.assertEqual(h.registered,{})
        h.user=Mock();h.user.RegisterHotKey.side_effect=[True,True,False]
        with self.assertRaises(RuntimeError):h.enable(ACTION_ORDER)
        self.assertEqual(h.registered,{})
        self.assertEqual([x.args[1] for x in h.user.UnregisterHotKey.call_args_list],[0x4600,0x4601])

    def test_dispatch_and_unregister(self):
        callback=Mock();h=GlobalHotkeys(callback);h.user=Mock()
        h.enable(ACTION_ORDER)
        self.assertEqual(len(h.registered),11)
        message=wintypes.MSG();message.message=0x0312;message.wParam=0x4607
        self.assertEqual(h.nativeEventFilter(b'windows_dispatcher_MSG',ctypes.addressof(message)),(True,0))
        callback.assert_called_once_with('wave')
        h.disable();self.assertEqual(h.user.UnregisterHotKey.call_count,11)
        self.assertEqual(h.registered,{})


if __name__=='__main__':unittest.main()
