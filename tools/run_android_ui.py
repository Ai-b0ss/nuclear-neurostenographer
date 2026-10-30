"""Drive disposable cloud Android UI using tree-derived controls, not guessed pixels.

Run AFTER the real inference instrumentation suite in an isolated installation.
Never use against a personal device/app data. Captures UI/metadata, not audio.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import struct
import time
import xml.etree.ElementTree as ET

PACKAGE = "ru.neurostenographer.app"


class AndroidUi:
    def __init__(self, directory, adb="adb"):
        self.directory, self.adb = directory, adb
        directory.mkdir(parents=True, exist_ok=True)
        self.index = 0
        self.checks = []

    def command(self, *arguments):
        return subprocess.check_output([self.adb, *arguments], timeout=30)

    def shell(self, *arguments):
        return self.command("shell", *arguments).decode("utf-8", errors="replace")

    def tree(self):
        raw = self.command("exec-out", "uiautomator", "dump", "/dev/tty").decode("utf-8")
        start, end = raw.find("<?xml"), raw.rfind("</hierarchy>")
        if start < 0 or end < start:
            raise ValueError("No UI hierarchy returned")
        text = raw[start:end + len("</hierarchy>")]
        (self.directory / f"tree-{self.index:03}.xml").write_text(text, encoding="utf-8")
        self.index += 1
        return ET.fromstring(text)

    @staticmethod
    def bounds(node):
        values = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", node.get("bounds", ""))
        if not values:
            raise ValueError("Control has no valid bounds")
        x1, y1, x2, y2 = map(int, values.groups())
        if x1 >= x2 or y1 >= y2:
            raise ValueError("Control is outside visible bounds")
        return x1, y1, x2, y2

    def find(self, label=None, resource_suffix=None, timeout=12):
        deadline = time.monotonic() + timeout
        while True:
            root = self.tree()
            found = [n for n in root.iter("node") if
                     (label is not None and label in n.get("text", "")) or
                     (resource_suffix is not None and n.get("resource-id", "").endswith(resource_suffix))]
            if found:
                return root, found[0]
            if time.monotonic() >= deadline:
                return root, None
            time.sleep(0.3)

    def scroll(self, root, down):
        candidates = [n for n in root.iter("node") if n.get("scrollable") == "true"]
        if not candidates:
            return False
        x1, y1, x2, y2 = self.bounds(candidates[0])
        x, top, bottom = (x1 + x2) // 2, y1 + (y2 - y1) // 4, y1 + (y2 - y1) * 3 // 4
        self.shell("input", "swipe", str(x), str(bottom if down else top), str(x),
                   str(top if down else bottom), "350")
        return True

    def visible(self, label):
        root, node = self.find(label=label, timeout=1)
        if node is not None:
            return root, node
        # Search both directions. Each swipe comes from current UI-tree bounds.
        for down in [True] * 4 + [False] * 7:
            if not self.scroll(root, down):
                break
            root, node = self.find(label=label, timeout=0)
            if node is not None:
                return root, node
        raise AssertionError(f"UI control/text not found: {label}")

    def tap(self, label=None, resource_suffix=None):
        if label is not None:
            root, node = self.visible(label)
        else:
            root, node = self.find(resource_suffix=resource_suffix)
            if node is None:
                raise AssertionError(f"UI resource missing: {resource_suffix}")
        self.bounds(node)
        x1, y1, x2, y2 = self.bounds(node)
        self.shell("input", "tap", str((x1 + x2) // 2), str((y1 + y2) // 2))

    def screenshot(self, name, landscape=False):
        deadline = time.monotonic() + 15
        while True:
            data = self.command("exec-out", "screencap", "-p")
            if not data.startswith(b"\x89PNG\r\n\x1a\n"):
                raise ValueError("Screenshot is not PNG")
            width, height = struct.unpack_from(">II", data, 16)
            (self.directory / (name + ".png")).write_bytes(data)
            if not landscape or width > height:
                return width, height
            if time.monotonic() >= deadline:
                raise AssertionError("Emulator did not enter landscape")
            time.sleep(0.3)

    def launch(self):
        self.shell("am", "start", "-W", "-n", PACKAGE + "/.MainActivity")


def run(ui):
    checks = ui.checks
    ui.shell("am", "force-stop", PACKAGE)
    ui.shell("pm", "revoke", PACKAGE, "android.permission.RECORD_AUDIO")
    ui.shell("pm", "clear-permission-flags", PACKAGE, "android.permission.RECORD_AUDIO", "user-set", "user-fixed")
    ui.launch()
    ui.visible("Нейро-стенографист")
    ui.screenshot("initial")
    ui.tap(label="Записать разговор")
    ui.tap(resource_suffix="permission_deny_button")
    ui.visible("Разрешение микрофона отклонено")
    checks.append("real_permission_dialog_denied")

    ui.tap(label="Записать разговор")
    ui.tap(resource_suffix="permission_allow_foreground_only_button")
    ui.visible("Остановить запись")
    checks.append("foreground_permission_starts_recording")
    ui.shell("settings", "put", "system", "accelerometer_rotation", "0")
    ui.shell("settings", "put", "system", "user_rotation", "1")
    ui.screenshot("rotated-recording", landscape=True)
    ui.visible("Остановить запись")
    checks.append("recording_survives_rotation")
    ui.shell("input", "keyevent", "KEYCODE_HOME")
    time.sleep(2)
    ui.launch()
    ui.visible("Записать разговор")
    ui.visible("WAV сохранён")
    checks.append("background_stops_and_finalizes_recording")
    ui.shell("settings", "put", "system", "user_rotation", "0")
    ui.tap(label="Распознать офлайн")
    # Actual native work runs in the app, never via remote ASR.
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        root, button = ui.find(label="JSON", timeout=0)
        if button is not None:
            break
        ui.scroll(root, True)
        time.sleep(0.5)
    else:
        raise AssertionError("Recorded-input transcription/export UI timed out")
    ui.screenshot("recorded-transcript")
    checks.append("recorded_input_reaches_real_transcript_export_controls")
    ui.tap(label="Удалить локальное аудио и результат")
    ui.visible("WAV не выбран")
    checks.append("ui_audio_cleanup_clears_source")

    ui.tap(label="Записать разговор")
    ui.visible("Остановить запись")
    prior_pid = ui.shell("pidof", PACKAGE).strip()
    ui.shell("pm", "revoke", PACKAGE, "android.permission.RECORD_AUDIO")
    ui.launch()
    ui.visible("Записать разговор")
    ui.visible("WAV не выбран")
    next_pid = ui.shell("pidof", PACKAGE).strip()
    if not prior_pid or not next_pid or prior_pid == next_pid:
        raise AssertionError("Expected Android permission-revocation process restart")
    checks.append("permission_revocation_restarts_without_phantom_recording")
    ui.tap(label="Удалить локальное аудио и результат")
    ui.visible("Локальные аудиокопии и результат очищены")
    ui.screenshot("final-clean")
    return {"status": "PASS", "checks": checks,
            "scope": "Disposable emulator UI and lifecycle; not physical-phone or microphone speech accuracy",
            "private_audio_collected": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("device-evidence/ui"))
    parser.add_argument("--adb", default="adb")
    args = parser.parse_args()
    ui = AndroidUi(args.output, args.adb)
    report_file = args.output / "ui-flow.json"
    report_file.unlink(missing_ok=True)
    try:
        report = run(ui)
    except Exception as error:
        report = {"status": "FAIL", "error": str(error), "checks_completed": ui.checks,
                  "scope": "Disposable emulator UI flow"}
        try:
            ui.screenshot("failure")
            ui.tree()
        except Exception:
            pass
    finally:
        # Only disposable emulator settings are touched; never the owner's PC.
        try:
            ui.shell("settings", "put", "system", "user_rotation", "0")
        except Exception as cleanup:
            report.update(status="FAIL", cleanup_error=type(cleanup).__name__)
    report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
