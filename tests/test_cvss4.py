from __future__ import annotations

import unittest

from rapid_os.domain.cvss4 import base_score, parse_vector, score_vector, severity_for_score

LOW_LOCAL = "CVSS:4.0/AV:L/AC:H/AT:P/PR:H/UI:P/VC:H/VI:N/VA:N/SC:N/SI:N/SA:N"
CRITICAL = "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N"
NO_IMPACT = "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:N/VI:N/VA:N/SC:N/SI:N/SA:N"


class Cvss4ScoreTests(unittest.TestCase):
    def test_scores_match_the_first_calculator(self):
        self.assertEqual(score_vector(LOW_LOCAL), (4.1, "medium"))
        self.assertEqual(score_vector(CRITICAL), (9.3, "critical"))
        self.assertEqual(
            score_vector("CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:H/SI:H/SA:H"), (10.0, "critical")
        )
        self.assertEqual(
            score_vector("CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:P/VC:L/VI:L/VA:N/SC:N/SI:N/SA:N"), (5.3, "medium")
        )

    def test_no_impact_scores_zero_and_none(self):
        self.assertEqual(score_vector(NO_IMPACT), (0.0, "none"))

    def test_severity_bands_follow_the_specification(self):
        for score, expected in (
            (0.0, "none"), (0.1, "low"), (3.9, "low"), (4.0, "medium"), (6.9, "medium"),
            (7.0, "high"), (8.9, "high"), (9.0, "critical"), (10.0, "critical"),
        ):
            with self.subTest(score=score):
                self.assertEqual(severity_for_score(score), expected)

    def test_score_stays_within_range_for_a_sample_of_vectors(self):
        for av in "NALP":
            for impact in "HLN":
                metrics = parse_vector(
                    f"CVSS:4.0/AV:{av}/AC:L/AT:N/PR:N/UI:N/VC:{impact}/VI:N/VA:N/SC:N/SI:N/SA:N"
                )
                self.assertTrue(0.0 <= base_score(metrics) <= 10.0)

    def test_malformed_vectors_are_rejected(self):
        for vector in (
            "CVSS:3.1/AV:N", "AV:N", LOW_LOCAL.replace("AV:L/AC:H", "AC:H/AV:L"),
            CRITICAL + "/E:A", CRITICAL.replace("VC:H", "VC:X"), CRITICAL.rsplit("/", 1)[0], None,
        ):
            with self.subTest(vector=vector), self.assertRaises(ValueError):
                parse_vector(vector)


if __name__ == "__main__":
    unittest.main()
