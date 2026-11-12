"""Compare pinned192D embedders under the unchanged product identity gates.
No tuning: this measures drop-in suitability, not each model's optimal threshold.
"""
import argparse,hashlib,json,sys,time,urllib.request,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from evaluate_russian_bookmix_voice_link import normalized,separate,ground_truth_owners,sha256,calculate_pairs,global_book_simulation
from evaluate_russian_bookmix_c2_link import build_owners
from score_russian_bookmix_c2 import parse_hypothesis,parse_rttm
from score_transcript import der
REV="0743f301363dec56491a490f6d6cbc9d67f9a3bf"
MODELS={
 "TitaNetSmall":("nemo_en_titanet_small.onnx","ad4a1802485d8b34c722d2a9d04249662f2ece5d28a7a039063ca22f515a789e",40257283),
 "TitaNetLarge":("nemo_en_titanet_large.onnx","d51abcf31717ef28162f26acb9d44dd4127c3d44c9b8624f699f3425daca8e77",101405493),
 "CAMppAdvanced":("3dspeaker_speech_campplus_sv_zh_en_16k-common_advanced.onnx","aa3cfc16963a10586a9393f5035d6d6b57e98d358b347f80c2a30bf4f00ceba2",28281164)}
def save(path,data):
    tmp=path.with_suffix(".tmp");tmp.write_text(json.dumps(data,indent=2)+"\n","utf8");tmp.replace(path)
