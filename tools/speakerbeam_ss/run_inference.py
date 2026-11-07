"""Extract the manually enrolled target speaker into an A3 PCM WAV."""
import argparse
import json
from pathlib import Path
import sys

from research import DEFAULT_CHECKPOINT, DEFAULT_UPSTREAM, run_inference


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mixture", type=Path, required=True)
    parser.add_argument("--enrollment", type=Path, required=True,
                        help="Manually selected clean-enrollment WAV for the target speaker")
    parser.add_argument("--output", type=Path, required=True,
                        help="A3 WAV path inside .local/speakerbeam-ss")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--upstream", type=Path, default=DEFAULT_UPSTREAM)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--python", default=sys.executable)
    args = parser.parse_args()
    result = run_inference(args.mixture, args.enrollment, args.output,
                           args.upstream, args.checkpoint, args.python)
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    manifest = args.manifest or args.output.with_suffix(".json")
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
