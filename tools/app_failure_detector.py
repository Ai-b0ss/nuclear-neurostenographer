"""Find crashes, ANRs and kills of OUR processes in emulator logs.

The UI script hides system error dialogs on the disposable CI emulator so that a
foreign ANR (for example the launcher) cannot cover the screen. That would also hide
an ANR of this app, so failures are detected from logcat and DropBox instead of from
what is visible. Other packages are deliberately ignored.
"""
import re

PACKAGE = "ru.neurostenographer.app"
DROPBOX_TAGS = ("data_app_anr", "data_app_crash", "data_app_native_crash",
                "system_app_anr", "system_app_crash", "system_app_native_crash")


def _ours(text, package):
    # The package itself or one of its processes (":diarization"), not a longer name.
    return re.search(re.escape(package) + r"(?![\w.])", text) is not None


def scan_logcat(logcat, package=PACKAGE):
    findings = []
    lines = logcat.splitlines()
    for index, line in enumerate(lines):
        if re.search(r"\bANR in " + re.escape(package) + r"(?![\w.])", line):
            findings.append("ANR: " + line.strip())
        elif "FATAL EXCEPTION" in line:
            # The crashing process is named on a following line.
            for follow in lines[index + 1:index + 6]:
                if "Process:" in follow:
                    if _ours(follow, package):
                        findings.append("Java crash: " + follow.strip())
                    break
        elif "Fatal signal" in line and _ours(line, package):
            findings.append("Native crash: " + line.strip())
        elif re.search(r"lowmemorykiller|Low on memory", line) and _ours(line, package):
            findings.append("Killed for memory: " + line.strip())
        elif "ForegroundServiceDidNotStartInTimeException" in line and _ours(line, package):
            findings.append("Foreground service start failure: " + line.strip())
        elif "Scheduling restart of crashed service" in line and _ours(line, package):
            findings.append("Service crash: " + line.strip())
    return findings


def scan_dropbox(dropbox, since="", package=PACKAGE):
    """`dumpsys dropbox --print` text; `since` is 'YYYY-MM-DD HH:MM:SS' in device time."""
    findings = []
    blocks = re.split(r"^=+\s*$", dropbox, flags=re.MULTILINE)
    for block in blocks:
        header = re.search(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) (\S+) \(", block, flags=re.MULTILINE)
        if not header or header.group(2) not in DROPBOX_TAGS:
            continue
        if since and header.group(1) < since:
            continue
        if re.search(r"^Process: .*" + re.escape(package) + r"(?![\w.])", block, flags=re.MULTILINE) \
                or re.search(r"\bANR in " + re.escape(package) + r"(?![\w.])", block):
            findings.append(f"DropBox {header.group(2)} at {header.group(1)}")
    return findings


def scan(logcat, dropbox="", since="", package=PACKAGE):
    return scan_logcat(logcat, package) + scan_dropbox(dropbox, since, package)
