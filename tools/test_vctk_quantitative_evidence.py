"""Sanity checks for public VCTK evidence; no audio/model downloads in CI."""
import collections
import json
from pathlib import Path
import re
import unittest


ROOT=Path(__file__).resolve().parents[1]
DIR=ROOT/"docs/evidence"


class VctkEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest=json.loads((DIR/"speakerbook-vctk-manifest-20261111.json").read_text(encoding="utf8"))
        cls.evidence=json.loads((DIR/"speakerbook-vctk-quantitative-20261111.json").read_text(encoding="utf8"))

    def test_bounded_public_source_and_speaker_disjointness(self):
        rows=self.manifest["files"]
        self.assertEqual(len(rows),108)
        per=collections.Counter(x["speaker_id"] for x in rows)
        self.assertEqual(len(per),36)
        self.assertEqual(set(per.values()),{3})
        self.assertEqual(len({x["id"] for x in rows}),108)
        self.assertEqual(set(self.manifest["first_cohort_speakers"]).intersection(
            self.manifest["external_fresh_speakers"]),set())
        self.assertEqual(len(self.manifest["external_fresh_speakers"]),24)
        for row in rows:
            self.assertEqual(row["mic_id"],"mic2")
            self.assertRegex(row["sha256"],r"^[0-9a-f]{64}$")
            self.assertRegex(row["path"],r"^p[0-9]+_[0-9]+[.]flac$")
            self.assertNotIn("url",row)
            self.assertNotIn("text",row)

    def test_pairs_and_rejections_coherent(self):
        result=self.evidence["external_24_speakers"]
        fixed=result["fixed_0_84_pairwise"]
        calibrated=result["frozen_0_632_pairwise"]
        for x in (fixed,calibrated):
            self.assertEqual(x["positive_pairs"],72)
            self.assertEqual(x["negative_pairs"],2484)
            self.assertEqual(x["true_accept_rate"]+x["false_reject_rate"],1.)
            self.assertEqual(x["false_accept_rate"],x["false_accepts"]/2484)
        self.assertEqual(fixed["false_accepts"],0)
        self.assertEqual(calibrated["false_accepts"],10)
        unknown=result["frozen_0_632_new_speaker_detection"]
        self.assertEqual(unknown["known_probes"],48)
        self.assertEqual(unknown["unknown_probes"],72)
        self.assertEqual(unknown["false_accepted_unknown"],5)
        self.assertEqual(unknown["false_accepted_unknown"]+
                         unknown["correct_rejected_unknown"],72)

    def test_dual_agreement_is_a_proxy_not_ground_truth(self):
        p=self.evidence["external_24_speakers"]["two_temporally_separated_voiceprints_proxy"]
        self.assertEqual(p["people"],24)
        self.assertEqual(p["verified_two_part_profiles"]+
                         p["rejected_inconsistent_profiles"],24)
        self.assertEqual(p["third_utterance_correct_links"]+
                         p["third_utterance_wrong_links"]+
                         p["third_utterance_link_rejections"]+
                         p["third_utterance_no_profile"],24)
        self.assertEqual(p["third_utterance_wrong_links"],0)
        text=" ".join(self.evidence["limitations"]).lower()
        self.assertIn("not",text)
        self.assertIn("der",text)

    def test_acoustic_stress_consistent(self):
        stress=self.evidence["acoustic_stress_conditions"]
        self.assertEqual(set(stress),{"clean","noise15db","telephone_bandpass",
                                      "echo_plus_noise15db"})
        for conditions in stress.values():
            for result in conditions.values():
                self.assertEqual(result["known_probes"],48)
                self.assertEqual(result["unknown_probes"],72)
                self.assertEqual(result["correct_known_links"]+
                                 result["rejected_known"],48)
        self.assertEqual(stress["telephone_bandpass"]["fixed_0_84"]
                         ["correct_known_links"],0)


if __name__=="__main__":
    unittest.main()
