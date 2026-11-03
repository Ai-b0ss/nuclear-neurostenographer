"""GO/NO-GO for C2 on a physical ARM64 phone from the evidence of run_c2_phone.sh.

python3 tools/phone_c2/check_phone_gate.py --evidence DIR --scored DIR/score.json
DIR/score.json comes from tools/c2_same_tracks/score_phone_run.py. Each criterion is PASS, FAIL or NOT_RUN. GO needs
every criterion to be PASS; any NOT_RUN keeps the verdict at NOT_RUN. GO means "C2 runs on this phone as it does on the
host, next to the contest app, within the speed and memory limits". Which system is more accurate is the quality table
in the score file, not this gate.
"""
import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET

PROTOTYPE = "ru.neurostenographer.app.c2"
HOST_DRIFT = 0.03


def junit(folder):
    """(tests, failures + errors) over all JUnit files, or None when there are none."""
    files = list(Path(folder).rglob("TEST-*.xml"))
    if not files:
        return None
    tests = failed = 0
    for f in files:
        root = ET.parse(f).getroot()
        for suite in [root] if root.tag == "testsuite" else root.iter("testsuite"):
            tests += int(suite.get("tests", 0))
            failed += int(suite.get("failures", 0)) + int(suite.get("errors", 0))
    return tests, failed


def read(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def evaluate(evidence, scored):
    device = read(evidence / "device.json") or {}
    exits = read(evidence / "exit-codes.json")
    installed = read(evidence / "prototype-package.json")
    checks = {}

    def put(name, ok, detail):
        checks[name] = {"status": "NOT_RUN" if ok is None else "PASS" if ok else "FAIL", "detail": detail}

    put("physical arm64-v8a", None if not device else device.get("abi") == "arm64-v8a", device.get("abi"))
    put("prototype ran as its own package", None if installed is None else installed.get("installed_as") == PROTOTYPE, installed)
    if exits is None:
        put("contest app untouched", None, "no exit-codes.json")
        put("prototype removed afterwards", None, "no exit-codes.json")
    else:
        untouched = exits.get("contest_app_untouched")
        put("contest app untouched", True if untouched is None and not device.get("contest_app_installed") else untouched is True,
            "contest app not installed" if untouched is None else untouched)
        put("prototype removed afterwards", exits.get("prototype_left_installed") is False, exits.get("prototype_left_installed"))
    prototype = junit(evidence / "prototype-junit")
    put("prototype tests 3/3 (same files, damaged model + C0 fallback, cancel)", None if prototype is None else prototype == (3, 0), prototype)
    names = ("no failed runs", "C2 matches host C2 on every file", "C0 matches host C0 on every file", "repeat runs identical",
             "C2 20 min full RTF <= 0.5", "C2 20 min peak PSS <= C0 + 100 MiB")
    if scored is None:
        for name in names:
            put(name, None, "no scored evidence")
    else:
        put("no failed runs", scored["failed_runs"] == 0, scored["failed_runs"])
        for system in ("C2", "C0"):
            rows = [r for r in scored["rows"] if r["system"] == system and "host_agreement" in r]
            bad = [{"case": r["case"], **r["host_agreement"]} for r in rows
                   if not r["host_agreement"]["same_speaker_count"] or (r["host_agreement"]["der_phone_vs_host"] or 0) > HOST_DRIFT]
            put(f"{system} matches host {system} on every file", None if not rows else not bad, {"files": len(rows), "differing": bad})
        repeats = scored.get("repeat_runs_identical", {})
        put("repeat runs identical", None if not repeats else all(repeats.values()), repeats)
        long = scored.get("long", {})
        c0, c2 = long.get("C0"), long.get("C2")
        if c0 and c2 and c0["status"] == "OK" and c2["status"] == "OK":
            put("C2 20 min full RTF <= 0.5", c2["wall_ms"] / c2["audio_ms"] <= 0.5, round(c2["wall_ms"] / c2["audio_ms"], 3))
            put("C2 20 min peak PSS <= C0 + 100 MiB", c2["peak_mib"] <= c0["peak_mib"] + 100, {"c0_mib": c0["peak_mib"], "c2_mib": c2["peak_mib"]})
        else:
            put("C2 20 min full RTF <= 0.5", None if not c2 else False, None if not c2 else c2["status"])
            put("C2 20 min peak PSS <= C0 + 100 MiB", None if not c2 else False, None)
    states = {c["status"] for c in checks.values()}
    verdict = "NO-GO" if "FAIL" in states else "NOT_RUN" if "NOT_RUN" in states else "GO"
    return {"verdict": verdict, "device": device, "checks": checks,
            "quality_not_gated": scored["summary"] if scored else None,
            "not_covered": ["human-reviewed DER", "natural 3-4 speaker speech in one room", "a real 20-minute microphone recording",
                            "thermal throttling over several runs"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--scored", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    scored = read(args.scored) if args.scored else None
    report = evaluate(args.evidence, scored)
    (args.out or args.evidence / "gate.json").write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("verdict", "checks")}, ensure_ascii=False, indent=1))
    return 0 if report["verdict"] == "GO" else 2


if __name__ == "__main__":
    raise SystemExit(main())
