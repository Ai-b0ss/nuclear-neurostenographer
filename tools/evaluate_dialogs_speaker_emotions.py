"""Frozen actor/emotion voice-link diagnostic. Not spontaneous-conversation or C2 accuracy."""
import argparse,collections,csv,hashlib,io,json,math,sys,time,urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from evaluate_russian_bookmix_voice_link import normalized,SHA_TITANET,sha256,calculate_pairs,global_book_simulation
REV="a74ff44d8d27ca3d21098ea3ed4d31a32923fbdd"
CSV_SHA="824091e87e879fdf8c7b8201e3f49be842203f411fba745afd95e320e4e4b5f2"
LICENSE_SHA="e136a6af001dd43a9002f20f39dd56d200afa9a6d408e28a625d90c9a0c22143"
REPO="langswap/dialogs-ru-emotional-conversations"
def save(path,value):
    tmp=path.with_suffix(".tmp")
    tmp.write_text(json.dumps(value,indent=2)+"\n","utf8");tmp.replace(path)
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source",type=Path,required=True)
    ap.add_argument("--site",type=Path,required=True)
    ap.add_argument("--model",type=Path)
    ap.add_argument("--output",type=Path,default=ROOT/".local/dialogs-speaker-current")
    ap.add_argument("--prepare",action="store_true")
    a=ap.parse_args()
    if not a.output.resolve().is_relative_to((ROOT/".local").resolve()):ap.error("Output must stay under .local")
    a.output.mkdir(parents=True,exist_ok=True)
    sys.path.insert(0,str(a.site.resolve()))
    import numpy as np,soundfile as sf
    from scipy.signal import resample_poly
    if a.prepare:
        if (a.output/"plan.json").exists():raise ValueError("Frozen plan already exists")
        if sha256(a.source/"test.csv")!=CSV_SHA or sha256(a.source/"LICENSE.md")!=LICENSE_SHA:
            raise ValueError("Unrecognized source metadata/license")
        # Fixed in CSV order, exclude every existing locally used utterance.
        excluded={f.name for f in a.source.glob("*.wav")}
        groups=collections.defaultdict(list); seconds=collections.defaultdict(float)
        for r in csv.DictReader((a.source/"test.csv").open(encoding="utf8"),delimiter="|"):
            key=(r["emotion"],r["speaker_id"])
            if Path(r["audio_path"]).name in excluded or seconds[key]>=32:continue
            if len(groups[key])>=8:continue
            groups[key].append({"path":r["audio_path"],"duration":float(r["duration"])})
            seconds[key]+=float(r["duration"])
        selected=[{"emotion":k[0],"speaker":k[1],"clips":v} for k,v in sorted(groups.items())]
        plan={"schema":"dialogs-speaker-frozen-plan-v1","repository":REPO,"revision":REV,
              "metadata_sha256":CSV_SHA,"license_sha256":LICENSE_SHA,"excluded_existing":sorted(excluded),
              "selection":"CSV order; up to8 utterances until32s per actor/emotion, then truncate to32s; no model-score selection",
              "groups":selected}
        save(a.output/"selection.json",plan) # freeze BEFORE downloads/inference
        paths=sorted({c["path"] for g in selected for c in g["clips"]})
        request=urllib.request.Request(f"https://huggingface.co/api/datasets/{REPO}/paths-info/{REV}",
            data=json.dumps({"paths":paths,"expand":False}).encode(),headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(request,timeout=30) as response:inventory=json.load(response)
        indexed={m["path"]:m for m in inventory}
        plan["missing_sources"]=sorted(set(paths)-set(indexed))
        plan["source_inventory"]=inventory
        paths=[path for path in paths if path in indexed]
        if sum(indexed[path]["size"] for path in paths)>200*1024*1024:raise ValueError("Download budget exceeded")
        for group in selected:group["clips"]=[c for c in group["clips"] if c["path"] in indexed]
        save(a.output/"selection-available.json",plan)
        def fetch(path):
            if not path.startswith("wavs/") or ".." in Path(path).parts:raise ValueError("Bad source path")
            url=f"https://huggingface.co/datasets/{REPO}/resolve/{REV}/{path}"
            with urllib.request.urlopen(url,timeout=45) as r:raw=r.read(12*1024*1024+1)
            expected=indexed[path]["lfs"]["oid"]
            if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError("Pinned source checksum mismatch")
            if len(raw)>12*1024*1024:raise ValueError("Clip exceeds memory/download cap")
            wave,rate=sf.read(io.BytesIO(raw),dtype="float32",always_2d=True)
            wave=wave.mean(axis=1)
            gcd=math.gcd(rate,16000)
            wave=resample_poly(wave,16000//gcd,rate//gcd).astype("float32")
            if not np.all(np.isfinite(wave)) or len(wave)>16000*60:raise ValueError("Bad source audio")
            dest=a.output/(Path(path).stem+".wav")
            sf.write(dest,wave,16000,subtype="PCM_16")
            return path,{"source_sha256":hashlib.sha256(raw).hexdigest(),"converted_sha256":sha256(dest),
                         "converted_frames":len(wave),"source_rate":rate,"source_bytes":len(raw)}
        sources={}
        with ThreadPoolExecutor(max_workers=4) as pool:
            for path,meta in pool.map(fetch,paths):
                sources[path]=meta
                if sum(x["source_bytes"] for x in sources.values())>200*1024*1024:raise ValueError("Download budget exceeded")
                print("FETCHED",len(sources),"/",len(paths),flush=True)
        plan["sources"]=sources;save(a.output/"plan.json",plan)
        print("PREPARED",len(selected),"groups",len(sources),"clips",flush=True);return
    result_path=a.output/"result.json";save(result_path,{"status":"RUNNING"})
    if not a.model or sha256(a.model)!=SHA_TITANET:raise ValueError("Wrong pinned model")
    import sherpa_onnx
    plan=json.loads((a.output/"plan.json").read_text("utf8"))
    if plan["revision"]!=REV or plan["metadata_sha256"]!=CSV_SHA:raise ValueError("Wrong frozen plan")
    encoder=sherpa_onnx.SpeakerEmbeddingExtractor(sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=str(a.model),num_threads=2,provider="cpu",debug=False))
    if encoder.dim!=192:raise ValueError("Unexpected embedding dimension")
    def embed(pcm):
        stream=encoder.create_stream();stream.accept_waveform(16000,np.ascontiguousarray(pcm,dtype=np.float32));stream.input_finished()
        if not encoder.is_ready(stream):raise ValueError("Model not ready")
        return normalized(encoder.compute(stream),np)
    methods={8:[],16:[]};scores=[];t0=time.monotonic()
    emotions=sorted({g["emotion"] for g in plan["groups"]},key=lambda x:(x!="neutral",x))
    for emotion in emotions:
        clips={b:{"id":emotion,"profiles":[]} for b in methods}
        for group in [g for g in plan["groups"] if g["emotion"]==emotion]:
            audio=[]
            for c in group["clips"]:
                path=a.output/(Path(c["path"]).stem+".wav")
                if sha256(path)!=plan["sources"][c["path"]]["converted_sha256"]:raise ValueError("Changed audio")
                w,rate=sf.read(path,dtype="float32")
                if rate!=16000:raise ValueError("Bad rate")
                audio.append(w)
            pcm=(np.concatenate(audio) if audio else np.empty(0,dtype="float32"))[:32*16000];mid=len(pcm)//2
            row={"emotion":emotion,"speaker_alias":group["speaker"],"available_seconds":len(pcm)/16000,"budgets":{}}
            for budget in methods:
                item={"local":group["speaker"],"truth":group["speaker"]}
                if mid<3*16000:item["valid"]="INSUFFICIENT_CLEAN_SPEECH"
                else:
                    first=embed(pcm[:min(mid,budget*16000)])
                    last=embed(pcm[max(mid,len(pcm)-budget*16000):])
                    cosine=float(np.dot(first,last))
                    item["valid"]="PASS" if cosine>=.84 else "AGREEMENT_REJECT"
                    item["v"]=normalized(first+last,np)
                    row["budgets"][str(budget)]={"agreement":cosine}
                row["budgets"].setdefault(str(budget),{})["status"]=item["valid"]
                clips[budget]["profiles"].append(item)
            scores.append(row)
        for budget in methods:methods[budget].append(clips[budget])
        print("SCORED",emotion,flush=True)
    summaries={}
    for budget,clips in methods.items():
        accepted=[p for c in clips for p in c["profiles"] if p["valid"]=="PASS"]
        book,_=global_book_simulation(clips,np)
        summaries[str(budget)]={"book":book,"accepted_pairs":calculate_pairs(accepted,np)}
    result={"schema":"dialogs-actor-emotion-speaker-qa-v1","status":"COMPLETED","runtime":sherpa_onnx.__version__,
            "model_sha256":sha256(a.model),"plan_sha256":sha256(a.output/"plan.json"),
            "script_sha256":sha256(Path(__file__)),"groups":len(scores),"source_clips":len(plan["sources"]),"unavailable_selected_clips":len(plan.get("missing_sources",[])),
            "unique_actor_aliases":len({g["speaker"] for g in plan["groups"]}),
            "summary":summaries,"scores":scores,"wall_seconds":round(time.monotonic()-t0,3),
            "limits":["Acted studio utterances regrouped by actor/emotion, not spontaneous dialogue or continuous meeting.",
            "Only three source actors; aliases are dataset labels, not real-person identification.",
            "Utterance labels assumed correct; pauses/possible contamination retained; not oracle clean-speech timing.",
            "No C2, ASR, DER, Android or thermal test. Host sherpa1.12.40 differs from Android1.12.20.",
            "Neutral first then alphabetic emotions; no threshold tuning. Results are correlated and not population safety.",
            "Source license OpenRAIL applies; no recordings, embeddings or transcript text exported."]}
    save(result_path,result);print("RESULT",json.dumps(summaries),flush=True)
if __name__=="__main__":main()
