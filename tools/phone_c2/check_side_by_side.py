"""Static proof that the C2 prototype installs next to the contest app instead of over it. No device is used.

python3 tools/phone_c2/check_side_by_side.py --apkanalyzer PATH --main APP.apk --main-test TEST.apk \
    --prototype APP-C2.apk --prototype-test TEST-C2.apk --out FILE.json
Reads the four merged manifests and fails on anything that would make one install replace, block or share data with the
other: same package, a test APK aimed at the wrong app, a shared provider authority, permission or sharedUserId,
an absolute process name, the same launcher label, or INTERNET.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

A = "{http://schemas.android.com/apk/res/android}"


def manifest_facts(xml):
    root = ET.fromstring(xml)
    application = root.find("application")
    instrumentation = root.find("instrumentation")
    authorities = set()
    processes = set()
    for element in root.iter():
        if element.tag == "provider":
            authorities.update(a for a in element.get(f"{A}authorities", "").split(";") if a)
        if element.get(f"{A}process"):
            processes.add(element.get(f"{A}process"))
    return {"package": root.get("package"),
            "label": application.get(f"{A}label") if application is not None else None,
            "shared_user_id": root.get(f"{A}sharedUserId"),
            "uses_permissions": sorted(e.get(f"{A}name") for e in root.findall("uses-permission")),
            "declared_permissions": sorted(e.get(f"{A}name") for e in root.findall("permission")),
            "authorities": sorted(authorities),
            "processes": sorted(processes),
            "instrumentation_target": instrumentation.get(f"{A}targetPackage") if instrumentation is not None else None}


def check(main, main_test, prototype, prototype_test):
    problems = []
    if prototype["package"] != main["package"] + ".c2":
        problems.append(f"Prototype package {prototype['package']} is not {main['package']}.c2")
    if main_test["instrumentation_target"] != main["package"]:
        problems.append("Contest test APK does not target the contest app")
    if prototype_test["instrumentation_target"] != prototype["package"]:
        problems.append(f"Prototype test APK targets {prototype_test['instrumentation_target']}, not {prototype['package']}")
    packages = [m["package"] for m in (main, main_test, prototype, prototype_test)]
    if len(set(packages)) != 4:
        problems.append(f"Package names collide: {packages}")
    for left, right, what in ((main, prototype, "apps"), (main_test, prototype_test, "test APKs"), (main, prototype_test, "contest app and prototype test"),
                              (main_test, prototype, "contest test and prototype")):
        shared = set(left["authorities"]) & set(right["authorities"])
        if shared:
            problems.append(f"Shared provider authority between {what}: {sorted(shared)}")
        same_permissions = set(left["declared_permissions"]) & set(right["declared_permissions"])
        if same_permissions:
            problems.append(f"Permission declared by both {what}: {sorted(same_permissions)}")
    for facts in (main, main_test, prototype, prototype_test):
        if facts["shared_user_id"]:
            problems.append(f"{facts['package']} uses sharedUserId {facts['shared_user_id']}")
        absolute = [p for p in facts["processes"] if not p.startswith(":")]
        if absolute:
            problems.append(f"{facts['package']} has absolute process names {absolute}")
    for facts in (main, prototype):
        if "android.permission.INTERNET" in facts["uses_permissions"]:
            problems.append(f"{facts['package']} requests INTERNET")
    if main["label"] == prototype["label"]:
        problems.append(f"Both apps show the same launcher label {main['label']!r}")
    return problems


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apkanalyzer", required=True)
    for name in ("main", "main-test", "prototype", "prototype-test"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    facts = {}
    for name in ("main", "main_test", "prototype", "prototype_test"):
        apk = getattr(args, name)
        xml = subprocess.run([args.apkanalyzer, "manifest", "print", str(apk)], capture_output=True, text=True, check=True).stdout
        facts[name] = manifest_facts(xml)
    problems = check(facts["main"], facts["main_test"], facts["prototype"], facts["prototype_test"])
    report = {"scope": "Merged manifests of the four APKs; nothing installed", "facts": facts, "problems": problems,
              "status": "PASS" if not problems else "FAIL"}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
