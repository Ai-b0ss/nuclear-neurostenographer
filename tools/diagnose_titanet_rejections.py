"""Diagnose TitaNet rejection without changing product policy or exporting embeddings.
Oracle audiobook annotations only; comparisons are exploratory, not release evidence.
"""
import argparse, json, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from evaluate_russian_bookmix_voice_link import (
    ground_truth_owners,separate,normalized,sha256,SHA_TITANET,calculate_pairs,global_book_simulation)
def contiguous(owners,who):
    active=[i for i,v in enumerate(owners) if v==who]
    if len(active)<150:return None
    midpoint=active[len(active)//2]
    halves=([i for i in active if i<midpoint],[i for i in active if i>=midpoint])
    result=[]
    for half in halves:
        runs=[]
        for i in half:
            if not runs or i!=runs[-1][-1]+1:runs.append([])
            runs[-1].append(i)
        longest=max(runs,key=len,default=[])
        if len(longest)<75:return None
        result.append(longest[:200])
    return result
def longer(owners,who):
    active=[i for i,v in enumerate(owners) if v==who]
    if len(active)<150:return None
    middle=len(active)//2
    return active[:middle][:400],active[middle:][-400:]
def trimmed(owners,who):
    clean=[v if i>=2 and i+2<len(owners) and all(x==who for x in owners[i-2:i+3]) else -1
           for i,v in enumerate(owners)]
    return separate(clean,who)
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for n in ("data","model","site","output"):ap.add_argument("--"+n,type=Path,required=True)
    ap.add_argument("--c2-predictions",type=Path)
    ap.add_argument("--exclude-manifest",type=Path)
    ap.add_argument("--methods",default="current,contiguous,trim80ms,long16s")
    a=ap.parse_args()
    if not a.output.resolve().is_relative_to((ROOT/".local").resolve()):
        ap.error("Output must stay in ignored .local")
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps({"status":"RUNNING"})+"\n","utf8")
    sys.path.insert(0,str(a.site.resolve()))
    import numpy as np, soundfile as sf, sherpa_onnx
    if sha256(a.model)!=SHA_TITANET:raise ValueError("Wrong model")
    manifest_path=a.data/"benchmark_manifest.json"
    if not manifest_path.exists():manifest_path=a.data/"local_manifest.json"
    manifest=json.loads(manifest_path.read_text("utf8"))
    files=manifest.get("files")
    if files is None:
        files=[{"file_id":r["file_id"],"speakers":r["source_voice_labels"],"audio_sha256":r["files"][".flac"]["sha256"],"rttm_sha256":r["files"][".rttm"]["sha256"]} for r in manifest["records"]]
    excluded=set()
    if a.exclude_manifest:
        excluded={r["file_id"] for r in json.loads(a.exclude_manifest.read_text("utf8"))["files"]}
    files=[r for r in files if r["file_id"] not in excluded]
    if a.c2_predictions:files=[r for r in files if 55<=int(r["file_id"].split("_")[1])<70]
    if not files:raise ValueError("Empty evaluation")
    encoder=sherpa_onnx.SpeakerEmbeddingExtractor(sherpa_onnx.SpeakerEmbeddingExtractorConfig(
        model=str(a.model),num_threads=2,provider="cpu",debug=False))
    def embed(pcm):
        st=encoder.create_stream()
        st.accept_waveform(16000,np.ascontiguousarray(pcm,dtype=np.float32))
        st.input_finished()
        if not encoder.is_ready(st):raise ValueError("Model not ready")
        return normalized(encoder.compute(st),np)
    methods={"current":separate,"contiguous":contiguous,"trim80ms":trimmed,"long16s":longer}
    methods={k:methods[k] for k in a.methods.split(",")}
    books={k:[] for k in methods}
    rows=[]; pools={k:[] for k in methods}; start=time.monotonic()
    for rec in sorted(files,key=lambda r:r["file_id"]):
        stem=rec["file_id"]
        if sha256(a.data/(stem+".rttm"))!=rec["rttm_sha256"]:raise ValueError("Reference hash mismatch")
        if sha256(a.data/(stem+".flac"))!=rec["audio_sha256"]:raise ValueError("Audio hash mismatch")
        audio,rate=sf.read(a.data/(stem+".flac"),dtype="float32")
        wav_path=a.data/(stem+".wav")
        wav,wr=sf.read(wav_path,dtype="float32") if wav_path.exists() else (audio,rate)
        if rate!=16000 or wr!=rate or audio.ndim!=1 or len(audio)!=960000:raise ValueError("Bad audio")
        names,owners=ground_truth_owners((a.data/(stem+".rttm")).read_text("utf8"),rec["speakers"])
        if a.c2_predictions:
            from evaluate_russian_bookmix_c2_link import build_owners
            from score_russian_bookmix_c2 import parse_hypothesis,parse_rttm
            from score_transcript import der
            hyp=parse_hypothesis(a.c2_predictions/(stem+".product.tsv"))
            inputs=json.loads((a.c2_predictions/"inputs.json").read_text("utf8"))
            if sha256(a.data/"c2-wavs"/(stem+".wav"))!=inputs["wavs"][stem+".wav"]:raise ValueError("C2 waveform pin mismatch")
            mapping=der(parse_rttm(a.data/(stem+".rttm"),stem),hyp,60000,0,False)["hypothesis_to_reference"]
            names,owners=build_owners(hyp)
            truths={name:rec["speakers"].get(mapping.get(name),"unmapped/"+stem+"/"+name) for name in names}
        else:truths=rec["speakers"]
        frames=audio.reshape(1500,640)
        for k in books:books[k].append({"id":stem,"profiles":[]})
        for who,label in enumerate(names):
            row={"recording":stem,"speaker_slot":who,"wav_flac_max_abs_difference":float(np.max(np.abs(audio-wav))) if wav_path.exists() else None,"methods":{}}
            for name,method in methods.items():
                parts=method(owners,who)
                if parts is None:
                    row["methods"][name]={"status":"INSUFFICIENT"}
                    books[name][-1]["profiles"].append({"local":label,"truth":truths[label],"valid":"INSUFFICIENT_CLEAN_SPEECH"})
                    continue
                first,second=[embed(frames[part].ravel()) for part in parts]
                score=float(np.dot(first,second))
                details={"status":"PASS" if score>=.84 else "AGREEMENT_REJECT","cosine":score,
                    "seconds":[len(v)*.04 for v in parts],
                    "joins":[sum(b!=aa+1 for aa,b in zip(v,v[1:])) for v in parts]}
                row["methods"][name]=details
                books[name][-1]["profiles"].append({"local":label,"truth":truths[label],"valid":details["status"],"v":normalized(first+second,np)})
                pools[name].append({"truth":truths[label],"v":normalized(first+second,np),"accepted":score>=.84})
            rows.append(row)
        print("PROFILED",stem,len(rows),flush=True)
    summary={}
    for name,pool in pools.items():
        scores=[r["methods"][name]["cosine"] for r in rows if "cosine" in r["methods"][name]]
        accepted=[p for p in pool if p["accepted"]]
        summary[name]={"total":len(rows),"accepted":len(accepted),"agreement_rejected":len(pool)-len(accepted),
            "insufficient":len(rows)-len(pool),"cosine_min":min(scores),"cosine_median":float(np.median(scores)),
            "cosine_max":max(scores),"accepted_pairs":calculate_pairs(accepted,np),
            "all_available_pairs":calculate_pairs(pool,np),"global_book":global_book_simulation(books[name],np)[0]}
    result={"schema":"titanet-rejection-diagnosis-v1","status":"COMPLETED",
        "model_sha256":sha256(a.model),"manifest_sha256":sha256(manifest_path),
        "turn_source":"C2 predicted" if a.c2_predictions else "oracle RTTM","excluded_ids":sorted(excluded),"script_sha256":sha256(Path(__file__)),"runtime":sherpa_onnx.__version__,"summary":summary,"rows":rows,
        "wall_seconds":round(time.monotonic()-start,3),
        "limits":["Exploratory comparison on already evaluated oracle synthetic audiobook data.",
        "No product or threshold change. No natural conversation or Android parity claim.",
        "Follow-up files exclude initial 20 by recording ID, but may share speakers and predate this experiment.",
        "C2 predicted mode reuses cached product outputs; it is host replay, not Android execution.",
        "Pairs are correlated; zero false accepts cannot establish population safety.",
        "Contiguous and trimmed methods may discard different speakers; compare availability too."]}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2)+"\n","utf8")
    print("SUMMARY",json.dumps(summary),flush=True)
if __name__=="__main__":main()
