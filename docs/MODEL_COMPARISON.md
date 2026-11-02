# Comparable model experiments — no performance claims without evidence

Use this protocol for issue #5 (Russian dialogue benchmarks), issue #7 (Nemotron 3 vs existing diarization) and issue #10 (overlap handling). It **does not** run a model or download a dataset; it validates and aggregates independent `tools/score_transcript.py` JSON outputs. No raw audio, recordings, transcripts, model weights or personal data should be committed.

## Workflow

1. Freeze a legally usable corpus **before** tuning; include different natural Russian conversations with 1–4 speakers, A–B–A returns, pauses, noise, and real overlapping speech. Keep private audio and its transcripts offline. Independently mark reference words, speaker identities and speech intervals (e.g., RTTM). If reference speech boundaries are missing, DER must remain `NOT_SCORED`.
2. Run the baseline and one candidate on the **same unmodified recording bytes**. Keep the source commit, binary/model SHA-256, runtime package SHA-256, device ABI, precise timing scope, cold/warm distinction and failure logs. For DER, preserve identical `--collar-ms` and `--skip-overlap` flags. Use a fixed test set, no per-model cherry picking.
3. For each candidate and recording, run:

   ```bash
   python tools/score_transcript.py --reference reference.json --hypothesis output.json --output scores/baseline-a.json --collar-ms 0
   ```

4. Prepare a private manifest referencing those reports (see schema below), then:

   ```bash
   python tools/compare_model_trials.py --manifest private-trials/manifest.json --output private-trials/comparison.json
   python tools/test_compare_model_trials.py
   ```

   Exit **0**: each model and case has scored WER, cpWER and DER. Exit **2**: valid comparison, but at least one metric is unavailable. Exit **1**: invalid or incomparable evidence, with a machine-readable ERROR report. Missing scores are **never** treated as zero.

## Manifest format (illustrative, no experimental result)

```json
{
  "schema_version": 1,
  "trials": [
    {
      "name": "pinned-baseline",
      "code_commit": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "runtime_sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
      "environment": {"platform": "physical-android", "device": "device-model-and-build", "abi": "arm64-v8a", "api_level": 35},
      "timing_scope": "end-to-end inference including model startup",
      "cases": [
        {"score_file": "scores/baseline-a.json", "audio_duration_ms": 60000, "elapsed_ms": 10000}
      ]
    },
    {
      "name": "candidate",
      "code_commit": "cccccccccccccccccccccccccccccccccccccccc",
      "runtime_sha256": "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
      "environment": {"platform": "physical-android", "device": "device-model-and-build", "abi": "arm64-v8a", "api_level": 35},
      "timing_scope": "end-to-end inference including model startup",
      "cases": [
        {"score_file": "scores/candidate-a.json", "audio_duration_ms": 60000, "elapsed_ms": 9500}
      ]
    }
  ]
}
```

The illustrative hashes and numbers above are **placeholders**, not benchmark results.

## Enforcement and limitations

- Corpus identity is checked using `recording_id`, source audio SHA-256, exact reference JSON SHA-256 and recorded duration; all trials must cover the exact same cases. Both score JSON inputs must contain hashes. A unit-test-only fabricated reference is rejected.
- Reported WER/cpWER are micro-averaged by **reference word count**; DER by **reference speaker time**. If a metric is missing on any recording, its aggregate rate is null, with a count of unscored cases.
- Different DER collar/overlap rules invalidate the comparison. Latency/RTF is marked *not comparable* when declared hardware or timing scopes differ. Per-trial RTF values are not evidence of phone speed unless actually measured on the named device.
- The tool checks consistency of supplied reports; it does **not** prove that a WAV exists, hashes were computed honestly, timestamps are accurately annotated, code ran on the claimed hardware, a human transcript is independent, or that a difference generalizes. Verify raw results separately, run a holdout without retuning, and publish an evidence digest without exposing personal recordings.
- The GitHub CI for this tool uses **synthetic reports only** and provides no model accuracy result.

**Decision criterion:** retain the existing working pipeline until a candidate delivers a repeatable quality improvement without unacceptable latency, peak RAM, energy cost, integration risk or redistribution restrictions on a physical Android ARM64 phone. Separate exploratory research from the November 6–8 demo release.
