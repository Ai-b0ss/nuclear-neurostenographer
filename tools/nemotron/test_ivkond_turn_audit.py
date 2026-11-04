"""Guard against scoring DER from utterance extents padded with silence."""

import unittest

import numpy as np

from provision_independent_ivkond import turn_label_audit


class TurnLabelAuditTest(unittest.TestCase):
    def test_almost_full_coverage_with_silent_pauses_is_rejected(self):
        # The pinned clean case covered 94.9% of the recording and still
        # labelled 43.5% low-energy frames as speech; the old 96% gate missed it.
        audio = np.zeros(50 * 16000, dtype=np.float32)
        audio[:27 * 16000] = 0.1
        audit = turn_label_audit([{"start_ms": 0, "end_ms": 47500}], audio)
        self.assertLess(audit["coverage"], 0.96)
        self.assertGreater(audit["silent_labelled"], 0.33)
        self.assertFalse(audit["der_usable"])

    def test_short_exact_speech_interval_is_accepted(self):
        audio = np.zeros(10 * 16000, dtype=np.float32)
        audio[2 * 16000:5 * 16000] = 0.1
        audit = turn_label_audit([{"start_ms": 2000, "end_ms": 5000}], audio)
        self.assertTrue(audit["der_usable"])


if __name__ == "__main__":
    unittest.main()
