#!/usr/bin/env python3
"""Reproducible WER / cpWER comparison on ONE shared, human-annotated reference.
NO audio is uploaded. Never compare scores measured on different corpora.
"""
import argparse
import json
import re
import sys
import unicodedata
from functools import lru_cache
from pathlib import Path


def words(text):
    text = unicodedata.normalize("NFKC", text).lower().replace("ё", "е")
    return re.findall(r"[^\W_]+", text, flags=re.UNICODE)


def distance(a, b):
    """Word-level Levenshtein; O(min(len(a),len(b))) memory."""
    if len(b) > len(a):
        a, b = b, a
    previous = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        row = [i]
        for j, y in enumerate(b, 1):
            row.append(min(previous[j] + 1, row[-1] + 1,
                           previous[j-1] + (x != y)))
        previous = row
    return previous[-1]


def transcript(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    turns = data["transcript"] if isinstance(data, dict) else data
    if not isinstance(turns, list):
        raise ValueError("Expected JSON transcript array")
    validated = []
    for item in turns:
        if not isinstance(item, dict) or not isinstance(item.get("text"), str):
            raise ValueError("Each turn needs text")
        start, end = item.get("start_ms"), item.get("end_ms")
        if type(start) is not int or type(end) is not int or not (0 <= start < end):
            raise ValueError("Invalid millisecond boundaries")
        speaker = item.get("speaker_id")
        if speaker is not None and not isinstance(speaker, str):
            raise ValueError("Invalid speaker_id type")
        validated.append((start, end, speaker or "unknown", item["text"]))
    return sorted(validated, key=lambda t: (t[0], t[1]))


def group(turns):
    grouped = {}
    for _, _, speaker, text in turns:
        grouped.setdefault(speaker, []).extend(words(text))
    return grouped


def cpwer(reference, hypothesis):
    """Minimum speaker-permutation word error with dummy empty speakers."""
    ref, hyp = group(reference), group(hypothesis)
    ra, ha = list(ref.values()), list(hyp.values())
    n = max(len(ra), len(ha))
    if n > 12:
        raise ValueError("cpWER >12 speakers requires a different assignment solver")
    ra += [[] for _ in range(n-len(ra))]
    ha += [[] for _ in range(n-len(ha))]
    costs = [[distance(ra[i],ha[j]) for j in range(n)] for i in range(n)]

    @lru_cache(None)
    def assign(i, mask):
        if i == n:
            return 0
        return min(costs[i][j] + assign(i+1, mask | (1 << j))
                   for j in range(n) if not mask & (1 << j))
    return assign(0, 0) if n else 0


def evaluate(reference, hypothesis):
    reference_words = [w for x in reference for w in words(x[3])]
    hypothesis_words = [w for x in hypothesis for w in words(x[3])]
    if not reference_words:
        raise ValueError("Reference has no words (WER undefined)")
    plain = distance(reference_words, hypothesis_words)
    speaker = cpwer(reference, hypothesis)
    return {"reference_words": len(reference_words), "hypothesis_words": len(hypothesis_words),
            "wer": round(plain / len(reference_words), 6),
            "cpwer": round(speaker / len(reference_words), 6),
            "word_errors": plain, "speaker_word_errors": speaker,
            "speakers_detected": len(group(hypothesis))}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--reference", required=True, help="Human-checked verbatim reference JSON")
    p.add_argument("--ours", required=True, help="Output JSON from our application")
    p.add_argument("--theirs", required=True, help="Output JSON from Skvor on the SAME audio")
    p.add_argument("--ours-wall-s", type=float, help="Measured same-device wall time to exported JSON")
    p.add_argument("--theirs-wall-s", type=float, help="Same measurement protocol/device")
    p.add_argument("--duration-s", type=float, help="Actual audio duration")
    a = p.parse_args(argv)
    ref, ours, theirs = transcript(a.reference), transcript(a.ours), transcript(a.theirs)
    result = {"method": "identical_audio_human_reference_word_levenshtein_speaker_permutation",
              "note": "Basic cpWER does not model concurrent independent word streams; review overlaps separately",
              "ours": evaluate(ref, ours), "theirs": evaluate(ref, theirs)}
    if a.duration_s is not None:
        if not 0 < a.duration_s <= 8*3600:
            p.error("--duration-s must be positive and <=8 hours")
        for name, time in [("ours", a.ours_wall_s), ("theirs", a.theirs_wall_s)]:
            if time is not None:
                if time <= 0:
                    p.error("Wall time must be positive")
                result[name]["rtf_export"] = round(time / a.duration_s, 6)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
