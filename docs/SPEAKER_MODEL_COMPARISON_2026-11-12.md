# Speaker embedding comparison,12 November2026

**Decision: retain TitaNet Small and keep ordinary global linking OFF.**
Neither candidate provides a convincing replacement under the existing
identity policy. This is a comparison of drop-in policy suitability, not a
ranking of independently calibrated model optima.

## Fixed protocol

All models use the same cached audio, two disjoint samples up to16s each,
minimum3s/sample, agreement/matching cosine .84 and margin .07. No threshold
was tuned on these sets. Models run sequentially through native
sherpa-onnx1.12.40, Windows CPU, two threads,192D output.
No model, audio, embeddings or transcript text is committed.

| Model | ONNX bytes | Warm control median,ms |
| --- | ---: | ---: |
| TitaNet Small |40,257,283|56.1851|
| TitaNet Large |101,405,493|161.4074|
| CAM++ Chinese/English Advanced |28,281,164|66.8864|

The control is the identical4.5271875s sample, one warmup and three measured
calls per model. This is an indicative host timing, not randomized hardware
or Android performance evidence. Loading is measured separately in JSON.
Large is approximately2.87x slower on this sample and2.52x the model bytes;
CAM++ is approximately1.19x the sample time and0.70x the bytes.
Quality inference uses the16s cap wherever enough evidence exists.

## Results

| Dataset and metric | Small | Large | CAM++ |
| --- | ---: | ---: | ---: |
| Dialogs: admitted /35 profiles |14|13|12|
| Dialogs: correct / admitted returning probes |8/11|9/10|5/9|
| Dialogs: returning profiles assigned new IDs |3|1|4|
| Oracle bookmix: admitted /60 profiles |28|30|31|
| Oracle bookmix: correct / admitted returning probes |6/6|8/8|7/7|
| Actual C2 bookmix: admitted /30 profiles |26|28|28|
| Actual C2 bookmix: correct / admitted returning probes |7/7|6/6|7/7|
| Wrong-person links or mixed global IDs observed |0|0|0|

Returning denominators are model-dependent because admission differs.
Large's6/6 actual-C2 returns must not be interpreted as the same probes as
Small's7/7. Rejected profiles are excluded. All models rejected four
insufficient Dialogs groups and four insufficient oracle-bookmix profiles.

Accepted-profile different-voice pair trials:
Dialogs65/54/48, oracle bookmix371/425/456, actual C2 317/371/370
(Small/Large/CAM++). None crossed .84. Different admissions change the pair
population, and pairs are correlated. This is not a population false-accept
safety estimate; do not pool datasets or claim equivalence of accuracy.

Large adds two admitted profiles on both bookmix checks and reduces the
number of admitted identity splits on Dialogs, but admits one fewer Dialogs
profile. The small benefit does not justify a phone model replacement on
this evidence. CAM++ is smaller and admits more bookmix profiles, but its
cross-style returning links are worse under the existing gates.
A model-specific calibration could change these conclusions; it requires
separate development and validation data, not threshold fitting on three
actors. Prior VCTK/41-utterance Dialogs comparisons of Small/CAM++/WeSpeaker
were found in the local archive; those used different protocols and are not
pooled with this result.

## Provenance and rights

ONNX mirror [csukuangfj/speaker-embedding-models](https://huggingface.co/csukuangfj/speaker-embedding-models),
revision0743f301363dec56491a490f6d6cbc9d67f9a3bf:

- Small: ad4a1802485d8b34c722d2a9d04249662f2ece5d28a7a039063ca22f515a789e.
- Large: d51abcf31717ef28162f26acb9d44dd4127c3d44c9b8624f699f3425daca8e77.
- CAM++ Advanced: aa3cfc16963a10586a9393f5035d6d6b57e98d358b347f80c2a30bf4f00ceba2.

Source model documentation:
[NVIDIA TitaNet Large,CC-BY-4.0](https://huggingface.co/nvidia/speakerverification_en_titanet_large);
[official CAM++ Advanced model card](https://www.modelscope.cn/models/iic/speech_campplus_sv_zh_en_16k-common_advanced)
(the official model API reports Apache License2.0);
[sherpa NeMo export/support](https://k2-fsa.github.io/sherpa/onnx/nemo/index.html).
CAM++ cached bytes were verified and reused; only Large required a new
101MB download. No machine-wide dependency changes, paid inference or
physical phone testing.

Audio source attribution: [Dialogs by Langswap](https://huggingface.co/datasets/langswap/dialogs-ru-emotional-conversations), OpenRAIL; [mexus/ru-book-mix-10h](https://huggingface.co/datasets/mexus/ru-book-mix-10h), CC-BY-4.0, with its stated audiobook/noise attributions.

Inputs are pinned in [metrics](evidence/speaker-model-comparison-20261112/result.json):
Dialogs35 groups from112 available utterances (three actors, acted studio
speech),20 oracle-labelled synthetic audiobook mixtures, and15 cached
actual-C2 predictions. Source identities can recur across bookmix subsets;
the sources and actors have been used before. These are not untouched
holdout trials or spontaneous-meeting safety evidence. Model training
overlap is not excluded.

Clarification of the preceding Dialogs report: seven cached originals in
.local/dialogs-ru-source were excluded. A separate earlier41-utterance
preview evaluation exists elsewhere in the archive; overlap with that
preview was not excluded. The snapshot is reproducible, not a new
independent actor/utterance holdout. This qualification does not improve or
invalidate the recorded failures, but limits generalization claims.

Dialogs-derived metrics carry the attached OpenRAIL license. Application
code/model licensing remains separate. No audio is redistributed.

## Reproduction and checks

    python tools/compare_speaker_embedding_candidates.py --site SITE

Defaults reuse the existing ignored datasets/model cache. Missing weights
are downloaded from the pinned mirror revision and verified before use.
Evidence is written to .local/speaker-model-compare-current/result.json
with RUNNING before work and COMPLETED only after all three models finish.
Do not run as a training or threshold-search loop.

All three native evaluations completed. The Small baseline reproduced
14/28/26 admitted profiles. All pair-count and returning-outcome invariants
and eleven existing isolation/selector regressions passed.
No app runtime, model default, identity thresholds or thermal guard changed.
