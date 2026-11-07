"""Generate the issue handoff from verified metrics, with explicit unavailable gates."""
import json
from pathlib import Path
from common import REPO,LOCAL,write_json

def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def ratio(m):return str(m.get('errors','NOT_SCORED'))+'/'+str(m.get('reference_words','')) if m.get('status')=='SCORED' else m.get('status','NOT_SCORED')
def range_s(d,scale=1):return f"{d['median']/scale:.2f} ({d['min']/scale:.2f}–{d['max']/scale:.2f})"
def readable(text):
    substitutions={'Issue10':'Issue #10','signed0.3.3':'signed 0.3.3','JNI1.12.20':'JNI 1.12.20','ORT1.17.1':'ORT 1.17.1','ORT1.31.1':'ORT 1.31.1',
        'are20.1555s':'are 20.1555 s','at0/250ms':'at 0/250 ms','than3100ms':'than 3100 ms','exactly48000':'exactly 48,000',
        'correlation0.':'correlation 0.','cpWER-U18/53':'cpWER-U 18/53','keeps11/12':'keeps 11/12','keeps29':'keeps 29',
        'keeps\n29':'keeps\n29','preserves0/41':'preserves 0/41','DNN-LX9,Android10,4KB':'DNN-LX9, Android 10, 4 KB',
        'Java1.17.1':'Java 1.17.1','IR8':'IR 8','opset17':'opset 17','repeats,30/30':'repeats, 30/30','exit0':'exit 0',
        'battery33':'battery 33','sensor34':'sensor 34','truncated20155ms':'truncated 20,155 ms','WAV20.1555s':'WAV 20.1555 s',
        'offset41':'offset 41','score16/53':'score 16/53','WER,18/53':'WER, 18/53','candidate19/53':'candidate 19/53',
        'exceed0.99999':'exceed 0.99999','reject47999':'reject 47,999','exception/exit137':'exception / exit 137',
        'INVALID_INPUT/exit2':'INVALID_INPUT / exit 2','OK/exit 0':'OK / exit 0','its5-repeat':'its 5-repeat','adb5047':'adb 5047',
        'align16KB':'align 16 KB','aligns4096':'aligns 4096','FAILS16KB':'FAILS 16 KB','A4KB':'A 4 KB','all10 DEV':'all 10 DEV',
        'checkpoint1d9fdda':'checkpoint 1d9fdda','repeats);16':'repeats); 16','and5 physical':'and 5 physical','/16KB':'/ 16 KB',
        'hashes,5 fresh':'hashes, 5 fresh','alignment4096':'alignment 4096','fails16KB':'fails 16 KB','checkpoint,2.47GB':'checkpoint, 2.47 GB',
        'plus16KB':'plus 16 KB','failed16KB':'failed 16 KB','stages0':'stages 0','exits0':'exits 0',
        'Contest0.3.3':'Contest 0.3.3','WER16/53':'WER 16/53','Android10':'Android 10','mode:5':'mode: 5',
        'RTF1.56':'RTF 1.56','maximum867.9MiB':'maximum 867.9 MiB','Java4KB':'Java 4 KB','pass,1':'pass, 1',
        'skip;16':'skip; 16','criteria:1':'criteria: 1','missing);2':'missing); 2','acceptance);3':'acceptance); 3',
        'missing);4':'missing); 4','FAIL;5':'FAIL; 5','migration;7':'migration; 7'}
    for before,after in substitutions.items():text=text.replace(before,after)
    return text

