"""Score run_asr.py outputs. WER/CER under the project normalization (tools/score_transcript.words: NFKC, lowercase, yo->ye,
alphanumeric tokens, NO number expansion) + separate punctuation F1 on aligned words + within-clip adjacent-repeat count.
Micro-averaged per group (DEV/HOLDOUT); per-clip rows kept; nothing excluded. cpWER/DER are NOT computed here (no speaker labels).
Usage: python -I score_asr.py <corpus_dir> <results_dir> <out_prefix> <cand...>"""
import csv, json, re, sys, unicodedata
from pathlib import Path

def words(t): return re.findall(r"[^\W_]+", unicodedata.normalize("NFKC", t).lower().replace("ё", "е"))
from num2words import num2words
FILL = re.compile(r"^(э+|м+|эм+|мм+|ы+|хм+|а+|ну)$")
def norm2(t):
    """SUPPLEMENTARY normalization (NORM2): glue '300 000', digits->Russian words (num2words, nominative, no agreement),
    then drop pure-filler tokens (э, ээ, м, мм, эм, ы, хм) from BOTH sides. 'а' and 'ну' are real words and are kept."""
    t = re.sub(r"(?<=\d)[  ](?=\d{3})", "", unicodedata.normalize("NFKC", t))
    t = re.sub(r"\d+", lambda m: " " + num2words(int(m.group()), lang="ru") + " ", t)
    return [w for w in words(t) if not re.match(r"^(э+|м+|эм+|мм+|ы+|хм+)$", w)]
def chars(w): return list(" ".join(w))
def align(r, h):
    n, m = len(r), len(h); D = [[0]*(m+1) for _ in range(n+1)]
    for i in range(n+1): D[i][0] = i
    for j in range(m+1): D[0][j] = j
    for i in range(1, n+1):
        for j in range(1, m+1):
            D[i][j] = min(D[i-1][j-1] + (r[i-1] != h[j-1]), D[i-1][j] + 1, D[i][j-1] + 1)
    i, j, S, De, I, pairs = n, m, 0, 0, 0, []
    while i or j:
        if i and j and D[i][j] == D[i-1][j-1] + (r[i-1] != h[j-1]):
            if r[i-1] != h[j-1]: S += 1
            else: pairs.append((i-1, j-1))
            i, j = i-1, j-1
        elif i and D[i][j] == D[i-1][j] + 1: De += 1; i -= 1
        else: I += 1; j -= 1
    return S, De, I, pairs[::-1]
def ptoks(t):
    """[(word, punct_class)] punct_class: '' / ',' / '.'(terminal . ! ? …)"""
    out = []
    for m in re.finditer(r"([^\W_]+(?:[-'][^\W_]+)*)([^\w\s]*)", unicodedata.normalize("NFKC", t)):
        p = m.group(2)
        c = "." if re.search(r"[.!?…]", p) else ("," if re.search(r"[,;:—–-]", p) else "")
        for w in words(m.group(1)): out.append((w, c))
    return out
def reps(w): return sum(1 for a, b in zip(w, w[1:]) if a == b)

def main(cdir, rdir, prefix, cands):
    man = json.loads((Path(cdir)/"manifest.json").read_text(encoding="utf8")); rows = []; agg = {}
    for c in cands:
        res = json.loads((Path(rdir)/f"{c}.json").read_text(encoding="utf8"))
        for it, r in zip(man["items"], res["items"]):
            assert it["id"] == r["id"]
            ref = (Path(cdir)/it["ref"]).read_text(encoding="utf8"); rw, hw = words(ref), words(r["text"])
            S, D, I, pairs = align(rw, hw); n2 = align(norm2(ref), norm2(r['text'])); e2, w2 = n2[0]+n2[1]+n2[2], len(norm2(ref)); cS, cD, cI, _ = align(chars(rw), chars(hw))
            rp, hp = ptoks(ref), ptoks(r["text"])
            tp = fp = fn = 0
            for i, j in pairs:
                a, b = rp[i][1] if i < len(rp) else "", hp[j][1] if j < len(hp) else ""
                if a and a == b: tp += 1
                else:
                    if b: fp += 1
                    if a: fn += 1
            rows.append(dict(cand=c, id=it["id"], group=it["group"], ref_words=len(rw), S=S, D=D, I=I, errors=S+D+I, errors2=e2, ref_words2=w2,
                ref_chars=len(chars(rw)), char_errors=cS+cD+cI, punct_tp=tp, punct_fp=fp, punct_fn=fn,
                hyp_adjacent_repeats=reps(hw), ref_adjacent_repeats=reps(rw), dur_s=r["dur_s"], dec_s=r["dec_s"],
                empty_hyp=int(len(hw) == 0)))  # hypothesis text intentionally NOT written (podlodka licence unstated)
        agg[c] = {k: res[k] for k in ("sherpa_onnx", "threads", "load_s", "peak_rss_mb", "rtf_total")}
    with open(f"{prefix}_per_clip.csv", "w", newline="", encoding="utf8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    out = []
    for c in cands:
        for g in ("DEV", "HOLDOUT"):
            R = [r for r in rows if r["cand"] == c and r["group"] == g]; s = lambda k: sum(r[k] for r in R)
            tp, fp, fn = s("punct_tp"), s("punct_fp"), s("punct_fn")
            pr = tp/(tp+fp) if tp+fp else None; rc = tp/(tp+fn) if tp+fn else None
            out.append(dict(cand=c, group=g, clips=len(R), ref_words=s("ref_words"), WER=round(s("errors")/s("ref_words"), 4), WER_NORM2=round(s("errors2")/s("ref_words2"), 4),
                S=s("S"), D=s("D"), I=s("I"), CER=round(s("char_errors")/s("ref_chars"), 4),
                punct_P=None if pr is None else round(pr, 3), punct_R=None if rc is None else round(rc, 3),
                hyp_repeats=s("hyp_adjacent_repeats"), ref_repeats=s("ref_adjacent_repeats"), empty=s("empty_hyp"),
                worst_clip_WER=round(max(r["errors"]/r["ref_words"] for r in R), 3), **agg[c]))
    Path(f"{prefix}_summary.json").write_text(json.dumps(out, indent=1), encoding="utf8")
    print("cand group  WER  WER2  CER   S   D   I  puncP puncR rep(h/r) RTF  peakMB")
    for o in out: print(f"{o['cand']:4} {o['group']:7} {o['WER']:.4f} {o['WER_NORM2']:.4f} {o['CER']:.4f} {o['S']:3} {o['D']:3} {o['I']:3} {o['punct_P']} {o['punct_R']} {o['hyp_repeats']}/{o['ref_repeats']} {o['rtf_total']} {o['peak_rss_mb']}")
main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:])
