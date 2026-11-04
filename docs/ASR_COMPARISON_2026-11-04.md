# ASR control: GigaAM v3 CTC INT8 vs Whisper Turbo, 2026-11-04

**Measured Whisper control only. This is NOT a GigaAM RNNT/e2e benchmark.**

| WAV recording | GigaAM A0, existing C2-window result | Whisper v3 Turbo Q5, newly tested | Source SHA-256 prefix |
|---|---:|---:|---|
| acted-dmd.wav | 1/41 (2.44%) | 2/41 (4.88%) | 9294f7fc91b96c... |
| syn3-clean.wav | 5/52 (9.62%) | 3/52 (5.77%) | 7b5d5f9c8d5a98... |
| syn4-noise.wav | 4/76 (5.26%) | 12/76 (15.79%) | 939648072d210e... |

The same WAV files were verified byte-for-byte against reference SHA-256 values and scored with the existing `tools/score_transcript.py` word normalization (NFKC/lowercase/yo->ye). Reference transcripts: `K:\nn-bench\data\corpus\acted-dmd.ref.json`, `K:\nn-bench\data\same\syn3-clean.ref.json` and `syn4-noise.ref.json`. The first is a curated, stitched actor dialogue, the others use synthetic voices.

**Comparability warning:** GigaAM numbers originate from the application's C2-derived speech windows; Whisper was run on complete original WAVs. Thus this comparison does NOT isolate the effect of the ASR model or decoder. Three short recordings cannot establish general quality; training-data independence is unverified. No natural meeting, word-level alignment, cpWER, or DER measured for Whisper.

New Whisper model: locally installed Whisper Large-v3 Turbo Q5 through Vulkan, RTX 2060 Super, no download. Processing per short clip 1.1-1.3 seconds after model load; **desktop performance must not be compared to ARM64 RTF**.

Local results (not committed, no private audio uploaded): `K:\nn-bench\asr-compare-20261104\results.json`. Local Whisper server terminated after the benchmark.

## Next actual GigaAM model experiments

1. A1: official GigaAM `v3_e2e_ctc` against current A0 `v3_ctc`; hold out independent Russian dialogue, score WER/CER and punctuation separately.
2. A2: `v3_e2e_rnnt`; test if quality compensates for higher inference costs. Confirm actual Android runtime/ONNX availability, don't assume compatibility.
3. A3: `v3_rnnt` and `multilingual_ctc` 220M only if 1-2 justify the engineering cost.
4. Independently vary A0 segmentation/quiet cuts on identical audio and compare to the same-window baselines before attributing ASR word repetitions to the acoustic model.
5. Advance to ARM64 only after independent paired PC evidence, and measure runtime, peak RAM, battery, word/diarization correctness with fixed C2 and export.

**Blocked by free disk space, not model quality:** at test time C: 1.19 GiB and K: 2.61 GiB free. Neither RNNT/e2e weights nor complete GigaAM Torch environment are locally installed. Those variants remain NOT_RUN; do not install large dependencies onto C: or disturb the working signed RC1.

Upstream model list: https://github.com/salute-developers/GigaAM
