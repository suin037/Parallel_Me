from choice_classifier import classify, extract_startup_context
from rulebase import query_choice_indicators, startup_closure_timeline


def test_startup_context_distinguishes_industry_and_scale():
    cafe = extract_startup_context("1인 카페 창업")
    software = extract_startup_context("직원 7명 IT 소프트웨어 회사 창업")

    assert classify("1인 카페 창업", record=False).kind == "창업"
    assert cafe.ksic_section == "I"
    assert cafe.scale == "1인~4인"
    assert software.ksic_section == "J"
    assert software.scale == "5인~9인"


def test_startup_statistics_follow_selected_context():
    cafe = {"choice": "1인 카페 창업"}
    software = {"choice": "직원 7명 IT 소프트웨어 회사 창업"}

    cafe_indicators = query_choice_indicators(cafe)
    software_indicators = query_choice_indicators(software)

    assert len(cafe_indicators) == 3
    assert len(software_indicators) == 3
    assert "숙박 및 음식점업" in cafe_indicators[0]["group"]
    assert "정보통신업" in software_indicators[0]["group"]
    assert startup_closure_timeline(cafe).keys() == {1, 2, 3, 4, 5}
    assert startup_closure_timeline(cafe) != startup_closure_timeline(software)
