"""Counterexamples for enrollment, overlap splicing and companion metrics. No accuracy claims."""
import copy
import unittest
import numpy as np
from metrics import score, overlap_spans, temporal_recall
from run_host import enrollments,build_hybrid

def s(a,b,who,text='',reliable=True):
    return dict(start_ms=a,end_ms=b,speaker_id=who,text=text,attribution_reliable=reliable)

class Counterexamples(unittest.TestCase):
    def test_half_open_overlap_and_duplicate_turns(self):
        self.assertEqual(overlap_spans([s(0,1000,'A'),s(1000,2000,'B')]),[])
        self.assertEqual(overlap_spans([s(0,1000,'A')]*2),[])
        self.assertEqual(overlap_spans([s(0,1000,'A'),s(500,1500,'B')]),[dict(start_ms=500,end_ms=1000,speakers=['A','B'])])

    def test_enrollment_no_padding_no_ambiguous_or_silent_identity(self):
        x=np.full(160000,0.1,np.float32)
        self.assertIsNotNone(enrollments(x,[s(0,5000,'A')],[[0,5000]])[0])
        self.assertIsNone(enrollments(x,[s(0,3000,'A')],[[0,3000]])[0])
        self.assertIsNone(enrollments(x,[s(0,5000,'A'),s(100,5000,'B')],[[0,5000]])[0])
        self.assertIsNone(enrollments(x*0,[s(0,5000,'A')],[[0,5000]])[0])
        self.assertIsNone(enrollments(x,[s(0,10000,'A')],[[0,5000],[5000,10000]])[0])

    def test_recovered_identity_remains_unverified_and_non_overlap_unchanged(self):
        base=[s(0,200,'A','one'),s(500,700,None,'two',False)]
        spans=[dict(start_ms=400,end_ms=900,speakers=['A','B'])]
        h=build_hybrid(base,{'A':[s(510,710,'A','two')],'B':[s(520,720,'B','three')]},spans)
        self.assertEqual(h[0],base[0]);self.assertEqual(len(h),3)
        self.assertTrue(all(x['speaker_id'] is None and not x['attribution_reliable'] for x in h[1:]))
        self.assertEqual(build_hybrid(base,{'A':base},[]),base)

    def test_temporal_matching_never_reuses_words_or_matches_wrong_speaker(self):
        r=[s(0,100,'A','one'),s(0,100,'A','one')]
        self.assertEqual(temporal_recall(r,[s(0,100,'A','one')])['matched'],1)
        self.assertEqual(temporal_recall(r,[s(0,100,'B','one')])['matched'],0)
        self.assertEqual(temporal_recall(r,[s(1000,1100,'A','one')])['matched'],0)
        self.assertEqual(temporal_recall(r,[s(0,100,None,'one')])['matched'],0)
        self.assertEqual(temporal_recall(r,[s(0,100,'A','one')]*3)['added_unmatched_words'],1)
        with self.assertRaises(ValueError):temporal_recall([s(0,100,'A','two words')],[])

    def test_unknown_insertions_are_visible_in_wer_but_u_is_not_upper_bound(self):
        r=dict(schema_version=1,recording_id='unit-no-audio',kind='AUTHORED_UNIT_TEST_NO_AUDIO',annotation_source='authored',
               license='test',audio_sha256='0'*64,audio_duration_ms=2000,text_segments=[s(0,1000,'A','one')])
        h=dict(audio_sha256='0'*64,audio_duration_ms=2000,segments=[s(0,1000,'A','one'),s(1000,2000,None,'alien')])
        m=score(r,h)
        self.assertEqual(m['wer']['insertions'],1);self.assertEqual(m['cpwer']['status'],'NOT_SCORED')
        self.assertEqual(m['cpwer_u']['errors'],0);self.assertEqual(m['unknown_words'],1)
        self.assertEqual(m['der']['status'],'NOT_SCORED');self.assertEqual(m['overlap_words']['status'],'NOT_SCORED')

    def test_hash_mismatch_and_unreliable_labels_rejected(self):
        r=dict(schema_version=1,recording_id='unit-no-audio',kind='AUTHORED_UNIT_TEST_NO_AUDIO',annotation_source='authored',
               license='test',audio_sha256='0'*64,audio_duration_ms=2000,text_segments=[s(0,1000,'A','one')])
        h=dict(audio_sha256='0'*64,audio_duration_ms=2000,segments=[s(0,1000,'A','one',False)])
        self.assertEqual(score(r,h)['cpwer']['status'],'NOT_SCORED')
        with self.assertRaises(ValueError):score(r,dict(h,audio_sha256='1'*64))

if __name__=='__main__':unittest.main()
