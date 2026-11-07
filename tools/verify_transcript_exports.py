"""Independently check JSON/SRT/TXT consistency from real host pipeline output.

This verifies serialization and timeline integrity, never ASR/diarization accuracy.
No audio, private paths, model weights or external services are used.
"""
import argparse
import json
from pathlib import Path
import re


def require(condition, message):
    # Validation must remain active with python -O / PYTHONOPTIMIZE.
    if not condition:
        raise AssertionError(message)


def milliseconds(value):
    match = re.fullmatch(r"([0-9]{2,}):([0-9]{2}):([0-9]{2})[,.]([0-9]{3})", value)
    require(match, f"Invalid timestamp: {value}")
    h, m, s, ms = map(int, match.groups())
    require(m < 60 and s < 60, 'Export consistency check failed')
    return ((h * 60 + m) * 60 + s) * 1000 + ms


def verify(directory, prefix="dialogue"):
    directory = Path(directory)
    data = json.loads((directory / (prefix + ".json")).read_text(encoding="utf-8"))
    require(data["units"] == "milliseconds" and data["audio_duration_ms"] > 0, 'Export consistency check failed')
    require(data["provenance"]["timestamp_source"] in ("diarization_boundaries_and_input_windows", "asr_token_timestamps",
                                                     "asr_token_timestamps_and_input_windows"), 'Export consistency check failed')
    require(isinstance(data["warnings"], list) and data["warnings"], 'Export consistency check failed')
    segments = data["segments"]
    require(segments, "Expected nonempty actual public Russian fixture output")
    subtitles = (directory / (prefix + ".srt")).read_text(encoding="utf-8").strip().split("\n\n")
    txt = (directory / (prefix + ".txt")).read_text(encoding="utf-8")
    require(len(subtitles) == len(segments), 'Export consistency check failed')
    previous = -1
    for index, (segment, cue) in enumerate(zip(segments, subtitles), 1):
        start, end = segment["start_ms"], segment["end_ms"]
        require(previous <= start < end <= data["audio_duration_ms"], 'Export consistency check failed')
        previous = start
        lines = cue.splitlines()
        require(lines[0] == str(index), 'Export consistency check failed')
        times = lines[1].split(" --> ")
        require(len(times) == 2 and list(map(milliseconds, times)) == [start, end], 'Export consistency check failed')
        sid = segment["speaker_id"]
        # 0.3.0+ TXT/SRT show "Говорящий N" for the JSON id "Speaker N" (TranscriptExport.displaySpeaker); earlier
        # builds wrote the id itself. Accept the label this SRT cue uses, then require exactly the same body in TXT.
        def display(i):
            return "Говорящий " + i[len("Speaker "):] if i.startswith("Speaker ") else i
        labels = ["Не определён"] if sid is None else (
            [sid, "Говорящий " + sid[len("Speaker "):]] if sid.startswith("Speaker ") else [sid])
        # 0.3.10+: overlapped speech without one speaker names everyone who spoke: "Говорящий 1 + Говорящий 2".
        overlap_ids = segment.get("overlap_speaker_ids")
        if overlap_ids is not None:
            require(sid is None and segment["overlapping_speech"] and isinstance(overlap_ids, list) and len(overlap_ids) >= 2
                    and all(isinstance(i, str) and i for i in overlap_ids), 'Export consistency check failed')
            labels = [" + ".join(display(i) for i in overlap_ids)]
        # 0.3.1+: a name the user gave this speaker is exported as "speaker_name" next to the stable id,
        # and TXT/SRT must then show exactly that name.
        name = segment.get("speaker_name")
        if name is not None:
            require(sid is not None and isinstance(name, str) and name.strip() == name and name and "\n" not in name,
                    'Export consistency check failed')
            labels = [name]
        # 0.3.3+: accepted spelling edits (term dictionary) keep the raw ASR "text" and add "text_edited";
        # TXT/SRT must then show exactly the edited text.
        shown = segment["text"]
        if "text_edited" in segment:
            edited = segment["text_edited"]
            require(isinstance(edited, str) and edited.strip() and edited != segment["text"], 'Export consistency check failed')
            shown = edited
        suffix = ": " + shown + (" [перекрытие речи]" if segment["overlapping_speech"] else "")
        if segment["overlapping_speech"]:
            require(segment["speaker_id"] is None and not segment["attribution_reliable"], 'Export consistency check failed')
        body = "\n".join(lines[2:])
        require(any(body == label + suffix for label in labels), 'Export consistency check failed')
        require(body in txt, 'Export consistency check failed')
        interval = re.escape(body)
        matches = re.finditer(r"\[([^\]\n]+)–([^\]\n]+)\] " + interval, txt)
        require(any(list(map(milliseconds, m.groups())) == [start, end] for m in matches), 'Export consistency check failed')
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
