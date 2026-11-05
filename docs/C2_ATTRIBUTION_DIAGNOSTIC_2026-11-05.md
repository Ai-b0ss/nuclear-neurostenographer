# Why C2 leaves text unattributed on a 20-minute call

An Android 16 API 36 x86_64 emulator run on the same 4 GiB, 16 KiB page AVD
used the pinned 20-minute [DataHive Russian call](https://huggingface.co/datasets/datahiveai/multilingual-conversations-sample)
and the current C2+A0 product policy. The diagnostic records aggregate counts
only. The call has no independent speaker/word reference, so these counts are
not cpWER, DER, or a proof that assigning more words would be correct.

Both the padded and merged policy produced 314 transcript segments: 208 with a
reliable speaker, 106 without one. The new opt-in `C2LongAsrProbeTest`
diagnostic classifies each unknown segment by the first applicable reason:

| Reason | Segments |
| --- | ---: |
| Multiple C2 speaker intervals overlap the ASR fragment | 89 |
| A short or otherwise ineligible C2 turn touches it | 17 |
| No turn / insufficient coverage or margin | 0 |
| **Total** | **106** |

None of the 89 overlap cases had at most 100 ms of overlap between only eligible
turns. A research-only rule permitting that much overlap changed no segment on
the six original or four acted Android clips; the experiment was reverted.
The product's merged policy produced 1,991 whitespace-delimited words, 165 of
them in unknown-speaker segments. The unmerged policy produced 2,010 words;
its text differs because the ASR windows differ.

The installed sherpa C API supports optional [token timestamps](https://k2-fsa.github.io/sherpa/onnx/c-api/html/structSherpaOnnxOfflineRecognizerResult.html).
A research-only A0 CTC probe confirmed 111 character tokens and 111 timestamps
on one public clip. A candidate grouped characters into timed words and used
the existing word-attribution rule. On the six original fixtures, WER remained
36/378; strict cpWER changed from 10/233 scored words to 8/141 because an
additional word became unattributed, so the differing denominators cannot be
read as an improvement. On four acted three-voice fixtures both policies gave
WER 4/147 and cpWER 61/147. On the long call the timed candidate preserved the
exact 1,991-word sequence hash, but increased unknown words from **165 to 168**.
ASR wall time was 23.870 s versus 23.833 s. The candidate was reverted; the
product's chunk-based attribution and native ASR API remain unchanged.

These findings point to real overlap and short-turn handling, not a minor
boundary tolerance or coarse text timing, as the next research target. Any
overlap-aware or speaker-conditioned approach needs independent Russian
conversation words and speaker intervals before promotion.

To reproduce the retained diagnostic, run `C2LongAsrProbeTest` with `head=a0`
after `tools/nemotron/provision_natural_long_android.py`, pull
`files/c2-natural-long-asr-evidence.json`, and run
`python tools/nemotron/score_unknown_reasons.py EVIDENCE.json`. The opt-in test
requires `-PnemotronPrototype=true -PnativeAsrCandidate=true
-PdiarThresholdProbe=true`. Audio, transcripts, and raw evidence stay ignored
under `.local`.
