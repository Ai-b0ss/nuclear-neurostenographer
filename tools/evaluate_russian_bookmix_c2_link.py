"""Host replay of actual Nemotron C2 turns -> TitaNet double-evidence -> GlobalSpeakerBook.

Unlike the oracle-turn test, this uses *predicted* C2 turns for extracting
voiceprints. Reference RTTM is used only AFTER extraction to identify the
real source voice for error scoring. Not a mobile Android claim.
"""
import argparse,hashlib,json,sys,time
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/"tools"))
from score_transcript import der
from score_russian_bookmix_c2 import parse_hypothesis,parse_rttm,digest
from evaluate_russian_bookmix_voice_link import (
    normalized,cosine,separate,global_book_simulation,calculate_pairs,SHA_TITANET)


def build_owners(segments,frame_count=1500):
    ids=sorted(set(seg["speaker_id"] for seg in segments if seg["speaker_id"] is not None))
    blockers=[0]*frame_count
    for x in segments:
        first=max(0,min(frame_count,x["start_ms"]//40))
        after=max(0,min(frame_count,(x["end_ms"]+39)//40))
        for i in range(first,after):
            blockers[i]=min(2,blockers[i]+1)
    owners=[-1]*frame_count
    for x in segments:
        if x["speaker_id"] is None:continue
        i=ids.index(x["speaker_id"])
        first=max(0,min(frame_count,(x["start_ms"]+39)//40))
        after=max(0,min(frame_count,x["end_ms"]//40))
        for frame in range(first,after):
            if blockers[frame]==1:owners[frame]=i
    return ids,owners


def purity_for_cluster(hyp,ref,cluster):
    total=0;by={}
    for i in range(6000):
        ms=i*10
        if any(x["speaker_id"]==cluster and x["start_ms"]<=ms<x["end_ms"] for x in hyp):
            labels={x["speaker_id"] for x in ref if x["start_ms"]<=ms<x["end_ms"]}
            if labels:
                total+=1
                for name in labels:by[name]=by.get(name,0)+1
    if not total:return 0.0,{}
    return max(by.values(),default=0)/total,{k:v/total for k,v in by.items()}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ("data","predictions","site","model","output"):
        ap.add_argument("--"+name,type=Path,required=True)
    a=ap.parse_args()
    sys.path.insert(0,str(a.site.resolve()))
    import numpy as np,soundfile as sf,sherpa_onnx
    if digest(a.model)!=SHA_TITANET:raise ValueError("Wrong pinned TitaNet")
    manifest=json.loads((a.data/"local_manifest.json").read_text(encoding="utf8"))
    rttm_manifest={x["file_id"]:x for x in manifest["records"]}
    inputs=json.loads((a.predictions/"inputs.json").read_text(encoding="utf8"))
    extractor=sherpa_onnx.SpeakerEmbeddingExtractor(
        sherpa_onnx.SpeakerEmbeddingExtractorConfig(
            model=str(a.model),num_threads=2,provider="cpu",debug=False))
    if extractor.dim!=192:raise ValueError("Wrong embedding width")
    def embed(pcm):
        st=extractor.create_stream()
        st.accept_waveform(16000,np.ascontiguousarray(pcm,dtype=np.float32))
        st.input_finished()
        if not extractor.is_ready(st):raise ValueError("TitaNet stream is not ready")
        return normalized(extractor.compute(st),np)
    def hashed(name):
        return hashlib.sha256(("mexus-ru-book-mix-10h/"+name).encode()).hexdigest()[:12]
    clips=[]
    purities=[]
    t0=time.monotonic()
    for i in range(55,70):
        stem=f"rec_{i:04d}"
        rec=rttm_manifest[stem]
        wav=a.data/"c2-wavs"/(stem+".wav")
        if digest(wav)!=inputs["wavs"][wav.name]:raise ValueError("WAV differs from actual C2 input")
        hyp=parse_hypothesis(a.predictions/(stem+".product.tsv"))
        ref=parse_rttm(a.data/(stem+".rttm"),stem)
        if len({x["speaker_id"] for x in hyp if x["speaker_id"]})!=2:
            raise ValueError("Expected 2 predicted speaker clusters")
        mapping=der(ref,hyp,60000,0,False)["hypothesis_to_reference"]
        ids,owners=build_owners(hyp)
        samples,sr=sf.read(str(wav),dtype="float32")
        if sr!=16000 or len(samples)!=960000:raise ValueError("Audio format mismatch")
        blocks=samples.reshape(1500,640)
        profile=[]
        for cid,idname in enumerate(ids):
            truth=mapping.get(idname)
            if truth is None or truth not in rec["source_voice_labels"]:
                label=hashed("unmapped/"+stem+"/"+idname)
            else:
                label=hashed(rec["source_voice_labels"][truth])
            purity,by=purity_for_cluster(hyp,ref,idname)
            purities.append({"recording":stem,"pred":idname,"purity":purity,
                             "reference_associated":truth,"has_mixed_activity":purity<.8})
            row={"local":idname,"truth":label}
            parts=separate(owners,cid)
            if parts is None:
                row["valid"]="INSUFFICIENT_CLEAN_SPEECH"
            else:
                try:
                    early=embed(blocks[parts[0]].ravel())
                    late=embed(blocks[parts[1]].ravel())
                    agreement=cosine(early,late,np)
                    if agreement<.84:
                        row["valid"]="AGREEMENT_REJECT"
                    else:
                        row["valid"]="PASS"
                        row["v"]=normalized(early+late,np)
                except ValueError:
                    row["valid"]="MODEL_REJECT"
            profile.append(row)
        clips.append({"id":stem,"n_speakers":2,"profiles":profile})
        print("C2_TITANET",stem,"profiled",sum(p["valid"]=="PASS" for p in profile),
              "purity",[round(x["purity"],3) for x in purities[-len(ids):]],
              "elapsed",round(time.monotonic()-t0,1),flush=True)
    metrics,events=global_book_simulation(clips,np)
    accepted=[p for rec in clips for p in rec["profiles"] if p["valid"]=="PASS"]
    result={
        "schema":"bookmix-c2-titanet-global-link-v1",
        "date":"2026-11-12",
        "scope":"Host JVM C2 true product predictions, native sherpa ONNX TitaNet, Python faithful Kotlin policy replay",
        "dataset_source":manifest["source"],
        "model_sha256":digest(a.model),
        "input_c2_source_sha256":digest(a.predictions/"inputs.json"),
        "source_manifest_sha256":manifest["source_manifest_sha256"],
        "reference":"Russian audiobook synthetic generator RTTM; no human annotations",
        "files":len(clips),"speaker_appearances":sum(len(x["profiles"]) for x in clips),
        "truly_distinct_speaker_sources":len(set(p["truth"] for rec in clips for p in rec["profiles"])),
        "c2_assignment_purity_median":float(np.median([x["purity"] for x in purities])),
        "c2_source_associations_under_80pct":sum(x["has_mixed_activity"] for x in purities),
        "c2_source_associations_under_60pct":sum(x["purity"]<.6 for x in purities),
        "two_excerpts_global_link":metrics,
        "pairwise_accepted":calculate_pairs(accepted,np),
        "model_runtime":"sherpa-onnx "+str(getattr(sherpa_onnx,"__version__","unknown")),
        "source_code_modes":"C2 product TSV, pinned threshold .84 and margin .07, no threshold training",
        "limitations":[
            "The global linking and TitaNet samples are replayed on a host computer, not executed inside Android",
            "C2 turns (actual model outputs) are used to extract voiceprints. RTTM is only used to map clusters to reference voice labels for scoring",
            "When a C2 cluster contains both speakers, Hungarian label alone can conceal confusion; purity metric reports its extent",
            "This is a 15-minute subset split into 15 one-minute files, not 20+ minute continuous processing",
            "Synthetic audiobook voices and generator RTTM are not a human-labeled natural Russian conversation",
            "Small sample, repeated voices correlated, model pretraining overlap not excluded"]}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf8")
    print("C2_LINK_FINAL",json.dumps({k:v for k,v in result.items() if k not in ("limitations","pairwise_accepted","source_code_modes")},ensure_ascii=False),flush=True)
    print("PAIRWISE",json.dumps(result["pairwise_accepted"]),flush=True)

if __name__=="__main__":main()
