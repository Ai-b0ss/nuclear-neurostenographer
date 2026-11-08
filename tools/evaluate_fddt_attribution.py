"""Score paired Android attribution results against a supplied text manifest.

Does not run ASR. The metric is speaker-permutation word error, not DER.
References may be synthetic or automatic: label them explicitly with --category.
"""
import argparse
import json
from pathlib import Path
from evaluate_fddt_field_results import compare, lev, words


def ordered_words(rows):
    return [w for row in sorted(rows, key=lambda r: (r.get("start", r.get("start_ms", 0)),
            r.get("end", r.get("end_ms", 0)))) for w in words(row["text"])]


def evaluate(manifest, results, category):
    cases = []
    for item in manifest:
        path = results / (Path(item["file"]).stem + ".json")
        data = json.loads(path.read_text(encoding="utf8"))
        if not data.get("success"):
            raise ValueError(f"Unsuccessful Android run: {path.name}")
        base = data.get("baseline_unmerged", data["baseline"])
        final = data["hybrid"]
        # Strict text and punctuation order, including the spaces added by the
        # same mergeReplies presentation operation in the baseline and final.
        if " ".join(r["text"] for r in base) != " ".join(r["text"] for r in final):
            raise ValueError(f"Attribution changed text or punctuation: {path.name}")
        b_overlap = [r for r in base if r.get("overlap")]
        f_overlap = [r for r in final if r.get("overlap")]
        fields = ("start_ms", "end_ms", "text")
        if [[r[k] for k in fields] for r in b_overlap] != [[r[k] for k in fields] for r in f_overlap]:
            raise ValueError(f"Attribution changed overlap timing: {path.name}")
        if any(b.get("speaker_id") is not None and b["speaker_id"] != f.get("speaker_id")
               for b, f in zip(b_overlap, f_overlap)):
            raise ValueError(f"Attribution changed a known voice: {path.name}")
        ref = item["speakers"]
        a, b = compare(ref, base), compare(ref, final)
        ref_words = ordered_words(ref)
        cases.append({"file": item["file"], "category": category,
            "reference_words": a["reference_words"], "baseline_errors": a["errors"],
            "final_errors": b["errors"], "unknown_before": a["unknown_words"],
            "unknown_after": b["unknown_words"],
            "baseline_timeline_word_errors": lev(ref_words, ordered_words(base)),
            "final_timeline_word_errors": lev(ref_words, ordered_words(final)),
            "exact_text_and_punctuation_preserved": True, "overlap_word_times_preserved": True,
            "fddt_ms": data.get("fddt_ms"), "changed": data.get("changed"),
            "baseline_assignment": a["assignment"], "final_assignment": b["assignment"]})
    keys = ("reference_words", "baseline_errors", "final_errors", "unknown_before", "unknown_after",
            "baseline_timeline_word_errors", "final_timeline_word_errors")
    return {"category": category, "metric": "speaker-permutation word error; not DER",
            "normalization": "NFKC, lowercase, yo->e, punctuation stripped for scoring; exact preservation checked separately",
            "unknown_policy": "unknown is a separate stream included in optimal label permutation",
            "cases": cases, "totals": {k: sum(r[k] for r in cases) for k in keys}}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--results-dir", type=Path, required=True)
    p.add_argument("--category", required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    result = evaluate(json.loads(args.manifest.read_text(encoding="utf8")), args.results_dir, args.category)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print(json.dumps(result["totals"], ensure_ascii=False))
