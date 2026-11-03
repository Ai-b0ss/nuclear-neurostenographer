"""Run ONE audio file through the app on a physical phone and save its JSON export (acceptance helper).

  python phone_run_clip.py SERIAL CLIP.wav --out-dir DIR [--wait-minutes 15]

Steps, all through the real UI and the system document picker: the clip is pushed to
/sdcard/Download/ns-acceptance (a folder this tool owns), imported with "Импортировать аудио", processed with
"Распознать офлайн", exported with "JSON" into the same folder, pulled, and the timings shown by the app
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
                      r"Диаризация: (\d+) кластеров, (\d+) мс", message)
    if not match:
        return None
    fragments, audio, load, asr, clusters, diarization = map(int, match.groups())
    total = load + asr + diarization
    return {"fragments": fragments, "audio_ms": audio, "model_load_ms": load, "asr_ms": asr, "clusters": clusters,
            "diarization_ms": diarization, "total_ms": total, "rtf": round(total / audio, 2) if audio else None}


def scroll_to(ui, label, direction="down", tries=8, exact=True):
    for _ in range(tries):
        node = ui.find(label=label, timeout=1, exact=exact)[1]
        if node is not None:
            return node
        ui.scroll(ui.tree(), direction == "down")
        time.sleep(0.6)
    raise SystemExit(f"Control not found: {label}")


def status_line(ui):
    texts = ui.texts()
    for text in texts:
        if DONE.match(text) or text.startswith(("Аудио проверено", "Диаризация", "Распознавание", "WAV сохранён", "Чтение")):
            return text
    return ""


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("serial")
    parser.add_argument("clip", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--wait-minutes", type=float, default=15)
    args = parser.parse_args()
    adb, _ = find_adb(None)
    ui = PhoneUi(args.serial, Path(".local/phone-ui-private"), adb)
    run = lambda *a, **k: subprocess.run([adb, "-s", args.serial, *a], capture_output=True, text=True, check=True, **k)
    name = args.clip.name
    run("shell", f"mkdir -p {FOLDER} && rm -f {FOLDER}/transcript.json")
    run("push", str(args.clip), f"{FOLDER}/{name}")
    run("shell", "am", "broadcast", "-a", "android.intent.action.MEDIA_SCANNER_SCAN_FILE", "-d", f"file://{FOLDER}/{name}")
    run("shell", "am", "start", "-n", "ru.neurostenographer.app/.MainActivity")
    time.sleep(2)
    for _ in range(8):
        ui.scroll(ui.tree(), False)
    scroll_to(ui, "Импортировать аудио")
    ui.tap_node(scroll_to(ui, "Импортировать аудио"))
    time.sleep(3)
    ui.tap_node(scroll_to(ui, name))
    time.sleep(4)
    ui.tap_node(scroll_to(ui, "Распознать офлайн"))
    started = time.monotonic()
    for _ in range(8):
        ui.scroll(ui.tree(), False)
    message = ""
    while time.monotonic() - started < args.wait_minutes * 60:
        message = status_line(ui)
        if DONE.match(message):
            break
        time.sleep(5)
    timings = parse_timings(message)
    if timings is None:
        print(json.dumps({"status": "FAIL", "message": message}, ensure_ascii=False))
        return 1
    ui.tap_node(scroll_to(ui, "JSON"))
    time.sleep(3)
    ui.tap_node(scroll_to(ui, "СОХР."))
    time.sleep(3)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    target = args.out_dir / f"{Path(name).stem}.phone.json"
    run("pull", f"{FOLDER}/transcript.json", str(target))
    result = {"status": "OK", "clip": name, "export": str(target), "wall_s": round(time.monotonic() - started, 1), **timings}
    (args.out_dir / f"{Path(name).stem}.timings.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
