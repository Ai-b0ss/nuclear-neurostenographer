# AMI manual-reference Android diarization probe

The [AMI Meeting Corpus](https://groups.inf.ed.ac.uk/ami/corpus/) provides real
meeting audio and [manual annotations](https://groups.inf.ed.ac.uk/ami/download/).
`tools/ami/provision.py` pins the official manual v1.6.2 ZIP and two official
Mix-Headset WAVs by SHA-256, cuts seconds 360–600 from each, and converts the
four speakers' `segments/*.segments.xml` transcriber boundaries into reference
turns. The selection was made from annotation speaker coverage before C2 ran.
The two excerpts have different meeting participants; ES2004a was used for
development and IS1009a for confirmation. Source audio and evidence remain in
ignored `.local/` and are distributed only by the AMI maintainers under CC BY 4.0.

The opt-in `AmiDiarizationProbeTest` runs C2 in the isolated Android inference
service on the 4 GiB Android 16 API 36 x86_64 emulator with 16 KiB pages. It
records raw turns, input SHA-256, inference time, and sampled peak PSS. Score
with `tools/ami/score.py`; protocol: 250 ms collar radius, overlap included,
minimum-cost global speaker permutation. AMI is English, so this tests only
diarization, not Russian WER/cpWER. The source is a headset mix, not the phone
microphone. The reference uses manual segment boundaries, not ASR chunks.

| Meeting | C2 raw DER | Current 150 ms DER | 200 ms DER | 300 ms DER | C2 inference | Peak total PSS |
|---|---:|---:|---:|---:|---:|---:|
| ES2004a | 38.35% | 28.68% | 26.23% | 22.88% | 3.286 s | 495 MiB |
| IS1009a | 14.82% | 7.89% | 6.72% | 6.11% | 3.218 s | 496 MiB |

On the existing four-recording Russian audiobook mix development and holdout
sets, respectively, 150→300 ms padding reduced C2 DER from 3.67%→3.04% and
0.79%→0.39% using the same 250 ms collar. However, paired Android A0 text
inference on ten Russian samples changed WER from **45/525 to 51/525**; one
sample also lost a valid strict cpWER score. The 300 ms policy is therefore
not promoted to the product. A small DER gain alone cannot justify worse text.
The paired 200 ms policy gave WER 43/525, but it also left one word unattributed
in `ivkond-3overlap`, making that case's strict cpWER unscorable. It too remains
a research setting. The product keeps 150 ms.

Reproduction: `python tools/ami/provision.py`, build the opt-in test APK with
`-PnemotronPrototype=true -PnativeAsrCandidate=true -PdiarThresholdProbe=true`,
run `AmiDiarizationProbeTest` with `-e case development` and `-e case holdout`,
pull `files/ami-c2-<case>-evidence.json` from the `.c2` debug app, then run
`python tools/ami/score.py ES2004a <development.json>` or `IS1009a <holdout.json>`.

This experiment points to speech boundary recall, especially overlapping
speech, rather than speaker clustering as the main AMI error. Research on
[target-speaker VAD](https://arxiv.org/abs/2208.13085) and
[overlap-aware diarization](https://arxiv.org/abs/2303.05397) motivates a
speaker-conditioned activity stage, but it needs a phone-sized implementation
and a paired Russian WER/cpWER gate before adoption.
