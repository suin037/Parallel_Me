"""조건이 실제로 소득 궤적에 반영되는지 — `compare.py` 의 순수 계산부만 검증한다.

`compare` 는 엔진(core/trajectory/models)을 import 하는데 그쪽은 무거운 학습
라이브러리와 `.pkl` 아티팩트를 요구한다. 여기서 보려는 것은 "조건 → 숫자" 변환
로직뿐이라, 엔진 모듈은 가짜로 끼워 넣고 계산 함수만 불러온다.

검증 대상은 배포본 응답에서 실제로 틀렸던 값들이다.
  · 은우  310 → 280 이라고 적었는데 1년차가 308.4 였다
  · 도현  반년 무소득이라고 적었는데 1년차가 418.0 이었다
  · 성민  창업비 1.2억·runway 8개월인데 어디에도 없었다
"""

import importlib
import sys
import types
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[2] / "backend"


# ── 엔진 모듈 스텁 ───────────────────────────────────────────────────────
# compare.py 가 import 하는 이름만 최소로 채운다. 실제 계산은 쓰지 않는다.
#
# ⚠ sys.modules 를 건드리므로 **같은 세션의 다른 테스트를 망가뜨리면 안 된다.**
#   처음 짤 때 `models` 를 평범한 모듈로 끼워 넣었더니, 뒤에 도는 테스트의
#   `import models.dynamic_effect` 가 "'models' is not a package" 로 죽었다.
#   그래서 (a) 진짜 모듈이 import 되면 스텁을 쓰지 않고,
#         (b) 패키지 자리는 __path__ 를 실제 폴더로 채워 하위 모듈이 계속 열리게 하고,
#         (c) 우리가 넣은 것만 끝나고 되돌린다.
_INSTALLED: list[str] = []


def _stub(name: str, **attrs) -> types.ModuleType:
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules[name] = mod
    _INSTALLED.append(name)
    return mod


def _real_or_stub(name: str, **attrs) -> None:
    """진짜가 import 되면 그대로 쓰고, 안 되면 최소 스텁을 끼운다."""
    try:
        importlib.import_module(name)
    except Exception:
        _stub(name, **attrs)


def _package_placeholder(name: str, path: Path) -> None:
    """하위 모듈 import 가 계속 되도록 __path__ 를 가진 자리만 만든다."""
    if name in sys.modules:
        return
    pkg = _stub(name)
    pkg.__path__ = [str(path)]


def setup_module(module):                      # noqa: D103 - pytest 훅
    if str(BACKEND) not in sys.path:
        sys.path.insert(0, str(BACKEND))

    _real_or_stub("core",
                  run_prediction=lambda *a, **k: None,
                  new_profile_cache=lambda: {},
                  KIND_TREATMENT={"이직": "move", "창업": "startup", "휴식": "break"},
                  choice_kind=lambda text: "이직")
    _real_or_stub("trajectory",
                  wage_basis=lambda: {"label": "2024년 기준 실질", "deflated": True})

    _package_placeholder("utils", BACKEND / "utils")
    _real_or_stub("utils.scoring", build_feature_vector=lambda req: {})

    _package_placeholder("models", BACKEND / "models")
    _real_or_stub("models.lifelines_model", model_confidence=lambda *a, **k: None)
    _real_or_stub("models.econml_model", effect_confidence=lambda *a, **k: None)

    global compare, gap_months, income_anchor, parse_conditions
    compare = importlib.import_module("compare")
    cc = importlib.import_module("choice_conditions")
    gap_months, income_anchor = cc.gap_months, cc.income_anchor
    parse_conditions = cc.parse_conditions


def teardown_module(module):                   # noqa: D103 - pytest 훅
    """우리가 끼운 것만 걷어낸다 — 뒤에 도는 테스트가 진짜 모듈을 쓰게."""
    for name in ("compare", *reversed(_INSTALLED)):
        sys.modules.pop(name, None)
    _INSTALLED.clear()


class FakePoint:
    """엔진 궤적 포인트(income_p50/p25/p75, sample_n)의 최소 대역."""

    def __init__(self, year, p50, p25=None, p75=None, n=100):
        self.year = year
        self.income_p50 = p50
        self.income_p25 = p25 if p25 is not None else p50 * 0.9
        self.income_p75 = p75 if p75 is not None else p50 * 1.1
        self.sample_n = n


