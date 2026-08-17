"""조건 파서 — 실제 페르소나 7명이 쓰는 표기를 그대로 테스트한다.

여기 있는 문자열은 `frontend/src/data/personas/*.profile.js` 의 `conditionHints`
원문이다. 표기를 바꾸면 이 테스트가 먼저 깨지도록 일부러 복사해 두었다.
"""

import pytest

from choice_conditions import (
    ChoiceConditions,
    gap_months,
    income_anchor,
    parse_conditions,
    parse_income_change,
    parse_money_manwon,
    parse_months,
)


# ── 금액 ────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("text,expected", [
    ("1억 2천만원", 12000),      # 성민 창업비
    ("3,000만원", 3000),         # 다운 창업비
    ("1억", 10000),
    ("90만", 90),
    ("총 2,000만원", 2000),
    ("0", 0),
    ("", None),
    (None, None),
])
def test_parse_money_manwon(text, expected):
    assert parse_money_manwon(text) == expected


# ── 기간 ────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("text,expected", [
    ("8개월", 8),                    # 성민 runway
    ("반년 (6개월)", 6),              # 도현 실행 기간
    ("6개월", 6),                    # 다운 runway
    ("3개월 안", 3),
    ("1개월 안", 1),
    ("1년은 더", 12),
    ("졸업 직후 (3개월 안)", 3),        # 린
    ("비자 만료 전 (6개월)", 6),        # 린
    ("당분간 유지", None),            # 기간이 아니다
    ("3월까지", None),               # 날짜지 기간이 아니다
    ("승진 제안 수락", None),
])
def test_parse_months(text, expected):
    assert parse_months(text) == expected


def test_반년_단독_표기도_읽는다():
    assert parse_months("반년") == 6
    assert parse_months("반 년 쉰다") == 6


# ── 소득 변화 ────────────────────────────────────────────────────────────
@pytest.mark.parametrize("text,mode,value", [
    # 화살표가 있으면 증감 문구보다 우선한다 — 기준 소득까지 알 수 있기 때문
    ("30만원 감소 (310→280)", "absolute", 280),     # 은우 A
    ("30만원 증가 (310→340)", "absolute", 340),     # 은우 B
    ("월 420만원 → 0", "absolute", 0),              # 도현 A
    ("월 90만 → 300만", "absolute", 300),           # 린 A
    # 증감분만 있을 때
    ("40만원 증가", "delta", 40),                    # 지원 A
    ("+18% (약 60만원 증가)", "delta", 60),          # 지호 A — %보다 만원을 쓴다
    # 기울기
    ("연 3.2% 인상", "growth_rate", 0.032),         # 지원 B
    ("연 4% 인상", "growth_rate", 0.04),            # 지호 B
    # 변화 없음
    ("변화 없음", "none", 0),                        # 성민 B · 다운 B
])
def test_parse_income_change(text, mode, value):
    got = parse_income_change(text)
    assert got is not None, text
    assert got["mode"] == mode
    assert got["value"] == pytest.approx(value)


@pytest.mark.parametrize("text", [
    "현지 오퍼 기준 월 £2,400",     # 린 B — 외화. 원화로 바꿔 추정하면 안 된다
    "월 300만원 → 브랜드 수익만",    # 다운 A — 금액이 정해지지 않았다
    "",
    None,
])
def test_읽을_수_없으면_None_이지_0이_아니다(text):
    """추정 금지. 못 읽은 것과 '0원' 은 완전히 다른 뜻이다."""
    assert parse_income_change(text) is None


# ── 묶음 파싱 ────────────────────────────────────────────────────────────
def test_context_가_detail_보다_우선한다():
    cond = parse_conditions(
        detail="40만원 증가",
        context={"income_change": "30만원 감소 (310→280)"},
    )
    assert cond.source == "context"
    assert cond.income["value"] == 280


def test_context_가_없으면_detail_에서_읽는다():
    cond = parse_conditions(detail="1개월 안 · 40만원 증가")
    assert cond.source == "detail"
    assert cond.income["mode"] == "delta"
    assert cond.income["value"] == 40


def test_성민_창업_조건():
    cond = parse_conditions(context={
        "runway": "8개월", "startup_cost": "1억 2천만원", "time_horizon": "3개월 안",
    })
    assert cond.no_income_months == 8
    assert cond.startup_cost_manwon == 12000
    assert cond.horizon_months == 3


def test_아무것도_못_읽으면_has_any_는_False():
    cond = parse_conditions(detail="잘 모르겠어요")
    assert not cond.has_any()
    assert cond.unparsed


# ── 공백 개월 ────────────────────────────────────────────────────────────
def test_휴식은_실행기간이_공백이_된다():
    cond = parse_conditions(context={
        "income_change": "월 420만원 → 0", "time_horizon": "반년 (6개월)",
    })
    assert gap_months(cond, "휴식") == 6


def test_창업은_runway_가_공백이_된다():
    cond = parse_conditions(context={"runway": "8개월", "startup_cost": "1억 2천만원"})
    assert gap_months(cond, "창업") == 8


@pytest.mark.parametrize("kind", ["이직", "유지"])
def test_이직과_유지는_공백을_가정하지_않는다(kind):
    """근거 없이 소득을 깎으면 안 된다."""
    cond = parse_conditions(context={"time_horizon": "1개월 안", "income_change": "40만원 증가"})
    assert gap_months(cond, kind) is None


# ── 소득 앵커 ────────────────────────────────────────────────────────────
def test_절대값은_그대로_앵커가_된다():
    cond = parse_conditions(context={"income_change": "30만원 감소 (310→280)"})
    assert income_anchor(cond, current_wage=310, kind="이직") == 280


def test_증감은_현재소득에_더한다():
    cond = parse_conditions(context={"income_change": "40만원 증가"})
    assert income_anchor(cond, current_wage=330, kind="이직") == 370


def test_휴식의_0원은_앵커가_아니다():
    """공백 기간의 값이지 복귀 후 수준이 아니다. 앵커로 쓰면 3년 뒤까지 0에 눌린다."""
    cond = parse_conditions(context={
        "income_change": "월 420만원 → 0", "time_horizon": "반년 (6개월)",
    })
    assert income_anchor(cond, current_wage=420, kind="휴식") is None
    assert gap_months(cond, "휴식") == 6


def test_기울기는_앵커로_쓰지_않는다():
    cond = parse_conditions(context={"income_change": "연 3.2% 인상"})
    assert income_anchor(cond, current_wage=330, kind="유지") is None


def test_현재소득이_없으면_증감은_앵커를_못_만든다():
    cond = parse_conditions(context={"income_change": "40만원 증가"})
    assert income_anchor(cond, current_wage=None, kind="이직") is None


def test_앵커는_음수로_내려가지_않는다():
    cond = parse_conditions(context={"income_change": "500만원 감소"})
    assert income_anchor(cond, current_wage=300, kind="이직") == 0.0


def test_빈_조건은_아무것도_만들지_않는다():
    cond = ChoiceConditions()
    assert not cond.has_any()
    assert income_anchor(cond, 300, "이직") is None
    assert gap_months(cond, "휴식") is None
