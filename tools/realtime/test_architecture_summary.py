import unittest
from architecture_summary import matched_word_attribution, stability


class AttributionMetricTest(unittest.TestCase):
    def test_unknown_wrong_and_insertions_are_separate(self):
        ref={'text_segments':[dict(start_ms=0,end_ms=1000,speaker_id='A',text='alpha beta gamma')]}
        hyp=[dict(text='alpha extra',speaker_id='S1'),dict(text='beta',speaker_id='S2'),dict(text='gamma',speaker_id=None)]
        score=matched_word_attribution(ref,hyp,{'S1':'A','S2':'B'})
        self.assertEqual((score['exact_lexical_matches'],score['wrong_speaker'],score['unknown_speaker']),(3,1,1))

    def test_overlap_does_not_invent_word_order(self):
        ref={'text_segments':[dict(start_ms=0,end_ms=1000,speaker_id='A',text='one'),dict(start_ms=500,end_ms=1500,speaker_id='B',text='two')]}
        self.assertEqual(matched_word_attribution(ref,[],{})['status'],'NOT_SCORED')

    def test_returning_voice_switch_and_missing_turn(self):
        ref={'diarization':[dict(start_ms=i*1000,end_ms=i*1000+500,speaker_id='A') for i in range(3)]}
        hyp=[dict(start_ms=0,end_ms=500,speaker_id='S1'),dict(start_ms=1000,end_ms=1500,speaker_id='S2')]
        result=stability(ref,hyp)
        self.assertEqual(result['reference_voices_with_multiple_dominant_ids'],1)
        self.assertEqual(result['missing_reference_turns'],1)


if __name__=='__main__': unittest.main()
