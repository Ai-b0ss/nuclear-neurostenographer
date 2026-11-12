"""Score REAL host Nemotron C2 predictions on frozen Russian RTTM benchmark.

Uses the existing product Kotlin C2 diarization code and pinned 1.17.1 ORT.
Reference timestamps/speaker labels are synthetic generator RTTM, NOT
human-validated meeting audio. This is DER only; cpWER is not possible.
"""
import argparse,hashlib,json,statistics,sys
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/"tools"))
from score_transcript import der


def digest(filename):
    h=hashlib.sha256()
    with Path(filename).open("rb") as f:
        for b in iter(lambda:f.read(1<<20),b""):h.update(b)
    return h.hexdigest()


def parse_rttm(p,clip):
    ref=[]
    for line in p.read_text(encoding="utf8").splitlines():
        if not line.strip():continue
        v=line.split()
        if len(v)!=10 or v[0]!="SPEAKER" or v[1]!=clip:
            raise ValueError("Invalid RTTM ground truth")
        start=round(float(v[3])*1000)
        end=round((float(v[3])+float(v[4]))*1000)
        if end>60001 or start<0 or end<=start:
            raise ValueError("Invalid RTTM bounds")
        ref.append({"start_ms":start,"end_ms":min(60000,end),"speaker_id":v[7]})
    if not ref:raise ValueError("Empty reference")
    return ref


def parse_hypothesis(p):
    out=[]
    for line in p.read_text(encoding="utf8").splitlines():
        if not line.strip():continue
        a,b,cluster=line.split("\t")
        start=max(0,min(60000,round(float(a)*1000)))
        end=max(0,min(60000,round(float(b)*1000)))
        if end>start:
            out.append({"start_ms":start,"end_ms":end,
                        "speaker_id":"h"+cluster if int(cluster)>=0 else None})
    return out


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data",type=Path,required=True)
    parser.add_argument("--predictions",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    a=parser.parse_args()
    manifest=json.loads((a.data/"local_manifest.json").read_text(encoding="utf8"))
    rows=manifest["records"][55:70]
    assert len(rows)==15 and all(x["n_speakers"]==2 for x in rows)
    inputs=a.predictions/"inputs.json"
    if not inputs.is_file():raise RuntimeError("Missing host Kotlin inference provenance")
    info=json.loads(inputs.read_text(encoding="utf8"))
    for row in rows:
        fid=row["file_id"]
        if digest(a.data/(fid+".rttm"))!=row["files"][".rttm"]["sha256"]:
            raise ValueError("RTTM reference SHA mismatch")
        source=a.data/"c2-wavs"/(fid+".wav")
        recorded=info.get("wavs",{}).get(source.name)
        if recorded!=digest(source):
            raise ValueError("Host C2 input audio fingerprint mismatch "+fid)
    outputs=[]
    for row in rows:
        fid=row["file_id"]
        p=a.predictions/(fid+".product.tsv")
        if not p.is_file():
            raise RuntimeError("Missing actual C2 inference output "+str(p))
        ref=parse_rttm(a.data/(fid+".rttm"),fid)
        hyp=parse_hypothesis(p)
        d0=der(ref,hyp,60000,0,False)
        d250=der(ref,hyp,60000,250,False)
        d250skip=der(ref,hyp,60000,250,True)
        assert all(x["status"]=="SCORED" for x in (d0,d250,d250skip))
        outputs.append({"recording":fid,
                        "reference_speakers":len({x["speaker_id"] for x in ref}),
                        "c2_speakers":len({x["speaker_id"] for x in hyp if x["speaker_id"]}),
                        "reference_turns":len(ref),"hypothesis_turns":len(hyp),
                        "reference_sha256":row["files"][".rttm"]["sha256"],
                        "hypothesis_sha256":digest(p),
                        "der_no_collar":d0["rate"],
                        "der_250ms_including_overlap":d250["rate"],
                        "der_250ms_excluding_overlap":d250skip["rate"],
                        "reference_speaker_ms_250":d250["reference_speaker_ms"],
                        "miss_ms_250":d250["miss_ms"],
                        "false_alarm_ms_250":d250["false_alarm_ms"],
                        "confusion_ms_250":d250["confusion_ms"]})
        print("SCORED",fid,
              "DER0",round(d0["rate"],4),
              "DER250",round(d250["rate"],4),
              "PRED_SPEAKERS",outputs[-1]["c2_speakers"],flush=True)
    total_ref=sum(x["reference_speaker_ms_250"] for x in outputs)
    total_err=sum(x["miss_ms_250"]+x["false_alarm_ms_250"]+x["confusion_ms_250"] for x in outputs)
    summary={
        "schema":"russian-bookmix-host-c2-der-v1",
        "date":"2026-11-12",
        "source":manifest["source"],
        "license":"CC-BY-4.0",
        "reference_type":"generator RTTM, NOT manually reviewed",
        "synthetic_audio":True,
        "source_manifest_sha256":manifest["source_manifest_sha256"],
        "model_pins":info.get("model_pins"),
        "runtime":"Host JVM, Kotlin Nemotron C2, ONNX Runtime 1.17.1, pinned IR9 INT8 model",
        "recordings":len(rows),
        "audio_minutes":len(rows),
        "true_speakers_per_recording":2,
        "pooled_der_250ms_including_overlap":total_err/total_ref,
        "pooled_miss_250ms":sum(x["miss_ms_250"] for x in outputs)/total_ref,
        "pooled_false_alarm_250ms":sum(x["false_alarm_ms_250"] for x in outputs)/total_ref,
        "pooled_confusion_250ms":sum(x["confusion_ms_250"] for x in outputs)/total_ref,
        "mean_der_250ms_including_overlap":statistics.mean(x["der_250ms_including_overlap"] for x in outputs),
        "median_der_250ms_including_overlap":statistics.median(x["der_250ms_including_overlap"] for x in outputs),
        "max_der_250ms_including_overlap":max(x["der_250ms_including_overlap"] for x in outputs),
        "mean_der_no_collar":statistics.mean(x["der_no_collar"] for x in outputs),
        "mean_der_250ms_excluding_overlap":statistics.mean(x["der_250ms_excluding_overlap"] for x in outputs),
        "c2_correct_speaker_count_files":sum(x["c2_speakers"]==2 for x in outputs),
        "c2_wrong_speaker_count_files":sum(x["c2_speakers"]!=2 for x in outputs),
        "rows":outputs,
        "cpwer":{"status":"NOT_SCORED","reason":"No reference transcript or output transcript for these 15 synthetic mixtures"},
        "caveats":[
            "Russian synthetic 60-second two-speaker audiobook mixes, not natural real meetings or phone recordings",
            "RTTM generated with mixing software, not manually checked by human annotators",
            "This is C2 local diarization DER on a host computer, not Android global speaker linking accuracy",
            "Per-file speaker permutation is optimal Hungarian assignment, according to tools/score_transcript.py",
            "Source audiobook readers may have been used for model training; independence from model pretraining unverified",
            "15 consecutive examples by fixed file ID, not randomly chosen based on model performance"]
    }
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(summary,indent=2,ensure_ascii=False)+"\n",encoding="utf8")
    print("FINAL_DER",json.dumps({k:v for k,v in summary.items() if k not in ("rows","model_pins","caveats")},ensure_ascii=False),flush=True)


if __name__=="__main__":main()
