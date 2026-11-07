"""Score only hash-bound task output; repeat metrics are standalone probes, not APK acceptance."""
import argparse
import json
from pathlib import Path
import re
import statistics
from common import LOCAL,sha,write_json
from metrics import score
from run_host import read_turns,build_hybrid

def stats(values):
    return dict(min=min(values),median=statistics.median(values),max=max(values),n=len(values)) if values else None

def summarize(folder):
    state=json.loads((folder/'state.json').read_text());inputs=json.loads((folder/'inputs.json').read_text())
    ref=json.loads((LOCAL/'dev/two-person-overlap.ref.json').read_text(encoding='utf-8'))
    if inputs['mix.wav']['sha256']!=ref['audio_sha256']:raise ValueError('Physical input/reference mismatch')
    runs={r['key']:r for r in state['runs']}
    for r in runs.values():
        for name,digest in r.get('output_sha256',{}).items():
            if sha(folder/name)!=digest:raise ValueError('Stored phone artifact changed:'+name)
    rows=[]
    for i in range(10):
        keys=['r'+str(i)+suffix for suffix in ('-c2','-baseline','-target0','-target0-asr','-target1','-target1-asr')]
        if not any(k in runs for k in keys):continue
        rr=[runs[k] for k in keys if k in runs]
        row=dict(attempt=i,status='COMPLETE' if len(rr)==6 and all(r['status']=='OK' for r in rr) else 'INCOMPLETE')
        if row['status']=='COMPLETE':
            turns=read_turns(folder/('r'+str(i)+'.tsv'))
            def hyp(name):
                h=json.loads((folder/name).read_text(encoding='utf-8'));h.update(audio_sha256=ref['audio_sha256'],diarization=turns);return h
            row['baseline']=score(ref,hyp('r'+str(i)+'-baseline.json'))
            row['targets']=[]
            for target in range(2):
                h=hyp('r'+str(i)+'-target'+str(target)+'.json')
                source_id=ref['text_segments'][target]['speaker_id']
                target_ref=dict(ref,text_segments=[s for s in ref['text_segments'] if s['speaker_id']==source_id])
                row['targets'].append(dict(target=target,score_against_whole_mixture=score(ref,h),target_only=score(target_ref,h),
                    stem_sha256=sha(folder/('r'+str(i)+'-target'+str(target)+'.wav'))))
            row['baseline_wall_rtf']=sum(r['wall_s'] for r in rr[:2])/(ref['audio_duration_ms']/1000)
            row['candidate_full_clip_probe_wall_rtf']=sum(r['wall_s'] for r in rr)/(ref['audio_duration_ms']/1000)
            row['baseline_sampled_peak_standalone_pss_kib']=max(r['sampled_peak_total_task_pss_kib'] or 0 for r in rr[:2])
            row['candidate_sampled_peak_standalone_pss_kib']=max(r['sampled_peak_total_task_pss_kib'] or 0 for r in rr)
            row['c2_turns_sha256']=sha(folder/('r'+str(i)+'.tsv'))
        rows.append(row)
    complete=[r for r in rows if r['status']=='COMPLETE']
    stage={}
    for suffix in ('c2','baseline','target0','target0-asr','target1','target1-asr'):
        selected=[r for k,r in runs.items() if re.fullmatch(r'r\d+-'+re.escape(suffix),k) and r['status']=='OK']
        stage[suffix]=dict(wall_s=stats([r['wall_s'] for r in selected]),
            sampled_standalone_pss_kib=stats([r['sampled_peak_total_task_pss_kib'] for r in selected if r['sampled_peak_total_task_pss_kib'] is not None]),
            process_cpu_ms=stats([r['inference']['process_cpu_ms'] for r in selected]),
            cpu_scope='After model load, inference only' if suffix in ('target0','target1') else 'Input read/native/model load/inference; excludes process startup',
            model_load_ms=stats([r['inference']['load_ms'] for r in selected]),
            inference_ms=stats([r['inference'].get('infer_ms',r['inference'].get('decode_ms')) for r in selected]))
    temperatures=[]
    for r in runs.values():
        m=re.search(r'temperature:\s*(\d+)',r.get('battery',''))
        if m:temperatures.append(int(m.group(1))/10)
    report=dict(scope='PHYSICAL_ARM64 Android10, task-only app_process, airplane mode; same exact A3/C2/ORT JNI bytes; fresh process per stage. Not contest APK/UI/Binder acceptance.',
        status=state['status'],complete_paired_repeats=len(complete),rows=rows,stage=stage,
        aggregate={k:stats([r[k] for r in complete]) for k in ('baseline_wall_rtf','candidate_full_clip_probe_wall_rtf','baseline_sampled_peak_standalone_pss_kib','candidate_sampled_peak_standalone_pss_kib')},
        battery_temperature_c=stats(temperatures),battery_energy='NOT_MEASURED: charging; temperature sensor only, not SoC thermal/power',
        raw_quality='Whole-stem ASR only until separate word-sidecar quality run; target-only insertion counts are proxies, not calibrated leakage',
        failures=[dict(key=r['key'],status=r['status']) for r in runs.values() if r['status'] not in ('OK','RUNNING')],
        pss_scope='One task process at a time; sum across concurrent app/worker processes NOT_MEASURED; sampled standalone pipeline-stage maximum, not true peak',
        production_gates=dict(apk='NOT_BUILT',binder_lifecycle='NOT_RUN',background='NOT_RUN',oom='NOT_RUN',pages16k='FAIL_EXISTING_ORT_JAVA_ALIGNMENT'))
    quality_keys=['quality-baseline','quality-target0','quality-target1']
    if all(runs.get(k,{}).get('status')=='OK' for k in quality_keys):
        from metrics import overlap_spans
        turns=read_turns(folder/'r0.tsv');spans=overlap_spans(turns)
        raw=[json.loads((folder/(k+'.json.words.json')).read_text(encoding='utf-8')) for k in quality_keys]
        from score_transcript import words
        for key,sidecar in zip(quality_keys,raw):
            app=json.loads((folder/(key+'.json')).read_text(encoding='utf-8'))
            if [w for s in app['segments'] for w in words(s['text'])] != [w for s in sidecar['segments'] for w in words(s['text'])]:
                raise ValueError('Physical sidecar does not match actual app-code text')
        base=dict(raw[0],audio_sha256=ref['audio_sha256'],diarization=turns)
        enroll=json.loads((LOCAL/'host-provided-v2/summary.json').read_text(encoding='utf-8'))['rows'][1]['enrollments']
        targets={e['speaker_id']:r['segments'] for e,r in zip(enroll,raw[1:])}
        candidate=dict(base,segments=build_hybrid(raw[0]['segments'],targets,spans))
        write_json(folder/'quality-candidate.json',candidate)
        report['quality']=dict(baseline=score(ref,base),candidate=score(ref,candidate),
            scope='Separate actual two-decode sidecar quality jobs, not used for performance RTF',
            accepted=dict(status='FALLBACK_IDENTITY_UNVERIFIED',baseline_exact=True))
    write_json(folder/'summary.json',report)
    print(json.dumps({k:report[k] for k in ('status','complete_paired_repeats','aggregate','battery_temperature_c')},indent=2))
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--folder',type=Path,default=LOCAL/'phone-runs');a=p.parse_args();summarize(a.folder)
