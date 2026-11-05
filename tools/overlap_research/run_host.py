"""Paired pinned app-code A3+C2 / VoxLock DEV experiment, local/offline inference.

All paths with generated audio/text are ignored. No holdout tuning. A candidate
never becomes a trusted speaker identification without an independent verifier.
"""
import argparse
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import numpy as np
from common import REPO, LOCAL, owned, sha, write_json
from make_dev import read_wav, write_wav
from metrics import score, overlap_spans, in_overlap
from provision import PINS

def read_turns(path):
    out=[]
    for line in Path(path).read_text().splitlines():
        a,b,c=map(int,line.split('\t'))
        out.append(dict(start_ms=a,end_ms=b,speaker_id=None if c<0 else 'Speaker '+str(c+1)))
    return out

def enrollments(x,turns,anchors):
    """First clean 3s inside each pre-registered source anchor, selected by C2 alone.
    Source identity text is never read. 50ms boundary guard, no padding, no auto sample.
    """
    results=[]
    for left,right in anchors:
        points=sorted({left,right,*[max(left,min(right,t[k])) for t in turns for k in ('start_ms','end_ms')]})
        intervals=[]
        for a,b in zip(points,points[1:]):
            active={t['speaker_id'] for t in turns if t['start_ms']<=a<t['end_ms']}
            if len(active)!=1 or None in active:continue
            who=next(iter(active))
            if intervals and intervals[-1][1]==a and intervals[-1][2]==who:intervals[-1]=(intervals[-1][0],b,who)
            else:intervals.append((a,b,who))
        candidates=[(a+50,b-50,s) for a,b,s in intervals if b-a>=3100]
        if not candidates: results.append(None);continue
        a,b,who=candidates[0]; sample=x[a*16:(a+3000)*16]
        if len(sample)!=48000 or not np.isfinite(sample).all() or np.sqrt(np.mean(sample**2))<1e-4 or np.max(np.abs(sample))>=0.99:
            results.append(None);continue
        results.append(dict(speaker_id=who,start_ms=a,end_ms=a+3000,pcm=sample))
    if len([r for r in results if r])!=len({r['speaker_id'] for r in results if r}):
        return [None for _ in results]
    return results

def seal_hyp(raw,wav,turns):
    h=copy.deepcopy(raw);h['audio_sha256']=sha(wav);h['diarization']=turns
    return h

