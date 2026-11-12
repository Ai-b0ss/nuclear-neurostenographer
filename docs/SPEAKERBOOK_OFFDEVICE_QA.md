# Off-device C2 + TitaNet QA

The main development loop runs on a PC and standard GitHub-hosted runners.
HONOR is reserved for short ARM64 checks and later hardware performance validation.
Do not repeat a continuous physical endurance run until load has been reduced.

| Environment | Evidence | Does not establish |
|---|---|---|
| PC / Linux Actions host | Actual product Kotlin C2 outputs, DER and TitaNet matching replay | Android correctness, phone speed, temperature |
| x86_64 Android emulator | Product A3 + C2 + TitaNet pipeline, cross-window links, missing-model fallback, 20m40s completeness | HONOR ARM64 performance or sustained thermal readiness |
| Physical HONOR | Target ABI, short profiling, memory and temperature | Population identity accuracy from a tiny fixture |

## Run the host suite

Provision fixed public inputs with Python 3.11 and Java 17:

```sh
pip install numpy==1.26.4 scipy==1.14.1 soundfile==0.13.1 sherpa-onnx==1.12.40
python tools/provision_speakerbook_qa.py --host
python tools/run_speakerbook_host_qa.py \
  --data .local/speakerbook-active/scratch/ru_book_mix_eval \
  --model .local/nemotron \
  --titanet .local/speakerbook-active/scratch/models/nemo_en_titanet_small.onnx \
  --harness .local/speakerbook-host-harness
```

Existing Windows inputs can be reused through --java, --harness, --model and --site.
The pre-existing auxiliary Python packages on the owner's PC are CPython 3.12
binaries; run them with py -3.12, not Python 3.13. The local native sherpa version
is recorded separately; CI pins the same host 1.12.40: PyPI has no 1.12.20 wheel for this platform.
Android remains pinned to 1.12.20; cross-runtime parity is not assumed.

The host suite freezes the first 15 two-speaker one-minute recordings from the
already-reviewed 70-file audiobook sample. It compiles actual product Kotlin
C2, executes inference afresh, computes DER and replays the conservative TitaNet
policy on predicted C2 turns. No accuracy thresholds are tuned on these files.
It is a repeatable regression set, not a new independent natural-conversation test.
COMPLETED means execution completed; the global identity release gate remains
NOT_ESTABLISHED.

## Run Android QA in GitHub Actions

Workflow: .github/workflows/speakerbook-offdevice.yml. It has separate host and
emulator jobs and uses standard public-repository Linux runners only.
The four emulator cases run in independent matrix jobs (fail-fast=false),
so every case publishes its own terminal result and diagnostic log.
Heavy runs start only by workflow_dispatch or a deliberate change to
.github/run-speakerbook-offdevice.txt on main/the QA branch. Ordinary code
pushes do not restart this suite. The long input controls the 20m40s case
for a manual run. The marker route also works through the connected GitHub
integration without refreshing local Git credentials.

The emulator uses an isolated .speakerbookqa APK with A3, product C2 and TitaNet.
Three cross-window cases check repeat, different source voices, and absent
optional TitaNet; a fourth processes continuous 20m40s repeated-source audio.
Functional inputs use rec_0058, whose host diagnostic admits voice profiles,
and the first later disjoint-source recording. This is a deliberately selected
positive control, never a held-out accuracy claim. The quality evaluation
continues to score ALL 15 frozen two-speaker recordings, including failures.
Fixtures prove functional behavior; repetition and digital silence cannot
establish independent accuracy or natural meeting performance.

The ephemeral Linux runner grants KVM only to its own user, requires
emulator -accel-check to pass, explicitly enables VM acceleration and
never silently falls back to CPU software emulation. Numeric stage/progress
heartbeats distinguish model installation, import, diarization and ASR.

Before installing any APK, the runner requires ALL of:
- emulator-NNNN ADB serial;
- ro.kernel.qemu=1;
- ro.product.cpu.abi=x86_64;
- exact isolated QA app and test package IDs.

Only explicit qaEnvironment=emulator on a ranchu/goldfish x86_64 build bypasses
simulated temperature checks and extends timeouts. The physical path retains
the existing battery/OS checks and mandatory host CPU watchdog.
A fresh emulator waits for bundled model installation before asserting readiness.
TitaNet is staged as a checksum-pinned instrumentation-only asset; the test
copies it into the external QA directory under the target app UID before
running. This avoids host-created nested-directory visibility problems on
scoped storage. No model is added to the product APK.

Each case needs both JUnit OK (1 test) and fresh PASS app evidence marked as
ANDROID_X86_64_EMULATOR_NOT_PHONE. Prior evidence is removed first; RUNNING,
skipped tests and physical-device evidence cannot establish success. QA
processes are force-stopped and their absence checked after every case.

## Artifacts and limitations

Current generated files stay under .local/speakerbook-offdevice-current/.
GitHub uploads JSON metadata/metrics for seven days, never audio, models,
embeddings, transcript previews or local raw instrumentation logs.
No additional checkout or production APK is created.

The thermal policy remains: start below 39 C battery / 65 C CPU, charge >=40%;
stop at battery >=45 C, CPU >=78 C, Android SEVERE or lost telemetry.
An emulator success does not erase the earlier physical THERMAL_ABORT.
Global speaker linking remains disabled in ordinary builds.

## Verified 12 November 2026

All five jobs passed in Actions run 43174151953, runtime code cac43214.

| Check | Result |
|---|---|
| Actual host C2 + TitaNet | 15 min corpus in 107.15 s; DER 3.20017%; 12/30 admitted profiles; no admitted returning probes |
| Repeat after boundary | Both expected voices linked; 27.043 s recognition |
| Different source control | No shared global IDs; 38.259 s recognition |
| Optional model absent | All labels remain block-local; 36.454 s recognition |
| 20m40s continuous input | 218.948 s recognition, 252 segments, five profiled blocks; timeline/end coverage PASS |

The long case kept 21 uncertain speaker segments. Functional checks do not
establish WER/cpWER, population identity accuracy or physical thermal readiness.
