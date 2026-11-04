"""Paired clip-level bootstrap (10000 resamples, seed 20261104) of WER difference cand - A0 from podlodka_per_clip.csv.
Usage: python -I paired_bootstrap.py <per_clip.csv> <out.json>"""
import csv, json, random, sys
rows = list(csv.DictReader(open(sys.argv[1], encoding="utf8")))
by = {}
for r in rows: by.setdefault((r["cand"], r["group"]), {})[r["id"]] = r
random.seed(20261104); out = []
for g in ("DEV", "HOLDOUT"):
    base = by[("A0", g)]; ids = sorted(base)
    for (c, gg), d in sorted(by.items()):
        if gg != g or c == "A0": continue
        e = [int(d[i]["errors"]) - int(base[i]["errors"]) for i in ids]; w = [int(base[i]["ref_words"]) for i in ids]
        diffs = []
        for _ in range(10000):
            k = [random.randrange(len(ids)) for _ in ids]; diffs.append(sum(e[j] for j in k) / sum(w[j] for j in k))
        diffs.sort(); pt = sum(e) / sum(w)
        out.append(dict(group=g, cand=c, delta_wer=round(pt, 4), ci95=[round(diffs[250], 4), round(diffs[9749], 4)],
                        significant=not (diffs[250] <= 0 <= diffs[9749])))
json.dump(out, open(sys.argv[2], "w"), indent=1)
for o in out: print(o)
