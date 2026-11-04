"""Score MOSS (J1) outputs with the SAME code/refs as the A0+C2 same-track study (tools/c2_same_tracks/score_same_corpus.measure).
WER / strict cpWER / cpWER-U / speaker count / A-B-A recurrence / attribution / DER(realmix only). Existing C0/C2 rows come from
docs/evidence/c2-same-tracks/scores.json (host, 2 threads, app code). Segments are timestamp-parsed from the model; unknown speaker never silently matched.
Usage: python -I score_moss.py <corpus_dir=same> <moss_results_dir> <c2_scores.json> <out_prefix>"""
import json, sys, re
from pathlib import Path
T = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(T / "c2_same_tracks")); sys.path.insert(0, str(T)); sys.path.insert(0, str(T / "diar_bench"))
import score_same_corpus as S
corpus, mdir, c2, prefix = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4]
man = json.loads((c2.parent / "manifest.json").read_text(encoding="utf8"))["cases"]
rows = []
for case in man:
    f = mdir / f"{case['id']}.json"
    row = {"case": case["id"], "set": case["set"], "system": "J1", "duration_ms": case["duration_ms"], "ref_speakers": case["speakers"], "noise": case["noise"]}
    if not f.exists(): row["status"] = "NOT_RUN"; rows.append(row); continue
    r = json.loads(f.read_text(encoding="utf8")); row["status"] = "OK" if r["status"] == "OK" else "FAIL"
    if row["status"] != "OK": row["error"] = r.get("error"); rows.append(row); continue
    ref = S.load_reference(corpus, case); dur = ref["audio_duration_ms"]
    ids = {}; segs = []; turns = []
    for s in r["segments"]:
        a, b = int(s["start"] * 1000), int(s["end"] * 1000)
        a = max(0, min(a, dur - 1)); b = max(a + 1, min(b, dur))
        sp = str(s["speaker"]); ids.setdefault(sp, len(ids))
        segs.append({"start_ms": a, "end_ms": b, "speaker_id": f"h{ids[sp]}", "text": s["text"]}); turns.append((a, b, ids[sp]))
    row.update(wall_ms=int(r["gen_s"] * 1000), rtf=round(r["gen_s"] * 1000 / dur, 4), peak_mib=r["peak_rss_mb"], device=r["device"])
    row.update(S.measure(case, ref, turns, segs)); rows.append(row)
base = json.loads(c2.read_text(encoding="utf8"))["rows"]
json.dump(rows, open(f"{prefix}_moss_rows.json", "w"), ensure_ascii=False, indent=1)
def agg(rs, key):
    ok = [x for x in rs if x["status"] == "OK" and x.get(key, {}).get("status") == "SCORED"]
    return (sum(x[key]["errors"] for x in ok), sum(x[key]["reference_words"] for x in ok), len(ok))
out = {}
for set_name in ("holdout", "phone3"):
    ids = {x["case"] for x in rows if x["set"] == set_name and x["status"] == "OK"}
    for sysname, rs in (("J1", rows), ("C0", base), ("C2", base)):
        sel = [x for x in rs if x["system"] == sysname and x["case"] in ids and x["set"] == set_name]
        both = {x["case"] for x in sel if x.get("cpwer", {}).get("status") == "SCORED"}
        out[f"{set_name}/{sysname}"] = dict(n=len(sel), WER=agg(sel, "wer"), cpWER_strict=agg(sel, "cpwer"), cpWER_U=agg(sel, "cpwer_u"),
            exact_count=sum(x["hyp_speakers"] == x["ref_speakers"] for x in sel), over=sum(x["hyp_speakers"] > x["ref_speakers"] for x in sel),
            under=sum(x["hyp_speakers"] < x["ref_speakers"] for x in sel),
            attribution=round(sum(x["speaker"]["attributed_correctly"] for x in sel) / max(1, sum(x["speaker"]["frames"] for x in sel)), 4),
            aba_same=f"{sum(x['recurrence']['same_correct'] for x in sel)}/{sum(x['recurrence']['same_pairs'] for x in sel)}",
            aba_diff=f"{sum(x['recurrence']['different_correct'] for x in sel)}/{sum(x['recurrence']['different_pairs'] for x in sel)}",
            unattributed_words=sum(x.get("unattributed_words", 0) for x in sel),
            median_rtf=sorted(x["rtf"] for x in sel if x.get("rtf"))[len([1 for x in sel if x.get("rtf")]) // 2] if any(x.get("rtf") for x in sel) else None)
rm = [x for x in rows if x["set"] == "realmix"]
out["realmix/J1"] = [{"case": x["case"], "status": x["status"], "hyp_speakers": x.get("hyp_speakers"), "ref": x["ref_speakers"], "der": x.get("der"), "rtf": x.get("rtf")} for x in rm]
out["realmix/C2"] = [{"case": x["case"], "hyp_speakers": x.get("hyp_speakers"), "der": x.get("der", {}).get("rate")} for x in base if x["system"] == "C2" and x["set"] == "realmix"]
out["failures"] = [{"case": x["case"], "status": x["status"], "error": x.get("error")} for x in rows if x["status"] != "OK"]
json.dump(out, open(f"{prefix}_moss_vs_c2.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False, indent=1)[:5000])
