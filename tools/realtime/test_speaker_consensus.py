"""No-reference unit tests for the experimental temporal fusion."""
import tempfile
import unittest
from pathlib import Path
from speaker_consensus import alignment,fuse,load,dump

class SpeakerConsensusTest(unittest.TestCase):
    def test_temporal_id_alignment(self):
        preview=[(0,100,0),(200,300,1)]
        final=[(0,100,1),(100,200,1),(200,300,0)]
        mapping,weights=alignment(final,preview)
        self.assertEqual(mapping[1],0)
        self.assertEqual(mapping[0],1)
        actual,stats=fuse(final,preview,'preview-first')
        self.assertEqual(actual,[(0,200,0),(200,300,1)])
        self.assertEqual(stats['disagreement_ms'],100)

    def test_preview_wins_if_final_disagrees(self):
        preview=[(0,100,0),(100,300,1),(300,400,0)]
        final=[(0,100,0),(100,300,0),(300,400,0)]
        fused,_=fuse(final,preview,'preview-first')
        self.assertEqual(fused,[(0,100,0),(100,300,1),(300,400,0)])
        fused_final,_=fuse(final,preview,'final-first')
        self.assertEqual(fused_final,[(0,400,0)])

    def test_final_fills_only_empty_preview(self):
        preview=[(0,100,0),(300,400,0)]
        final=[(0,400,0)]
        fused,_=fuse(final,preview,'preview-first')
        self.assertEqual(fused,[(0,400,0)])

    def test_overlap_preserved(self):
        preview=[(0,200,0),(50,150,1)]
        final=[(0,200,0),(50,150,1)]
        fused,_=fuse(final,preview,'preview-first')
        self.assertEqual(fused,[(0,200,0),(50,150,1)])

    def test_empty_and_invalid_source(self):
        self.assertEqual(fuse([],[], 'preview-first')[0],[])
        self.assertEqual(fuse([(0,20,2)],[],'preview-first')[0],[(0,20,2)])
        with self.assertRaises(ValueError):
            fuse([],[], 'invented')
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'output.tsv';dump([(0,100,0),(40,80,1)],out)
            self.assertEqual(load(out),[(0,100,0),(40,80,1)])
            out.write_text('0\t15\t8\n',encoding='utf-8')
            with self.assertRaises(ValueError):load(out)

if __name__=='__main__':unittest.main()
