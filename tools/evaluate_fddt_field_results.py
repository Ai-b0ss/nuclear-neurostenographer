"""Independent permutation-invariant speaker WER scorer. No ASR model code imported."""
import json, re, pathlib, unicodedata, functools
from collections import defaultdict
ROOT=pathlib.Path.cwd()

def words(text):
    text=unicodedata.normalize("NFKC",str(text)).lower().replace("ё","е")
    return re.findall(r"[а-яa-z0-9]+",text)

def lev(a,b):
    if len(a)<len(b):a,b=b,a
    dp=list(range(len(b)+1))
    for i,x in enumerate(a,1):
        ndp=[i]+[0]*len(b)
        for j,y in enumerate(b,1):
            ndp[j]=min(ndp[j-1]+1,dp[j]+1,dp[j-1]+(x!=y))
        dp=ndp
    return dp[-1]

def group(segments, ref=False):
    res=defaultdict(list)
    for seg in sorted(segments,key=lambda r:(r.get("start",r.get("start_ms",0)),r.get("end",r.get("end_ms",0)))):
        key=seg.get("speaker_id")
        if key is None:key="unknown"
        res[str(key)].extend(words(seg.get("text","")))
    return dict(res)

def compare(reference,predicted):
    a=group(reference);b=group(predicted)
    aa=list(a.items());bb=list(b.items());m=max(len(aa),len(bb))
    while len(aa)<m:aa.append(("*EMPTY*",[]))
    while len(bb)<m:bb.append(("*EMPTY*",[]))
    cost=[[lev(x[1],y[1]) for y in bb] for x in aa]
    @functools.lru_cache(None)
    def rec(i,mask):
        if i>=m:return (0,())
        best=(10**9,())
        for j in range(m):
            if mask&(1<<j):continue
            cand=rec(i+1,mask|(1<<j))
            w=cost[i][j]+cand[0]
            if w<best[0]:best=(w,(j,)+cand[1])
        return best
    error,assignment=rec(0,0)
    ref_count=sum(len(v) for v in a.values())
    pred_count=sum(len(v) for v in b.values())
    return {
        "errors":error,"reference_words":ref_count,"pred_words":pred_count,
        "piewer":round(error/ref_count,4) if ref_count else None,
        "assignment":[{"ref":aa[i][0],"pred":bb[j][0],"ref_words":len(aa[i][1]),"pred_words":len(bb[j][1]),"errors":cost[i][j]} for i,j in enumerate(assignment)],
        "unknown_words":len(b.get("unknown",[])),"speaker_count":len(b),"segments":len(predicted)
    }

def synthetic():
    src=json.loads((ROOT/"sample_manifest.json").read_text("utf8"))
    out=[]
    for item in src:
        p=ROOT/"results"/(item["file"].replace(".wav",".json"))
        if not p.exists():continue
        data=json.loads(p.read_text("utf8"))
        if not data.get("success"):continue
        ref=item["speakers"]
        if not ref:continue
        out.append({
            "case":item["file"],"duration":item["duration"],"ref_speakers":len(set(x["speaker_id"] for x in ref)),
            "overlap_ref_sec":sum(x["duration"] for x in item["simultaneous_segments"]),
            "baseline":compare(ref,data["baseline"]),"hybrid":compare(ref,data["hybrid"]),
            "fddt_changed":data.get("changed"),"c2_ms":data.get("c2_ms"),"a3_ms":data.get("a3_ms"),"fddt_ms":data.get("fddt_ms")
        })
    return out

def real():
    out=[]
    for src in json.loads((ROOT/"real_manifest.json").read_text("utf8")):
        entries={}
        for label,name in src["outputs"].items():
            p=ROOT/"results"/name.replace(".wav",".json")
            if p.exists():
                j=json.loads(p.read_text("utf8"))
                if j.get("success"):entries[label]=j
        if not set(["left","right","mix"])<=entries.keys():continue
        oracle=[]
        for label in ["left","right"]:
            for s in entries[label]["a3"]:
                oracle.append({**s,"speaker_id":label})
        mixed=entries["mix"]
        out.append({"case":src["file"],"clip_start_sec":src["start_sec"],"clip_duration_sec":src["duration_sec"],
                    "audio_energy_overlap_estimate":src["window_energy_overlap_estimate"],
                    "baseline_vs_A3_clean_pseudoref":compare(oracle,mixed["baseline"]),
                    "hybrid_vs_A3_clean_pseudoref":compare(oracle,mixed["hybrid"]),
                    "fddt_changed":mixed.get("changed"),"c2_ms":mixed.get("c2_ms"),"a3_ms":mixed.get("a3_ms"),"fddt_ms":mixed.get("fddt_ms")})
    return out

def main():
    out={"synthetic_with_text_reference":synthetic(),"real_unscripted_with_A3_clean_pseudo_reference":real()}
    (ROOT/"scores.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf8")
    for cat,arr in out.items():
        print("CATEGORY",cat,"CASES",len(arr))
        for d in arr:
            a=d.get("baseline",d.get("baseline_vs_A3_clean_pseudoref"))
            b=d.get("hybrid",d.get("hybrid_vs_A3_clean_pseudoref"))
            print("CASE",d["case"],"REFERENCE",a["reference_words"],"BASE",a["errors"],a["piewer"],"HYBRID",b["errors"],b["piewer"],"CHANGED",d["fddt_changed"],"FDDT_MS",d["fddt_ms"])
        if arr:
            bsum=sum(d.get("baseline",d.get("baseline_vs_A3_clean_pseudoref"))["errors"] for d in arr)
            hsum=sum(d.get("hybrid",d.get("hybrid_vs_A3_clean_pseudoref"))["errors"] for d in arr)
            words=sum(d.get("baseline",d.get("baseline_vs_A3_clean_pseudoref"))["reference_words"] for d in arr)
            print("AGG",words,bsum,hsum,round(bsum/words,4),round(hsum/words,4))

def self_test():
    assert words("Ёлка, 123!") == ["елка","123"]
    assert lev(words("кот пес"),words("кот пес")) == 0
    assert lev(words("кот пес"),words("кот слон")) == 1
    reference=[{"speaker_id":"1","start":0,"end":1,"text":"кот спит"},
               {"speaker_id":"2","start":0,"end":1,"text":"пес идет"}]
    pred=[{"speaker_id":"Speaker 9","start_ms":0,"end_ms":1000,"text":"пес идет"},
          {"speaker_id":"Speaker 3","start_ms":0,"end_ms":1000,"text":"кот спит"}]
    assert compare(reference,pred)["errors"] == 0
    pred[1]["text"] = "кот ест"
    assert compare(reference,pred)["errors"] == 1
    pred.append({"speaker_id":None,"start_ms":1100,"end_ms":1200,"text":"лишнее"})
    assert compare(reference,pred)["errors"] == 2
    assert compare(reference,pred)["reference_words"] == 4
    print("SCORER SELF-TEST PASS")

if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser(description="Offline independent speaker-permutation WER scoring; pass locally downloaded dataset manifests and Android JSON results")
    parser.add_argument("--data-dir",type=pathlib.Path,default=pathlib.Path.cwd(),help="Directory holding sample_manifest.json, real_manifest.json and results/*.json")
    parser.add_argument("--self-test",action="store_true")
    args=parser.parse_args()
    ROOT=args.data_dir.resolve()
    if args.self_test: self_test()
    else:main()
