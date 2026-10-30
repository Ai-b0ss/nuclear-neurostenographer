"""Execute collector with fake commands to test failures, NOT Android behavior."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASH = "C:/Program Files/Git/bin/bash.exe" if os.name == "nt" else shutil.which("bash")


@unittest.skipUnless(BASH and Path(BASH).exists(), "Bash unavailable")
class CollectorTests(unittest.TestCase):
    def run_collector(self, gradle_code, adb_fail=False, false_success=False, ui_code=0):
        (ROOT / ".local").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".local") as tmp:
            root = Path(tmp)
            startup = root / "fake-commands.sh"
            startup.write_text('''
adb() {
  if [[ "$*" == *"files/inference-evidence/asr-0.json"* ]]; then
    printf '{"fixture":"FAKE_COLLECTOR_UNIT_TEST"}'
    return 0
  elif [[ "$*" == *"exec-out"* ]]; then
    if [[ "$FAKE_ADB_FALSE_SUCCESS" == 1 ]]; then
      echo 'run-as: unknown package: ru.neurostenographer.app'
      return 0
    elif [[ "$FAKE_GRADLE_EXIT" == 0 && "$FAKE_ADB_EXIT" == 0 ]]; then
      printf '{"fixture":"FAKE_COLLECTOR_UNIT_TEST"}'
      return 0
    fi
    return 1
  elif [[ "$*" == *"logcat -d"* ]]; then
    echo FAKE_LOG
    return 0
  elif [[ "$*" == *"svc wifi"* ]]; then
    return "$FAKE_ADB_EXIT"
  fi
  return 0
}
gradle() { echo FAKE_GRADLE; return "$FAKE_GRADLE_EXIT"; }
python3() {
  if [[ "$*" == *"run_android_ui.py"* ]]; then
    echo FAKE_UI_FLOW_NOT_ANDROID
    return "$FAKE_UI_EXIT"
  fi
  "$TEST_PYTHON" "$@"
}
''', encoding="utf-8", newline="\n")
            # A stale collector-owned output must disappear when retrieval fails.
            (root / "device-evidence").mkdir()
            (root / "device-evidence/asr-1.json").write_text('{"old":true}')
            (root / "device-evidence/codec-import.json").write_text('{"old_codec":true}')
            (root / "device-evidence/recording.json").write_text('{"old_recording":true}')
            (root / "device-evidence/worker-lifecycle.json").write_text('{"old_worker":true}')
            (root / "device-evidence/mixture.json").write_text('{"old_mixture":true}')
            (root / "device-evidence/recording-pipeline.json").write_text('{"old_pipeline":true}')
            env = dict(os.environ, BASH_ENV=startup.as_posix(), FAKE_GRADLE_EXIT=str(gradle_code),
                       FAKE_ADB_EXIT="9" if adb_fail else "0", FAKE_ADB_FALSE_SUCCESS="1" if false_success else "0",
                       TEST_PYTHON=Path(sys.executable).as_posix(), FAKE_UI_EXIT=str(ui_code))
            completed = subprocess.run([BASH, (ROOT / "tools/run_android_inference.sh").as_posix()],
                                       cwd=root, env=env, capture_output=True, text=True)
            expected = 9 if adb_fail else gradle_code or ui_code or (1 if false_success else 0)
            self.assertEqual(completed.returncode, expected, completed.stderr)
            self.assertEqual(json.loads((root / "device-evidence/asr-0.json").read_text())["fixture"], "FAKE_COLLECTOR_UNIT_TEST")
            complete = not adb_fail and gradle_code == 0 and not false_success
            for name in ["asr-1", "codec-import", "recording", "worker-lifecycle", "mixture", "recording-pipeline"]:
                self.assertEqual(complete, (root / f"device-evidence/{name}.json").exists())
            report = json.loads((root / "device-evidence/collection-summary.json").read_text())
            self.assertEqual(complete, report["complete"])
            if false_success:
                self.assertIn("asr-1", report["invalid"])
            self.assertIn("FAKE_LOG", (root / "asr-evidence.txt").read_text())
            if adb_fail:
                self.assertNotIn("FAKE_GRADLE", completed.stdout)

    def test_success(self):
        self.run_collector(0)

    def test_gradle_failure_preserved_with_evidence(self):
        self.run_collector(7)

    def test_adb_failure_does_not_run_gradle_or_hide_failure(self):
        self.run_collector(0, adb_fail=True)

    def test_zero_exit_adb_error_is_not_json_evidence_or_green_run(self):
        self.run_collector(0, false_success=True)

    def test_ui_failure_preserved_with_completed_instrumentation_collection(self):
        self.run_collector(0, ui_code=5)


if __name__ == "__main__":
    unittest.main()
