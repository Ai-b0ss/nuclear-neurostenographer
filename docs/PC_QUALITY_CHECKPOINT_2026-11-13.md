# PC quality checkpoint: Russian speaker separation

The development loop continues on PC and cloud Android emulators. Physical HONOR endurance is suspended by owner direction; no cooling-pause feature is being added.

Fresh current-source Kotlin Nemotron C2 inference and independent DER scoring completed on all three Veche hard-noise recordings, total848.247 s. All39 compiled source fingerprints match the current checkout. Model and ORT1.17.1 pins were verified before inference. No phone was used.

| Speakers | Duration | Predicted speakers | DER, no collar | DER,250 ms collar |
|---|---|---|---|---|
|2|153.189 s|2|6.021%|2.005%|
|3|304.520 s|3|6.951%|2.764%|
|5|390.538 s|5|6.965%|3.087%|
|Pooled|848.247 s|Correct in3/3 files|6.787%|2.778%|

[Numeric results and source/model provenance](evidence/veche-current-c2-pc.json). These reproduce the earlier saved measurements with newly compiled current sources. Veche contains volunteers reading scripts, assembled into meetings with noise; it is not spontaneous conversation. Two scripts were already used in other variants, so this is a regression check rather than a new unseen holdout. Supplied CSV speaker/time annotations are used as reference without independently auditing their boundaries.

Only local anonymous diarization is scored. No persistent voice profiles, identity recognition, ASR, WER or cpWER are inferred from this result. The ordinary globalSpeakerBook flag remains OFF. The earlier cloud Android20m40s completeness PASS remains functional evidence, separate from unverified sustained phone performance.

The score-only step initially lacked scipy in the selected venv; it was rerun successfully with the existing Python3.12 evaluation dependencies, reusing the fresh inference rather than running it again.
