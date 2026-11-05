"""Measure the B0 term dictionary (core BuiltinTerms + TermDictionary, applied by the Kotlin code via :core:runTermEval).

  python -I tools/term_dictionary/eval.py --podlodka-corpus K:/nn-asr-data/corpus --podlodka-run K:/nn-asr-data/results/hotwords/greedy.json
         --dialogues K:/nn-bench/results-a3w/new --dialogue-refs K:/nn-bench/data/same --out docs/evidence/term-dictionary-20261105/score.json

Podlodka (human references, IT podcast): WER / TER before and after, for "accept all" and "accept unambiguous" policies,
and every edit classified as fixing (the changed words now match the reference), harmful (they matched before) or neutral.
Synthetic dialogues (ivkond, everyday speech, no IT terms): any edit is a false change. Writes metrics and edit pairs only
(edit pairs are single words / short terms, not transcripts)."""
import argparse, json, os, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/asr_20261104")); sys.path.insert(0, str(Path(__file__).parent))
from score_asr_lib import words, align
from ref_terms import terms, norm  # same term definition as tools/asr_hotwords (PR #23)


def kotlin_apply(rows):
    with tempfile.TemporaryDirectory() as tmp:
        src, dst = Path(tmp) / "in.tsv", Path(tmp) / "out.tsv"
        src.write_text("".join(f"{i}\t{t.replace(chr(9), ' ').replace(chr(10), ' ')}\n" for i, t in rows), encoding="utf8")
        tc = os.environ.get("TOOLCHAIN", "K:/nn-c2-android/.local/toolchain")
        env = dict(os.environ, JAVA_HOME=f"{tc}/jdk/jdk-17.0.21+9", GRADLE_USER_HOME=f"{tc}/gradle-home")
        gradle = f"{tc}/gradle/gradle-8.9/bin/gradle" + (".bat" if os.name == "nt" else "")
        subprocess.run([gradle, "--no-daemon", "--offline", "-q", ":core:runTermEval", f"-PtermEvalArgs={src} {dst}"],
                       cwd=ROOT, env=env, check=True, capture_output=True)
        out = {}
        for line in dst.read_text(encoding="utf8").splitlines():
            i, a, s, n, amb, pairs = (line.split("\t") + [""])[:6]
            out[i] = {"all": a, "safe": s, "edits": int(n), "ambiguous": int(amb), "pairs": [p for p in pairs.split(" | ") if p]}
        return out


def errs(ref, hyp):
    S, D, I, _ = align(words(ref), words(hyp)); return S + D + I


def term_errors(ref, hyp):
    rw = words(ref); tset = {norm(w) for w in terms(ref)}
    _, _, _, pairs = align(rw, words(hyp)); hit = {i for i, _ in pairs}
    pos = [i for i, w in enumerate(rw) if w in tset]
    return sum(1 for i in pos if i not in hit), len(pos)


def classify(ref, pair):
    """fix: the replacement's words occur in the reference and the original's did not; harm: the reverse."""
    o, r = pair.split("=>", 1); rs = set(words(ref)); ow, nw = words(o), words(r)
    before, after = all(w in rs for w in ow), all(w in rs for w in nw)
    return "fix" if after and not before else ("harm" if before and not after else "neutral")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--podlodka-corpus", type=Path, required=True); ap.add_argument("--podlodka-run", type=Path, required=True)
    ap.add_argument("--dialogues", type=Path); ap.add_argument("--dialogue-refs", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    man = {it["id"]: it for it in json.loads((a.podlodka_corpus / "manifest.json").read_text(encoding="utf8"))["items"]}
    run = json.loads(a.podlodka_run.read_text(encoding="utf8"))["items"]
    fixed = kotlin_apply([(r["id"], r["text"]) for r in run])
    report = {"podlodka_run": a.podlodka_run.name, "policies": {}, "edits": []}
    for g in ("DEV", "HOLDOUT"):
        R = [r for r in run if r["group"] == g]
        refs = {r["id"]: (a.podlodka_corpus / man[r["id"]]["ref"]).read_text(encoding="utf8") for r in R}
        n = sum(len(words(refs[r["id"]])) for r in R)
        for pol in ("raw", "all", "safe"):
            hyp = {r["id"]: r["text"] if pol == "raw" else fixed[r["id"]][pol] for r in R}
            e = sum(errs(refs[i], hyp[i]) for i in refs); te = [term_errors(refs[i], hyp[i]) for i in refs]
            report["policies"].setdefault(pol, {})[g] = {"wer_pct": round(e / n * 100, 2), "errors": e, "ref_words": n,
                "term_errors": sum(x for x, _ in te), "term_occurrences": sum(y for _, y in te)}
        for r in R:
            for p in fixed[r["id"]]["pairs"]:
                report["edits"].append({"group": g, "clip": r["id"], "edit": p, "class": classify(refs[r["id"]], p)})
    for g in ("DEV", "HOLDOUT"):
        E = [e for e in report["edits"] if e["group"] == g]
        report["policies"]["all"][g]["edits"] = {c: sum(1 for e in E if e["class"] == c) for c in ("fix", "neutral", "harm")}
    if a.dialogues and a.dialogue_refs:
        rows = []
        for f in sorted(a.dialogues.glob("*.transcript.json")):
            doc = json.loads(f.read_text(encoding="utf8"))
            for k, s in enumerate(doc["segments"]):
                rows.append((f"{f.name.split('.')[0]}#{k}", s["text"]))
        fx = kotlin_apply(rows)
        report["synthetic_dialogues"] = {"tracks": len({r[0].split('#')[0] for r in rows}), "segments": len(rows),
            "words": sum(len(words(t)) for _, t in rows), "edits_proposed": sum(v["edits"] for v in fx.values()),
            "pairs": [p for v in fx.values() for p in v["pairs"]]}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf8")
    for pol, v in report["policies"].items(): print(pol, json.dumps(v, ensure_ascii=False))
    for e in report["edits"]: print(e["group"], e["class"], e["edit"])
    if "synthetic_dialogues" in report: print("synthetic", {k: v for k, v in report["synthetic_dialogues"].items()})


if __name__ == "__main__":
    main()
