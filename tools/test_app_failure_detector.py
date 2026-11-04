"""Negative and positive cases for the app failure detector (authored logs, not device runs)."""
import unittest
from app_failure_detector import scan, scan_logcat, scan_dropbox, PACKAGE


class DetectorTests(unittest.TestCase):
    def test_clean_log_has_no_findings(self):
        self.assertEqual(scan("I ActivityManager: Start proc " + PACKAGE + "\nD x: fine\n", ""), [])

    def test_app_anr_is_found(self):
        log = f"E ActivityManager: ANR in {PACKAGE} (ru.neurostenographer.app/.MainActivity)\n"
        self.assertEqual(len(scan_logcat(log)), 1)

    def test_worker_process_anr_is_found(self):
        log = f"E ActivityManager: ANR in {PACKAGE}:diarization\n"
        self.assertEqual(len(scan_logcat(log)), 1)

    def test_foreign_anr_is_ignored_even_with_hidden_dialogs(self):
        log = "E ActivityManager: ANR in com.google.android.apps.nexuslauncher\n"
        self.assertEqual(scan_logcat(log), [])

    def test_similar_package_name_is_not_ours(self):
        log = f"E ActivityManager: ANR in {PACKAGE}.test\nF libc: Fatal signal 11 (SIGSEGV), pid 1 ({PACKAGE}x)\n"
        self.assertEqual(scan_logcat(log), [])

    def test_java_crash_of_app_found_and_of_other_ignored(self):
        mine = f"E AndroidRuntime: FATAL EXCEPTION: main\nE AndroidRuntime: Process: {PACKAGE}, PID: 12\nE AndroidRuntime: boom\n"
        other = "E AndroidRuntime: FATAL EXCEPTION: main\nE AndroidRuntime: Process: com.android.systemui, PID: 3\n"
        self.assertEqual(len(scan_logcat(mine)), 1)
        self.assertEqual(scan_logcat(other), [])

    def test_native_crash_and_memory_kill_found(self):
        log = (f"F libc: Fatal signal 11 (SIGSEGV), code 1, fault addr 0x0 in tid 9 (inference), pid 8 ({PACKAGE}:diarization)\n"
               f"I lowmemorykiller: Kill '{PACKAGE}' (123), uid 10100, oom_adj 0\n")
        self.assertEqual(len(scan_logcat(log)), 2)

    def test_foreground_service_failure_found(self):
        log = f"E AndroidRuntime: ForegroundServiceDidNotStartInTimeException {PACKAGE}/.RecordingService\n"
        self.assertEqual(len(scan_logcat(log)), 1)

    def test_deliberate_permission_revocation_kill_is_not_a_failure(self):
        log = f"I ActivityManager: Killing 123:{PACKAGE}/u0a100 (adj 0): permission revoked\n"
        self.assertEqual(scan_logcat(log), [])

    DROPBOX = (
        "========================================\n"
        "2026-11-02 20:10:05 data_app_anr (text, 100 bytes)\nProcess: {pkg}\nSubject: Input dispatching timed out\n"
        "========================================\n"
        "2026-11-02 20:11:00 data_app_crash (text, 100 bytes)\nProcess: com.other.app\n")

    def test_dropbox_anr_of_app_found_and_other_ignored(self):
        found = scan_dropbox(self.DROPBOX.format(pkg=PACKAGE))
        self.assertEqual(found, ["DropBox data_app_anr at 2026-11-02 20:10:05"])

    def test_dropbox_entries_before_the_run_are_ignored(self):
        self.assertEqual(scan_dropbox(self.DROPBOX.format(pkg=PACKAGE), since="2026-11-02 20:10:06"), [])

    def test_dropbox_untracked_tag_ignored(self):
        text = "========================================\n2026-11-02 20:10:05 system_log (text, 1 bytes)\nProcess: " + PACKAGE + "\n"
        self.assertEqual(scan_dropbox(text), [])


if __name__ == "__main__":
    unittest.main()
