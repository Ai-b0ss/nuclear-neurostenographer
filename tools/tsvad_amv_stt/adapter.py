import hashlib
import json
import math
from pathlib import Path

from .upstream.overlap_resolver import OverlapResolver

_UPSTREAM_DIR = Path(__file__).resolve().parent / "upstream"
PROVENANCE = json.loads((_UPSTREAM_DIR / "provenance.json").read_text(encoding="utf-8"))


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_upstream():
    checks = {
        "source_sha256": (_UPSTREAM_DIR / "overlap_resolver.py", PROVENANCE["source_sha256"]),
        "license_sha256": (_UPSTREAM_DIR / "LICENSE", PROVENANCE["license_sha256"]),
    }
    for field, (path, expected) in checks.items():
        actual = _sha256(path)
        if actual != expected:
            raise RuntimeError(f"Pinned AMV-STT {field} mismatch: {actual}")
    return dict(PROVENANCE)


def to_amv_intervals(intervals):
    converted = []
    for interval in intervals:
        start_ms = interval["start_ms"]
        end_ms = interval["end_ms"]
        speaker_id = interval["speaker_id"]
        if type(start_ms) is not int or type(end_ms) is not int:
            raise ValueError("Interval bounds must be integer milliseconds")
        if start_ms < 0 or start_ms >= end_ms:
            raise ValueError("Interval must satisfy 0 <= start_ms < end_ms")
        if speaker_id is None:
            raise ValueError("AMV-STT requires a known speaker_id")
        hash(speaker_id)
        converted.append((start_ms / 1000.0, end_ms / 1000.0, speaker_id))
    return converted


def from_amv_intervals(intervals):
    converted = []
    for start, end, speaker_id in intervals:
        if not math.isfinite(start) or not math.isfinite(end) or start < 0 or start >= end:
            raise ValueError("AMV-STT returned an invalid interval")
        start_ms = int(round(start * 1000.0))
        end_ms = int(round(end * 1000.0))
        if start_ms >= end_ms:
            raise ValueError("AMV-STT interval collapsed during millisecond conversion")
        converted.append({"start_ms": start_ms, "end_ms": end_ms, "speaker_id": speaker_id})
    return converted


class AmvOverlapResolverAdapter:
    def __init__(self, resolver=None, **resolver_options):
        if resolver is not None and resolver_options:
            raise ValueError("resolver_options cannot be combined with an injected resolver")
        self.resolver = resolver or OverlapResolver(**resolver_options)

    def resolve(self, document, samples, sample_rate, extractor):
        if type(sample_rate) is not int or sample_rate <= 0:
            raise ValueError("sample_rate must be a positive integer")
        verify_upstream()
        resolved = self.resolver.resolve_overlaps(
            to_amv_intervals(document["diarization"]), samples, sample_rate, extractor
        )
        output = dict(document)
        output["diarization"] = from_amv_intervals(resolved)
        return output
