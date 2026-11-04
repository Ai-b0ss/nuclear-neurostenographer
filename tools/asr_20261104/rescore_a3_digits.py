"""Rescore the run_a3_same_corpus.py transcripts with digits written out in words (num2words, Russian, nominative), applied
to the HYPOTHESIS of both systems before the unchanged score_same_corpus.measure. The references already spell numbers out,
A0 never emits digits, A3 does; this isolates the formatting effect. Agreement of case is not attempted (num2words nominative),
so this still slightly penalizes A3.

python -I rescore_a3_digits.py --root K:/nn-bench --out K:/nn-bench/results-a3 --evidence docs/evidence/asr-20261104/same-corpus-a3
"""
import argparse, json, re, sys
from pathlib import Path
from num2words import num2words

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools")); sys.path.insert(0, str(REPO / "tools/c2_same_tracks"))
from score_same_corpus import measure, load_reference, read_turns, bootstrap  # noqa: E402

def spell(text):
    text = re.sub(r"(?<=\d)[ \u00a0](?=\d{3}\b)", "", text)
    return re.sub(r"\d+", lambda m: " " + num2words(int(m.group()), lang="ru") + " ", text)

ap = argparse.ArgumentParser()
for a in ("--root", "--out", "--evidence"): ap.add_argument(a, type=Path, required=True)
args = ap.parse_args()
cases = [c for c in json.loads((REPO / "docs/evidence/c2-same-tracks/manifest.json").read_text(encoding="utf-8"))["cases"] if c["text"]]
rows = []
for system in ("A0", "A3"):
    for c in cases:
        segs = json.loads((args.out / system / f"{c['id']}.transcript.json").read_text(encoding="utf-8"))["segments"]
        segs = [dict(s, text=spell(s["text"])) for s in segs]
        rows.append(dict(case=c["id"], set=c["set"], system=system,
                         **measure(c, load_reference(args.root / "data/same", c), read_turns(args.root / "results-same/C2" / f"{c['id']}.tsv"), segs)))
summary = {}
for name in ("all", "holdout", "phone3"):
    sel = [r for r in rows if name == "all" or r["set"] == name]
    summary[name] = {}
    for k in ("wer", "cpwer", "cpwer_u"):
        for s in ("A0", "A3"):
            R = [r for r in sel if r["system"] == s and r[k].get("status") == "SCORED"]
            e, n = sum(r[k]["errors"] for r in R), sum(r[k]["reference_words"] for r in R)
            summary[name].setdefault(s, {})[k] = dict(errors=e, words=n, rate=round(e / n, 4) if n else None, cases=len(R))
        pairs = []
        for c in cases:
            if name != "all" and c["set"] != name: continue
            a = next(r for r in sel if r["system"] == "A0" and r["case"] == c["id"]); b = next(r for r in sel if r["system"] == "A3" and r["case"] == c["id"])
            if a[k].get("status") == b[k].get("status") == "SCORED": pairs.append((a[k]["errors"], b[k]["errors"], a[k]["reference_words"]))
        summary[name][f"bootstrap_{k}_A3_minus_A0"] = bootstrap(pairs) if len(pairs) > 1 else None
(args.evidence / "summary_digits_spelled.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
print(json.dumps(summary, indent=1))