# 은우의 배포본 실제 궤적(A: 이직). 0년은 현재 소득 310.
EUNWOO_PATH = [FakePoint(0, 310.0), FakePoint(1, 308.4),
               FakePoint(3, 325.2), FakePoint(5, 342.6)]


def _values(points):
    return {p.year: p.value for p in points if p.available}


# ── 앵커 없음 = 기존 동작 그대로 ──────────────────────────────────────────
def test_조건이_없으면_기존_값을_그대로_쓴다():
    got = _values(compare._income(EUNWOO_PATH, "이직"))
    assert got == {1: 308.4, 3: 325.2, 5: 342.6}


# ── ① 소득 수준 앵커 ─────────────────────────────────────────────────────
def test_은우_310에서_280으로_적으면_1년차가_280이_된다():
    """배포본에서는 308.4 였다."""
    cond = parse_conditions(context={"income_change": "30만원 감소 (310→280)"})
    anchor = income_anchor(cond, 310, "이직")
    got = _values(compare._income(EUNWOO_PATH, "이직", anchor=anchor))
    assert got[1] == pytest.approx(280.0, abs=0.05)


def test_앵커를_적용해도_연차별_증가율은_모델을_따른다():
    """수준만 옮기고 기울기는 건드리지 않는다."""
    raw = _values(compare._income(EUNWOO_PATH, "이직"))
    cond = parse_conditions(context={"income_change": "30만원 감소 (310→280)"})
    anchored = _values(compare._income(EUNWOO_PATH, "이직",
                                       anchor=income_anchor(cond, 310, "이직")))
    # 표시값은 0.1만원 단위로 반올림하므로 비율도 그만큼 흔들린다(1e-3 이면 충분).
    assert anchored[3] / anchored[1] == pytest.approx(raw[3] / raw[1], rel=1e-3)
    assert anchored[5] / anchored[1] == pytest.approx(raw[5] / raw[1], rel=1e-3)


def test_증감_표기도_현재소득_기준으로_앵커가_된다():
    """지원 A: '40만원 증가', 현재 330 → 370."""
    cond = parse_conditions(context={"income_change": "40만원 증가"})
    anchor = income_anchor(cond, 330, "이직")
    got = _values(compare._income(EUNWOO_PATH, "이직", anchor=anchor))
    assert got[1] == pytest.approx(370.0, abs=0.05)


def test_앵커를_쓰면_출처에_사용자_입력이라고_적힌다():
    """모델이 낸 값과 구분되지 않으면 안 된다."""
    points = compare._income(EUNWOO_PATH, "이직", anchor=280)
    assert "입력 조건" in points[0].source


def test_증감률도_앵커된_값에서_계산된다():
    """소득 줄과 증감률 줄이 다른 숫자를 근거로 삼으면 안 된다."""
    anchored = compare._income(EUNWOO_PATH, "이직", anchor=280)
    growth = compare._growth_potential(EUNWOO_PATH, anchored)
    by_year = {p.year: p.value for p in growth if p.available}
    # 현재 310 → 1년차 280 이므로 약 −9.7%
    assert by_year[1] == pytest.approx((280 / 310 - 1) * 100, abs=0.2)


# ── ① 공백 · 초기비용 → 누적 소득 ────────────────────────────────────────
DOHYUN_PATH = [FakePoint(0, 420.0), FakePoint(1, 418.0),
               FakePoint(3, 436.9), FakePoint(5, 474.6)]


def test_도현_반년_공백이_누적소득에_반영된다():
    """월소득 줄은 모델 그대로 두고, 못 번 돈은 누적 줄에서 드러난다."""
    cond = parse_conditions(context={
        "income_change": "월 420만원 → 0", "time_horizon": "반년 (6개월)",
    })
    gap = gap_months(cond, "휴식")
    assert gap == 6

    points = compare._income(DOHYUN_PATH, "휴식")
    with_gap = compare._income_cumulative(points, 420.0, gap, None)
    without = compare._income_cumulative(points, 420.0, None, None)

    v_gap = {p.year: p.value for p in with_gap if p.available}
    v_no = {p.year: p.value for p in without if p.available}
    # 6개월치 ≈ 420×6 = 2,520만원이 빠져야 한다
    assert v_no[1] - v_gap[1] == pytest.approx(2520, rel=0.05)
    assert v_no[3] - v_gap[3] == pytest.approx(2520, rel=0.05)


