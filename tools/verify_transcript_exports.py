"""Independently check JSON/SRT/TXT consistency from real host pipeline output.

This verifies serialization and timeline integrity, never ASR/diarization accuracy.
No audio, private paths, model weights or external services are used.
"""
import argparse
import json
from pathlib import Path
import re


def milliseconds(value):
    match = re.fullmatch(r"([0-9]{2,}):([0-9]{2}):([0-9]{2})[,.]([0-9]{3})", value)
    assert match, f"Invalid timestamp: {value}"
    h, m, s, ms = map(int, match.groups())
    assert m < 60 and s < 60
    return ((h * 60 + m) * 60 + s) * 1000 + ms


def verify(directory, prefix="dialogue"):
    directory = Path(directory)
    data = json.loads((directory / (prefix + ".json")).read_text(encoding="utf-8"))
    assert data["units"] == "milliseconds" and data["audio_duration_ms"] > 0
    assert data["provenance"]["timestamp_source"] == "diarization_boundaries_and_input_windows"
    assert isinstance(data["warnings"], list) and data["warnings"]
    segments = data["segments"]
    assert segments, "Expected nonempty actual public Russian fixture output"
    subtitles = (directory / (prefix + ".srt")).read_text(encoding="utf-8").strip().split("\n\n")
    txt = (directory / (prefix + ".txt")).read_text(encoding="utf-8")
    assert len(subtitles) == len(segments)
    previous = -1
    for index, (segment, cue) in enumerate(zip(segments, subtitles), 1):
        start, end = segment["start_ms"], segment["end_ms"]
        assert previous <= start < end <= data["audio_duration_ms"]
        previous = start
        lines = cue.splitlines()
        assert lines[0] == str(index)
        times = lines[1].split(" --> ")
        assert len(times) == 2 and list(map(milliseconds, times)) == [start, end]
        speaker = segment["speaker_id"] or "Не определён"
        body = speaker + ": " + segment["text"]
        if segment["overlapping_speech"]:
            assert segment["speaker_id"] is None and not segment["attribution_reliable"]
            body += " [перекрытие речи]"
        assert "\n".join(lines[2:]) == body
        assert body in txt
        interval = re.escape(body)
        match = re.search(r"\[([^\]\n]+)–([^\]\n]+)\] " + interval, txt)
        assert match and list(map(milliseconds, match.groups())) == [start, end]
    return {"status": "PASS", "segments": len(segments), "audio_ms": data["audio_duration_ms"],
            "formats": ["json", "srt", "txt"], "checks": ["UTF8", "milliseconds", "duration_bounds",
            "cue_order", "same_text_speaker_and_intervals", "provenance_and_warnings"],
            "accuracy_benchmark": "NOT_RUN", "android": "NOT_RUN_BY_THIS_FILE_CHECK"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = verify(args.directory)
    body = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.write_text(body, encoding="utf-8")
    print(body)


if __name__ == "__main__":
    main()