def build_hybrid(base_words,target_words,spans):
    # No calibrated identity verifier exists: recovered speaker is deliberately null.
    kept=[s for s in base_words if not in_overlap(s,spans)]
    recovered=[]
    for who,words in target_words.items():
        for s in words:
            if in_overlap(s,spans):
                recovered.append(dict(s,speaker_id=None,attribution_reliable=False,overlapping_speech=True,
                                      conditioned_target_id=who,verification='IDENTITY_UNVERIFIED'))
    return sorted(kept+recovered,key=lambda s:(s['start_ms'],s['end_ms']))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--java',required=True,type=Path);ap.add_argument('--a3',required=True,type=Path)
    ap.add_argument('--c2',required=True,type=Path);ap.add_argument('--out',type=Path,default=LOCAL/'host-v1')
    ap.add_argument('--enrollment-mode',choices=['strict-c2','provided-dev'],default='strict-c2');args=ap.parse_args()
    out=owned(args.out); h=LOCAL/'harness';tmp=owned(out/'tmp')
    # Verify same pinned A3 bytes used by the contest app, including opset-fixed encoder.
    pins={'gigaam_v3_e2e_rnnt_encoder_int8.onnx':'75e93f387fa3cf5743e2b702dbc3108214b9769fdf4ae131f4e4c6d6087571ac',
          'gigaam_v3_e2e_rnnt_decoder.onnx':'781971998e6a355d6a714f6932a30eab295e7ba0d14fd7e0f78c83b87e811860',
          'gigaam_v3_e2e_rnnt_joint.onnx':'602ff7017a93311aad34df1437c8d7f49911353c13d6eae7a6ee7b041339465c',
          'gigaam_v3_e2e_rnnt_tokens.txt':'7ddf22514c42c531358182c81446a8159771e9921019f09ae743ea622d40221d'}
    for name,digest in pins.items():
        if sha(args.a3/name)!=digest:raise ValueError('A3 model pin mismatch: '+name)
    for name,(_,digest) in PINS.items():
        if sha(LOCAL/'voxlock'/name)!=digest:raise ValueError('VoxLock pin mismatch: '+name)
    manifest=json.loads((LOCAL/'dev/manifest.json').read_text(encoding='utf-8'))
    protocol=dict(split='SYNTHETIC DEV; no holdout read',candidate='VoxLock v2 INT8, threads1, 3s C2-clean enrollment, no automatic enrollment',
                  quality_gate='Exploratory only: lower paired cpWER-U and no increase of clean-speech WER errors; strict cpWER, full WER, unknown and negative controls mandatory. Natural manual ground truth and independent identity verifier still required.',
                  frozen_before_candidate=True,enrollment_mode=args.enrollment_mode,
                  enrollment='strict-c2: C2 continuous clean>=3100ms,50ms guard; provided-dev: controlled synthetic single-source anchor,250ms guard,3s with natural pauses; unique C2 identity in anchor; neither uses reference text',
                  overlap='Replace midpoint-in-C2-overlap words only; baseline kept elsewhere; no identity verifier -> null speaker',
                  word_recall='NOT_SCORED: no independent reference word times',
                  parity='Actual production OfflineAsr/TokenWords/fusion/C2; host JNI build differs from signed APK; QuietCuts refines each waveform independently; extra word decode excluded from app timing',
                  a3=pins,host_jar=sha(h/'overlap-host.jar'),manifest_sha256=sha(LOCAL/'dev/manifest.json'))
    write_json(out/'protocol.json',protocol)
    cp=os.pathsep.join(str(h/p) for p in ['overlap-host.jar','kotlin/kotlin-stdlib.jar','classes.jar','placeholder.jar','onnxruntime-1.17.1.jar'])
    jvm=[str(args.java),'-Djava.io.tmpdir='+str(tmp),'-Djava.library.path='+str(h/'native'),'-Xmx3g','-XX:ErrorFile='+str(out/'hs_err_%p.log'),'-cp',cp,'ru.neurostenographer.tools.OverlapHostKt']
    runs=[]
    def java(mode,model,wav,turns_path,tr=None):
        meta=Path(str(tr or turns_path)+'.meta.json'); outputs=[turns_path,meta] if tr is None else [tr,Path(str(tr)+'.words.json'),meta]
        for p in outputs:p.unlink(missing_ok=True)
        command=jvm+[mode,str(model),str(wav),str(turns_path)]+([str(tr)] if tr else [])+[str(meta)]
        t=time.perf_counter();r=subprocess.run(command,capture_output=True,timeout=900)
        log=out/(str(len(runs))+'.jvm.log');log.write_bytes(r.stdout+r.stderr)
        record=dict(mode=mode,input_sha256=sha(wav),returncode=r.returncode,wall_s=time.perf_counter()-t,log=log.name,
                    outputs={p.name:sha(p) for p in outputs if p.exists()})
        runs.append(record);write_json(out/'runs.json',runs)
        if r.returncode or not all(p.exists() for p in outputs):raise RuntimeError('JVM failure; see '+str(log))
        record['inference']=json.loads(meta.read_text());write_json(out/'runs.json',runs)
        return json.loads(tr.read_text(encoding='utf-8')) if tr else read_turns(turns_path)
    # Network-denied Python model path: all assets explicit, model runner cannot fetch.
    import socket, urllib.request
    def denied(*a,**k):raise RuntimeError('OFFLINE_TEST_NETWORK_DENIED')
    class NoNetwork(socket.socket):
        connect=denied; connect_ex=denied
    socket.socket=NoNetwork;socket.create_connection=denied;urllib.request.urlopen=denied
    spec=importlib.util.spec_from_file_location('audited_voxlock',LOCAL/'voxlock/core.py');vlcore=importlib.util.module_from_spec(spec);spec.loader.exec_module(vlcore)
    t=time.perf_counter();vl=vlcore.VoxLock(model_dir=LOCAL/'voxlock',precision='int8',threads=1);load_s=time.perf_counter()-t
    rows=[]
    for case in manifest['cases']:
        name=case['id'];wav=LOCAL/'dev'/(name+'.wav');reference=LOCAL/'dev'/(name+'.ref.json')
        if sha(wav)!=case['audio_sha256'] or sha(reference)!=case['reference_sha256']:raise ValueError('Fixture changed')
        ref=json.loads(reference.read_text(encoding='utf-8'));x=read_wav(wav)
        turns_path=out/(name+'.c2.tsv');turns=java('c2',args.c2,wav,turns_path)
        tr=out/(name+'.baseline.json');base=seal_hyp(java('asr',args.a3,wav,turns_path,tr),wav,turns)
        write_json(tr,base)
        base_words=json.loads(Path(str(tr)+'.words.json').read_text(encoding='utf-8'))['segments']
        # Check extra word decode agrees in normalized sequence with actual app output.
        from score_transcript import words
        app_tokens=[w for s in base['segments'] for w in words(s['text'])]
        word_tokens=[w for s in base_words for w in words(s['text'])]
        if app_tokens!=word_tokens:raise ValueError('Sidecar word decode differs from production text')
        spans=overlap_spans(turns);enroll=enrollments(x,turns,case['enrollment_anchor_ms'])
        if args.enrollment_mode=='provided-dev':
            # Separate experiment, never a relaxation of failed automatic enrollment.
            # Composition guarantees one source in these anchors; only cluster ID is inferred.
            provided=[]
            for left,right in case['enrollment_anchor_ms']:
                active={t['speaker_id'] for t in turns if t['start_ms']<right and t['end_ms']>left}
                a=left+250;sample=x[a*16:(a+3000)*16]
                if len(active)!=1 or None in active or a+3000>right or len(sample)!=48000:
                    provided.append(None)
                else:provided.append(dict(speaker_id=next(iter(active)),start_ms=a,end_ms=a+3000,pcm=sample,
                    source='PROVIDED_SYNTHETIC_SINGLE_SOURCE_ANCHOR_NOT_AUTOMATIC_C2_ENROLLMENT'))
            enroll=provided
        row=dict(case=name,audio_sha256=sha(wav),baseline=score(ref,base),c2_turns=turns,overlap_spans=spans,
                 enrollments=[{k:v for k,v in e.items() if k!='pcm'} if e else None for e in enroll],voxlock_load_s=load_s,controls={})
        write_json(out/(name+'.no-enrollment.json'),base)
        row['controls']['no_enrollment']=dict(status='FALLBACK',baseline_exact=True,hypothesis_sha256=sha(out/(name+'.no-enrollment.json')))
        if not all(enroll):
            row['candidate']=dict(status='NO_ENROLLMENT',baseline_unchanged=True);rows.append(row);write_json(out/'summary.json',dict(protocol=protocol,rows=rows));continue
        if enroll[0]['speaker_id']==enroll[1]['speaker_id']:raise ValueError('Duplicate enrollment identity')
        for i,e in enumerate(enroll):
            ep=out/(name+'.enroll-'+str(i)+'.wav');write_wav(ep,e['pcm']);row['enrollments'][i]['sha256']=sha(ep)
        target_words={};stems=[]
        for i,e in enumerate(enroll):
            t=time.perf_counter();cpu=time.process_time();y=vl.isolate(x,sample=e['pcm']);cpu=time.process_time()-cpu;elapsed=time.perf_counter()-t
            if len(y)!=len(x) or not np.isfinite(y).all():raise ValueError('Invalid extracted length/finiteness')
            p=out/(name+'.target-'+str(i)+'.wav');write_wav(p,y);stems.append(y)
            target_tr=out/(name+'.target-'+str(i)+'.json')
            target=seal_hyp(java('asr',args.a3,p,turns_path,target_tr),wav,turns)
            write_json(target_tr,target)
            target_words[e['speaker_id']]=json.loads(Path(str(target_tr)+'.words.json').read_text(encoding='utf-8'))['segments']
            row['controls']['target_'+str(i)]=dict(status='OK',speaker_id=e['speaker_id'],audio_sha256=sha(p),samples=len(y),
                peak=float(np.max(np.abs(y))),clipped_samples=int(np.sum(np.abs(y)>=1)),rms=float(np.sqrt(np.mean(y*y))),wall_s=elapsed,cpu_s=cpu,rtf=elapsed/(len(x)/16000),
                transcript=score(ref,target))
            # Target-only words evaluated against independently scripted source text.
            # Source anchor index maps only evaluation identity, never output speaker assignment.
            anchor_source=ref['text_segments'][i]['speaker_id']
            target_ref=dict(ref,text_segments=[s for s in ref['text_segments'] if s['speaker_id']==anchor_source])
            row['controls']['target_'+str(i)]['target_only']=score(target_ref,target)
            wrong_ref=dict(ref,text_segments=[s for s in ref['text_segments'] if s['speaker_id']!=anchor_source])
            row['controls']['target_'+str(i)]['wrong_requested_target_only']=score(wrong_ref,target)
            print(name,'target',i,'extracted+same-A3',flush=True)
        row['target_correlation']=float(np.corrcoef(stems)[0,1]);row['targets_duplicate_bytes']=np.array_equal(stems[0],stems[1])
        hybrid=dict(base,segments=build_hybrid(base_words,target_words,spans));write_json(out/(name+'.candidate.json'),hybrid)
        row['candidate']=score(ref,hybrid)
        # Explicit wrong-enrollment control: swap target samples, keeping requested identity.
        # Outputs equal the already-run opposite extraction by construction; no false claim of third voice.
        wrong={enroll[0]['speaker_id']:target_words[enroll[1]['speaker_id']],enroll[1]['speaker_id']:target_words[enroll[0]['speaker_id']]}
        wrong_h=dict(base,segments=build_hybrid(base_words,wrong,spans));write_json(out/(name+'.wrong-enrollment.json'),wrong_h)
        row['controls']['wrong_enrollment']=dict(status='EXECUTED_OPPOSITE_SPEAKER_ENROLLMENT',identity_verifier='UNAVAILABLE',score=score(ref,wrong_h),
            limitation='Same two model executions reused with requested identity swapped; known different person, not a third unseen voice. Conservative null assignment intentionally makes aggregate scores identical.')
        # Clean/no-overlap negative: same whole-clip extraction is measured above, but overlap-only splicing must preserve baseline.
        row['controls']['clean_policy']=dict(baseline_unchanged=(hybrid['segments']==base_words) if not spans else None,
                                             c2_false_overlaps_possible=True)
        silent=vl.isolate(np.zeros(16000,np.float32),sample=enroll[0]['pcm'])
        row['controls']['silence']=dict(samples=len(silent),peak=float(np.max(np.abs(silent))),rms=float(np.sqrt(np.mean(silent*silent))))
        write_wav(out/(name+'.silence.wav'),silent)
        # Final accepted research path requires calibrated identity verification, absent here.
        write_json(out/(name+'.accepted.json'),base)
        row['accepted']=dict(status='FALLBACK_IDENTITY_UNVERIFIED',baseline_exact=True)
        rows.append(row);write_json(out/'summary.json',dict(protocol=protocol,rows=rows,runs=runs,network='Python socket connects disabled during inference; JVM uses local files'))
    print('COMPLETED',out/'summary.json',flush=True)

if __name__=='__main__':main()
