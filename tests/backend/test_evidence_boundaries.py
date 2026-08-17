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
        self.assertEqual(statuses["경제"]["status"], "directional_evidence")
        for axis in ("성장", "관계", "안정"):
            self.assertEqual(statuses[axis]["status"], "insufficient_evidence", axis)
        # 자기실현은 어느 선택에서도 직접 측정 근거가 없다 — '없음'을 명시적으로 낸다.
        self.assertEqual(statuses["자기실현"]["status"], "unmeasured")
        self.assertEqual(indicators.psych_eligible_scores(statuses), {})

    def test_explicit_current_state_can_feed_psych_rag(self):
        scores = {"경제": 0.6, "성장": 0.2, "관계": 0.7, "자기실현": 0.5, "안정": 0.7}
        statuses = indicators.evidence_statuses("이직", provided_scores=scores)
        eligible = indicators.psych_eligible_scores(statuses)
        result = get_psych_evidence(
            eligible,
            eligible_indicators=eligible.keys(),
            basis="user_provided_state",
        )
        self.assertEqual(result["focus_indicator"], "성장")
        self.assertEqual(result["basis"], "user_provided_state")

    def test_matched_observations_upgrade_display_evidence_not_psych_score(self):
        # 관측 지표는 축별로 배타 배분된다 — 어떤 key 가 왔는지에 따라 축이 갈린다.
        statuses = indicators.evidence_statuses("이직", {
            "observed_outcomes": {"domains": {
                "growth": [{"key": "occupation_changed", "available": True}],
                "quality_of_life": [
                    {"key": "satisfaction_family_relationship_change", "available": True},
                    {"key": "health_score_change", "available": True},
                    {"key": "satisfaction_leisure_change", "available": True},
                ],
            }}
        })
        self.assertEqual(statuses["성장"]["status"], "matched_observation")
        self.assertEqual(statuses["관계"]["status"], "matched_observation")
        self.assertEqual(statuses["안정"]["status"], "matched_observation")
        # 여가만족은 자율성의 부분 대리일 뿐이라 matched 로 승격하지 않는다.
        self.assertEqual(statuses["자기실현"]["status"], "proxy_observation")
        self.assertEqual(indicators.psych_eligible_scores(statuses), {})

    def test_axis_components_are_never_double_counted(self):
        """★회귀: 한 구성요소가 두 축에 들어가면 같은 근거를 두 번 세게 된다.

        v2 까지 income_growth 가 경제적안정도·성장가능성에, low_exit_risk 가
        경제적안정도·삶의질에 중복 투입돼 '성장가능성' 이 사실상 경제적안정도의
        부분집합이었다. 이 성질이 다시 깨지지 않도록 고정한다.
        """
        seen = {}
        for axis, mix in indicators.WEIGHTS.items():
            for comp in mix:
                self.assertNotIn(comp, seen,
                                 f"{comp} 이 {seen.get(comp)} 과 {axis} 두 축에 들어갔다")
                seen[comp] = axis
        self.assertEqual(set(indicators.WEIGHTS), set(indicators.INDICATOR_KEYS))

    def test_uncovered_choices_report_why_not_just_reference_only(self):
        """진학은 데이터가 막힌 것이라 '모델 없음' 이 아니라 사유를 밝힌다."""
        statuses = indicators.evidence_statuses("진학")
        self.assertEqual(statuses["성장"]["status"], "reference_only")
        self.assertIn("178", statuses["성장"]["reason"])

    def test_life_event_choices_have_causal_evidence(self):
        """★회귀: 결혼·주택·이사는 KOWEPS 생활효과가 학습돼 있는데 분기가 없어
        전부 reference_only 로 떨어지고 있었다."""
        for kind, axis in (("결혼", "관계"), ("주택", "안정"), ("이사", "안정")):
            statuses = indicators.evidence_statuses(kind)
            self.assertEqual(statuses[axis]["status"], "causal_estimate", kind)
            self.assertIsNotNone(statuses[axis]["ci95"], kind)

    def test_no_eligible_score_means_no_psych_cards(self):
        result = get_psych_evidence(
            {"성장": 0.1}, eligible_indicators=[], basis="model"
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
