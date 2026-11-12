"""Selection regressions for the exploratory TitaNet diagnostic."""
import unittest
from diagnose_titanet_rejections import contiguous,trimmed,longer
class SelectionTests(unittest.TestCase):
    def test_short_runs_cannot_supply_contiguous_evidence(self):
        self.assertIsNone(contiguous([0]*74+[-1]+[0]*74,0))
    def test_samples_are_disjoint_and_keep_original_frames(self):
        owners=[0]*200+[-1]*10+[0]*200
        parts=contiguous(owners,0)
        self.assertEqual([len(x) for x in parts],[200,200])
        self.assertLess(parts[0][-1],parts[1][0])
        self.assertTrue(all(owners[i]==0 for part in parts for i in part))
    def test_trim_can_remove_minimum_duration(self):
        self.assertIsNone(trimmed([0]*150,0))
    def test_longer_cap_does_not_reuse_evidence(self):
        parts=longer([0]*1000,0)
        self.assertEqual([len(x) for x in parts],[400,400])
        self.assertFalse(set(parts[0])&set(parts[1]))
if __name__=="__main__":unittest.main()
