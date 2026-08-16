from domain_router import DOMAIN_LABELS, route_domains


def test_all_nine_domains_share_one_contract():
    routed = route_domains(list(DOMAIN_LABELS), {"age": 29, "sex": "2", "major": "공학"})

    assert set(routed) == set(DOMAIN_LABELS)
    for key, outcome in routed.items():
        assert outcome["domain"] == key
        assert outcome["status"] in {"available", "unavailable"}
        assert outcome["evidence"] in {"model", "group_stat", "rag", "insufficient"}
        assert isinstance(outcome["indicators"], list)
        assert "claim_type" in outcome
        assert "limitation" in outcome


def test_business_domain_uses_each_choice_detail():
    cafe = route_domains(["business"], {"age": 29}, "1인 카페 창업")["business"]
    software = route_domains(["business"], {"age": 29}, "직원 7명 IT 소프트웨어 창업")["business"]

    assert cafe["status"] == "available"
    assert software["status"] == "available"
    assert cafe["indicators"][0]["value"] != software["indicators"][0]["value"]
    assert "숙박 및 음식점업" in cafe["indicators"][0]["note"]
    assert "정보통신업" in software["indicators"][0]["note"]


def test_health_domain_includes_knhanes_behavior_reference_by_age_and_sex():
    health = route_domains(["health"], {"age": 29, "sex": "2"})["health"]
    by_name = {item["name"]: item for item in health["indicators"]}
    assert {"유산소신체활동실천율", "현재흡연율", "월간음주율", "평균BMI"} <= set(by_name)
    assert by_name["유산소신체활동실천율"]["source"] == "KNHANES 제9기"
    assert by_name["유산소신체활동실천율"]["sample_n"] >= 40
