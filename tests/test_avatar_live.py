"""直播追踪数据与驱动回归。测试不会启动真实摄像头。"""
from pathlib import Path
import sys,math,unittest
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parent.parent
sys.path[:0]=[str(ROOT/'.runtime/python'),str(ROOT/'.runtime/avatar-live-python'),str(ROOT)]
import numpy as np
from avatar_app.tracking import MotionFilter,Motion,Observation,rotation_angles,shoulder_angle
from avatar_app.rig import Rig


class TrackingTests(unittest.TestCase):
    def test_no_input_is_neutral(self):
        f=MotionFilter()
        motion,found=f.sample(now=0)
        self.assertFalse(found)
        self.assertEqual(motion,Motion())
        self.assertFalse(f.calibrate(now=0))

    def test_calibration_and_live_actions(self):
        f=MotionFilter()
        raw=Observation(5,7,-3,jaw=.1,eye_left=.2,eye_right=.1,shoulder_roll=4)
        f.observe(raw,now=0)
        self.assertTrue(f.calibrate(now=0))
        motion,found=f.sample(now=.05,mirror=False)
        self.assertTrue(found)
        self.assertEqual(motion,Motion())
        f.observe(Observation(30,7,-3,jaw=.7,eye_left=1,eye_right=.1,shoulder_roll=16),now=.1)
        motion,_=f.sample(now=.1,mirror=False)
        self.assertGreater(motion.turn,.3)
        self.assertGreater(motion.mouth,.5)
        self.assertGreater(motion.blink_left,.5)
        self.assertEqual(motion.blink_right,0)
        self.assertGreater(motion.lean,.3)

    def test_mirror_changes_direction_and_eyes(self):
        values=[]
        for mirror in (False,True):
            f=MotionFilter();f.observe(Observation(yaw=20,eye_left=1,eye_right=0),now=0)
            values.append(f.sample(now=.1,mirror=mirror)[0])
        self.assertAlmostEqual(values[0].turn,-values[1].turn)
        self.assertAlmostEqual(values[0].blink_left,values[1].blink_right)
        self.assertEqual(values[1].blink_left,0)

    def test_lost_tracking_returns_to_neutral(self):
        f=MotionFilter();f.observe(Observation(yaw=25,jaw=.6,eye_left=1,eye_right=1),now=0)
        first,_=f.sample(now=.1)
        self.assertGreater(first.mouth,.5)
        for t in np.arange(.5,2,.1):
            result,found=f.sample(now=float(t))
        self.assertFalse(found)
        self.assertLess(max(abs(v) for v in result.kwargs().values()),.001)
        self.assertFalse(f.calibrate(now=2))

    def test_nonfinite_and_large_inputs_do_not_escape_limits(self):
        f=MotionFilter();f.observe(Observation(float('nan'),1e9,-1e9,jaw=float('inf'),eye_left=-100,eye_right=500),now=0)
        motion,_=f.sample(now=.1)
        self.assertTrue(all(math.isfinite(v) and abs(v)<=1 for v in motion.kwargs().values()))
        self.assertEqual(motion.mouth,0)

    def test_rotation_matrix_and_shoulder_visibility(self):
        a=math.radians(20);matrix=np.eye(4)
        matrix[:3,:3]=[[math.cos(a),0,math.sin(a)],[0,1,0],[-math.sin(a),0,math.cos(a)]]
        yaw,pitch,roll=rotation_angles(matrix)
        self.assertAlmostEqual(yaw,20);self.assertAlmostEqual(pitch,0);self.assertAlmostEqual(roll,0)
        self.assertEqual(rotation_angles(np.full((4,4),float('nan'))),(0,0,0))
        points=[SimpleNamespace(x=0,y=0,visibility=0) for _ in range(33)]
        points[11]=SimpleNamespace(x=.7,y=.45,visibility=.99)
        points[12]=SimpleNamespace(x=.3,y=.35,visibility=.99)
        self.assertGreater(shoulder_angle(points,4/3),0)
        points[11].visibility=.2
        self.assertIsNone(shoulder_angle(points))

    def test_eyes_are_independent_and_no_mouth_holes(self):
        r=Rig(scale=360/1024)
        a=np.array(r.frame(0,(360,540),blink=0,breath=False))
        left=np.array(r.frame(0,(360,540),blink=0,blink_left=1,blink_right=0,breath=False))
        right=np.array(r.frame(0,(360,540),blink=0,blink_left=0,blink_right=1,breath=False))
        self.assertTrue(np.array_equal(a[:,:,3],left[:,:,3]))
        self.assertTrue(np.array_equal(a[:,:,3],right[:,:,3]))
        self.assertFalse(np.array_equal(left,right))
        self.assertTrue(np.array_equal(a[80:95,190:230],left[80:95,190:230]))
        self.assertTrue(np.array_equal(a[80:95,140:180],right[80:95,140:180]))
        for level in [.081,.1,.15]:
            frame=np.array(r.frame(0,(360,540),mouth=level,roll=.4,lean=.4,blink_left=0,blink_right=0))
            self.assertGreater(int(frame[110:124,175:188,3].min()),240)


class LiveUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app=QApplication.instance() or QApplication([])

    def test_opening_window_never_opens_camera(self):
        from avatar_app.app import Window
        from unittest.mock import patch
        with patch('avatar_app.live.QCamera',side_effect=AssertionError('camera may start only after click')):
            w=Window(ROOT/'.runtime/avatar-live-test-workspace')
            w.tabs.setCurrentIndex(1)
            w.show_output();w.tick();self.app.processEvents()
            self.assertFalse(w.live.active)
            self.assertIsNone(w.live.camera)
            rgb=w.output_window.grab().toImage().pixelColor(0,0)
            self.assertEqual((rgb.red(),rgb.green(),rgb.blue()),(0,255,0))
            w.close();self.app.processEvents()

    def test_mailbox_is_bounded_and_stop_clears_frames(self):
        from avatar_app.live import InferenceWorker
        w=InferenceWorker()
        for i in range(100):
            w.submit(i)
        self.assertEqual(w.pending[0],99)
        w.stop();w.submit(1000)
        self.assertIsNone(w.pending)

    def test_stop_releases_camera_and_session(self):
        from avatar_app.live import LiveCapture
        from unittest.mock import Mock
        capture=LiveCapture()
        camera,session,sink=Mock(),Mock(),Mock()
        capture.camera,capture.session,capture.sink=camera,session,sink
        capture.stop()
        camera.stop.assert_called_once()
        session.setCamera.assert_called_once_with(None)
        session.setVideoSink.assert_called_once_with(None)
        self.assertIsNone(capture.camera)
        capture.close()


if __name__=='__main__':unittest.main()
