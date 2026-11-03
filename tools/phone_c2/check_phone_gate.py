"""GO/NO-GO for C2 on a physical ARM64 phone from the evidence of run_c2_phone.sh.

python3 tools/phone_c2/check_phone_gate.py --evidence DIR --scored DIR/score.json --reference docs/evidence/nemotron-android/android-emulator-41678965845.json
Each criterion is PASS, FAIL or NOT_RUN. GO needs every criterion to be PASS; any NOT_RUN keeps the verdict at NOT_RUN.
"""
import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET

LONG = "long-ru_000010"


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


def first(rows, case, backend):
    return next((r for r in rows if r["case"] == case and r["backend"] == backend and r.get("attempt", 0) == 0), None)


def evaluate(evidence, scored, reference):
    device = json.loads((evidence / "device.json").read_text(encoding="utf-8")) if (evidence / "device.json").exists() else {}
    checks = {}

    def put(name, ok, detail):
        checks[name] = {"status": "NOT_RUN" if ok is None else "PASS" if ok else "FAIL", "detail": detail}

    put("physical arm64-v8a", None if not device else device.get("abi") == "arm64-v8a", device.get("abi"))
    prototype, ordinary = junit(evidence / "prototype-junit"), junit(evidence / "ordinary-junit")
    put("prototype tests 3/3 (same files, damaged model + C0 fallback, cancel)", None if prototype is None else prototype == (3, 0), prototype)
    put("ordinary build C0 tests 7/7", None if ordinary is None else ordinary == (7, 0), ordinary)
    if scored is None:
        for name in ("no failed runs", "C2 DER within 1 pp of emulator", "C2 output within 3% DER of emulator per file",
                     "C2 20 min full RTF <= 0.5", "C2 20 min peak PSS <= C0 + 100 MiB", "repeat runs identical"):
            put(name, None, "no scored evidence")
    else:
        s = scored["summary"]
        failed = sum(s[b]["failed"] for b in s)
        put("no failed runs", failed == 0, failed)
        phone, emulator = s["c2"]["pooled_der_collar250"], reference["summary"]["c2"]["pooled_der_collar250"]
        put("C2 DER within 1 pp of emulator", phone is not None and phone <= emulator + 0.01, {"phone": phone, "emulator": emulator})
        reference_rows = {(r["case"], r["backend"]): r for r in reference["rows"] if r.get("attempt", 0) == 0}
        drift = []
        for row in scored["rows"]:
            if row["backend"] == "c2" and row.get("attempt", 0) == 0 and "der" in row and (row["case"], "c2") in reference_rows:
                drift.append(abs(row["der"] - reference_rows[(row["case"], "c2")].get("der", row["der"])))
        put("C2 output within 3% DER of emulator per file", bool(drift) and max(drift) <= 0.03, max(drift) if drift else None)
        c0, c2 = first(scored["rows"], LONG, "c0"), first(scored["rows"], LONG, "c2")
        if c0 and c2 and c2["status"] == "OK" and c0["status"] == "OK":
            put("C2 20 min full RTF <= 0.5", c2["wall_ms"] / c2["audio_ms"] <= 0.5, round(c2["wall_ms"] / c2["audio_ms"], 3))
            put("C2 20 min peak PSS <= C0 + 100 MiB", c2["peak_total_pss_kib"] <= c0["peak_total_pss_kib"] + 100 * 1024,
                {"c0_mib": round(c0["peak_total_pss_kib"] / 1024), "c2_mib": round(c2["peak_total_pss_kib"] / 1024)})
        else:
            put("C2 20 min full RTF <= 0.5", None if not c2 else False, None if not c2 else c2["status"])
            put("C2 20 min peak PSS <= C0 + 100 MiB", None if not c2 else False, None)
        repeats = scored.get("repeat_runs_identical", {})
        put("repeat runs identical", bool(repeats) and all(repeats.values()), repeats)
    states = {c["status"] for c in checks.values()}
    verdict = "NO-GO" if "FAIL" in states else "NOT_RUN" if "NOT_RUN" in states else "GO"
    return {"verdict": verdict, "device": device, "checks": checks,
            "not_covered": ["human-reviewed DER", "natural 3-4 speaker speech", "a real 20-minute microphone recording", "thermal throttling over several runs"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--scored", type=Path)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    scored = json.loads(args.scored.read_text(encoding="utf-8")) if args.scored and args.scored.exists() else None
    report = evaluate(args.evidence, scored, json.loads(args.reference.read_text(encoding="utf-8")))
    (args.out or args.evidence / "gate.json").write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=1))
    return 0 if report["verdict"] == "GO" else 2


if __name__ == "__main__":
    raise SystemExit(main())
