"""Validate the exact four-field contest JSON against a raw ASR export.

Official presentation: {"transcript":[{"speaker_id":str,"start_ms":int,
"end_ms":int,"text":str}]}. All times are relative to source audio in ms.
No private recordings or audio are accessed. No claim of ASR accuracy.
"""
import json
from pathlib import Path
import re
import sys

def verify(contest_path: Path, original_path: Path) -> None:
    contest = json.loads(contest_path.read_text(encoding="utf-8"))
    source = json.loads(original_path.read_text(encoding="utf-8"))
    assert type(contest) is dict and set(contest) == {"transcript"}
    rows, original = contest["transcript"], source["segments"]
    assert type(rows) is list and len(rows) == len(original)
    mapping = {}
    previous = -1
    for row, src in zip(rows, original):
        assert type(row) is dict and set(row) == {"speaker_id", "start_ms", "end_ms", "text"}
        assert type(row["speaker_id"]) is str
        assert re.fullmatch(r"speaker_[1-9]\d*|unknown", row["speaker_id"])
        assert type(row["start_ms"]) is int and type(row["end_ms"]) is int
        assert 0 <= previous <= row["start_ms"] < row["end_ms"] <= source["audio_duration_ms"] if previous >= 0 else 0 <= row["start_ms"] < row["end_ms"] <= source["audio_duration_ms"]
        previous = row["start_ms"]
        assert type(row["text"]) is str and row["text"] == src["text"] and bool(row["text"])
        assert row["start_ms"] == src["start_ms"] and row["end_ms"] == src["end_ms"]
        sid = src["speaker_id"]
        if sid is None:
            assert row["speaker_id"] == "unknown"
        else:
            if sid not in mapping:
                mapping[sid] = "speaker_" + str(len(mapping) + 1)
            assert row["speaker_id"] == mapping[sid]
    print("PASS official contest JSON: exact keys, speaker strings, original text, ms intervals, order and raw source parity; accuracy NOT_SCORED")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage: verify_contest_json.py contest.json original.json")
    verify(Path(sys.argv[1]), Path(sys.argv[2]))
