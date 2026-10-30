"""Drive disposable cloud Android UI using tree-derived controls, not guessed pixels.

Run AFTER the real inference instrumentation suite in an isolated installation.
Never use against a personal device/app data. Captures UI/metadata, not audio.
"""
import argparse
import json
import hashlib
from pathlib import Path
import re
import subprocess
import struct
import time
import xml.etree.ElementTree as ET
from verify_transcript_exports import verify as verify_transcript_files

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

    @staticmethod
    def matches(node, label=None, resource_suffix=None, class_name=None, description=None, exact=False):
        if label is not None:
            text = node.get("text", "")
            if not (text.casefold() == label.casefold() if exact else label in text):
                return False
        if resource_suffix is not None and not node.get("resource-id", "").endswith(resource_suffix):
            return False
        if class_name is not None and node.get("class") != class_name:
            return False
        if description is not None and node.get("content-desc", "").casefold() != description.casefold():
            return False
        return any(v is not None for v in (label, resource_suffix, class_name, description))

    def find(self, label=None, resource_suffix=None, timeout=12, class_name=None, description=None, exact=False):
        deadline = time.monotonic() + timeout
        while True:
            root = self.tree()
            found = [n for n in root.iter("node") if self.matches(n, label, resource_suffix, class_name, description, exact)]
            if found:
                if len(found) != 1:
                    raise AssertionError("Ambiguous UI selector; no control was selected")
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

    def visible(self, label, exact=False):
        root, node = self.find(label=label, timeout=1, exact=exact)
        if node is not None:
            return root, node
        # Search both directions. Each swipe comes from current UI-tree bounds.
        for down in [True] * 4 + [False] * 7:
            if not self.scroll(root, down):
                break
            root, node = self.find(label=label, timeout=0, exact=exact)
            if node is not None:
                return root, node
        raise AssertionError(f"UI control/text not found: {label}")

    def tap_node(self, node):
        x1, y1, x2, y2 = self.bounds(node)
        self.shell("input", "tap", str((x1 + x2) // 2), str((y1 + y2) // 2))

    def tap(self, label=None, resource_suffix=None, description=None, exact=False):
        if label is not None and resource_suffix is None and description is None:
            # Buttons use exact labels. A status sentence may repeat the action
            # name; substring selection must not choose that sentence instead.
            root, node = self.visible(label, exact=True)
        else:
            root, node = self.find(label=label, resource_suffix=resource_suffix, description=description, exact=exact)
            if node is None:
                raise AssertionError(f"UI resource missing: {resource_suffix}")
        self.tap_node(node)

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

    def downloads(self):
        root, node = self.find(description="Show roots", timeout=2)
        if node is None:
            root, node = self.find(description="Show navigation drawer", timeout=2)
        if node is None:
            raise AssertionError("Document picker root navigation missing")
        self.tap_node(node)
        self.tap(label="Downloads", exact=True)

    def save_document(self, format, rotate=False):
        self.tap(label=format.upper(), exact=True)
        self.downloads()
        root, field = self.find(class_name="android.widget.EditText")
        if field is None:
            raise AssertionError("Document filename field missing")
        current = field.get("text", "")
        if not re.fullmatch(r"transcript\.(txt|json|srt)", current):
            raise AssertionError("Unexpected initial document filename")
        self.tap_node(field)
        self.shell("input", "keyevent", "KEYCODE_MOVE_END")
        self.shell("input", "keyevent", *(["KEYCODE_DEL"] * len(current)))
        name = "neuro-qa-ui." + format
        self.shell("input", "text", name)
        keyboard = self.shell("dumpsys", "input_method")
        if re.search(r"mInputShown\s*[=:]\s*true", keyboard):
            self.shell("input", "keyevent", "KEYCODE_BACK")
        if rotate:
            self.shell("settings", "put", "system", "user_rotation", "1")
            self.screenshot("picker-rotated", landscape=True)
            self.shell("settings", "put", "system", "user_rotation", "0")
        self.tap(label="Save", exact=True)
        self.visible(f"Экспорт {format} сохранён")
        body = self.command("exec-out", "cat", "/sdcard/Download/" + name)
        (self.directory / name).write_bytes(body)
        return body


def verify_saved_exports(exports, expected_runtime, directory):
    # This checks actual provider-saved files, not an app success message alone.
    data = json.loads(exports["json"].decode("utf-8"))
    if data["provenance"]["runtime_sha256"] != expected_runtime:
        raise AssertionError("Saved JSON runtime identity mismatch")
    segments = data["segments"]
    if not segments or not any("у лукоморья дуб зеленый" in s["text"] for s in segments):
        raise AssertionError("Public Russian fixture phrase missing from saved JSON")
    for format in ("txt", "srt"):
        body = exports[format].decode("utf-8")
        if not all(s["text"] in body for s in segments):
            raise AssertionError("Saved export text differs across formats")
    if " --> " not in exports["srt"].decode("utf-8"):
        raise AssertionError("Saved SRT cues missing")
    verify_transcript_files(directory, prefix="neuro-qa-ui")
    return {format: {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()} for format, body in exports.items()}


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

    # Public checksum-verified fixture only; never an owner's recording. It is
    # pushed transiently, not included in the collected UI artifact.
    fixture = Path(".local/androidTestAssets/example.wav")
    if hashlib.sha256(fixture.read_bytes()).hexdigest() != "d8aaaa18a5098d7c6de0595ae7ac1e64cacd0d4022af3595213bdaf23be77e69":
        raise AssertionError("Unexpected public UI import fixture")
    ui.command("push", str(fixture), "/sdcard/Download/neuro-qa-public.wav")
    ui.shell("am", "broadcast", "-a", "android.intent.action.MEDIA_SCANNER_SCAN_FILE", "-d", "file:///sdcard/Download/neuro-qa-public.wav")
    ui.tap(label="Импортировать аудио")
    ui.downloads()
    ui.tap(label="neuro-qa-public.wav", exact=True)
    ui.visible("Аудио проверено")
    checks.append("public_wav_import_through_system_document_picker")
    ui.tap(label="Распознать офлайн")
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        root, node = ui.find(label="JSON", exact=True, timeout=0)
        if node is not None:
            break
        ui.scroll(root, True)
        time.sleep(0.5)
    else:
        raise AssertionError("Public Russian UI inference timed out")
    ui.tap(label="TXT", exact=True)
    _, field = ui.find(class_name="android.widget.EditText")
    if field is None:
        raise AssertionError("Cancellation test did not open document picker")
    for _ in range(2):
        ui.shell("input", "keyevent", "KEYCODE_BACK")
        _, field = ui.find(class_name="android.widget.EditText", timeout=0)
        if field is None:
            break
    ui.visible("JSON")
    checks.append("cancelled_system_export_keeps_transcript_available")
    exports = {format: ui.save_document(format, rotate=format == "json") for format in ["txt", "json", "srt"]}
    runtime = json.loads(Path(".local/runtime-selection.json").read_text())["sha256"]
    export_evidence = verify_saved_exports(exports, runtime, ui.directory)
    checks.append("real_txt_json_srt_saved_and_read_from_documents_provider")
    checks.append("pending_json_export_survives_picker_rotation")
    ui.tap(label="Удалить локальное аудио и результат")
    ui.visible("WAV не выбран")
    for format, body in exports.items():
        if ui.command("exec-out", "cat", "/sdcard/Download/neuro-qa-ui." + format) != body:
            raise AssertionError("App cleanup modified provider-owned exports")
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
            "private_audio_collected": False, "saved_public_exports": export_evidence}


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
