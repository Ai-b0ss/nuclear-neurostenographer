# RINCO Russian manual-text Android ASR comparison

The [RINCO corpus on Zenodo](https://zenodo.org/records/8119302) includes
time-aligned ELAN transcripts and corresponding WAVs. Before inference,
`tools/rinco/provision.py` selected the two longest eligible mixed-gender
recordings with at least six `Text` annotations from each of the Questions,
Imperatives and Statements folders. The source ZIP and each selected EAF/WAV
member are pinned by hash. WAVs are resampled to mono 16 kHz PCM16; exact output
hashes are pinned too. Source audio, converted WAVs, manual references and raw
Android evidence stay in ignored `.local/`.

These are short, edited or staged dialogue utterance collections, not a
natural 20-minute phone call. The ELAN `Voice` tier records gender, not a
verified speaker identity. Therefore this benchmark scores **WER only**;
cpWER and DER are not claimed. Editorial `(a)` and `(b)` interlocutor markers
embedded in one `Text` tier are removed before scoring because they are not
spoken words. Otherwise the manual text is kept as published.

`AsrHeadProbeTest` ran A0 GigaAM v3 CTC and A3 GigaAM v3 RNN-T on identical
C2 speech windows with the product 150 ms padding and 400 ms same-speaker
merge. The test used the 4 GiB Android 16 API 36 x86_64 emulator, 16 KiB pages;
A0 used four ASR threads and A3 two. Both heads were scored on all six WAVs.

| Head | WER errors/words | WER | Total ASR wall | Sampled peak app PSS |
|---|---:|---:|---:|---:|
| A0 CTC, current | **3/295** | **1.02%** | **10.011 s** | 750,486 KiB |
| A3 RNN-T | 4/295 | 1.36% | 12.142 s | 760,510 KiB |

A3 corrected no net words on this material and took 21% longer in summed ASR
wall time. It remains a research candidate; A0 remains the product head. The
low WER reflects the short, clean RINCO material and does not establish natural
conversation quality on the HONOR ARM64 phone.

An initial score counted six editorial `(a)`/`(b)` markers as reference words,
incorrectly reporting A0 9/301 and A3 10/301. The scorer now verifies the
corrected, pinned references and reports 3/295 versus 4/295. The Android
inference itself did not change.

During the first run, the isolated C2 process failed with `NoSuchMethodException`:
the debug-only native activity-threshold parameter had changed the Kotlin/JVM
method signature used by `NemotronBackend` reflection. `@JvmOverloads`
restored the three-argument entry point. The four-minute AMI isolated-worker
test then passed, followed by this complete six-recording RINCO run. The
worker failure message now carries its exception class, so a repeat failure
can be diagnosed without exposing file paths or model data.

Reproduce: `python tools/rinco/provision.py`, build with
`-PnemotronPrototype=true -PnativeAsrCandidate=true -PasrHeadProbe=true`,
run `AsrHeadProbeTest` with `suite=rinco`, `heads=a0,a3`, `backends=c2`,
`c2ProductPolicy=true`, `rnntThreads=2`; pull
`files/asr-head-product-rinco-evidence.json` from the `.c2` debug app and
run `python tools/rinco/score_android.py EVIDENCE.json`.
