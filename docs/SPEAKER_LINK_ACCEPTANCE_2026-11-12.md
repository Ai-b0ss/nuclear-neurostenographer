# Speaker linking acceptance decision,12 November2026

**Decision: keep global speaker linking disabled in the ordinary application.**
PR56's longer samples improve evidence admission, but the new human-actor
check still rejects most profiles and fragments some admitted identities.
This decision concerns cross-window/global voice linking, not the existing
local C2 diarization or ASR pipeline.

## New cross-style check

Source: [Dialogs](https://huggingface.co/datasets/langswap/dialogs-ru-emotional-conversations),
revision a74ff44d8d27ca3d21098ea3ed4d31a32923fbdd, OpenRAIL.
These are acted studio utterances, regrouped by dataset actor alias and
emotion. They are not natural spontaneous multi-party conversations.
The test isolates TitaNet and the faithful global-book replay; it does not
run C2, ASR, Android, DER or physical thermal testing.

Selection was frozen before inference: CSV order, excluding all seven
previously cached utterances; at most eight clips until32s per actor/style,
then truncate to32s. No selection by model scores. Of129 selected clips,
112 exist in the pinned repository;17 missing entries are explicitly
recorded, without replacement. All source SHA256 values match HF LFS
metadata; converted audio is checked before inference. Source download
total65,485,918 bytes; retained grouped audio711.3945625s.
All available utterance paths are unique across groups.

Three actor aliases,35 actor/style groups,12 styles. Four groups lack enough
audio for two disjoint3s samples. Pauses and possible contamination within
utterances are retained; speaker labels are dataset labels, not human-
verified clean-frame annotations. This is not an end-to-end identity metric.

| Metric | Two samples up to8s each | Two samples up to16s each |
| --- | ---: | ---: |
| Expected actor/style profiles |35|35|
| Admitted profiles |4|14|
| Agreement rejections |27|17|
| Insufficient audio |4|4|
| Distinct actor aliases admitted |2|3|
| Admitted returning probes |2|11|
| Correct returning links |2|8|
| Returning profiles assigned new IDs |0|3|
| Wrong-person links / mixed global identities |0 /0|0 /0|
| Global IDs created |2|6|
| Accepted same-actor pairs |3|26|
| Same-actor pairs below .84 |0|5|
| Accepted different-actor pairs |3|65|
| Different-actor pairs above .84 |0|0|

The8s result's100% accepted-return success is conditioned on just two
returning probes; it does not outperform the16s candidate on overall
coverage. The16s candidate admits40% of all profiles;8/11 admitted returns
link correctly. Rejected profiles are excluded from that denominator.
Zero false merges on three actors and65 correlated negative pairs does not
establish population safety. Thresholds .84 and .07 were not tuned.

For16s, no profile is admitted in the poem or whisper groups (three expected
profiles each); whisper includes one insufficient group. Fear has two
insufficient groups and one agreement rejection. These observations do not
isolate emotion as the cause: duration, phonetic content, silence and recording
conditions differ between groups. Even neutral speech admits only2/3.
No real identities were inferred; D/M/S are source-provided aliases.

## Why the spontaneous-Russian gate stays open

- [Veche](https://huggingface.co/datasets/artem-tish/veche-bench)
  explicitly prohibits voice profiling, biometric recognition and speaker
  re-identification. Its permitted local diarization results cannot be
  repurposed as an identity benchmark.
- [DAI-ASR-I18N](https://huggingface.co/datasets/davidai-labs/DAI-ASR-I18N)
  offers spontaneous Russian conversations, but files are gated behind
  an access request and Data Use Agreement. No access request, account
  information sharing or acceptance on the user's behalf was performed.
  Its no-re-identification terms require checking the exact intended task
  before any global voice-link evaluation.
- [SpeechDataAI Russian](https://huggingface.co/datasets/SpeechDataAI/russian-conversational-speech)
  is a commercial data card, not a free downloadable audio release.
  Nothing was purchased and no third party was contacted.

This search did not establish a freely usable spontaneous-Russian identity
benchmark. It is not a claim that none exists.

## Evidence and reproduction

[Metrics](evidence/dialogs-speaker-20261112/result.json),
[frozen available-input plan](evidence/dialogs-speaker-20261112/plan.json),
[source license and restrictions](evidence/dialogs-speaker-20261112/LICENSE.md).

    python tools/evaluate_dialogs_speaker_emotions.py --prepare --source .local/dialogs-ru-source --site SITE
    python tools/evaluate_dialogs_speaker_emotions.py --source .local/dialogs-ru-source --site SITE --model TITANET

Requires Python3.12 for the existing Windows dependency site, numpy1.26.4,
scipy1.14.1, soundfile0.13.1, sherpa-onnx1.12.40. The local source CSV and
license must match their pinned hashes. Outputs stay under ignored .local;
the report exports metrics and source metadata, no audio, embeddings or
transcript text. Derived evidence in its subdirectory carries the source
OpenRAIL terms; application/code licensing is separate.

Actual native inference completed successfully. Pair counts, profile totals,
returning-outcome accounting and unique input paths were independently
checked; the eleven existing isolation/selection regressions passed.
No product runtime, thresholds or thermal guard changed in this stage.

Next work should compare a more robust embedding candidate on a separate
development set, retaining this snapshot as a regression test. Do not lower
thresholds using these three actors or enable the feature on this evidence.
Physical HONOR sustained endurance also remains unverified; no phone was used.
