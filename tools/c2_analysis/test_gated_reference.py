"""Regression tests for the energy gate on synthetic levels; no audio or model."""
import unittest

import numpy as np

from gated_reference import gate


def turn(start, end, speaker):
    return {"start_ms": start, "end_ms": end, "speaker_id": speaker}


class Gate(unittest.TestCase):
    def levels(self, caller_db, callee_db, frames=500):
        return [np.full(frames, -120.0), np.full(frames, -120.0)] if caller_db is None else [np.array(caller_db, dtype=float), np.array(callee_db, dtype=float)]

    def test_label_over_a_silent_channel_is_removed(self):
        # The ru_000001 defect: a caller label where the caller channel sits near -86 dBFS.
        caller = np.full(500, -86.0)
        callee = np.full(500, -120.0)
        callee[100:200] = -25.0
        out = gate([turn(0, 4000, "caller"), turn(2000, 4000, "callee")], [caller, callee], 10000)
        self.assertEqual([t for t in out if t["speaker_id"] == "caller"], [])
        self.assertEqual([t for t in out if t["speaker_id"] == "callee"], [turn(2000, 4000, "callee")])

    def test_loud_labelled_speech_is_kept(self):
        caller = np.full(500, -120.0)
        caller[50:150] = -24.0
        out = gate([turn(1000, 3000, "caller")], [caller, np.full(500, -120.0)], 10000)
        self.assertEqual(out, [turn(1000, 3000, "caller")])

    def test_gate_never_adds_unlabelled_speech(self):
        loud = np.full(500, -20.0)
        self.assertEqual(gate([], [loud, loud], 10000), [])

    def test_quiet_frames_split_a_turn_and_short_pieces_drop(self):
        caller = np.full(500, -120.0)
        caller[0:100] = -25.0      # 0-2000 ms loud
        caller[100:110] = -90.0    # 200 ms silent inside the label: merged back (gap <= 200 ms)
        caller[110:200] = -25.0
        caller[300:305] = -25.0    # a 100 ms blip inside another label: dropped as shorter than 250 ms
        out = gate([turn(0, 4000, "caller"), turn(6000, 6100, "caller")], [caller, np.full(500, -120.0)], 10000)
        self.assertEqual(out, [turn(0, 4000, "caller")])


if __name__ == "__main__":
    unittest.main()
