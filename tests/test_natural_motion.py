import math
import unittest
from avatar3d.natural_motion import sample
from avatar3d.contracts import RenderSpec


class MotionTests(unittest.TestCase):
    def test_loop_endpoint_and_velocity_are_continuous(self):
        for action in ('idle', 'explain'):
            for key in ('gesture', 'breath', 'sway', 'blink', 'head_nod', 'emphasis'):
                self.assertAlmostEqual(sample(action, 0, 4)[key], sample(action, 4, 4)[key], places=10)
                before = (sample(action, 4, 4)[key] - sample(action, 4 - 1e-5, 4)[key]) / 1e-5
                after = (sample(action, 1e-5, 4)[key] - sample(action, 0, 4)[key]) / 1e-5
                self.assertAlmostEqual(before, after, places=3)

    def test_blink_is_bounded_and_gesture_has_rest_and_hold(self):
        values = [sample('explain', i / 120, 4) for i in range(481)]
        self.assertEqual(values[0]['gesture'], 0)
        self.assertEqual(values[-1]['gesture'], 0)
        self.assertEqual(values[240]['gesture'], 1)
        self.assertGreater(max(v['blink'] for v in values), .99)
        self.assertTrue(all(0 <= v['blink'] <= 1 for v in values))
        self.assertEqual(sample('idle', .2, .5)['blink'], 0)

    def test_new_actions_and_old_snapshots_remain_supported(self):
        for action in ('neutral', 'bend', 'wave', 'hold', 'turntable', 'idle', 'explain'):
            spec = RenderSpec('a' * 64, action)
            self.assertEqual(RenderSpec.from_dict(spec.to_dict()), spec)
        for duration in (0, float('inf'), float('nan')):
            with self.assertRaises(ValueError):sample('idle', 0, duration)


if __name__ == '__main__':unittest.main()
