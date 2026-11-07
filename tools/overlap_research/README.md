# Issue #10 executable research

This is an isolated research harness. It does not change or replace the signed
contest application. The copied `docs/OVERLAP_*_20261105.md` files describe the
earlier audit; new execution results belong in `docs/ISSUE10_EXECUTION_20261105.md`
and `docs/evidence/issue10-codex-20261105/`.

## Shared real DataHive manual-enrollment path

This branch adds a separate real-data path in `manual_manifest.py`, `run_manual.py`,
`manual_metrics.py` and `export_manual.py`. It accepts only hash-bound manual
references and two explicit 3-second manual enrollments per two-speaker fragment.
There is no automatic enrollment or no-enrollment fallback. Do not run `make_dev.py`,
`run_host.py` or the synthetic-bound `run_phone.py` as a substitute for this path.
The shared real fragments are not yet available, so their host/HONOR metrics remain
`NOT_RUN`; see `docs/evidence/issue10-tse-voxlock-manual/README.md` for the Russian
protocol and commands to use after the common baseline is ready.

## Inputs and boundaries

- Actual app Kotlin `OfflineAsr`, `TokenWords`, `TranscriptFusion` and Nemotron C2
  are compiled into a host harness, with A3=true. A3 weights are checked against
  `AsrModelSpec.kt`; C2 verifies its own pinned bundle before inference.
- Host sherpa JNI is the existing pinned Windows 1.12.20 release build, not the
  identical signed-APK native build. Android probes use the exact pinned no-TTS
  AAR plus ORT Java 1.17.1. Neither uses a sherpa2 upgrade.
- VoxLock core `48b9a71e…`, v2 graphs `2413b292…`, NumPy and ORT are separate.
  Hashes and upstream URLs are executable pins in `provision.py`. Current v2
  Python graphs cannot be passed to sherpa2.0.1's older VoxLock1.1 API.
- Only three already-used ACTED DEV clips are mixed. No holdout audio is read.
  The output is **SYNTHETIC DEV**, with externally scripted utterance text, not
  manually audited words/times or natural overlap. DER and overlap word recall
  remain `NOT_SCORED`. Source license is [Dialogs OpenRAIL](../../docs/licenses/dialogs-OpenRAIL.md);
  recipients of derivatives must comply with its Section2 restrictions.
- Audio, model weights, utterance references, raw transcripts, SDK binaries and
  phone traces stay under ignored `.local/issue10`. Committed evidence contains
  metrics/provenance/hash manifests. No participant recording is sent to a service.
- VoxLock [Apache2 license](../../docs/licenses/issue10-voxlock-LICENSE.txt) and
  [NOTICE](../../docs/licenses/issue10-voxlock-NOTICE.txt) are preserved. The Java
  OLA probe independently implements the pinned core's reflect padding, hop128,
  Hann-squared normalization and gain−0.5; it is numerically compared to upstream.

## Reproduce on Windows

Use an existing Python environment with NumPy, ORT and psutil. Same-corpus
regression imports also need SciPy/PyArrow; optional A3 reprovisioning needs ONNX.
No script installs a package or edits user-wide settings. Actual tested package
versions are recorded in evidence. Use JDK17, SDK35/build-tools35 for Android DEX.

Example using the already verified local assets on the execution PC:

```powershell
$TaskPython = 'K:/nn-bench/venv/Scripts/python.exe'
$TaskJava = 'C:/Users/user/Documents/nuclear-neurostenographer/.local/java17/jdk-17.0.17+10-jre/bin/java.exe'
$TaskJdk = 'C:/Users/user/Documents/nuclear-neurostenographer/.local/build-tools/jdk-17.0.17+10'
$TaskSdk = 'C:/Users/user/Documents/nuclear-neurostenographer/.local/android-sdk'
$TaskA3 = 'K:/nn-bench/data/models/a3-opsetfix'
$TaskC2 = 'K:/nn-c2-android/.local/nemotron'

& $TaskPython -B tools/overlap_research/preflight.py
& $TaskPython -B tools/overlap_research/provision.py --harness K:/nn-bench/harness
& $TaskPython -B tools/overlap_research/make_dev.py --source C:/Users/user/Documents/nuclear-neurostenographer/.local/dialogs-ru-source
& $TaskPython -B tools/overlap_research/build_host.py --java $TaskJava
& $TaskPython -B tools/overlap_research/run_host.py --java $TaskJava --a3 $TaskA3 --c2 $TaskC2 --out .local/issue10/my-strict-run
& $TaskPython -B tools/overlap_research/run_host.py --java $TaskJava --a3 $TaskA3 --c2 $TaskC2 --enrollment-mode provided-dev --out .local/issue10/my-provided-run
& $TaskPython -B tools/overlap_research/verify.py
```

