"""Run ONE audio file through the app on a physical phone and save its JSON export (acceptance helper).

  python phone_run_clip.py SERIAL CLIP.wav --out-dir DIR [--wait-minutes 15]

Steps, all through the real UI and the system document picker: the clip is pushed to
/sdcard/Download/ns-acceptance (a folder this tool owns), imported with "Открыть аудиофайл", processed (starts by itself)
, exported with "JSON" (top of the transcript screen) into the same folder, pulled, and the timings shown by the app
are parsed. Screenshots go to .local/phone-ui-private (git-ignored: pickers can show personal file names).
Never run it against an emulator; it refuses serials of emulators. It never reads other files of the phone.
"""
import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

from phone_kit import find_adb
from phone_ui import PhoneUi

FOLDER = "/sdcard/Download/ns-acceptance"
DONE = re.compile(r"^(ASR вернул|Ошибка|Недостаточно|Диаризация недоступна|Операция отменена)")


def parse_timings(message):
    """Timings and counts from the app status line, or None when it is not a finished-run message."""
    match = re.search(r"ASR вернул (\d+) фрагментов\. Аудио: (\d+) мс; загрузка (\d+) мс; обработка (\d+) мс\. "
                      r"Диаризация(?: [A-Z0-9]+)?: (\d+) кластеров, (\d+) мс", message)
    if not match:
        return None
    fragments, audio, load, asr, clusters, diarization = map(int, match.groups())
    total = load + asr + diarization
    return {"fragments": fragments, "audio_ms": audio, "model_load_ms": load, "asr_ms": asr, "clusters": clusters,
            "diarization_ms": diarization, "total_ms": total, "rtf": round(total / audio, 2) if audio else None}


def swipe_largest(ui, down, fast=False):
    """Swipe the biggest scrollable view (a picker can also expose a small breadcrumb list)."""
    nodes = [n for n in ui.tree().iter("node") if n.get("scrollable") == "true"]
    boxes = []
    for n in nodes:
        try:
            boxes.append(ui.bounds(n))
        except ValueError:
            pass
    if not boxes:
        return
    x1, y1, x2, y2 = max(boxes, key=lambda b: (b[2] - b[0]) * (b[3] - b[1]))
    x, top, bottom = (x1 + x2) // 2, y1 + (y2 - y1) // 4, y1 + (y2 - y1) * 3 // 4
    for _ in range(6 if fast else 1):  # fast: flings through a long transcript list
        ui.shell("input", "swipe", str(x), str(bottom if down else top), str(x), str(top if down else bottom), "80" if fast else "350")


def scroll_to(ui, label, direction="down", tries=8, exact=True):
    for _ in range(tries):
        node = ui.find(label=label, timeout=1, exact=exact)[1]
        if node is not None:
            try:
                ui.bounds(node)  # present in the tree but maybe off screen (long picker lists)
                return node
            except ValueError:
                pass
        swipe_largest(ui, direction == "down", fast=tries > 8)
        time.sleep(0.6)
    raise SystemExit(f"Control not found: {label}")


def status_line(ui):
    texts = ui.texts()
    for text in texts:
        if DONE.match(text) or text.startswith(("Аудио проверено", "Диаризация", "Распознавание", "WAV сохранён", "Запись сохранена", "Чтение")):
            return text
    return ""


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("serial")
    parser.add_argument("clip", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--wait-minutes", type=float, default=15)
    parser.add_argument("--package", default="ru.neurostenographer.app", help="e.g. ru.neurostenographer.app.a3 for the A3 test build")
    args = parser.parse_args()
    adb, _ = find_adb(None)
    ui = PhoneUi(args.serial, Path(".local/phone-ui-private"), adb)
    run = lambda *a, **k: subprocess.run([adb, "-s", args.serial, *a], capture_output=True, text=True, check=True, **k)
    name = args.clip.name
    stem = Path(name).stem
    run("shell", f"mkdir -p {FOLDER} && rm -f {FOLDER}/transcript.json '{FOLDER}/{stem}.json' '{FOLDER}/{stem}.full.json'")
    run("shell", "am", "force-stop", args.package)  # start on the home screen, not on a transcript left open
    run("push", str(args.clip), f"{FOLDER}/{name}")
    run("shell", "am", "broadcast", "-a", "android.intent.action.MEDIA_SCANNER_SCAN_FILE", "-d", f"file://{FOLDER}/{name}")
    run("shell", "am", "start", "-n", f"{args.package}/ru.neurostenographer.app.MainActivity")
    time.sleep(3)
    ui.tap_node(scroll_to(ui, "Открыть аудиофайл", direction="up"))
    time.sleep(3)
    if ui.find(label=name, timeout=1, exact=True)[1] is None:
        # A new package's picker opens at "Recent": walk the drawer to Downloads/ns-acceptance.
        ui.tap_node(ui.find(description="Показать", timeout=3)[1])
        time.sleep(2)
        ui.tap_node(scroll_to(ui, "Загрузки"))
        time.sleep(3)
        ui.tap_node(scroll_to(ui, FOLDER.rsplit("/", 1)[1]))
        time.sleep(3)
    ui.tap_node(scroll_to(ui, name))
    time.sleep(4)
    # Since 0.4.0 recognition starts by itself after the file is picked.
    started = time.monotonic()
    message = ""
    while time.monotonic() - started < args.wait_minutes * 60:
        message = status_line(ui)
        if DONE.match(message):
            break
        if ui.find(label="JSON", timeout=1, exact=True)[1] is not None:  # transcript screen: details are at its end
            for _ in range(40):
                message = status_line(ui)
                if DONE.match(message):
                    break
                swipe_largest(ui, True, fast=True)
                time.sleep(0.5)
            break
        time.sleep(5)
    timings = parse_timings(message)
    if timings is None:
        print(json.dumps({"status": "FAIL", "message": message}, ensure_ascii=False))
        return 1
    ui.tap_node(scroll_to(ui, "JSON расш.", direction="up", tries=40))  # export buttons sit at the top of the transcript
    time.sleep(3)
    ui.tap_node(scroll_to(ui, "СОХР."))
    time.sleep(3)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    target = args.out_dir / f"{Path(name).stem}.phone.json"
    run("pull", f"{FOLDER}/{stem}.full.json", str(target))  # the app names the export after the audio file
    result = {"status": "OK", "package": args.package, "clip": name, "export": str(target), "wall_s": round(time.monotonic() - started, 1), **timings}
    (args.out_dir / f"{Path(name).stem}.timings.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
