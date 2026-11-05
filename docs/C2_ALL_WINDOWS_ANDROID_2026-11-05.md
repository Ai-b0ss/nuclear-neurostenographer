# Decoding C2 silence gaps with A0

`C2PaddingAsrProbeTest` ran the production C2 (zero native activity threshold,
150 ms turn padding, 400 ms same-speaker ASR merge) on ten frozen Russian
recordings in the 4 GiB Android 16 API 36 emulator. With instrumentation
argument `experiment=all_windows`, its candidate kept C2 speaker turns but
also decoded the gaps between them. Both policies used the same C++ A0 CTC
runtime and the same WAVs and references.

| Policy | WER | Strict cpWER on the same scorable recordings | ASR load + decode |
|---|---:|---:|---:|
| Current C2 speech windows | 40/525 | 71/380 | 15.079 s |
| All windows, including C2 silence gaps | 44/525 | 75/380 | 17.688 s |

The full-coverage policy worsened both text metrics and took about 17% longer.
It is not promoted. This does not rule out an independent VAD that selects only
genuine speech missed by C2; indiscriminate decoding is not sufficient.

Reproduce with `-PnemotronPrototype=true -PnativeAsrCandidate=true
-PdiarThresholdProbe=true`, then run `C2PaddingAsrProbeTest` with `-e
experiment all_windows`. Pull `files/c2-all-windows-evidence.json` from the
`.c2` debug app and score it with `python
tools/nemotron/score_c2_padding_asr.py EVIDENCE.json`. The frozen audio,
references and raw transcript evidence remain in ignored `.local/`.