def acquire(directory):
    directory.mkdir(parents=True,exist_ok=True)
    for name,(filename,wanted,size) in MODELS.items():
        path=directory/filename
        if not path.exists():
            if shutil.disk_usage(directory).free<500*1024*1024:raise ValueError("Insufficient disk headroom")
            tmp=path.with_suffix(".download")
            url=f"https://huggingface.co/csukuangfj/speaker-embedding-models/resolve/{REV}/{filename}"
            print("DOWNLOAD",name,flush=True);start=time.monotonic();total=0
            with urllib.request.urlopen(url,timeout=30) as response,tmp.open("wb") as f:
                while True:
                    part=response.read(1024*1024)
                    if not part:break
                    total+=len(part)
                    if total>size or time.monotonic()-start>180:raise ValueError("Download bounds exceeded")
                    f.write(part)
            if tmp.stat().st_size!=size or sha256(tmp)!=wanted:raise ValueError("Downloaded model mismatch")
            tmp.replace(path)
        if path.stat().st_size!=size or sha256(path)!=wanted:raise ValueError("Wrong cached model")
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--site",type=Path,required=True)
    ap.add_argument("--models",type=Path,default=ROOT/".local/speakerbook-active/scratch/models")
    ap.add_argument("--dialogs",type=Path,default=ROOT/".local/dialogs-speaker-current")
    ap.add_argument("--oracle20",type=Path,default=ROOT/".local/qa-three-checks-current/russian_rttm")
    ap.add_argument("--bookmix",type=Path,default=ROOT/".local/speakerbook-active/scratch/ru_book_mix_eval")
    ap.add_argument("--c2",type=Path,default=ROOT/".local/speakerbook-offdevice-current/host/predictions")
    ap.add_argument("--output",type=Path,default=ROOT/".local/speaker-model-compare-current")
    ap.add_argument("--dual-anchor-experiment",action="store_true")
    a=ap.parse_args()
    if not a.output.resolve().is_relative_to((ROOT/".local").resolve()):ap.error("Output must be under .local")
    a.output.mkdir(parents=True,exist_ok=True)
    result={"schema":"speaker-model-drop-in-comparison-v1","status":"RUNNING","models":{},
            "policy":{"agreement":.84,"matching":.84,"margin":.07,"max_sample_s":16,"min_sample_s":3},
            "input_pins":{}}
    save(a.output/"result.json",result)
    if not a.dual_anchor_experiment:acquire(a.models)
    sys.path.insert(0,str(a.site.resolve()))
    import numpy as np,soundfile as sf,sherpa_onnx
    result["runtime"]=sherpa_onnx.__version__
    data={}
    plan=json.loads((a.dialogs/"plan.json").read_text("utf8"))
    result["input_pins"]["dialogs_plan"]=sha256(a.dialogs/"plan.json")
    groups=[]
    for g in sorted(plan["groups"],key=lambda g:(g["emotion"]!="neutral",g["emotion"],g["speaker"])):
        waves=[]
        for c in g["clips"]:
            path=a.dialogs/(Path(c["path"]).stem+".wav")
            if sha256(path)!=plan["sources"][c["path"]]["converted_sha256"]:raise ValueError("Dialogs audio mismatch")
            w,sr=sf.read(path,dtype="float32");assert sr==16000;waves.append(w)
        pcm=(np.concatenate(waves) if waves else np.empty(0,dtype="float32"))[:32*16000];mid=len(pcm)//2
        parts=None if mid<48000 else (pcm[:min(mid,256000)],pcm[max(mid,len(pcm)-256000):])
        groups.append((g["emotion"],g["speaker"],g["speaker"],parts))
    data["Dialogs35"]=groups
    manifest=json.loads((a.oracle20/"benchmark_manifest.json").read_text("utf8"))
    result["input_pins"]["oracle20_manifest"]=sha256(a.oracle20/"benchmark_manifest.json")
    groups=[]
    for r in sorted(manifest["files"],key=lambda x:x["file_id"]):
        stem=r["file_id"];path=a.oracle20/(stem+".flac")
        if sha256(path)!=r["audio_sha256"] or sha256(a.oracle20/(stem+".rttm"))!=r["rttm_sha256"]:raise ValueError("Oracle input mismatch")
        w,sr=sf.read(path,dtype="float32");assert sr==16000
        names,owners=ground_truth_owners((a.oracle20/(stem+".rttm")).read_text("utf8"),r["speakers"])
        frames=w.reshape(1500,640)
        for who,label in enumerate(names):
            parts=separate(owners,who,max_frames=400)
            groups.append((stem,label,r["speakers"][label],None if parts is None else tuple(frames[x].ravel() for x in parts)))
    data["BookmixOracle60"]=groups
    manifest=json.loads((a.bookmix/"local_manifest.json").read_text("utf8"));groups=[]
    result["input_pins"]["bookmix_manifest"]=sha256(a.bookmix/"local_manifest.json")
    result["input_pins"]["c2_inputs"]=sha256(a.c2/"inputs.json")
    result["input_pins"]["c2_tsv"]={}
    inputs=json.loads((a.c2/"inputs.json").read_text("utf8"))
    for r in manifest["records"][55:70]:
        stem=r["file_id"];wav=a.bookmix/"c2-wavs"/(stem+".wav");tsv=a.c2/(stem+".product.tsv")
        if sha256(wav)!=inputs["wavs"][wav.name]:raise ValueError("C2 WAV mismatch")
        result["input_pins"]["c2_tsv"][stem]=sha256(tsv)
        hyp=parse_hypothesis(tsv);ref=parse_rttm(a.bookmix/(stem+".rttm"),stem)
        mapping=der(ref,hyp,60000,0,False)["hypothesis_to_reference"]
        names,owners=build_owners(hyp);w,sr=sf.read(wav,dtype="float32");assert sr==16000;frames=w.reshape(1500,640)
        for who,label in enumerate(names):
            parts=separate(owners,who,max_frames=400)
            truth=r["source_voice_labels"].get(mapping.get(label),"unmapped/"+stem+"/"+label)
            groups.append((stem,label,truth,None if parts is None else tuple(frames[x].ravel() for x in parts)))
    data["ActualC2_30"]=groups
    # Freeze test input counts and model list before inference; no model-based selection.
    result["group_counts"]={k:len(v) for k,v in data.items()};save(a.output/"result.json",result)
    parity_lines=[];expected_lines=[]
    selected={"TitaNetSmall":MODELS["TitaNetSmall"]} if a.dual_anchor_experiment else MODELS
    for name,(filename,wanted,size) in selected.items():
        if sha256(a.models/filename)!=wanted:raise ValueError("Wrong model")
        start=time.monotonic()
        extractor=sherpa_onnx.SpeakerEmbeddingExtractor(sherpa_onnx.SpeakerEmbeddingExtractorConfig(
            model=str(a.models/filename),num_threads=2,provider="cpu",debug=False))
        if extractor.dim!=192:raise ValueError("Not a compatible192D embedder")
        load=time.monotonic()-start
        def embed(pcm):
            stream=extractor.create_stream();stream.accept_waveform(16000,np.ascontiguousarray(pcm,dtype=np.float32));stream.input_finished()
            if not extractor.is_ready(stream):raise ValueError("Model not ready")
            return normalized(extractor.compute(stream),np)
        control=next(v[3] for v in data["Dialogs35"] if v[3] is not None)[0]
        embed(control) # one untimed warmup, then identical three measured calls
        control_times=[]
        for _ in range(3):
            began=time.perf_counter();v=embed(control);control_times.append(1000*(time.perf_counter()-began))
            assert abs(float(np.dot(v,v))-1)<1e-6
        out={"sha256":wanted,"bytes":size,"dimension":192,"load_seconds":load,
             "control_sample_s":len(control)/16000,"control_wall_ms":control_times,
             "control_median_ms":float(np.median(control_times)),"datasets":{}}
        for dataset,groups in data.items():
            clips=[];scores=[];began=time.perf_counter()
            for clip_id,local,truth,parts in groups:
                if not clips or clips[-1]["id"]!=clip_id:clips.append({"id":clip_id,"profiles":[]})
                item={"local":local,"truth":truth}
                if parts is None:item["valid"]="INSUFFICIENT_CLEAN_SPEECH"
                else:
                    early,late=[embed(x) for x in parts];score=float(np.dot(early,late))
                    item["early"]=early;item["late"]=late;item["early_ms"]=len(parts[0])*1000//16000;item["late_ms"]=len(parts[1])*1000//16000
                    scores.append(score);item["valid"]="PASS" if score>=.84 else "AGREEMENT_REJECT";item["v"]=normalized(early+late,np)
                clips[-1]["profiles"].append(item)
            elapsed=time.perf_counter()-began
            accepted=[p for c in clips for p in c["profiles"] if p["valid"]=="PASS"]
            all_vectors=[p for c in clips for p in c["profiles"] if "v" in p]
            book,_=global_book_simulation(clips,np)
            out["datasets"][dataset]={"wall_seconds":round(elapsed,3),"global_book":book,
                "accepted_pairs":calculate_pairs(accepted,np),"all_available_pairs":calculate_pairs(all_vectors,np),
                "agreement_scores":scores}
            if a.dual_anchor_experiment:
                from dual_anchor_policy import simulate
                out["datasets"][dataset]["dual_anchor"],events=simulate(clips,np)
                for clip in clips:
                    parity_lines.append("B\t"+dataset+"\t"+clip["id"])
                    for item in clip["profiles"]:
                        if "early" not in item:continue
                        parity_lines.append("\t".join(["P",item["local"],str(item["early_ms"]),str(item["late_ms"]),
                            ",".join(map(str,item["v"])),",".join(map(str,item["early"])),",".join(map(str,item["late"]))]))
                    parity_lines.append("E")
                expected_lines.extend("\t".join([dataset,e["clip"],e["local"],e["id"]]) for e in events if e["id"] is not None)
                first_by_truth={};anchors={}
                for clip in clips:
                    for item in clip["profiles"]:
                        if "early" in item:first_by_truth.setdefault(item["truth"],item)
                        if item["valid"]=="PASS":anchors.setdefault(item["truth"],item)
                seed=[{"id":"seed"+str(i),"profiles":[item]} for i,item in enumerate(anchors.values())]
                switched=0;rescued=0;already_consistent=0
                known_switches=0
                for truth_a,item_a in first_by_truth.items():
                    for truth_b,item_b in first_by_truth.items():
                        if truth_a==truth_b:continue
                        early=item_a["early"];late=item_b["late"]
                        agreement=float(np.dot(early,late))
                        if agreement>=.84:already_consistent+=1;continue
                        switched+=1
                        known_switches+=int(truth_a in anchors and truth_b in anchors)
                        mixed={"local":"changed","truth":"MIXED","valid":"AGREEMENT_REJECT",
                               "early":early,"late":late,"v":normalized(early+late,np)}
                        _,events=simulate(seed+[{"id":"switch","profiles":[mixed]}],np)
                        if events[-1]["id"] is not None:rescued+=1
                out["datasets"][dataset]["speaker_switch_controls"]={
                    "inconsistent_ordered_pairs":switched,"both_sources_enrolled":known_switches,
                    "wrongly_rescued":rescued,"pairs_already_consistent_under_baseline":already_consistent}
            print("SCORED",name,dataset,"admitted",book["profiles_consistent"],"returning",book["correct_returning_links"],flush=True)
        result["models"][name]=out;save(a.output/"result.json",result)
        del extractor
    if a.dual_anchor_experiment:
        (a.output/"private-replay.tsv").write_text("\n".join(parity_lines)+"\n","utf8")
        (a.output/"expected-links.tsv").write_text("\n".join(expected_lines)+"\n","utf8")
    result["status"]="COMPLETED";result["script_sha256"]=sha256(Path(__file__))
    result["limits"]=["Fixed production gates measure drop-in suitability, not independently calibrated model optima.",
      "These sets and some source actors were used previously; not untouched heldout evidence or training.",
      "Dialogs is three acted studio voices; bookmix is synthetic audiobook mixtures; ActualC2 subset may overlap Oracle20.",
      "No new Android or HONOR test; model training overlap not excluded. Runtime is host sherpa1.12.40.",
      "Timing is indicative Windows CPU2-thread evidence after warmup, not a randomized hardware benchmark.",
      "No raw audio, embeddings or transcript text exported. OpenRAIL applies to Dialogs-derived metrics."]
    save(a.output/"result.json",result);print("COMPLETED",flush=True)
if __name__=="__main__":main()
