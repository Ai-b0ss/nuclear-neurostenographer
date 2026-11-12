"""Fetch ONLY the first fixed 70 Russian RTTM-labelled benchmark examples.
No duplicate repo or full 181MB tar. No persistent archive of raw audio.
"""
import urllib.request,json,hashlib,tarfile,io,time,re,argparse
from pathlib import Path
source="https://huggingface.co/datasets/mexus/ru-book-mix-10h/resolve/18655c48833c5acfcd868a36eb38465712d15f1c/"
root=Path(__file__).resolve().parents[1]/".local/speakerbook-active/scratch/ru_book_mix_eval"
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output",type=Path,default=root)
root=parser.parse_args().output
root.mkdir(parents=True,exist_ok=True)
manifest_req=urllib.request.Request(source+"manifest.jsonl",
                                    headers={"User-Agent":"Neurostenographer-heldout-QA/1.0"})
with urllib.request.urlopen(manifest_req,timeout=25) as r:
    manifest_bytes=r.read()
if hashlib.sha256(manifest_bytes).hexdigest()!="2f1e26fe123afe43e76b96cd49fd62e75bdb94c2f056c1fc7fa43c981de46a6c":
    raise ValueError("Frozen benchmark manifest changed")
lines=[json.loads(x) for x in manifest_bytes.splitlines() if x.strip()]
assert len(lines)==600
assert all(x["file_id"]==f"rec_{i:04d}" for i,x in enumerate(lines))
n=70
selected={x["file_id"]:x for x in lines[:n]}
assert all(x["shard"]=="data/shard-0000.tar" for x in selected.values())
(root/"source_manifest.jsonl").write_bytes(manifest_bytes)
tar_url=source+"data/shard-0000.tar"
req=urllib.request.Request(tar_url,headers={
    "User-Agent":"Neurostenographer-heldout-QA/1.0","Range":"bytes=0-112000000"})
print("FETCH_FIXED",n,"manifest_sha256",hashlib.sha256(manifest_bytes).hexdigest(),flush=True)
done={}
started=time.monotonic()
with urllib.request.urlopen(req,timeout=55) as r:
    if r.status!=206 or not r.headers.get("Content-Range","").startswith("bytes 0-"):
        raise RuntimeError("Range request not honored; refusing 182MB full shard download")
    print("PARTIAL_CONTENT",r.status,r.headers.get("Content-Range"),flush=True)
    with tarfile.open(fileobj=r,mode="r|") as tar:
        for member in tar:
            stem=Path(member.name).stem
            suffix=Path(member.name).suffix.lower()
            if stem not in selected or suffix not in (".flac",".json",".rttm") or not member.isfile():
                continue
            if not 0<member.size<(3_500_000 if suffix==".flac" else 150_000):
                raise ValueError("Unexpected member size "+member.name+" "+str(member.size))
            data=tar.extractfile(member).read()
            if len(data)!=member.size:
                raise ValueError("Truncated "+member.name)
            if suffix==".flac" and not data.startswith(b"fLaC"):
                raise ValueError("Not FLAC "+member.name)
            if suffix==".json":
                j=json.loads(data)
                expected=selected[stem]
                if j.get("file_id")!=stem or j.get("speakers")!=expected["speakers"]:
                    raise ValueError("Metadata mismatch "+stem)
            if suffix==".rttm" and not data.startswith(b"SPEAKER "):
                raise ValueError("Not RTTM "+stem)
            target=root/(stem+suffix)
            if target.exists():
                if target.stat().st_size!=len(data) or hashlib.sha256(target.read_bytes()).digest()!=hashlib.sha256(data).digest():
                    raise RuntimeError("Existing member mismatch: "+member.name)
            else:target.write_bytes(data)
            done.setdefault(stem,{})[suffix]={
              "bytes":len(data),"sha256":hashlib.sha256(data).hexdigest()}
            if len(done)%10==0 and suffix==".rttm":
                print("EXTRACTED",len(done),"of",n,"seconds",round(time.monotonic()-started,1),flush=True)
            if len(done)==n and all(len(files)==3 for files in done.values()):
                break
if len(done)!=n or any(len(files)!=3 for files in done.values()):
    raise RuntimeError(f"Incomplete extraction: {len(done)} samples, {sum(len(x) for x in done.values())} members")
short=[{"file_id":x,"source_voice_labels":selected[x]["speakers"],
        "n_speakers":selected[x]["n_speakers"],"files":done[x]} for x in sorted(done)]
out={"schema":"ru-book-mix-sample-manifest-v1",
     "source":"https://huggingface.co/datasets/mexus/ru-book-mix-10h",
     "license":"CC-BY-4.0", "data_type":"synthetic mixtures, generator RTTM not manual human review",
     "selection":"first 70 consecutive files (55 single speaker, 15 mixed), frozen by file index not scores",
     "source_manifest_sha256":hashlib.sha256(manifest_bytes).hexdigest(),
     "records":short}
(root/"local_manifest.json").write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding="utf8")
print("FINISHED",len(done),"seconds",round(time.monotonic()-started,2),
      "bytes",sum(v["bytes"] for m in done.values() for v in m.values()),flush=True)
