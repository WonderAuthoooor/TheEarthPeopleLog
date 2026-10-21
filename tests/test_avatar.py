"""角色试验版的能力边界、透明导出、取消与音量驱动检查。"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT/".runtime/python"),str(ROOT)]
import json
import tempfile
import threading
import unittest
import wave
import numpy as np
import av
from avatar_app.rig import Rig,Envelope
from avatar_app.export import export_clip
TEMP_ROOT = ROOT/".runtime/avatar-tests"
TEMP_ROOT.mkdir(parents=True,exist_ok=True)


class AvatarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rig = Rig(scale=480/1024)

    def test_alpha_and_independent_features(self):
        a = np.array(self.rig.frame(0,(480,720),blink=0,breath=False))
        b = np.array(self.rig.frame(0,(480,720),blink=1,breath=False))
        c = np.array(self.rig.frame(0,(480,720),mouth=1,blink=0,breath=False))
        self.assertEqual(int(a[0,0,3]),0)
        self.assertGreater(int(a[300,240,3]),245)
        self.assertTrue(np.array_equal(a[210:],b[210:]))
        self.assertTrue(np.array_equal(a[210:],c[210:]))
        self.assertGreater(np.abs(a.astype(float)-b).sum(),1000)
        self.assertGreater(np.abs(a.astype(float)-c).sum(),1000)

    def test_turn_does_not_move_body(self):
        a = np.array(self.rig.frame(0,(480,720),turn=0,blink=0,breath=False))
        b = np.array(self.rig.frame(0,(480,720),turn=1,blink=0,breath=False))
        self.assertTrue(np.array_equal(a[220:],b[220:]))
        self.assertFalse(np.array_equal(a[:200],b[:200]))

    def test_mouth_transition_keeps_face_opaque(self):
        # 覆盖低开合的黑条回归点和连续范围；不是只查全闭／全开。
        for width in (360,480,720,1080):
            rig = Rig(scale=width/1024)
            original = np.array(rig.frame(0,(width,width*3//2),blink=0,breath=False))
            for level in (.0801,.081,.09,.1,.11,.12,.15,.25,.5,.75,1):
                with self.subTest(width=width,level=level):
                    current = np.array(rig.frame(0,(width,width*3//2),mouth=level,blink=0,breath=False))
                    self.assertTrue(np.array_equal(original[:,:,3],current[:,:,3]),
                                    "嘴部开合不应在脸上挖出透明缺口")
                    # 暗色预览底／黑色取样不应出现在嘴唇上方的皮肤条带。
                    skin = current[round(310*width/1024):round(318*width/1024),
                                   round(487*width/1024):round(545*width/1024),:3]
                    self.assertGreater(int(skin.min()),50)

    def test_supported_actions_truthful(self):
        self.assertIn("wave",self.rig.config["capabilities"])
        self.assertIn("finger_tracking",self.rig.config["unsupported"])
        self.assertIn("phoneme_alignment",self.rig.config["unsupported"])

    def test_audio_silence_and_energy(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            p = Path(tmp)/"audio.wav"
            data = np.zeros(48000,dtype=np.int16)
            data[16000:32000] = (np.sin(np.arange(16000)*2*np.pi*230/16000)*10000).astype(np.int16)
            with wave.open(str(p),"w") as f:
                f.setparams((1,2,16000,0,"NONE","not compressed"))
                f.writeframes(data.tobytes())
            e = Envelope(p)
            self.assertAlmostEqual(e.duration,3)
            self.assertEqual(e.at(.5),0)
            self.assertGreater(e.at(1.5),.8)
            self.assertEqual(e.at(2.5),0)
            self.assertEqual(e.at(4),0)

    def test_real_video_alpha_and_preview(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            out = export_clip(tmp,duration=1,width=480,fps=24)
            with av.open(str(out/"角色透明.mov")) as f:
                s = f.streams.video[0]
                self.assertEqual(s.codec_context.name,"prores")
                frames = list(f.decode(video=0))
                self.assertEqual(len(frames),24)
                alpha = frames[0].to_ndarray(format="rgba")[:,:,3]
                self.assertEqual(int(alpha[0,0]),0)
                self.assertGreater(int(alpha[300,240]),245)
            with av.open(str(out/"棋盘预览.mp4")) as f:
                self.assertEqual(len(list(f.decode(video=0))),24)
            self.assertEqual(json.loads((out/"request.json").read_text(encoding="utf-8"))["status"],"complete")

    def test_cancel_no_completed_video(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            cancel = threading.Event()
            with self.assertRaises(InterruptedError):
                export_clip(tmp,width=480,duration=1,cancel=cancel,progress=lambda _:cancel.set())
            folder = next(Path(tmp).iterdir())
            self.assertFalse(list(folder.glob("*.mov")))
            self.assertFalse(list(folder.glob("*.mp4")))
            self.assertEqual(json.loads((folder/"request.json").read_text(encoding="utf-8"))["status"],"cancelled")

    def test_invalid_options_do_not_write(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            for kwargs in ({"duration":float("nan")},{"width":999},{"fps":100},{"fixed_turn":9}):
                with self.assertRaises(ValueError):
                    export_clip(tmp,**kwargs)
            self.assertEqual(list(Path(tmp).iterdir()),[])


if __name__ == "__main__":
    unittest.main()
