"""사용자가 적은 선택 조건을 '계산에 쓸 수 있는 수치' 로 바꾼다.

왜 필요한가
    `choice_a_detail`(자유 텍스트)과 `choice_a_context`(구조화 답변)는 지금까지
    **서사 프롬프트와 근거 검색에만** 쓰였다(`main.py` 의 note, `koweps_evidence`).
    수치 경로(`compare._scenario_view` → `PredictRequest.choice`)에서는 분류용
    문자열로만 소비돼서, 사용자가 "월 420만원 → 0" 이라고 적어도 소득 궤적은
    그대로였다.

    실제로 배포본 7개 페르소나 응답을 전수 확인한 결과 전원 미반영이었다.
    가장 눈에 띄는 것:
      · 도현  "반년 무소득" 인데 1년차 418.0만원
      · 성민  창업비 1.2억·runway 8개월인데 1년차가 현재보다 +48만원
      · 린    "90 → 300" 인데 182.9만원

    서사만 조건을 읽고 있었기 때문에 린의 서사에는 "월급은 3배 가까이 오르지만"
    이 나오는데 그래프는 2배도 안 되는, 눈에 띄는 불일치가 생겼다.

무엇을 하지 않는가
    · **추정하지 않는다.** 파싱에 실패하면 `None` 을 돌려주고 그대로 둔다.
      숫자를 지어내면 "모델이 계산한 값" 과 구분이 사라진다.
    · 파싱된 값도 모델 예측을 대체하지 않는다. 소득 '수준' 만 사용자가 말한
      값에 맞추고, **연차별 증가율은 모델 궤적을 그대로 따른다**(`compare.py`).

읽는 소스는 두 곳이며 구조화 답변이 우선한다.
    1) `choice_*_context`  — `scenarioIntake.js` 의 질문 답변 dict
                             (income_change / runway / startup_cost / time_horizon …)
    2) `choice_*_detail`   — 같은 답변을 이어붙인 자유 텍스트(폴백)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict

# ── 숫자 표기 ────────────────────────────────────────────────────────────
# 한국어 금액은 "1억 2천만원", "3,000만원", "90만", "420만원" 처럼 섞여 나온다.
# 단위를 만원으로 통일한다(백엔드 소득 단위가 만원).

_NUM = r"[\d,]+(?:\.\d+)?"


def _to_float(raw: str) -> float:
    return float(raw.replace(",", ""))


def parse_money_manwon(text: str | None) -> float | None:
    """금액 표현 → 만원. 못 읽으면 None.

    "1억 2천만원" → 12000 / "3,000만원" → 3000 / "90만" → 90 / "0" → 0
    """
    if not text:
        return None
    s = str(text).strip()

    total = 0.0
    matched = False

    m = re.search(rf"({_NUM})\s*억", s)
    if m:
        total += _to_float(m.group(1)) * 10000
        matched = True
        s = s[m.end():]                      # 억 뒤쪽만 남겨 "2천만원" 을 이어 읽는다

    m = re.search(rf"({_NUM})\s*천\s*만", s)
    if m:
        total += _to_float(m.group(1)) * 1000
        matched = True
    else:
        m = re.search(rf"({_NUM})\s*만", s)
        if m:
            total += _to_float(m.group(1))
            matched = True

    if matched:
        return total

    # 단위 없는 순수 숫자. "→ 0" 같은 경우가 여기 걸린다.
    m = re.fullmatch(rf"\s*({_NUM})\s*(?:원)?\s*", s)
    if m:
        return _to_float(m.group(1))
    return None


_HALF_YEAR = re.compile(r"반\s*년")


def parse_months(text: str | None) -> float | None:
    """기간 표현 → 개월 수. "반년 (6개월)" → 6 / "8개월" → 8 / "1년" → 12.

    "당분간 유지", "일단 유지" 처럼 기간이 없는 표현은 None.
    """
    if not text:
        return None
    s = str(text)

    m = re.search(rf"({_NUM})\s*개월", s)
    if m:
        return _to_float(m.group(1))
    m = re.search(rf"({_NUM})\s*년", s)
    if m:
        return _to_float(m.group(1)) * 12
    if _HALF_YEAR.search(s):
        return 6.0
    return None


# ── 소득 변화 ────────────────────────────────────────────────────────────
# 우선순위: 화살표(절대 목표) > 만원 증감 > 퍼센트.
# 화살표가 가장 명시적이라 먼저 본다 — "30만원 감소 (310→280)" 처럼 둘 다 있을 때
# 증감분만 읽으면 기준 소득이 무엇인지 알 수 없다.

_ARROW = re.compile(rf"({_NUM})\s*(?:만원|만)?\s*(?:→|->|~>|=>)\s*({_NUM})\s*(?:만원|만)?")
_NO_CHANGE = re.compile(r"변화\s*없|변동\s*없|그대로|동일|유지만|없음")
_DECREASE = re.compile(r"감소|줄|하락|삭감|↓")
_INCREASE = re.compile(r"증가|인상|상승|오르|올라|↑|\+")


def parse_income_change(text: str | None) -> dict | None:
    """소득 변화 표현 → {mode, value, raw}. 못 읽으면 None.

    mode
      "absolute"     value = 목표 월소득(만원). "310 → 280", "월 420만원 → 0"
      "delta"        value = 증감분(만원, 부호 포함). "40만원 증가", "30만원 감소"
      "growth_rate"  value = 연 증가율(비율). "연 3.2% 인상"
      "none"         변화 없음
    """
    if not text:
        return None
    s = str(text).strip()
    if not s:
        return None

    if _NO_CHANGE.search(s):
        return {"mode": "none", "value": 0.0, "raw": s}

    m = _ARROW.search(s)
    if m:
        # 화살표 양쪽 단위가 생략될 수 있다("월 90만 → 300만" / "310→280").
        after = _to_float(m.group(2))
        return {"mode": "absolute", "value": after, "raw": s}

    # 만원 단위 증감. 퍼센트와 함께 오면("+18% (약 60만원 증가)") 만원 쪽을 쓴다 —
    # 퍼센트는 기준이 총소득인지 기본급인지 모호하지만 만원은 그대로 더하면 된다.
    m = re.search(rf"({_NUM})\s*만원?", s)
    if m:
        v = _to_float(m.group(1))
        if _DECREASE.search(s):
            return {"mode": "delta", "value": -v, "raw": s}
        if _INCREASE.search(s):
            return {"mode": "delta", "value": v, "raw": s}

    m = re.search(rf"({_NUM})\s*%", s)
    if m:
        v = _to_float(m.group(1)) / 100
        if _DECREASE.search(s):
            v = -v
        return {"mode": "growth_rate", "value": v, "raw": s}

    return None


# ── 묶음 ────────────────────────────────────────────────────────────────
# context 키 이름은 frontend/src/data/scenarioIntake.js 의 DOMAIN_QUESTIONS 와 맞춘다.
# 이름이 갈리면 조용히 아무것도 안 읽히므로 여기 한 곳에만 적는다.

_INCOME_KEYS = ("income_change",)
_RUNWAY_KEYS = ("runway",)
_COST_KEYS = ("startup_cost", "cost")
_HORIZON_KEYS = ("time_horizon", "duration")


@dataclass
class ChoiceConditions:
    """사용자가 말한 조건 중 수치로 쓸 수 있는 것만."""

    income: dict | None = None            # parse_income_change 결과
    no_income_months: float | None = None  # 소득이 끊기는 기간(휴식 공백 · 창업 runway)
    startup_cost_manwon: float | None = None
    horizon_months: float | None = None
    source: str | None = None             # "context" | "detail" | None
    unparsed: list[str] = field(default_factory=list)

    def has_any(self) -> bool:
        return any((self.income, self.no_income_months,
                    self.startup_cost_manwon, self.horizon_months))

    def to_dict(self) -> dict:
        return asdict(self)


def _first(ctx: dict, keys: tuple[str, ...]) -> str | None:
    for k in keys:
        v = ctx.get(k)
        if v not in (None, ""):
            return str(v)
    return None


def parse_conditions(detail: str | None = None,
                     context: dict | None = None) -> ChoiceConditions:
    """구조화 답변(context) 우선, 없으면 자유 텍스트(detail) 에서 읽는다."""
    out = ChoiceConditions()
    ctx = context if isinstance(context, dict) else {}

    if ctx:
        out.source = "context"
        out.income = parse_income_change(_first(ctx, _INCOME_KEYS))
        out.no_income_months = parse_months(_first(ctx, _RUNWAY_KEYS))
        out.startup_cost_manwon = parse_money_manwon(_first(ctx, _COST_KEYS))
        out.horizon_months = parse_months(_first(ctx, _HORIZON_KEYS))
        for k in _INCOME_KEYS + _RUNWAY_KEYS + _COST_KEYS:
            v = ctx.get(k)
            if v and not out.has_any():
                out.unparsed.append(f"{k}={v}")

    if not out.has_any() and detail:
        out.source = "detail"
        out.income = parse_income_change(detail)
        # 자유 텍스트에서는 runway 와 실행시점을 구분할 수 없다. 기간은 하나만 읽고,
        # 그것이 '공백 기간' 인지는 호출부가 선택 유형(휴식/창업)으로 판단한다.
        out.horizon_months = parse_months(detail)
        out.startup_cost_manwon = None
        if not out.has_any():
            out.unparsed.append(detail[:120])

    return out


def gap_months(cond: ChoiceConditions, kind: str) -> float | None:
    """이 선택에서 '소득이 끊기는 개월 수'.

    휴식은 쉬는 기간 자체가 공백이고, 창업은 runway 가 그 역할을 한다.
    이직·유지는 공백을 가정하지 않는다 — 근거 없이 소득을 깎으면 안 된다.
    """
    if cond.no_income_months:
        return cond.no_income_months
    if kind == "휴식":
        # "월 420만원 → 0" 처럼 소득이 0으로 간다고 적었으면 기간은 실행시점 답변에서.
        if cond.income and cond.income.get("mode") == "absolute" and cond.income["value"] == 0:
            return cond.horizon_months
        return cond.horizon_months
    return None


def income_anchor(cond: ChoiceConditions, current_wage: float | None,
                  kind: str) -> float | None:
    """조건이 말하는 '새로운 월소득 수준'(만원). 없으면 None.

    휴식의 0원은 **공백 기간의 값**이지 복귀 후 수준이 아니다. 그걸 새 수준으로
    잡으면 3년 뒤 소득까지 0 근처로 눌린다 — 그래서 휴식은 여기서 제외하고
    `gap_months` 로만 다룬다.
    """
    inc = cond.income
    if not inc:
        return None
    mode, value = inc["mode"], inc["value"]

    if mode == "absolute":
        if kind == "휴식" and value == 0:
            return None
        return float(value)
    if mode == "delta" and current_wage:
        return max(0.0, float(current_wage) + float(value))
    # growth_rate 는 '수준' 이 아니라 기울기라 앵커로 쓰지 않는다.
    return None
