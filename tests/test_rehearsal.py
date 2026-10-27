import copy,math,unittest
from avatar3d.rehearsal import DEFAULT,validate,sample,selected_frames

class RehearsalTests(unittest.TestCase):
    def test_default_timing_and_weights(self):
        plan=validate(copy.deepcopy(DEFAULT))
        for time in (0,2.99,6,15,22,28,30):self.assertIsNone(sample(plan,time)[0])
        for time,action in ((4,'wave'),(12,'explain'),(20,'wave'),(26,'explain')):
            clip,_,weight=sample(plan,time);self.assertEqual(clip['action'],action);self.assertEqual(weight,1)
    def test_fades_are_continuous_at_boundaries(self):
        for clip in DEFAULT['gestures']:
            for time in (clip['start'],clip['start']+1e-5,clip['start']+clip['duration']-1e-5):
                self.assertLess(sample(DEFAULT,time)[2],1e-10)
    def test_invalid_overlap_order_and_durations_rejected(self):
        for edit in (lambda p:p.update(fade=0),lambda p:p.update(duration=float('nan')),
                     lambda p:p['gestures'][1].update(start=4),lambda p:p['gestures'][0].update(action='unknown'),
                     lambda p:p['gestures'][0].update(duration=.1),lambda p:p['gestures'][-1].update(start=29)):
            plan=copy.deepcopy(DEFAULT);edit(plan)
            with self.assertRaises(ValueError):validate(plan)
    def test_sample_invalid_times(self):
        for time in (-1,31,float('nan')):
            with self.assertRaises(ValueError):sample(DEFAULT,time)
    def test_sparse_render_does_not_change_baked_duration(self):
        request={'duration':30,'fps':30,'rehearsal':DEFAULT,'rehearsal_render_frames':[0,45,899]}
        self.assertEqual(selected_frames(request),[0,45,899])
        for frames in ([],[-1],[900],[2,1],[1,1],[False]):
            with self.assertRaises(ValueError):selected_frames({**request,'rehearsal_render_frames':frames})
        del request['rehearsal_render_frames'];self.assertEqual(len(selected_frames(request)),900)

if __name__=='__main__':unittest.main()
