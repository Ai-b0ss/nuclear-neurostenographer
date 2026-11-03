"""run_c2_phone.sh against a fake adb and gradle: proves what the script would install and uninstall. No phone is used."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().with_name("run_c2_phone.sh")
BASH = "C:/Program Files/Git/bin/bash.exe" if os.name == "nt" else shutil.which("bash")
CONTEST = "ru.neurostenographer.app"

FAKE_ADB = r'''#!/usr/bin/env bash
[ "$1" = -s ] && shift 2
echo "$*" >> "$FAKE/adb.log"
state="$FAKE/installed"
case "$*" in
  get-state) echo device ;;
  "shell getprop ro.product.model") echo "$FAKE_MODEL" ;;
  "shell getprop ro.product.cpu.abi") echo arm64-v8a ;;
  "shell settings get global airplane_mode_on") echo 1 ;;
  "shell pm list packages "*) p=${@: -1}; grep -qx "$p" "$state" && echo "package:$p" ;;
  "shell dumpsys package $CONTEST") echo "    versionCode=1 minSdk=26"; echo "    firstInstallTime=2026-11-03 10:00:00"; echo "    lastUpdateTime=$(cat "$FAKE/contest-update")" ;;
  "shell ls -lR /sdcard/Android/data/$CONTEST/files") echo "kits:"; echo "-rw-rw---- 1 u0 u0 123 2026-11-03 10:01 gigaam-v3.zip" ;;
  "shell run-as $CONTEST ls -lR files") echo "models:" ;;
  "exec-out run-as $CONTEST.c2 cat files/nemotron-evidence.json") echo '{"device": {}, "runs": []}' ;;
  "uninstall "*) p=${@: -1}; grep -vx "$p" "$state" > "$state.new"; mv "$state.new" "$state"; echo Success ;;
  *) : ;;
esac
'''

FAKE_GRADLE = r'''#!/usr/bin/env bash
echo "$*" >> "$FAKE/gradle.log"
case "$*" in *nemotronPrototype=true*) printf '%s\n%s\n' "$CONTEST.c2" "$CONTEST.c2.test" >> "$FAKE/installed" ;; esac
[ "$FAKE_TOUCH_CONTEST" = 1 ] && echo "2026-11-04 09:00:00" > "$FAKE/contest-update"
exit 0
'''


@unittest.skipUnless(BASH and Path(BASH).exists(), "Bash unavailable")
class PhoneScript(unittest.TestCase):
    def run_script(self, handover=True, installed=(CONTEST,), suffix=True, touch_contest=False):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            fake, work, bin_dir = root / "fake", root / "work", root / "bin"
            for d in (fake, work / "app", bin_dir):
                d.mkdir(parents=True)
            (fake / "installed").write_text("".join(p + "\n" for p in installed), encoding="utf-8")
            (fake / "contest-update").write_text("2026-11-03 10:00:00\n", encoding="utf-8")
            (work / "app/build.gradle.kts").write_text('defaultConfig.applicationIdSuffix = ".c2"\n' if suffix else "android {}\n", encoding="utf-8")
            for name, body in (("adb", FAKE_ADB), ("gradle", FAKE_GRADLE), ("python3", f'#!/usr/bin/env bash\nexec "{Path(sys.executable).as_posix()}" "$@"\n')):
                (bin_dir / name).write_text(body, encoding="utf-8", newline="\n")
                (bin_dir / name).chmod(0o755)
            env = dict(os.environ, FAKE=fake.as_posix(), FAKE_MODEL="DNN-LX9", CONTEST=CONTEST, ANDROID_SERIAL="FAKE", EXPECTED_MODEL="DNN-LX9",
                       OUT=(work / "out").as_posix(), FAKE_TOUCH_CONTEST="1" if touch_contest else "0")
            if handover:
                env["HANDOVER_CONFIRMED"] = "1"
            # A drive letter's colon would split PATH in Git Bash, so convert it there.
            bin_path = f'$(cygpath -u "{bin_dir.as_posix()}")' if os.name == "nt" else bin_dir.as_posix()
            command = f'export PATH="{bin_path}:$PATH"; bash "{SCRIPT.as_posix()}"'
            done = subprocess.run([BASH, "-c", command], cwd=work, env=env, capture_output=True, text=True)
            read = lambda p: p.read_text(encoding="utf-8") if p.exists() else ""
            exit_codes = work / "out/exit-codes.json"
            return {"code": done.returncode, "out": done.stdout + done.stderr, "adb": read(fake / "adb.log"), "gradle": read(fake / "gradle.log"),
                    "installed": read(fake / "installed").split(), "exit": json.loads(exit_codes.read_text()) if exit_codes.exists() else None}

    def test_no_handover_no_device_access(self):
        r = self.run_script(handover=False)
        self.assertEqual(r["code"], 2)
        self.assertEqual(r["adb"], "")

    def test_only_the_c2_packages_are_installed_and_removed(self):
        r = self.run_script()
        self.assertEqual(r["code"], 0, r["out"])
        uninstalled = [line.split()[1] for line in r["adb"].splitlines() if line.startswith("uninstall ")]
        self.assertEqual(sorted(uninstalled), [CONTEST + ".c2", CONTEST + ".c2.test"])
        self.assertEqual(r["installed"], [CONTEST])
        self.assertIn("class=ru.neurostenographer.app.NemotronBenchmarkTest", r["gradle"])
        self.assertEqual(r["exit"]["contest_app_untouched"], True)
        self.assertEqual(r["exit"]["prototype_left_installed"], False)

    def test_a_changed_contest_app_is_reported(self):
        r = self.run_script(touch_contest=True)
        self.assertEqual(r["exit"]["contest_app_untouched"], False)
        self.assertIn("WARNING", r["out"])

    def test_leftover_prototype_stops_before_gradle(self):
        r = self.run_script(installed=(CONTEST, CONTEST + ".c2"))
        self.assertEqual(r["code"], 2)
        self.assertEqual(r["gradle"], "")
        self.assertNotIn("uninstall", r["adb"])

    def test_checkout_without_suffix_stops_before_gradle(self):
        r = self.run_script(suffix=False)
        self.assertEqual(r["code"], 2)
        self.assertEqual(r["gradle"], "")


if __name__ == "__main__":
    unittest.main()