def test_도현의_월소득_줄은_손대지_않는다():
    """휴식의 '0원' 은 공백 기간 값이지 복귀 후 수준이 아니다."""
    cond = parse_conditions(context={
        "income_change": "월 420만원 → 0", "time_horizon": "반년 (6개월)",
    })
    assert income_anchor(cond, 420, "휴식") is None
    got = _values(compare._income(DOHYUN_PATH, "휴식",
                                  anchor=income_anchor(cond, 420, "휴식")))
    assert got[1] == 418.0


def test_성민_창업비와_runway_가_누적소득에서_빠진다():
    path = [FakePoint(0, 380.0), FakePoint(1, 428.2),
            FakePoint(3, 461.5), FakePoint(5, 502.5)]
    cond = parse_conditions(context={"runway": "8개월", "startup_cost": "1억 2천만원"})
    points = compare._income(path, "창업")
    cum = {p.year: p.value for p in compare._income_cumulative(
        points, 380.0, gap_months(cond, "창업"), cond.startup_cost_manwon) if p.available}
    plain = {p.year: p.value for p in compare._income_cumulative(
        points, 380.0, None, None) if p.available}
    # 창업비 12,000만원 + 8개월 공백이 빠진다
    assert plain[1] - cum[1] > 12000
    assert cum[1] < 0            # 첫해는 자본 지출이 소득보다 크다


def test_공백도_비용도_없으면_누적은_단순합에_가깝다():
    points = compare._income(EUNWOO_PATH, "이직")
    cum = {p.year: p.value for p in compare._income_cumulative(points, 310.0, None, None)
           if p.available}
    assert cum[1] == pytest.approx((310 + 308.4) / 2 * 12, rel=0.02)


def test_현재소득이_없으면_누적을_계산하지_않는다():
    points = compare._income(EUNWOO_PATH, "이직")
    cum = compare._income_cumulative(points, None, None, None)
    assert all(not p.available for p in cum)


def test_관측범위_밖_연차는_누적도_비운다():
    points = compare._income(EUNWOO_PATH, "이직")
    cum = {p.year: p.available for p in compare._income_cumulative(points, 310.0, None, None)}
    assert cum[10] is False       # 궤적이 5년까지만 있다


# ── ③ 해외 선택지는 국내 패널로 답하지 않는다 ────────────────────────────
@pytest.mark.parametrize("text", [
    "런던에 남아 현지 취업을 한다",          # 린 B — 배포본에서 '유지' 로 분류됐다
    "해외로 이직한다",
    "미국에 가서 일한다",
    "워홀 다녀온다",
    "싱가포르 지사로 옮긴다",
    "이민 간다",
])
def test_해외_이동은_관측범위_밖으로_본다(text):
    assert compare._is_out_of_scope_region(text) is True


@pytest.mark.parametrize("text", [
    "귀국해서 이직한다",            # 린 A — 국내로 돌아오는 선택이다
    "한국으로 돌아와 취업한다",
    "지금 회사에 남는다",
    "합격한 회사로 이직한다",
    "퇴사하고 카페를 창업한다",
    "번아웃으로 퇴사하고 반년 쉬어간다",
])
def test_국내_선택은_막지_않는다(text):
    assert compare._is_out_of_scope_region(text) is False


def test_해외_단어만_있고_이동_표현이_없으면_막지_않는다():
    """'해외 영업팀' 같은 국내 직무까지 막으면 멀쩡한 비교가 사라진다."""
    assert compare._is_out_of_scope_region("해외 영업팀") is False


def test_detail_에만_해외가_적혀도_잡는다():
    assert compare._is_out_of_scope_region("현지 취업", "런던 · 비자 만료 전") is True


def test_관측범위_밖이면_값을_비우고_이유를_남긴다():
    blanked = compare._blank(compare._income(EUNWOO_PATH, "이직"),
                             compare._OUT_OF_SCOPE_NOTE)
    assert all(not p.available for p in blanked)
    assert all("국내 패널" in p.note for p in blanked)
