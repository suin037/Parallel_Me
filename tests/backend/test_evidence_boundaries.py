import unittest

import indicators
from rag.psych_narrative import get_psych_evidence
from rag.psych_retriever import _load_cards
from stat_evidence import _is_statistical_source


class EvidenceBoundaryTests(unittest.TestCase):
    def test_job_model_does_not_claim_unvalidated_indicators(self):
        statuses = indicators.evidence_statuses(
            "이직",
            {"population_evidence": {"effect": 0.08, "ci95": [0.02, 0.14]}},
        )
        self.assertEqual(statuses["경제적안정도"]["status"], "directional_evidence")
        self.assertEqual(statuses["성장가능성"]["status"], "insufficient_evidence")
        self.assertEqual(statuses["삶의질"]["status"], "insufficient_evidence")
        self.assertEqual(indicators.psych_eligible_scores(statuses), {})

    def test_explicit_current_state_can_feed_psych_rag(self):
        scores = {"경제적안정도": 0.6, "성장가능성": 0.2, "삶의질": 0.7}
        statuses = indicators.evidence_statuses("이직", provided_scores=scores)
        eligible = indicators.psych_eligible_scores(statuses)
        result = get_psych_evidence(
            eligible,
            eligible_indicators=eligible.keys(),
            basis="user_provided_state",
        )
        self.assertEqual(result["focus_indicator"], "성장가능성")
        self.assertEqual(result["basis"], "user_provided_state")

    def test_matched_observations_upgrade_display_evidence_not_psych_score(self):
        statuses = indicators.evidence_statuses("이직", {
            "observed_outcomes": {"domains": {
                "growth": [{"available": True}],
                "quality_of_life": [{"available": True}],
            }}
        })
        self.assertEqual(statuses["성장가능성"]["status"], "matched_observation")
        self.assertEqual(statuses["삶의질"]["status"], "matched_observation")
        self.assertEqual(indicators.psych_eligible_scores(statuses), {})

    def test_no_eligible_score_means_no_psych_cards(self):
        result = get_psych_evidence(
            {"성장가능성": 0.1}, eligible_indicators=[], basis="model"
        )
        self.assertEqual(result["cards"], [])
        self.assertIsNone(result["focus_indicator"])

    def test_extra_psych_cards_are_loaded(self):
        self.assertGreaterEqual(len(_load_cards()), 19)

    def test_psychology_source_is_not_statistical_evidence(self):
        self.assertFalse(_is_statistical_source("Ryff, Journal of Personality"))
        self.assertTrue(_is_statistical_source("한국노동패널 KLIPS 통계"))


if __name__ == "__main__":
    unittest.main()
