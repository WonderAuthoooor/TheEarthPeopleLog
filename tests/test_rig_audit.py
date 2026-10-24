import copy
import unittest
from avatar3d.rig_audit import audit_document


def fixture():
    return {'nodes': [{'mesh': 0, 'children': [1]}, {}],
            'meshes': [{'primitives': [{'targets': [{}]}]}],
            'extensions': {'VRMC_vrm': {'expressions': {'preset': {'aa': {
                'morphTargetBinds': [{'node': 0, 'index': 0, 'weight': 1}]}}}},
                'VRMC_springBone': {'springs': [{'joints': [{'node': 0}, {'node': 1}]}]}}}


class RigAuditTests(unittest.TestCase):
    def test_valid_references_do_not_imply_visual_acceptance(self):
        result = audit_document(fixture())
        self.assertTrue(result['structure_valid'])
        self.assertFalse(result['visual_accepted'])

    def test_broken_export_references_are_rejected(self):
        for field, value in [('node', 9), ('index', 9), ('weight', float('nan'))]:
            doc = copy.deepcopy(fixture())
            doc['extensions']['VRMC_vrm']['expressions']['preset']['aa']['morphTargetBinds'][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                audit_document(doc)

    def test_disconnected_spring_is_rejected(self):
        doc = fixture(); doc['nodes'][0]['children'] = []
        with self.assertRaisesRegex(ValueError, '连续父子链'):
            audit_document(doc)

    def test_bad_collider_reference_is_rejected(self):
        doc = fixture()
        doc['extensions']['VRMC_springBone']['springs'][0]['colliderGroups'] = [0]
        with self.assertRaisesRegex(ValueError, '引用越界'):
            audit_document(doc)


if __name__ == '__main__':
    unittest.main()