if __name__=='__main__':
    host=read(LOCAL/'host-provided-v2/summary.json');phone=read(LOCAL/'phone-runs/summary.json')
    if phone['complete_paired_repeats']!=5 or phone['status']!='COMPLETE' or 'quality' not in phone:raise ValueError('Finish five physical repeats and quality sidecars first')
    negative=read(LOCAL/'phone-negatives.json')
    if negative['status']!='PASS':raise ValueError('Physical negative probe incomplete')
    if read(LOCAL/'input-guard-regression.json')['status']!='PASS':raise ValueError('Input-handler repair not verified')
    rows=host['rows'];overlap=rows[1];ag=phone['aggregate'];temp=phone['battery_temperature_c']
    verification=read(REPO/read(LOCAL/'verification/latest.json')['path']/'summary.json')
    checks=sum(r['tests'] or 0 for r in verification['rows']);skips=sum(r.get('skipped',0) for r in verification['rows'])
    host_table='\n'.join(f"| {r['case']} | {ratio(r['baseline']['wer'])} | {ratio(r['candidate']['wer'])} | {ratio(r['baseline']['cpwer_u'])} / {ratio(r['candidate']['cpwer_u'])} | {r['baseline']['unknown_words']} / {r['candidate']['unknown_words']} |" for r in rows)
    criteria=[
        dict(id=1,status='PARTIAL / EXTERNAL BLOCKER',evidence='Two hash-frozen SYNTHETIC DEV fixtures; no independently manually annotated natural Russian overlap or untouched natural holdout.'),
        dict(id=2,status='PARTIAL',evidence='New host and5 physical paired standalone repeats; WER/cpWER-U scored. Strict cpWER/DER/overlap word recall unavailable where annotation or attribution missing. App+worker PSS/UI/emulator remain unverified.'),
        dict(id=3,status='EXECUTED / RESEARCH ONLY',evidence='Correct A/B, opposite-speaker enrollment, short/no enrollment, clean/silence controls, both stems through same pinned A3; conservative accepted output falls back unchanged. Identity verifier missing.'),
        dict(id=4,status='PARTIAL /16KB FAIL',evidence='Actual ARM64 JNI/ORT1.17.1 inference, native mapped paths, transfer hashes,5 fresh-process repeats, standalone cancel/recovery. Existing ORT Java ELF alignment4096 fails16KB. No research APK/Binder/background/OOM clearance.'),
        dict(id=5,status='RESEARCH COMPLETE',evidence='DiCoP live commit b9ccee411877f5e8da42e56ed27e693829f80ce1; no code license found; English CC-BY4 checkpoint,2.47GB. No training/conversion attempted.'),
        dict(id=6,status='RESEARCH COMPLETE / NO MIGRATION',evidence='audio.cpp live commit f7ac446fb75e594a6913c846bea6c85b637f6ac0; Apache2 license inspected; no Android/JNI/NDK paths in tree. No comparative Android implementation/proof.'),
        dict(id=7,status='EXECUTED ON SYNTHETIC DEV / STILL OPEN',evidence='Paired same-input host and physical tables, negative outcomes and diagnostic positive counterevidence retained. Natural holdout and identity/app gates not satisfied.')]
    write_json(LOCAL/'decision.json',dict(decision='RESEARCH ONLY',integration='NO-GO',issue_recommendation='STILL OPEN',criteria=criteria,
        measured_quality='Accepted fallback preserves baseline; exploratory splice regresses sequence WER. Assumed identity improves cpWER-U but is not accepted speaker proof.',
        genuine_blocker='Independent natural Russian manual word/speaker/activity annotation and untouched holdout are absent; cannot fabricate human annotation or calibrated speaker verification.'))
    criterion_table='\n'.join(f"| {c['id']} | {c['status']} | {c['evidence']} |" for c in criteria)
    quality=phone['quality']
    report=f'''# Issue10 — executed engineering and decision,2026-11-05

**RESEARCH ONLY; NO-GO for contest integration; Issue10 STILL OPEN.** Actual host
and physical ARM64 experiments now exist. They do not establish a shippable
overlap-recovery feature. The signed0.3.3 contest application, main and release
were not changed. No audio/weights/private participant text are committed.

Base: `a10dd3954a1a53aaf749f7ef7696bf6446cc42f4`. Branch:
`research/issue10-codex-20261105`. Engineering checkpoints: `1d9fdda`, `9d3b277`;
the final evidence commit follows them. The copied initial audit/protocol/comment
are preserved unchanged; their NOT_RUN descriptions are historical.

## New measured host evidence

Actual production Kotlin A3/C2, original C2 turns and same GigaAM weights; host
JNI1.12.20/ORT1.17.1, separate VoxLock v2 INT8 Python ORT1.31.1 CPU. Source/model
pins, references and input hashes precede inference. Both fixtures are20.1555s,
**SYNTHETIC DEV from three licensed ACTED source clips**. No holdout audio read.
Scripted utterances are not manually verified words or acoustic boundaries.

| Fixture | Baseline WER | Exploratory splice WER | cpWER-U base / splice | unknown words base / splice |
|---|---:|---:|---:|---:|
{host_table}

Overlap baseline S/D/I/N=1/9/6/53; splice=2/7/10/53. Strict cpWER is NOT_SCORED
when unknown words remain. DER at0/250ms and overlap-only word recall remain
NOT_SCORED because independent reference activity/word times are absent, even
though actual raw C2 speech turns are saved. No fake reference or zero DER.

Strict automatic enrollment fails for the second voice: C2's longest continuous
clean turn is shorter than3100ms. Both fixtures retain the original baseline.
The separate provided-DEV experiment uses exactly48000 clean-source samples per
target, including natural pauses, with C2 cluster IDs. Crop hashes, zero other-
source energy, finiteness, length and clipping were independently checked.

Both outputs differ (overlap correlation{overlap['target_correlation']:.6f}) and
preserve the target's scripted words. **Positive counterevidence:** assuming
enrollment identity reduces diagnostic cpWER-U18/53→4/53. This is not a trusted
application result: there is no independently calibrated identity verifier.
Conservative recovered words remain null, so cpWER-U structurally cannot improve
them. Its definition drops unknown words and can hide unknown insertions; it is
not a guaranteed pessimistic upper bound.

Target-only S/D/I/N on overlap: D=0/0/11/29, M=0/0/20/24. Insertions are leakage
proxies. Raw source-exclusive intervals independently show retention of the
other voice: D-target keeps11/12 M words in M-only speech; clean M-target keeps
29 D words in D-only speech. Exact overlap leakage/recall is not measurable here.
Sequence WER is also affected by interleaved simultaneous words and C2 splice
boundary artifacts. Therefore these data do not prove that VoxLock cannot help.

Correct/wrong enrollment controls reuse the two actually executed target runs
with requested identities swapped; this is not an unseen-third-speaker test.
No-enrollment and final accepted outputs were independently compared byte for
byte to baseline: identical. Clean overlap-only policy preserves0/41 WER; both
target outputs leak clean non-target speech. Actual silence extraction is zero;
five host init/infer/free cycles and short-enrollment rejection pass.

## New physical ARM64 evidence

HONOR DNN-LX9,Android10,4KB pages, airplane mode, Wi-Fi off; charging. Task-only
`app_process` DEX, no APK install/replacement, no personal-file reads. Exact stable
no-TTS AAR and ORT Java1.17.1 libraries were transferred with hashes and their
loaded paths independently observed in the owned PID's maps. VoxLock v2 IR8 /
opset17 graphs run directly on pinned ORT1.17.1: no sherpa upgrade was required.

Five paired repeats,30/30 stage processes exit0. Each repeat: C2→baseline A3→
target0 extraction/A3→target1 extraction/A3, sequential fresh processes. The
candidate cost below includes baseline plus two whole-clip extractions and their
A3 decoding; it is not optimized overlap-window cost or signed-app performance.

| Metric | Baseline C2+A3 | Full research probe |
|---|---:|---:|
| Wall RTF, median(min–max),n=5 | {range_s(ag['baseline_wall_rtf'])} | {range_s(ag['candidate_full_clip_probe_wall_rtf'])} |
| Sampled standalone stage PSS MiB, median(min–max) | {range_s(ag['baseline_sampled_peak_standalone_pss_kib'],1024)} | {range_s(ag['candidate_sampled_peak_standalone_pss_kib'],1024)} |
| Native-failure exits during paired repeats |0/10|0/30|

One-second requested PSS sampling plus adb overhead gives an estimate, not true
peak or concurrent application+Binder-worker PSS. Outer wall time includes
startup/load/monitoring tail. Detailed model-load/inference/CPU counters are
retained per stage: baseline CPU includes loading; separator CPU covers inference
after loading, so full end-to-end process CPU comparison is unavailable.
Initial battery33°C; per-stage sensor{temp['min']:.1f}–{temp['max']:.1f}°C; SoC thermal and energy/power not measured.
OS caches warm between fresh-process runs; no cold-device claim.
RTF uses the app's truncated20155ms duration (actual WAV20.1555s). Both measured
DEX JAR entries start at ZIP offset41, causing Android's fallback to extraction;
this startup/cache cost is included. The measured JARs are preserved unchanged.

All five baseline outputs score16/53 WER,18/53 cpWER-U. Separately collected
word-sidecar quality jobs, excluded from performance, give baseline
{ratio(quality['baseline']['wer'])}, exploratory candidate{ratio(quality['candidate']['wer'])} WER;
accepted fallback remains unchanged. Every sidecar's normalized word sequence
is checked against actual app-code output. Actual ARM64 vs Python extracted PCM
correlations exceed0.99999; numerical agreement is not speaker-quality proof.

Negative physical probes additionally reject47999-sample enrollment, terminate
only a verified owned native-loaded PID, confirm its death, and run A3 recovery
with identical baseline text. This tests standalone process containment only.
The first invalid-input test exposed an uncaught Java exception/exit137 in the
research probe (not a native crash). Its PID-filtered log is retained. The guard
was repaired in a separate DEX: actual ARM64 now returns INVALID_INPUT/exit2,
and a valid silence inference still returns OK/exit0. Original measured DEX
and its5-repeat evidence were preserved byte for byte.
Binder/service/UI/background cancellation, same-process repeated session lifetime,
app OOM and APK packaging remain NOT_RUN. Global logcat/tombstones were not read;
successful exits/task logs show no observed native crash, not a system-wide audit.
After collection, the exact owned remote directory was resolved/identified by its
probe hash, removed, and only the owned adb5047 server stopped. Phone settings
and signed application remain untouched; raw evidence and models remain local.

Static ARM64/x86_64 symbol checks find no missing ORT imports. Stable sherpa native
libraries align16KB; `libonnxruntime4j_jni.so` aligns4096 and still **FAILS16KB**.
A4KB phone cannot clear that gate. VoxLock graph bytes=77,584,388; DEX=2,468,280.
APK delta is NOT_BUILT, not zero.

## Engineering repairs and reproducibility

- Preserve `attribution_reliable` in both score adapters; known-but-unreliable
  words cannot receive favorable strict cpWER. Preserve unknown DER speech;
  handle null speakers and empty post-collar reference without a crash/false zero.
- Independently verify optional original WAV hash in phone-score adapter; a
  mismatch tombstones stale favorable scores. Retain legacy association-only
  calls with explicit provenance warning. Report actual thread counts.
- Atomic task journals, unknown outcome before device dispatch, exact input pins,
  bounded output paths, source/fixture/runtime manifests and no automatic retry
  after unresolved device timeout. New remote staging accepts only four pinned
  A3 files, not arbitrary files from a model directory.
- Independent regeneration matches all10 DEV files byte for byte. Pinned A3/C2
  reprovisioning reproduces exact contest hashes. Twelve measured host source
  hashes and both measured phone source files reconcile to committed blobs,
  including checkpoint1d9fdda; raw source snapshots are retained locally.
- {checks-skips} passed Python test executions, {skips} optional Windows symlink skip
  ({checks} total,including optimized-mode repeats);16 Kotlin core groups and
  plain/named/edited export corruption checks pass. The earlier export-path
  invocation failure is retained locally; it was corrected and rerun.

Full commands and environment: [tools/overlap_research/README.md](../tools/overlap_research/README.md).
Machine-readable results: [evidence directory](evidence/issue10-codex-20261105/),
[manifest](evidence/issue10-codex-20261105/evidence-manifest.json).
Raw generated WAV/reference/hypothesis/trace outputs stay in ignored
`.local/issue10`; only their paths/hashes/sizes and deidentified metrics are shared.
No paid APIs/package installs or user-wide auth/security changes. GitHub connector
read succeeded; git authenticated read also succeeded with ordinary sandbox
approval. Publishing this branch is separate from publishing an issue comment.

## Evidence ledger and original issue criteria

| Criterion | Verified status | Evidence / remaining limitation |
|---|---|---|
{criterion_table}

Three read-only independent audits covered provenance/licensing, scoring/confounds
and Android compatibility. Their findings were checked against actual code and
outputs, not treated as measurements. Key contradictions retained: positive
assumed-identity recovery versus conservative unknown fallback; substantial clean
spill; sequence-order/splice confounds; standalone versus APK memory/lifecycle;
4KB execution versus failed16KB alignment.

**Decision:** keep current A3+C2 conservative fallback; VoxLock remains RESEARCH
ONLY/OPTIONAL future experiment. Do not integrate this prototype or close Issue10.
Independent natural Russian annotation/untouched holdout, calibrated identity and
splice verification, then an optimized isolated app worker plus16KB/lifecycle and
physical acceptance are required. Missing human annotation is a genuine external
blocker; no assistant/ASR-generated annotation is substituted. Existing observed
quality/cost and identity gates justify stopping impractical contest integration.
'''
    (REPO/'docs/ISSUE10_EXECUTION_20261105.md').write_text(readable(report),encoding='utf-8')
    base='https://github.com/Ai-b0ss/nuclear-neurostenographer/blob/research/issue10-codex-20261105/'
    short=f'''## Issue10 — executable A/B update,2026-11-05

**RESEARCH ONLY / NO-GO for contest integration; STILL OPEN.** The earlier
NOT_RUN gap now has actual host and physical ARM64 evidence. Contest0.3.3/main
remain untouched; no audio/weights/participant text published.

- Frozen licensed SYNTHETIC DEV A/B/A and overlap, same pinned app-code A3+C2,
  both VoxLock targets, correct/opposite/short/no-enrollment and clean controls.
- Host overlap: WER16/53→19/53; conservative cpWER-U18/53 unchanged; strict cpWER,
  DER and overlap-word recall unavailable under unknown/annotation limitations.
  Assumed-identity diagnostic cpWER-U18/53→4/53 shows potential, not verified
  identity. Non-target speech retention and splice/order confounds are preserved.
- Physical HONOR ARM64/Android10/airplane mode:5 paired repeats,30/30 stage exits0.
  Median standalone wall RTF{ag['baseline_wall_rtf']['median']:.2f} baseline vs
  {ag['candidate_full_clip_probe_wall_rtf']['median']:.2f} full two-target whole-clip probe.
  Sampled standalone PSS maximum{ag['candidate_sampled_peak_standalone_pss_kib']['max']/1024:.1f}MiB;
  this is not app+worker peak or optimized overlap-window cost. Same A3 decodes
  both physical stems; separate sidecar quality runs exclude duplicate decode cost.
- Exact pinned ORT1.17.1/JNI bytes execute VoxLock v2 directly, without sherpa
  upgrade. Invalid enrollment, owned-process cancellation and recovery pass.
  Existing ORT Java4KB ELF alignment still fails16KB; APK/Binder/background/OOM
  gates are unverified. No production integration attempted after failed gates.
- {checks-skips} Python checks pass,1 optional Windows symlink skip;16 core groups,
  three export regression suites, fixture/source/model hash reproduction pass.

Original criteria:1 PARTIAL(manual natural holdout missing);2 PARTIAL(standalone
metrics, no independent DER/word times/full APK acceptance);3 EXECUTED RESEARCH
ONLY(identity verifier missing);4 PARTIAL/16KB FAIL;5 DiCoP RESEARCH COMPLETE;
6 audio.cpp RESEARCH COMPLETE/no migration;7 same-fixture measured table DONE
for synthetic DEV, natural/app gates STILL OPEN.

[Execution and criterion ledger]({base}docs/ISSUE10_EXECUTION_20261105.md) ·
[Reproduction commands]({base}tools/overlap_research/README.md) ·
[Machine-readable evidence]({base}docs/evidence/issue10-codex-20261105/evidence-manifest.json).

Keep baseline fallback. Next independent requirements are consented natural Russian
manual word/speaker/activity annotation, untouched holdout and calibrated identity,
then splice validation and isolated app-worker/16KB acceptance. No issue closure
without completing these gates or an explicit owner-approved scope change.
'''
    (REPO/'docs/ISSUE10_READY_COMMENT_CODEX_20261105.md').write_text(readable(short),encoding='utf-8')
    print('WROTE execution report, decision.json, ready-to-post comment; nothing posted')
