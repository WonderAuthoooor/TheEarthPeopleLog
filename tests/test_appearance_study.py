import math
import unittest

from avatar3d.appearance_study import VARIANTS, Variant, shoulder_underlayer, study_spec


class AppearanceStudyTests(unittest.TestCase):
    def test_baseline_is_identity(self):
        for point in ((.1, -.2, 1.49), (0, 0, -1)):
            self.assertEqual(VARIANTS[0].transform(point), point)

    def test_inner_change_does_not_touch_torso_or_width(self):
        variant = VARIANTS[1]
        self.assertEqual(variant.transform((.06, -.064, 1.4)), (.06, -.064, 1.4))
        self.assertEqual(variant.transform((.06, -.064, 1.445)), (.06, -.064, 1.445))
        x, y, z = variant.transform((.06, -.064, 1.49))
        self.assertEqual((x, y), (.06, -.064))
        self.assertAlmostEqual(z, 1.463)

    def test_outer_trim_moves_with_collar(self):
        v = VARIANTS[2]
        self.assertEqual(len(v.meshes), 4)
        self.assertAlmostEqual(v.transform((0, 0, 1.515))[2], 1.471)
        self.assertEqual(v.transform((0, 0, 1.4)), (0, 0, 1.4))
        self.assertFalse(set(v.meshes) & set(VARIANTS[1].meshes))

    def test_monotonic_no_fold(self):
        for v in VARIANTS:
            zs = [v.transform((0, 0, i / 1000))[2] for i in range(1000, 1600)]
            self.assertTrue(all(a < b for a, b in zip(zs, zs[1:])))

    def test_invalid_coordinates_and_recipe_rejected(self):
        for value in (math.inf, math.nan):
            with self.assertRaises(ValueError): VARIANTS[1].transform((0, value, 1))
        for scale in (0, -1, 2):
            with self.assertRaises(ValueError): Variant('bad', '', (), 1, scale).transform((0, 0, 2))

    def test_underlayer_preserves_height_and_torso(self):
        for z in (1.0, 1.39, 1.50):
            self.assertEqual(shoulder_underlayer((.07, -.06, z)), (.07, -.06, z))
        x, y, z = shoulder_underlayer((.072, .064, 1.445))
        self.assertAlmostEqual(x, .1368)
        self.assertAlmostEqual(y, .06656)
        self.assertEqual(z, 1.445)
        self.assertEqual(shoulder_underlayer((.072, -.064, 1.445)), (.072, -.064, 1.445))

    def test_underlayer_symmetric_and_finite(self):
        right = shoulder_underlayer((.08, .02, 1.46))
        left = shoulder_underlayer((-.08, .02, 1.46))
        self.assertAlmostEqual(right[0], -left[0])
        self.assertEqual(right[1:], left[1:])
        with self.assertRaises(ValueError): shoulder_underlayer((0, 0, math.nan))

    def test_studies_independent(self):
        old, _, _ = study_spec('collar')
        new, views, _ = study_spec('shoulder')
        self.assertEqual([v.key for v in old], ['A', 'B', 'C'])
        self.assertEqual([v.key for v in new], ['A', 'D'])
        self.assertTrue(new[1].repair_shoulders)
        self.assertEqual(len(views), 6)
        with self.assertRaises(ValueError): study_spec('unknown')


if __name__ == '__main__':
    unittest.main()
