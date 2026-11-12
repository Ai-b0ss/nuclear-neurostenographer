"""Pinned OFFLINE oracle-turn speaker-link evaluation on 70 Russian audiobook mixes.

RTTM turns are the dataset's *generator references*, not C2 predictions.
This evaluates the two-excerpt TitaNet + conservative global voice-link
policy under ideal turn boundaries. It is not end-to-end DER/cpWER.
Data was frozen by file index before evaluating model scores.
"""
import argparse
import hashlib
import itertools
import json
import math
import subprocess
import sys
import time
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]
SHA_TITANET="ad4a1802485d8b34c722d2a9d04249662f2ece5d28a7a039063ca22f515a789e"


def sha256(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for part in iter(lambda:f.read(1<<20),b""):h.update(part)
    return h.hexdigest()


def normalized(a,np):
    a=np.asarray(a,dtype="float64")
    n=np.linalg.norm(a)
    if not np.all(np.isfinite(a)) or not np.isfinite(n) or n<1e-9:
        raise ValueError("Invalid voice embedding")
    return a/n


def cosine(a,b,np):
    return float(np.dot(a,b))


def ground_truth_owners(rttm_text,expected_speakers,frame_count=1500):
    """Exact frame coverage and overlap exclusions as CleanSpeakerFrames.select."""
    turns=[]
    for line in rttm_text.splitlines():
        parts=line.split()
        if not parts:continue
        if len(parts)!=10 or parts[0]!="SPEAKER" or parts[7] not in expected_speakers:
            raise ValueError("Invalid NIST RTTM reference turn")
        a=round(float(parts[3])*1000)
        b=round((float(parts[3])+float(parts[4]))*1000)
        if a<0 or b<=a or b>60000+1:
            raise ValueError("Out-of-bounds turn")
        turns.append((a,b,parts[7]))
    if not turns:raise ValueError("Missing reference speech")
    names=list(expected_speakers)
    blockers=[0]*frame_count
    for a,b,_ in turns:
        start=max(0,min(frame_count,a//40))
        end=max(0,min(frame_count,(b+39)//40))
        for i in range(start,end):
            blockers[i]=min(2,blockers[i]+1)
    owners=[-1]*frame_count
    for a,b,name in turns:
        start=max(0,min(frame_count,(a+39)//40))
        end=max(0,min(frame_count,b//40))
        for i in range(start,end):
            if blockers[i]==1:owners[i]=names.index(name)
    return names,owners


def separate(owners,who,max_frames=400):
    """Exact CleanSpeakerFrames.separate - two 16-sec, >=3-sec clean extracts."""
    active=[i for i,s in enumerate(owners) if s==who]
    if len(active)<150:return None
    middle=len(active)//2
    early=active[:middle][:max_frames]
    late=active[middle:][-max_frames]
    if len(early)<75 or len(late)<75 or early[-1]>=late[0]:
        return None
    return early,late


def calculate_pairs(records,np):
    pairs=list(itertools.combinations(records,2))
    pos=[];neg=[]
    for a,b in pairs:
        x=cosine(a["v"],b["v"],np)
        if a["truth"]==b["truth"]:pos.append(x)
        else:neg.append(x)
    return {"positive_pairs":len(pos),"negative_pairs":len(neg),
            "positive_above_0_84":sum(s>=0.84 for s in pos),
            "false_rejects_0_84":sum(s<0.84 for s in pos),
            "false_accepts_0_84":sum(s>=0.84 for s in neg),
            "positive_median":float(np.median(pos)) if pos else None,
            "negative_max":max(neg) if neg else None,
            "negative_p99":float(np.quantile(neg,.99)) if neg else None}


def global_book_simulation(clips,np):
    """Faithfully reproduce GlobalSpeakerBook Kotlin matching and in-block collision."""
    entries=[];n=1
    truth_to_ids={}
    outcome={
      "total_expected_profiles":0,
      "profiles_consistent":0,
      "profiles_rejected_early_late":0,
      "profiles_rejected_insufficient_evidence":0,
      "first_valid_enrollments":0,
      "returning_valid_probes":0,
      "correct_returning_links":0,
      "returning_false_splits":0,
      "new_speaker_false_links":0,
      "wrong_returning_links":0,
      "speaker_mixes":0,
      "in_block_collisions":0
    }
    event=[]
    for item in clips:
        candidates=[]
        for p in item["profiles"]:
            outcome["total_expected_profiles"]+=1
            if p["valid"]!="PASS":
                key=("profiles_rejected_early_late" if p["valid"]=="AGREEMENT_REJECT" else
                     "profiles_rejected_insufficient_evidence")
                outcome[key]+=1
                continue
            outcome["profiles_consistent"]+=1
            v=p["v"]
            scores=sorted(((i,cosine(v,e["centroid"],np)) for i,e in enumerate(entries)),
                          key=lambda z:-z[1])
            top=scores[0] if scores else (-1,-1)
            other=scores[1][1] if len(scores)>1 else -1
            at=cosine(v,entries[top[0]]["anchor"],np) if top[0]>=0 else -1
            ao=max((cosine(v,e["anchor"],np) for i,e in enumerate(entries) if i!=top[0]),default=-1)
            eligible=(top[0]>=0 and top[1]>=.84 and top[1]-other>=.07 and at>=.84 and at-ao>=.07)
            candidates.append({"id":p["local"],"truth":p["truth"],
                               "v":v,"top":top[0],"eligible":eligible})
        collided={}
        for p in candidates:
            if p["eligible"]:
                collided[p["top"]]=collided.get(p["top"],0)+1
        for p in candidates:
            known=p["truth"] in truth_to_ids
            if p["eligible"] and collided[p["top"]]==1:
                ent=entries[p["top"]]
                global_id=ent["id"]
                blended=.85*ent["centroid"]+.15*p["v"]
                ent["centroid"]=normalized(blended,np)
            else:
                if p["eligible"] and collided[p["top"]]>1:
                    outcome["in_block_collisions"]+=1
                global_id="Speaker "+str(n)
                n+=1
                entries.append({"id":global_id,
                                "anchor":p["v"].copy(),"centroid":p["v"].copy()})
            old=truth_to_ids.setdefault(p["truth"],set())
            if known:
                outcome["returning_valid_probes"]+=1
                if global_id in old:outcome["correct_returning_links"]+=1
                elif any(global_id in idset for truth,idset in truth_to_ids.items() if truth!=p["truth"]):
                    outcome["wrong_returning_links"]+=1
                else:outcome["returning_false_splits"]+=1
            else:
                outcome["first_valid_enrollments"]+=1
                if any(global_id in idset for truth,idset in truth_to_ids.items() if truth!=p["truth"]):
                    outcome["new_speaker_false_links"]+=1
            old.add(global_id)
            event.append({"file_id":item["id"],"speaker_hash":p["truth"],
                          "accepted":global_id, "previously_known":known})
    global_to_true={}
    for label, ids in truth_to_ids.items():
        for i in ids:global_to_true.setdefault(i,set()).add(label)
    outcome["speaker_mixes"]=sum(len(v)>1 for v in global_to_true.values())
    outcome["distinct_true_voices_admitted"]=len(truth_to_ids)
    outcome["total_global_ids_created"]=len(entries)
    outcome["returning_recall_accepted"]=(
        outcome["correct_returning_links"]/outcome["returning_valid_probes"]
        if outcome["returning_valid_probes"] else None)
    return outcome,event


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data",type=Path,required=True)
    p.add_argument("--model",type=Path,required=True)
    p.add_argument("--site",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    sys.path.insert(0,str(args.site.resolve()))
    import numpy as np
    import soundfile as sf
    import sherpa_onnx
    assert sha256(args.model)==SHA_TITANET,"Pinned TitaNet SHA256 mismatch"
    manifest=json.loads((args.data/"local_manifest.json").read_text(encoding="utf8"))
    files=manifest["records"]
    assert len(files)==70 and [x["file_id"] for x in files]==[f"rec_{i:04d}" for i in range(70)]
    assert sum(x["n_speakers"]==1 for x in files)==55
    extractor=sherpa_onnx.SpeakerEmbeddingExtractor(
        sherpa_onnx.SpeakerEmbeddingExtractorConfig(
            model=str(args.model),num_threads=2,debug=False,provider="cpu"))
    assert extractor.dim==192
    def embed(signal):
        stream=extractor.create_stream()
        stream.accept_waveform(16000,np.ascontiguousarray(signal,dtype=np.float32))
        stream.input_finished()
        if not extractor.is_ready(stream):raise ValueError("TitaNet not ready")
        ret=extractor.compute(stream)
        if len(ret)!=192:raise ValueError("TitaNet unexpected embedding dimension")
        return normalized(ret,np)
    def pseudo_label(real):
        return hashlib.sha256(("mexus-ru-book-mix-10h/"+real).encode()).hexdigest()[:12]

    results=[]
    start=time.monotonic()
    for idx,rec in enumerate(files):
        stem=rec["file_id"]
        for suffix,meta in rec["files"].items():
            candidate=args.data/(stem+suffix)
            if sha256(candidate)!=meta["sha256"]:raise ValueError("Invalid file hash "+str(candidate))
        audio,sr=sf.read(str(args.data/(stem+".flac")),dtype="float32")
        if sr!=16000 or audio.ndim!=1 or abs(len(audio)-960000)>16 or not np.all(np.isfinite(audio)):
            raise ValueError("Unexpected audio format")
        metadata=json.loads((args.data/(stem+".json")).read_text(encoding="utf8"))
        if metadata["file_id"]!=stem or metadata["speakers"]!=rec["source_voice_labels"]:
            raise ValueError("Manifest metadata mismatch")
        names,owners=ground_truth_owners((args.data/(stem+".rttm")).read_text(encoding="utf8"),
                                          rec["source_voice_labels"])
        framearray=audio[:1500*640].reshape(1500,640)
        profiles=[]
        for i,label in enumerate(names):
            frames=separate(owners,i)
            truevoice=pseudo_label(rec["source_voice_labels"][label])
            row={"local":label,"truth":truevoice}
            if frames is None:
                row["valid"]="INSUFFICIENT_CLEAN_SPEECH"
            else:
                try:
                    early=embed(framearray[frames[0]].flatten())
                    late=embed(framearray[frames[1]].flatten())
                    agreement=cosine(early,late,np)
                    row["early_late_cosine"]=agreement
                    if agreement<.84:
                        row["valid"]="AGREEMENT_REJECT"
                    else:
                        row["valid"]="PASS"
                        row["v"]=normalized(early+late,np)
                except ValueError:
                    row["valid"]="MODEL_REJECT"
            profiles.append(row)
        results.append({"id":stem,"n_speakers":rec["n_speakers"],"profiles":profiles})
        if idx%10==9:
            print("PROCESSED",idx+1,"of",len(files),
                  "seconds",round(time.monotonic()-start,1),flush=True)

    solo=results[:55]
    all_profiles=[p for rec in results for p in rec["profiles"] if p["valid"]=="PASS"]
    solo_profiles=[p for rec in solo for p in rec["profiles"] if p["valid"]=="PASS"]
    full,events=global_book_simulation(results,np)
    first55,_=global_book_simulation(solo,np)
    summary={
        "schema":"russian-bookmix-speaker-link-oracle-qa-v1",
        "date":"2026-11-12",
        "source":manifest["source"],
        "source_corpus_license":"CC-BY-4.0",
        "data_type":"synthetic Russian audiobook speaker-mix with generator RTTM",
        "first_n_fixed_files":70,"single_speaker_files":55,"mixed_speaker_files":15,
        "unique_source_voices_all":len({p["truth"] for x in results for p in x["profiles"]}),
        "unique_source_voices_solo":len({p["truth"] for x in solo for p in x["profiles"]}),
        "source_manifest_sha256":manifest["source_manifest_sha256"],
        "model_sha256":sha256(args.model),
        "model_runtime":"sherpa-onnx "+str(getattr(sherpa_onnx,"__version__","unknown")),
        "thresholds_frozen":{"early_late_cosine":.84,"link_cosine":.84,"link_margin":.07},
        "turns":"ORACLE generator RTTM, not the actual Nemotron C2 output",
        "solo_pairwise":calculate_pairs(solo_profiles,np),
        "all_pairwise":calculate_pairs(all_profiles,np),
        "solo_55_global_simulation":first55,
        "all_70_global_simulation":full,
        "diagnostic_early_late": {
          "profiles_total":sum(len(x["profiles"]) for x in results),
          "profiles_accepted":len(all_profiles),
          "agreement_cosine_median":float(np.median(
             [p["early_late_cosine"] for x in results for p in x["profiles"]
              if "early_late_cosine" in p]))},
        "inference_wall_s":round(time.monotonic()-start,2),
        "caveats":[
          "Russian audiobook mixes are synthetic. RTTM time/identity annotations are generator-produced, not manually reviewed.",
          "Oracle clean speaker turns bypass C2 diarization and source-attribution errors, so these results are an upper bound for profiling quality, NOT end-to-end DER or cpWER.",
          "Source voice identities are assumed distinct by dataset metadata; model training-set overlap is not independently excluded.",
          "Only first 70 files by ID: 55 single-voice and 15 mixed, one corpus. No threshold tuning on these samples.",
          "Mixed RTTM often contains short overlap excluded from clean embeddings; no speech recognition or time alignment scored.",
          "The runtime is native sherpa-onnx 1.12.40 on Windows, while production Android QA was 1.12.20.",
          "Pairwise trials are correlated within voice; not independent population observations."] }
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(summary,indent=2,ensure_ascii=False)+"\n",encoding="utf8")
    print("RESULT_FILE",args.output,flush=True)
    print("SOLO_GLOBAL",json.dumps(first55,ensure_ascii=False),flush=True)
    print("ALL_GLOBAL",json.dumps(full,ensure_ascii=False),flush=True)
    print("PAIRWISE",json.dumps(summary["all_pairwise"],ensure_ascii=False),flush=True)

if __name__=="__main__":
    main()
