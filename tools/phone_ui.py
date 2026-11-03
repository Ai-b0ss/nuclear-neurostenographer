"""Drive the app UI on ONE physical phone by serial (never an emulator), for acceptance runs.

  python phone_ui.py SERIAL shot NAME            # screenshot -> .local/phone-ui-private/NAME.png (git-ignored: it can show personal file names)
  python phone_ui.py SERIAL texts                # visible texts on the current screen
  python phone_ui.py SERIAL tap "Импортировать аудио"   # tap the control whose text contains this
  python phone_ui.py SERIAL tapdesc "Поиск"        # tap by content description (icons)
  python phone_ui.py SERIAL scroll down|up
  python phone_ui.py SERIAL key BACK|HOME

Same tree-derived controls as run_android_ui.py (no guessed pixels). Only taps controls the
operator names, so it never clicks system dialogs by itself. Metadata and screenshots only.
"""
import subprocess
import sys
from pathlib import Path

from run_android_ui import AndroidUi

DEFAULT_ADB = None


class PhoneUi(AndroidUi):
    def __init__(self, serial, directory, adb="adb"):
        if serial.startswith("emulator-"):
            raise SystemExit("Refusing to drive an emulator as the physical phone")
        super().__init__(directory, adb)
        self.serial = serial

    def command(self, *arguments):
        return subprocess.check_output([self.adb, "-s", self.serial, *arguments], timeout=60)

    def texts(self):
        root = self.tree()
        return [n.get("text") or n.get("content-desc") for n in root.iter("node")
                if (n.get("text") or n.get("content-desc"))]

    def png(self, name):
        target = self.directory / f"{name}.png"
        target.write_bytes(self.command("exec-out", "screencap", "-p"))
        return target


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    serial, action, rest = sys.argv[1], sys.argv[2], sys.argv[3:]
    from phone_kit import find_adb
    adb, _ = find_adb(None)
    ui = PhoneUi(serial, Path(".local/phone-ui-private"), adb)
    if action == "shot":
        print(ui.png(rest[0]))
    elif action == "texts":
        print("\n".join(ui.texts()))
    elif action == "tap":
        node = ui.find(label=rest[0], timeout=5, exact=len(rest) > 1 and rest[1] == "exact")[1]
        if node is None:
            sys.exit(f"Not found: {rest[0]}")
        ui.tap_node(node)
    elif action == "tapdesc":
        node = ui.find(description=rest[0], timeout=5)[1]
        if node is None:
            sys.exit(f"Not found: {rest[0]}")
        ui.tap_node(node)
    elif action == "scroll":
        ui.scroll(ui.tree(), rest[0] == "down")
    elif action == "key":
        ui.shell("input", "keyevent", f"KEYCODE_{rest[0]}")
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
