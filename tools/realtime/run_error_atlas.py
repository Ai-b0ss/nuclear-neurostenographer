"""Repeatable fixed-fixture RMS/DER error audit (does not change inference)."""
import hashlib
import json
from pathlib import Path
from error_atlas import audit

ROOT = Path(__file__).resolve().parents[2]
SYN = Path("C:/Users/user/Documents/nuclear-neurostenographer/.local/synthetic-ru")
REF = ROOT / "docs/evidence/architecture-20261106/references"
DEVICE_REFS = ROOT / "docs/evidence/realtime-honor-20261105/fixture-references"
DATA = ROOT / "docs/evidence/architecture-20261106"
WAV = ROOT / ".local/realtime-fixtures"
OUT = ROOT / "docs/evidence/error-atlas-20261106"

CASES = [
    ("syn3", SYN / "syn3-clean.wav", SYN / "syn3-clean.reference.json", ["fast", "revised-fast", "incremental-offline"]),
    ("syn4", SYN / "syn4-noise.wav", SYN / "syn4-noise.reference.json", ["fast", "incremental-offline"]),
    ("aba", WAV / "aba.wav", DEVICE_REFS / "aba.reference.json", ["fast", "incremental-offline"]),
    ("overlap", WAV / "overlap.wav", DEVICE_REFS / "overlap.reference.json", ["fast", "incremental-offline"]),
    ("abab", WAV / "abab.wav", REF / "abab.reference.json", ["fast", "incremental-offline"]),
    ("return-pause", WAV / "return-pause.wav", REF / "return-pause.reference.json", ["fast", "incremental-offline"]),
    ("short-tail", WAV / "short-tail.wav", REF / "short-tail.reference.json", ["fast", "incremental-offline"]),
]

def main():
    comparisons = []
    for label, wav, ref, modes in CASES:
        for mode in modes:
            f = DATA / label / (mode + ".tsv")
            try:
                summary = audit(wav, ref, f, OUT / label / mode)
                totals = summary["totals"]
                comparisons.append(dict(fixture=label, mode=mode,
                    der=summary["score"]["rate"], miss_ms=totals["missed_ms"],
                    quiet45_ms=totals["missed_quiet45_ms"],
                    quiet35_ms=totals["missed_quiet35_ms"],
                    loud35_ms=totals["missed_loud35_ms"],
                    false_alarm_ms=totals["false_alarm_ms"],
                    confusion_ms=totals["confusion_ms"],
                    reference_ms=totals["reference_ms"],
                    wav_sha256=summary["source_audio_sha256"]))
            except Exception as exc:
                raise RuntimeError(f"{label}/{mode}: {exc}") from exc
    (OUT / "comparison.json").write_text(json.dumps(dict(scope="SYNTHETIC_COARSE_TTS_RMS_ONLY", runs=comparisons),
                                                  indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    print("AUDITED",len(comparisons),"runs; no model or reference changed")

if __name__ == "__main__":
    main()
