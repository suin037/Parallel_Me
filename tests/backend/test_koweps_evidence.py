from koweps_evidence import evidence_for_request, indicator_statuses


def test_move_evidence_is_available_and_observational():
    result = evidence_for_request({"choice_a": "현재 집 유지", "choice_b": "서울로 이사"})
    assert result["available"] is True
    assert result["scenario"] == "housing.move"
    assert result["evidence_level"] == "observed_group"
    assert result["event_people"] > 1000


def test_unsupported_generic_health_choice_does_not_invent_evidence():
    result = evidence_for_request({"choice_a": "건강", "choice_b": "회복"})
    assert result["available"] is False


def test_marriage_evidence_maps_event_and_comparison_to_ab_choices():
    result = evidence_for_request({
        "choice_a": "미혼 유지",
        "choice_b": "결혼",
        "choice_a_domains": ["relationship"],
        "choice_b_domains": ["relationship"],
    })
    assert result["available"] is True
    assert result["scenario"] == "relationship.marriage_start"
    assert result["event_side"] == "B"
    assert result["comparison_side"] == "A"
    assert {outcome["key"] for outcome in result["outcomes"]} >= {
        "disposable_income", "family_satisfaction", "overall_satisfaction",
    }
    assert result["indicator_mapping"]["경제"]["strength"] == "direct"
    assert result["indicator_mapping"]["성장"]["strength"] == "proxy"
    # ★결혼은 관계 축의 정면 사건이다. 예전엔 가족·사회관계 만족이 건강·여가와 함께
    #   '삶의질' 한 칸에 뭉쳐 있어 어떤 영역이 바뀌는지 구분되지 않았다.
    assert result["indicator_mapping"]["관계"]["strength"] == "direct"
    assert set(result["indicator_mapping"]["관계"]["outcome_keys"]) <= {
        "family_satisfaction", "social_satisfaction",
    }
    assert result["indicator_mapping"]["안정"]["strength"] == "direct"
    statuses = indicator_statuses(result, "B")
    assert statuses["경제"]["status"] == "observed_group"
    assert statuses["성장"]["status"] == "proxy_observation"
    assert statuses["관계"]["status"] == "observed_group"
    assert statuses["안정"]["status"] == "observed_group"


def test_startup_uses_official_employment_transition_and_maps_quality_of_life():
    result = evidence_for_request({
        "choice_a": "임금근로 유지",
        "choice_b": "1인 카페 창업",
        "choice_a_domains": ["career"],
        "choice_b_domains": ["business"],
    })
    assert result["available"] is True
    assert result["scenario"] == "business.self_employment_start"
    assert result["event_side"] == "B"
    assert result["event_people"] == 308
    statuses = indicator_statuses(result, "B")
    assert statuses["경제"]["status"] == "observed_group"
    assert statuses["성장"]["status"] == "proxy_observation"
    assert statuses["관계"]["status"] == "observed_group"
    assert statuses["안정"]["status"] == "observed_group"


def test_profile_returns_personalized_matched_observation_without_diary_score_adjustment():
    result = evidence_for_request({
        "choice_a": "미혼 유지",
        "choice_b": "결혼",
        "profile": {
            "age": 29, "sex": "2", "edu_level": 7,
            "monthly_wage": 280, "occupation_group": 3,
            "employment_status": 1,
        },
        "diary": "요즘 결혼이 걱정되지만 관계와 안정이 중요하다",
    })
    assert result["available"] is True
    assert result["evidence_level"] == "personalized_matched_observation"
    assert result["personalization"]["event_sample_n"] >= 40
    assert result["personalization"]["comparison_sample_n"] >= 40
    assert "나이" in result["personalization"]["applied_features"]
    assert "일기 성향은 결과 수치를 바꾸지 않고" in result["personalization"]["diary_policy"]
    statuses = indicator_statuses(result, "B")
    assert statuses["경제"]["status"] == "matched_observation"


def test_finance_and_lifestyle_choices_route_to_concrete_events():
    savings = evidence_for_request({"choice_a": "적금 유지", "choice_b": "저축 늘리기"})
    hours = evidence_for_request({"choice_a": "현재 근무 유지", "choice_b": "근로시간 줄이기"})
    assert savings["scenario"] == "finance.savings_increase"
    assert hours["scenario"] == "lifestyle.work_hours_decrease"
    assert "installment_savings" in {item["key"] for item in savings["outcomes"]}
    assert "weekly_work_hours" in {item["key"] for item in hours["outcomes"]}


def test_two_active_choices_keep_independent_comparison_cohorts():
    result = evidence_for_request({
        "choice_a": "서울로 이사",
        "choice_b": "1인 카페 창업",
        "profile": {"age": 29, "sex": "2", "edu_level": 7, "monthly_wage": 280},
    })
    assert result["comparison_mode"] == "independent_events"
    assert result["side_scenarios"] == {
        "A": "housing.move", "B": "business.self_employment_start",
    }
    assert result["side_evidence"]["A"]["event_side"] == "A"
    assert result["side_evidence"]["B"]["event_side"] == "B"
    assert result["side_evidence"]["A"]["comparison_side"] is None
    assert result["side_evidence"]["B"]["comparison_side"] is None
    assert indicator_statuses(result, "A")["경제"]["status"] == "matched_observation"
    assert indicator_statuses(result, "B")["안정"]["status"] == "matched_observation"


def test_structured_event_context_routes_without_keyword_guessing():
    result = evidence_for_request({
        "choice_a": "그대로 살기",
        "choice_b": "새로운 길 택하기",
        "choice_b_context": {"event": "housing.move", "domain": "housing", "answers": {"commute": "20분 감소"}},
    })
    assert result["available"] is True
    assert result["scenario"] == "housing.move"
    assert result["event_side"] == "B"


def test_relationship_action_experiment_is_not_promoted_to_panel_prediction():
    result = evidence_for_request({
        "choice_a": "솔직하게 대화하기",
        "choice_b": "잠시 거리를 두기",
        "choice_a_context": {"event": "relationship.conversation", "domain": "relationship"},
        "choice_b_context": {"event": "relationship.distance", "domain": "relationship"},
    })
    assert result["available"] is False
