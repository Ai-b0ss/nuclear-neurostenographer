import unittest
from speaker_verification_metrics import (cosine,make_pairs,rates,calibrate,auc,
  equal_error_rate,score_summary,open_set_probe,open_set_known_unknown,dual_profile_proxy)


class VerificationMetricTests(unittest.TestCase):
    def setUp(self):
        self.rows=[
            {"id":"a1","speaker_id":"a","vector":[1.,0.,0.]},
            {"id":"a2","speaker_id":"a","vector":[.99,.10,0.]},
            {"id":"a3","speaker_id":"a","vector":[.98,.20,0.]},
            {"id":"b1","speaker_id":"b","vector":[0.,1.,0.]},
            {"id":"b2","speaker_id":"b","vector":[.10,.99,0.]},
            {"id":"b3","speaker_id":"b","vector":[.20,.98,0.]},
        ]

    def test_cosine_and_validation(self):
        self.assertAlmostEqual(cosine([2,0],[1,0]),1)
        self.assertAlmostEqual(cosine([1,0],[0,1]),0)
        with self.assertRaises(ValueError):cosine([0,0],[1,0])
        with self.assertRaises(ValueError):cosine([float("nan"),1],[1,0])
        with self.assertRaises(ValueError):cosine([1,0],[1,0,1])

    def test_pairs_and_rates(self):
        pairs=make_pairs(self.rows)
        self.assertEqual(len(pairs),15)
        vals=rates(pairs,.8)
        self.assertEqual((vals["positive_pairs"],vals["negative_pairs"]),(6,9))
        self.assertEqual(vals["false_accepts"],0)
        self.assertEqual(vals["false_rejects"],0)
        self.assertAlmostEqual(auc(pairs),1)
        self.assertIn("threshold",equal_error_rate(pairs))
        self.assertIn("median",score_summary(pairs)["different"])

    def test_calibrate_on_dev_only(self):
        pairs=make_pairs(self.rows)
        best=calibrate(pairs,.01)
        self.assertEqual(best["false_accepts"],0)
        self.assertEqual(best["false_rejects"],0)
        with self.assertRaises(ValueError):calibrate(pairs,1.1)

    def test_enrolment_conservative(self):
        val=open_set_probe(self.rows,.8,margin=.07)
        self.assertEqual(val["correct_links"],4)
        self.assertEqual(val["false_links"],0)
        self.assertEqual(val["rejections"],0)
        val=open_set_probe(self.rows,1.0,margin=.07)
        self.assertGreater(val["rejections"],0)

    def test_unknown_speaker_rejection(self):
        rows=self.rows+[
            {"id":"c1","speaker_id":"c","vector":[0.,0.,1.]},
            {"id":"c2","speaker_id":"c","vector":[.05,0.,.99]},
            {"id":"d1","speaker_id":"d","vector":[0.,-.9,-.9]},
            {"id":"d2","speaker_id":"d","vector":[0.,-.95,-1.]},
        ]
        result=open_set_known_unknown(rows,.8,margin=.07)
        self.assertEqual(result["unknown_probes"],10)
        self.assertEqual(result["false_accepted_unknown"],0)
        self.assertEqual(result["wrong_known_links"],0)
        self.assertEqual(result["rounds"],2)
        with self.assertRaises(ValueError):
            open_set_known_unknown(rows,1.5)

    def test_two_fingerprint_proxy(self):
        correct=dual_profile_proxy(self.rows,consistency=.84,link_threshold=.84)
        self.assertEqual(correct["people"],2)
        self.assertEqual(correct["verified_two_part_profiles"],2)
        self.assertEqual(correct["third_utterance_correct_links"],2)
        self.assertEqual(correct["third_utterance_wrong_links"],0)
        rejected=dual_profile_proxy(self.rows,consistency=1.,link_threshold=.84)
        self.assertEqual(rejected["verified_two_part_profiles"],0)
        self.assertEqual(rejected["third_utterance_no_profile"],2)

    def test_duplicate_id(self):
        copies=[x.copy() for x in self.rows]
        copies[1]["id"]=copies[0]["id"]
        with self.assertRaises(ValueError):make_pairs(copies)


if __name__=="__main__":
    unittest.main()
