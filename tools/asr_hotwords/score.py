"""Score run.py outputs: WER (project normalization, tools/asr_20261104/score_asr.words), term error rate (TER) on the
reference terms of terms.py, and false term insertions (hypothesis words that belong to the clip's hotword list but are
not in its reference). Paired bootstrap over clips for WER deltas vs. the beam baseline. Writes metrics only (no texts).
  python -I score.py CORPUS_DIR RESULTS_DIR OUT.json"""
import json, random, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parents[1] / "asr_20261104"))
from score_asr_lib import words, align
from terms import terms, norm

cdir, rdir, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
man = {it["id"]: it for it in json.loads((cdir / "manifest.json").read_text(encoding="utf8"))["items"]}
refs = {i: (cdir / it["ref"]).read_text(encoding="utf8") for i, it in man.items()}

BEAM = None  # filled below: beam word counts, to flag silently truncated hypotheses

def per_clip(res, hot_lists=None):
    rows = []
    for r in res["items"]:
        ref = refs[r["id"]]; rw, hw = words(ref), words(r["text"])
        S, D, I, pairs = align(rw, hw)
        tset = {norm(w) for w in terms(ref)}
        tpos = [i for i, w in enumerate(rw) if w in tset]
        hit = {i for i, _ in pairs}
        hot = {w for h in (hot_lists[r["id"]] if hot_lists else r["hotwords"]) for w in words(h)}
        refset = set(rw)
        ins = sum(1 for w in hw if w in hot and w not in refset)
        rows.append(dict(id=r["id"], group=r["group"], n=len(rw), err=S + D + I, terms=len(tpos),
                         term_err=sum(1 for i in tpos if i not in hit), hot_ins=ins, empty=int(not hw),
                         truncated=int(BEAM is not None and len(hw) < 0.7 * BEAM.get(r["id"], 0)), dec_s=r["dec_s"], dur_s=r["dur_s"]))
    return rows

def boot(a, b, group, k=10000, seed=7):
    ids = [x["id"] for x in a if x["group"] == group]; A = {x["id"]: x for x in a}; B = {x["id"]: x for x in b}
    rnd = random.Random(seed); ds = []
    for _ in range(k):
        s = [rnd.choice(ids) for _ in ids]
        n = sum(A[i]["n"] for i in s)
        ds.append((sum(B[i]["err"] for i in s) - sum(A[i]["err"] for i in s)) / n * 100)
    ds.sort(); return [round(ds[int(0.025 * k)], 2), round(ds[int(0.975 * k)], 2)]

runs = {p.stem: json.loads(p.read_text(encoding="utf8")) for p in sorted(rdir.glob("*.json")) if p.stem != "score"}
BEAM = {r["id"]: len(words(r["text"])) for r in runs["beam"]["items"]}
rows = {k: per_clip(v) for k, v in runs.items()}
summary = {}
for k, rs in rows.items():
    for g in ("DEV", "HOLDOUT"):
        R = [r for r in rs if r["group"] == g]; s = lambda f: sum(r[f] for r in R)
        e = {"wer_pct": round(s("err") / s("n") * 100, 2), "errors": s("err"), "ref_words": s("n"),
             "ter_pct": round(s("term_err") / s("terms") * 100, 1) if s("terms") else None, "term_errors": s("term_err"),
             "term_occurrences": s("terms"), "hotword_insertions": s("hot_ins"), "empty_hyp": s("empty"), "truncated_vs_beam": s("truncated"),
             "rtf": round(s("dec_s") / s("dur_s"), 3)}
        if k.startswith("distractor") and "beam" in runs:
            base = per_clip(runs["beam"], {r["id"]: r["hotwords"] for r in runs[k]["items"]})
            e["same_words_in_beam_without_hotwords"] = sum(r["hot_ins"] for r in base if r["group"] == g)
        if k != "beam" and "beam" in rows:
            e["delta_wer_vs_beam_pp_95ci"] = boot(rows["beam"], rs, g)
        summary.setdefault(k, {})[g] = e
out.write_text(json.dumps({"summary": summary, "per_clip": rows}, ensure_ascii=False, indent=1), encoding="utf8")
for k in summary:
    print(k.ljust(14), "  ".join(f"{g}: WER {v['wer_pct']} TER {v['ter_pct']} ({v['term_errors']}/{v['term_occurrences']}) ins {v['hotword_insertions']} trunc {v['truncated_vs_beam']} Δ {v.get('delta_wer_vs_beam_pp_95ci')}" for g, v in summary[k].items()))
