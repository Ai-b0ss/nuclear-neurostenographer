"""Adversarial regression of the export validator against actual inference files."""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
from verify_transcript_exports import verify


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    verify(args.directory)
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        def reset():
            for suffix in ("json", "srt", "txt"):
                shutil.copyfile(args.directory / ("dialogue." + suffix), root / ("dialogue." + suffix))
        def rejected():
            try:
                verify(root)
            except AssertionError:
                return
            raise AssertionError("Corrupt export passed validation")
        reset()
        srt = root / "dialogue.srt"
        srt.write_text(srt.read_text(encoding="utf-8").replace(" --> ", " INVALID ", 1), encoding="utf-8")
        rejected()
        reset()
        txt = root / "dialogue.txt"
        txt.write_text("missing transcript", encoding="utf-8")
        rejected()
        reset()
        path = root / "dialogue.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["segments"][-1]["end_ms"] = data["audio_duration_ms"] + 1
        path.write_text(json.dumps(data), encoding="utf-8")
        rejected()
        reset()
        verify(root)
    print("PASS export validator: corrupted SRT, missing TXT, beyond-audio JSON rejected; original regression PASS")


if __name__ == "__main__":
    main()
