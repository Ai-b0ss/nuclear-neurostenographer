"""Hermetic regression tests for the Russian book-mix QA scorers.

These never access the phone, audio data, HF, or model weights.
"""
import math
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import numpy as np

from evaluate_russian_bookmix_voice_link import (
    ground_truth_owners,separate,normalized,calculate_pairs,global_book_simulation)
from evaluate_russian_bookmix_c2_link import build_owners
from score_russian_bookmix_c2 import parse_hypothesis,parse_rttm
from score_transcript import der


def profile(local,truth,vector,status="PASS"):
    return {"local":local,"truth":truth,"valid":status,
            "v":normalized(vector,np) if status=="PASS" else None}


class OracleTruthSelectionTest(unittest.TestCase):
    def test_subframe_overlap_is_rejected(self):
        text=("SPEAKER rec_0000 1 0.000 4.000 <NA> <NA> spk0 <NA> <NA>\n"
              "SPEAKER rec_0000 1 1.999 0.002 <NA> <NA> spk1 <NA> <NA>\n")
        ids,owners=ground_truth_owners(text,{"spk0":"actor_a","spk1":"actor_b"},100)
        self.assertEqual(ids,["spk0","spk1"])
        self.assertEqual(owners[49],-1)
        self.assertEqual(owners[50],-1)
        self.assertEqual(owners.count(0),98)

    def test_split_requires_twice_three_seconds(self):
        owners=[0]*149+[1]*30
        self.assertIsNone(separate(owners,0))
        owners=[0]*300+[1]*300
        a,b=separate(owners,0)
        self.assertEqual(len(a),150)
        self.assertEqual(len(b),150)
        self.assertLess(a[-1],b[0])

    def test_mixed_speaker_boundaries(self):
        turns=[
            {"speaker_id":"h0","start_ms":0,"end_ms":4000},
            {"speaker_id":"h1","start_ms":2000,"end_ms":3000}]
        ids,owners=build_owners(turns,100)
        self.assertEqual(ids,["h0","h1"])
        self.assertTrue(all(x==-1 for x in owners[50:75]))


class LinkedIdentityTests(unittest.TestCase):
    def test_clean_aba_is_linked(self):
        data=[
            {"id":"one","profiles":[profile("s","speaker_a",[1,0,0])]},
            {"id":"two","profiles":[profile("s","speaker_b",[0,1,0])]},
            {"id":"three","profiles":[profile("s","speaker_a",[.99,.08,0])]},
        ]
        summary,_=global_book_simulation(data,np)
        self.assertEqual(summary["returning_valid_probes"],1)
        self.assertEqual(summary["correct_returning_links"],1)
        self.assertEqual(summary["speaker_mixes"],0)

    def test_wrong_join_is_counted_not_hidden(self):
        # Identical embeddings for distinct true speakers MUST be scored as a
        # false merge. This tests the scorer's detection, not feature safety.
        data=[
            {"id":"one","profiles":[profile("s","speaker_a",[1,0,0])]},
            {"id":"two","profiles":[profile("s","speaker_b",[1,0,0])]},
        ]
        summary,_=global_book_simulation(data,np)
        self.assertEqual(summary["new_speaker_false_links"],1)
        self.assertEqual(summary["speaker_mixes"],1)

    def test_undecidable_profile_does_not_enroll(self):
        data=[
            {"id":"one","profiles":[profile("s","speaker_a",[1,0,0],"AGREEMENT_REJECT")]},
            {"id":"two","profiles":[profile("s","speaker_b",[0,1,0])]}
        ]
        summary,_=global_book_simulation(data,np)
        self.assertEqual(summary["profiles_rejected_early_late"],1)
        self.assertEqual(summary["profiles_consistent"],1)
        self.assertEqual(summary["total_global_ids_created"],1)

    def test_cosine_pair_count_and_source_labels(self):
        a=[profile("a","x",[1,0]),profile("b","y",[0,1]),profile("c","x",[.98,.1])]
        score=calculate_pairs(a,np)
        self.assertEqual(score["positive_pairs"],1)
        self.assertEqual(score["negative_pairs"],2)
        self.assertEqual(score["false_accepts_0_84"],0)
        self.assertEqual(score["false_rejects_0_84"],0)


class RttmDerTest(unittest.TestCase):
    def test_absolute_time_and_cluster_assignment(self):
        rttm=("SPEAKER rec_0000 1 1.000 2.000 <NA> <NA> spk0 <NA> <NA>\n"
              "SPEAKER rec_0000 1 3.000 1.000 <NA> <NA> spk1 <NA> <NA>\n")
        with TemporaryDirectory() as base:
            ref=Path(base)/"ref.rttm"
            hyp=Path(base)/"hyp.tsv"
            ref.write_text(rttm)
            hyp.write_text("1.0\t3.0\t1\n3.0\t4.0\t0\n")
            truth=parse_rttm(ref,"rec_0000")
            generated=parse_hypothesis(hyp)
            score=der(truth,generated,60000,0,False)
            self.assertAlmostEqual(score["rate"],0)
            hyp.write_text("1.0\t4.0\t1\n")
            generated=parse_hypothesis(hyp)
            score=der(truth,generated,60000,0,False)
            self.assertGreater(score["rate"],0)

if __name__=="__main__":unittest.main()
