"""Audit archived public-fixture files; never claim fresh Android execution."""
import argparse
import hashlib
import json
from pathlib import Path
import re
from verify_transcript_exports import verify as verify_transcript


def verify(report, apk, directory, prefix):
    if report.get("status") != "PASS":
        raise ValueError("UI report did not pass")
    checks = report.get("checks")
    if not isinstance(checks, list) or not checks or any(not isinstance(c, str) for c in checks) or len(set(checks)) != len(checks):
        raise ValueError("Missing or duplicated UI checks")
    identity = apk["runtime_identity"]
    runtime = identity["aar_sha256"]
    if not isinstance(runtime, str) or not re.fullmatch(r"[0-9a-f]{64}", runtime):
        raise ValueError("Invalid recorded runtime hash")
    if identity.get("native_bytes") != "MATCH" or identity.get("build_config_digest") != "MATCH":
        raise ValueError("Packaged runtime identity was not verified")
    recorded = report["saved_public_exports"]
    if set(recorded) != {"txt", "json", "srt"}:
        raise ValueError("Incomplete provider export inventory")
    for format, pin in recorded.items():
        raw = (directory / (prefix + "." + format)).read_bytes()
        if type(pin.get("bytes")) is not int or pin["bytes"] <= 0 or len(raw) != pin["bytes"]:
            raise ValueError("Provider export byte count mismatch: " + format)
        if hashlib.sha256(raw).hexdigest() != pin.get("sha256"):
            raise ValueError("Provider export hash mismatch: " + format)
    document = json.loads((directory / (prefix + ".json")).read_bytes())
    if document["provenance"]["runtime_sha256"] != runtime:
        raise ValueError("Export and APK report identify different runtimes")
    verify_transcript(directory, prefix=prefix)
    return {"status": "PASS", "scope": "ARCHIVED_FILE_INTEGRITY_ONLY_NO_ANDROID_EXECUTION_OR_ACCURACY",
            "runtime_sha256": runtime, "exports_verified": 3, "recorded_ui_checks": len(checks)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ui-report", type=Path, required=True)
    parser.add_argument("--apk-report", type=Path, required=True)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--prefix", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.prefix):
        parser.error("Prefix must be a plain filename stem")
    try:
        result = verify(json.loads(args.ui_report.read_bytes()), json.loads(args.apk_report.read_bytes()),
                        args.directory, args.prefix)
    except (ValueError, KeyError, TypeError, OSError, AssertionError) as error:
        print(json.dumps({"status": "ERROR", "reason": str(error)}))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
