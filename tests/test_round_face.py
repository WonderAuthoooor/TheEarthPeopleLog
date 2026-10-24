import math
import unittest
from avatar3d.round_face import rounded_point


class RoundedFaceTests(unittest.TestCase):
    eyes = ((-.04, -.09, 1.605), (.04, -.09, 1.605))

    def test_zero_is_exact_identity(self):
        point = (.06, -.08, 1.55)
        self.assertEqual(rounded_point(point, self.eyes, 0), point)

    def test_cheeks_widen_and_chin_shortens_progressively(self):
        cheek = (.06, -.09, 1.55)
        chin = (0, -.09, 1.505)
        mild = rounded_point(cheek, self.eyes, .7)
        strong = rounded_point(cheek, self.eyes, 1.2)
        self.assertGreater(mild[0], cheek[0])
        self.assertGreater(strong[0], mild[0])
        self.assertLess(strong[1], cheek[1])
        self.assertGreater(rounded_point(chin, self.eyes, 1.2)[2], chin[2])

    def test_symmetry_and_back_neck_preservation(self):
        left = rounded_point((-.055, -.09, 1.555), self.eyes, 1)
        right = rounded_point((.055, -.09, 1.555), self.eyes, 1)
        self.assertAlmostEqual(left[0], -right[0])
        self.assertEqual(left[1:], right[1:])
        point = (.09, .03, 1.50)
        self.assertEqual(rounded_point(point, self.eyes, 1), point)

    def test_eye_displacement_bounded_and_continuity(self):
        eye = self.eyes[1]
        point = (eye[0], -.09, eye[2])
        transformed = rounded_point(point, self.eyes, 1)
        # 圆脸会让眼间距随脸颊略变宽；限制在2毫米内，避免整体眼位漂移。
        self.assertLess(abs(transformed[0] - point[0]), .002)
        for z in (1.50, 1.55, 1.60, 1.65):
            a = rounded_point((.04, -.09, z), self.eyes, 1.2)
            b = rounded_point((.04, -.09, z + 1e-5), self.eyes, 1.2)
            self.assertLess(math.dist(a, b), 3e-5)

    def test_invalid_recipe_rejected(self):
        for strength in (-1, 2, math.nan):
            with self.assertRaises(ValueError): rounded_point((0, 0, 0), self.eyes, strength)
        with self.assertRaises(ValueError): rounded_point((0, 0, math.inf), self.eyes, 1)

    def test_chin_lift_capped_for_existing_neck(self):
        point = (0, -.09, 1.495)
        for strength in (.7, 1., 1.2):
            changed = rounded_point(point, self.eyes, strength)
            self.assertLessEqual(changed[2] - point[2], .00950001)


if __name__ == '__main__':
    unittest.main()
