# Golos farfield Android ASR comparison (2026-11-05)

This is a **single-speaker WER probe**, not a conversation or speaker-attribution
benchmark. The [Golos SLR114 test set](https://openslr.org/114/) contains manually
annotated Russian speech; its farfield test split has 1,916 utterances. The local
source is the pinned `farfield/test/test-00000.tar` in the
[`Sh1man/golos_opus` mirror](https://huggingface.co/datasets/Sh1man/golos_opus),
revision `931f5c412a8045e0b03b9e5584072f0810c41dcc`, archive SHA-256
`f0a587ea242d22c3e1bfacfd08ecb6fd822bcee199811c2154b5bca883b7ec3b`.
Source audio and transcripts remain in ignored `.local`, never in Git.

Before inference, `provision_golos_farfield_android.py --freeze` selected ten
utterances in each duration bin `[2,3)`, `[3,4)`, `[4,8)` seconds using a fixed
SHA-256 ranking. The committed lock records the 30 source IDs and hashes of
their Opus, converted 16 kHz PCM WAV, and reference JSON. Total audio is 106.4 s;
the transcripts contain 180 words under the existing NFKC/lowercase word scorer.

Android 16 API 36 x86_64 emulator, 4 GiB RAM, 16 KiB pages. Both heads used
the same C2 diarization windows with the product's 150 ms boundary padding and
400 ms conservative window merge. A0 is the product GigaAM v3 CTC INT8 via
native C++ sherpa C API, four ASR threads. A3 is GigaAM v3 RNN-T INT8 via the
same C API, two ASR threads. Each of the 30 WAVs decoded at least one window.

| Head | WER errors / reference words | WER | Sum ASR wall time | Sampled max app PSS |
| --- | ---: | ---: | ---: | ---: |
| A0 CTC | 11 / 180 | 6.11% | 35.345 s | 754,185 KiB |
| A3 RNN-T | 9 / 180 | 5.00% | 37.760 s | 753,919 KiB |

A3 corrected two additional words but took 6.8% more cumulative ASR wall time.
The PSS samples are confounded by sequential model loading and do not show a
memory advantage. Combined with the previous 14 mixed/acted cases, A0 has
53/863 WER errors and A3 has 52/863; the domain mix makes this only a sanity
check, not a pooled deployment score. A3 is not promoted on a one-word pooled
difference. The test set is short assistant-style requests; it has no verified
multi-speaker labels, long turns, overlap, cpWER, or DER. It also appears in
[GigaAM's published evaluation](https://www.isca-archive.org/interspeech_2025/kutsakov25_interspeech.pdf),
so it is independent of our tuning fixtures but not a novel unseen domain for
the model family. Emulator timing is not Kirin 710A timing.

To reproduce: place the pinned tar at `.local/golos-farfield-test.tar`, run
`python tools/nemotron/provision_golos_farfield_android.py` to verify the frozen
lock, build the opt-in Android test with `-PnemotronPrototype=true
-PnativeAsrCandidate=true -PasrHeadProbe=true`, and run
`AsrHeadProbeTest#compareAsrHeads` with `suite=golos-farfield`, `heads=a0,a3`,
`backends=c2`, `c2ProductPolicy=true`, `rnntThreads=2`. A3 files in the app's
`files/asr-rnnt-v3` are SHA-256 verified by the test. Pull
`files/asr-head-product-golos-farfield-evidence.json` and run
`python tools/nemotron/score_golos_farfield_android.py EVIDENCE.json`.