For a clean checkout omit `--harness` to fetch exact pinned compiler/JNI inputs,
and omit `--source` to fetch only the three pinned DEV clips, metadata and license.
`provision_baseline.py` can fetch and reproduce pinned A3/C2 under
`.local/issue10/baseline`; it requires ONNX already installed. The historical
`fetch_models.py` resolves current Hub head, so is deliberately not used here.
The fixture generator explicitly preserves the original CRLF reference/manifest
bytes across platforms. Audio, reference and manifest regeneration was compared
byte for byte. `run_host.py` refuses an output directory with an existing summary.

## Interpreting host results

`strict-c2` requires a contiguous3100ms clean interval with50ms boundary guards.
If this fails, no separator is called and the baseline is retained.
`provided-dev` is a separate controlled experiment: exactly3s from a known
single-source composition anchor, including natural pauses. C2 supplies its
cluster ID; reference text is never used to assign an output speaker.

Both stems pass through the same A3 and original C2 turns. `QuietCuts` refines
each waveform, so boundaries can differ; this is not fixed-window separator-only
parity. A second decode saves unmerged emission-word sidecars, and their normalized
word sequences are checked against actual app output. Extra sidecar decoding is
excluded from app-inference metadata, but included in outer host process time.

Overlap splicing preserves baseline words outside C2 overlap and leaves every
recovered identity unknown. This means cpWER-U cannot improve those words:
the project metric drops unknown words and can also hide unknown insertions.
Report full WER, strict cpWER status and unknown count alongside it. The separate
`assumed_identity_diagnostic` stamps enrollment IDs without a calibrated verifier;
its improvement is evidence of potential, never an accepted application metric.
Simultaneous-word ordering and splice boundaries can distort sequence WER.

Wrong enrollment reuses the actually executed opposite-speaker extraction with
the requested identity swapped. It is not an unseen-third-voice test. Source-only
utterance spill is identifiable from controlled composition; target-only insertion
counts alone are only leakage proxies. Silence and short-enrollment tests and
five actual host session create/infer/free cycles are separately recorded.

## Physical Android feasibility

```powershell
& $TaskPython -B tools/overlap_research/prepare_phone.py --jdk $TaskJdk --sdk $TaskSdk --sherpa C:/Users/user/Documents/nuclear-neurostenographer/app/libs/sherpa-onnx-1.12.20.aar
& $TaskPython -B tools/overlap_research/run_phone.py --serial DEVICE_SERIAL --a3 $TaskA3 --c2 $TaskC2 --repeats 5
& $TaskPython -B tools/overlap_research/run_phone.py --serial DEVICE_SERIAL --a3 $TaskA3 --c2 $TaskC2 --quality-only
& $TaskPython -B tools/overlap_research/summarize_phone.py
```

Use `--out .local/issue10/new-phone-run` for a separate trial; pass the same out
to the quality-only and summary commands.
After a run has been cleaned, its journal is retired; use a new `--out` to run
physical inference again. Local summarization/verification still works offline.

Official Google platform-tools are staged with the official repository checksum.
Probe adb uses its own port5047,
task-local Android home, and a new `/data/local/tmp/nn_issue10_codex_*` directory.
Every transferred model/native/DEX/WAV hash is checked on the phone. No APK is
installed, replaced or cleared. Airplane mode must already be enabled; the script
refuses to silently change settings. Never select an unrelated device.

There are six sequential fresh workers per paired repeat: C2, baseline A3,
target0 separation/A3, target1 separation/A3. One-second requested PSS sampling
adds adb/tail overhead. PSS is a **standalone sampled estimate**, not the actual
app+Binder-worker simultaneous peak. CPU scopes differ: baseline includes
input/native/model loading; VoxLock's counter covers inference after load.
Outer wall RTF includes startup/load/monitoring and is the comparable total.
The measured candidate runs whole-clip extraction for each target and overlap-only
transcript splicing; it does not prove optimized overlap-window device cost.
Measured DEX JAR entries are not4-byte aligned and Android extracts them as a
fallback; that startup/cache cost is included. Preserve these JARs when comparing
the published runs. A separately repaired DEX handles invalid enrollment with
`INVALID_INPUT`/exit2 and passes actual ARM64 valid-silence regression; it is not
substituted into the original5-repeat measurements.

Performance runs disable extra word-sidecar decoding. `--quality-only` separately
reruns A3 with sidecars and excludes those jobs from performance summaries.
This probe does not clear Binder lifecycle, background/UI cancellation, app OOM,
APK packaging or16KB-device gates. The existing ORT Java JNI's4KB ELF alignment
remains a failed16KB check even when inference works on a4KB phone.

The journal writes `UNKNOWN_OUTCOME` before external dispatch. A timeout refuses
retry until the owned job exit is reconciled. Never kill the default adb server,
clear global logcat or inspect unrelated phone files. When work is complete,
only the exact journal-owned remote directory and port5047 server may be cleaned.

`export_evidence.py` exports only deidentified metrics. It refuses a final export
before five paired physical repeats and a green regression summary. This is an
artifact gate, not permission to close Issue10. No issue comment is posted by
these tools.
