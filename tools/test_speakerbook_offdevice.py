"""Guard regressions for off-device Android QA."""
import unittest
from run_speakerbook_emulator_qa import accepted_result, verify_emulator


class EmulatorIsolation(unittest.TestCase):
    def test_physical_serial_refused_even_with_spoofed_properties(self):
        with self.assertRaises(ValueError):
            verify_emulator("AKPNU20B24113866", "1", "x86_64")

    def test_physical_properties_refused_with_emulator_serial(self):
        for qemu, abi in [("0", "x86_64"), ("1", "arm64-v8a"), ("", "")]:
            with self.assertRaises(ValueError):
                verify_emulator("emulator-5554", qemu, abi)

    def test_x86_emulator_accepted(self):
        verify_emulator("emulator-5554", "1\n", "x86_64\n")

    def test_shell_exit_or_skipped_junit_cannot_establish_success(self):
        record = {"status": "PASS", "execution_environment": "ANDROID_X86_64_EMULATOR_NOT_PHONE"}
        for output in ["", "OK (0 tests)", "FAILURES!!! Tests run: 1, Failures: 1"]:
            self.assertFalse(accepted_result(output, record))

    def test_stale_or_physical_evidence_cannot_establish_success(self):
        for record in [{}, {"status": "RUNNING"},
                       {"status": "PASS", "execution_environment": "PHYSICAL_ANDROID"}]:
            self.assertFalse(accepted_result("OK (1 test)", record))

    def test_both_junit_and_current_emulator_evidence_required(self):
        self.assertTrue(accepted_result("Time: 10\nOK (1 test)\n",
            {"status": "PASS", "execution_environment": "ANDROID_X86_64_EMULATOR_NOT_PHONE"}))


if __name__ == "__main__":
    unittest.main()
