"""A vs B 비교 출력 계층 (`/compare`).

핵심 서사 = **"너와 데이터가 비슷한 사람들이 이 길을 갔을 때"** 의 평행우주.
주인공 3지표는 **만족도 · 소득 · 후회**. 기존 예측(run_prediction)을 정규화해 재구성하며
**엔진(L1~L5)·`/predict` 계약은 그대로** 둔다.

3지표 매핑(전부 기존 레이어에서 도출 — 새 모델 없음):
  · 만족도  = 종합 만족도 궤적(1~5, YP 청년패널, L5). '만족도가 이렇게 변하더라'
  · 소득    = 소득 궤적 중앙값·분포(L5). 이직은 L3 인과효과 반영 경로 사용
  · 후회    = 이직 이탈확률(L4) / 창업 폐업확률(생멸) / 진학은 이탈데이터 없음

시점(1·3·5·10)은 데이터가 지지하는 곳만 채우고, 없으면 available=false 로 정직하게 비운다
(우리 데이터가 방대하지 않다는 걸 숨기지 않고, 지어내지 않는다).
"""

from schemas import (
    CompareRequest, CompareResponse, ScenarioView, IndicatorPoint,
    FacetTrajectory, FacetPoint, PredictRequest, PredictResponse,
)
from core import run_prediction, new_profile_cache, KIND_TREATMENT, choice_kind
from trajectory import wage_basis
from choice_conditions import parse_conditions, gap_months, income_anchor
from utils.scoring import build_feature_vector
from models.lifelines_model import model_confidence
from models.econml_model import effect_confidence

SNAPSHOTS = [1, 3, 5, 10]
HEALTH_DIMS = {"정신건강", "신체건강", "직업환경"}

# 만족도 facet: 원변수 → (표시 이름, 묶음 차원)
FACET_META = {
    "satis_work":      ("직무 만족", "직무"),
    "satis_growth":    ("자기발전(성장) 만족", "성장"),
    "satis_income":    ("소득 만족", "소득"),
    "satis_stability": ("고용안정 만족", "안정"),
    "satis_future":    ("장래성 만족", "미래"),
}


def _point_at(traj: list, year: int):
    """궤적 리스트에서 특정 연차 시점을 찾는다(없으면 None)."""
    for p in traj:
        if p.year == year:
            return p
    return None


# ---------------------------------------------------------------- 관측범위 밖
# 우리 패널은 전부 국내다(GOMS·YP2021·KLIPS·KOWEPS). 해외 취업·이주는 학습
# 데이터에 존재하지 않으므로 어떤 숫자도 근거가 없다.
#
# 그런데 분류기는 이걸 모른다. 실제로 린("런던에 남아 현지 취업을 한다")은
# '남아' 키워드에 걸려 **'유지'(현직 잔류)** 로 분류됐고(확신도 0.583),
# 그 결과 한국에서 지금 자리를 지키는 사람의 소득 궤적이 그려졌다.
# 서사는 런던 이야기를 하는데 그래프는 국내 잔류자 175만원이었다.
#
# 국가·도시 이름을 나열하는 방식은 끝이 없어서, **이동을 뜻하는 표현과 함께
# 쓰이는 해외 신호**만 본다. "해외 영업팀" 같은 국내 직무는 걸리지 않게 한다.
import re as _re

# 그 자체로 '국외에 나가 있음' 을 뜻하는 말. 다른 단서가 없어도 범위 밖이다.
_ABROAD_ALONE = _re.compile(
    r"현지\s*취업|이민|영주권|워홀|워킹\s*홀리데이|"
    r"주재원|해외\s*파견|유학|어학연수|교환학생"
)
# 지명은 그것만으로는 부족하다("일본 애니 회사 한국지사" 같은 국내 근무가 있다).
# 이동을 뜻하는 표현과 같이 나올 때만 범위 밖으로 본다.
_ABROAD_PLACE = _re.compile(
    r"해외|국외|외국|"
    r"미국|캐나다|호주|뉴질랜드|영국|런던|일본|도쿄|싱가포르|독일|베를린|"
    r"프랑스|파리|네덜란드|두바이|베트남|중국|상하이|홍콩|대만"
)
_MOVE_SIGNAL = _re.compile(
    r"취업|이직|남아|남는|남을|건너|정착|살|일하|근무|나가|진출|이주|체류|비자|"
    r"옮기|옮긴|옮길|옮겨|가서|가기|간다|갈까|떠나"
)
_DOMESTIC_RETURN = _re.compile(r"귀국|한국으로|국내로|돌아")


def _is_out_of_scope_region(*texts: str | None) -> bool:
    """해외 이동·체류 선택인가 — 그렇다면 국내 패널로 수치를 낼 수 없다.

    '귀국' 은 국내로 돌아오는 선택이라 제외한다(린의 A가 그렇다).
    """
    joined = " ".join(t for t in texts if t)
    if not joined:
        return False
    if _DOMESTIC_RETURN.search(joined):
        return False
    if _ABROAD_ALONE.search(joined):
        return True
    return bool(_ABROAD_PLACE.search(joined) and _MOVE_SIGNAL.search(joined))


_OUT_OF_SCOPE_NOTE = (
    "해외 이동·체류 선택 — 학습 데이터(GOMS·YP2021·KLIPS·KOWEPS)가 전부 국내 패널이라 "
    "이 선택의 소득·이탈확률을 낼 근거가 없음(국내 궤적을 대신 그리지 않음)"
)


def _blank(points: list[IndicatorPoint], note: str) -> list[IndicatorPoint]:
    """근거가 없는 줄은 값을 지우고 이유를 남긴다."""
    return [IndicatorPoint(year=p.year, available=False, note=note) for p in points]


def _income_path(pr: PredictResponse, kind: str) -> list:
    """이 선택의 '선택 반영' 소득 궤적.

    L3 인과가 붙는 선택(이직·창업)은 평행우주 경로(기준 + 연차별 인과효과 + CI 밴드)를,
    그 외(진학·유지·기타)는 관측 기준 궤적을 쓴다.
    """
    return pr.scenario_trajectories.get(kind) or pr.trajectory


# ---------------------------------------------------------------- 주인공: 만족도
def _satisfaction_source(pr: PredictResponse) -> str:
    """만족도 궤적의 출처 — 선택별 분기 여부를 반드시 명시한다.

    분기된 경로는 '그 선택을 한 사람들' 만 따라간 것이라 자기선택이 섞여 있다.
    인과효과로 읽히면 안 되므로 출처 문자열에 그대로 적는다.
    """
    b = pr.wellbeing_branch or {}
    if b.get("branched"):
        return (f"YP 청년패널 만족도 궤적(L5) — '{b['label']}' 한 유사인 "
                f"{b['branch_n']}명의 관측 경로(인과효과 아님)")
    return "YP 청년패널 만족도 궤적(L5) — 프로필 기준(선택별 분기 미적용)"


def _satisfaction(pr: PredictResponse) -> list[IndicatorPoint]:
    wb = pr.wellbeing_trajectory
    src = _satisfaction_source(pr)
    out = []
    for y in SNAPSHOTS:
        p = _point_at(wb, y)
        if p is None:
            note = ("청년패널(YP) 관측범위(약 4년) 밖" if wb
                    else "만족도 궤적 없음(청년 범위 밖이거나 표본 부족)")
            out.append(IndicatorPoint(year=y, available=False, note=note))
        else:
            out.append(IndicatorPoint(
                year=y, value=float(p.satis_p50), p25=float(p.satis_p25),
                p75=float(p.satis_p75), unit="점(1~5)", sample_n=p.sample_n, source=src))
    return out


def _satisfaction_summary(pr: PredictResponse) -> dict | None:
    """'만족도가 이렇게 변하더라' 한 줄 요약 (시작→최근 관측)."""
    wb = pr.wellbeing_trajectory
    if not wb:
        return None
    start, latest = wb[0], wb[-1]
    delta = round(float(latest.satis_p50) - float(start.satis_p50), 2)
    direction = "상승" if delta > 0.05 else ("하락" if delta < -0.05 else "유지")
    return {
        "start_year": start.year, "start": float(start.satis_p50),
        "latest_year": latest.year, "latest": float(latest.satis_p50),
        "delta": delta, "direction": direction,
        "span_years": latest.year - start.year,
        "sample_n": latest.sample_n, "scale": "1~5",
        "branched": bool((pr.wellbeing_branch or {}).get("branched")),
        "source": _satisfaction_source(pr),
    }


def _satisfaction_facets(pr: PredictResponse) -> list[FacetTrajectory]:
    """만족도 5개 facet(직무·자기발전·소득·고용안정·장래성)별 궤적 + 변화 방향.

    '이 길 간 사람들은 소득 만족은 높은데 장래성 만족은 낮더라' 같은 결을 만든다.
    선택별 분기가 적용됐으면 facet 도 같은 하위집단(그 선택을 한 유사인)으로 계산된다.
    """
    b = pr.wellbeing_branch or {}
    src = (f"YP 청년패널(L5) — '{b['label']}' 한 유사인 기준"
           if b.get("branched") else "YP 청년패널(L5) — 프로필 기준")
    out = []
    for key, (label, dim) in FACET_META.items():
        pts = pr.satisfaction_facets.get(key) or []
        if not pts:
            continue
        start, latest = float(pts[0]["mean"]), float(pts[-1]["mean"])
        delta = round(latest - start, 2)
        direction = "상승" if delta > 0.05 else ("하락" if delta < -0.05 else "유지")
        out.append(FacetTrajectory(
            key=key, label=label, dimension=dim,
            points=[FacetPoint(year=p["year"], value=float(p["mean"]), sample_n=p["sample_n"])
                    for p in pts],
            start=start, latest=latest, delta=delta, direction=direction,
            scale="1~5", source=src))
    return out


def _regret_meta(pr: PredictResponse, kind: str) -> tuple[str, str]:
    """(단위 라벨, 출처) — 창업은 L4 자영 스펠이 있으면 개인단위, 없으면 집단통계."""
    if kind == "이직":
        return "이탈확률", "lifelines 생존분석(L4)"
    if kind == "창업":
        # survival_months 가 있으면 개인단위 L4 가 붙은 것(없으면 KOSIS 폴백)
        if pr.survival_months is not None:
            return ("자영 이탈확률",
                    "lifelines 생존분석(L4, KLIPS 자영 스펠) — 폐업·업종전환·재취업 포함")
        return "폐업확률", "기업생멸행정통계"
    if kind == "휴식":
        # 다른 선택은 '그 상태에서 이탈' 이 나쁜 쪽인데, 쉬어가기는 이탈(=복귀)이
        # 좋은 쪽이다. 그래서 후회 축에 올리는 값은 그 여집합인 **미복귀** 확률이다.
        return ("미복귀확률",
                "lifelines 생존분석(L4, KLIPS 직업력 공백 스펠) — 그 시점에 아직 "
                "일로 돌아오지 못했을 확률")
    return "이탈확률", "lifelines 생존분석(L4)"


def _regret_summary(pr: PredictResponse, kind: str) -> dict | None:
    """후회 리스크 한 줄 요약 — 관측 범위 내 '가장 나쁜(높은)' 누적확률."""
    rt = {y: v for y, v in pr.risk_timeline.items()}
    if not rt:
        return None
    # 값이 가장 큰 연차를 고른다 — 마지막 연차가 아니다.
    # 이탈·폐업 누적확률은 단조증가라 둘이 같지만, 쉬어가기의 '미복귀확률' 은
    # 시간이 갈수록 **줄어든다**(1년 55% → 5년 17%). 마지막 연차를 집으면
    # 가장 낮은 값을 '가장 나쁜 값' 이라고 내놓게 된다.
    worst_year = max(rt, key=lambda y: rt[y])
    label, src = _regret_meta(pr, kind)
    return {"label": label, "worst_year": worst_year,
            "worst_value": round(float(rt[worst_year]) * 100, 1),
            "unit": "%", "source": src}


# ---------------------------------------------------------------- 주인공: 소득
def _income(income_path: list, kind: str, anchor: float | None = None) -> list[IndicatorPoint]:
    """소득 궤적 → 화면용 포인트. `anchor` 가 있으면 사용자가 말한 수준에 맞춘다.

    앵커 적용 방식 — **수준만 옮기고 기울기는 모델을 따른다.**
        사용자는 "옮기면 280만원" 처럼 *출발점* 을 안다. 3년 뒤 얼마가 될지는
        모른다. 그래서 1년차를 사용자가 말한 값에 맞추는 배율을 구해 전 연차에
        곱한다. 모델이 추정한 연차별 증가율(325.2/308.4 = +5.4% …)은 그대로 남는다.

        더하기(offset)가 아니라 곱하기인 이유: 더하면 증가'율' 이 바뀐다.
        모델이 실제로 추정한 것은 비율 궤적이므로 그쪽을 보존한다.

    앵커는 모델 예측이 아니다. 사용자 입력이다. 그래서 `source` 에 그렇게 적는다 —
    화면에서 "모델이 계산한 값" 과 구분되지 않으면 안 된다.
    """
    # 화폐 기준(실질/기준연도)을 출처에 명시 — 안 적으면 "5년 뒤 400만원" 을 명목으로 오독한다.
    src = (f"KLIPS 종단 소득 궤적(L5, {wage_basis()['label']})"
           + (" + 이직 인과(L3)" if kind == "이직" else ""))

    factor = None
    if anchor is not None:
        first = _point_at(income_path, SNAPSHOTS[0])
        base = float(first.income_p50) if first and first.income_p50 else None
        if base and base > 0:
            factor = float(anchor) / base
            src += f" · 입력 조건({anchor:g}만원)에 수준 맞춤 — 증가율은 모델 궤적"

    out = []
    for y in SNAPSHOTS:
        p = _point_at(income_path, y)
        if p is None:
            out.append(IndicatorPoint(year=y, available=False,
                                      note="해당 연차까지 추적된 유사 표본 부족(관측범위 밖)"))
            continue
        scale = factor if factor is not None else 1.0
        out.append(IndicatorPoint(
            year=y, value=round(float(p.income_p50) * scale, 1),
            p25=round(float(p.income_p25) * scale, 1),
            p75=round(float(p.income_p75) * scale, 1),
            unit="만원", sample_n=p.sample_n, source=src))
    return out


def _growth_potential(income_path: list,
                      income_points: list[IndicatorPoint] | None = None) -> list[IndicatorPoint]:
    """현재 대비 소득 증감률.

    `income_points`(앵커가 적용된 화면용 값)를 받으면 그쪽에서 계산한다. 앵커를
    무시하고 원 궤적으로 계산하면, 화면의 소득 줄과 증감률 줄이 서로 다른 숫자를
    근거로 삼게 된다.
    """
    base = _point_at(income_path, 0)
    base_income = float(base.income_p50) if base and base.income_p50 else None
    # 실질 궤적 위에서 계산해야 물가상승분이 '성장'으로 잡히지 않는다.
    wb = wage_basis()
    src = ("L5 소득 궤적 기울기(현재 대비, 실질)" if wb["deflated"]
           else "L5 소득 궤적 기울기(현재 대비) ⚠명목 — 물가상승분 포함")
    by_year = {p.year: p for p in (income_points or [])}
    out = []
    for y in SNAPSHOTS:
        shown = by_year.get(y)
        value = shown.value if shown and shown.available else None
        if value is None:
            p = _point_at(income_path, y)
            value = float(p.income_p50) if p else None
            sample_n = p.sample_n if p else None
        else:
            sample_n = shown.sample_n
        if value is None or not base_income:
            out.append(IndicatorPoint(year=y, available=False,
                                      note="기준(현재) 또는 해당 연차 소득 궤적 없음"))
        else:
            growth = round((float(value) / base_income - 1) * 100, 1)
            out.append(IndicatorPoint(year=y, value=growth, unit="%(현재 대비 소득)",
                                      sample_n=sample_n, source=src))
    return out


# ---------------------------------------------------------------- 누적 소득
def _income_cumulative(income_points: list[IndicatorPoint],
                       base_income: float | None,
                       gap: float | None,
                       startup_cost: float | None) -> list[IndicatorPoint]:
    """공백과 초기 비용을 반영한 **누적 소득**(만원).

    왜 월소득을 고치지 않고 새 줄을 만드는가
        `WORKLOG` 7-6 이 정확히 이 문제를 적어 두었다. 쉬어가기 효과는
        `outcome="월소득_실질"`, 즉 **복귀한 뒤의 월임금**을 견준 값이라 공백
        기간의 0원이 결과변수에 애초에 없다. 월소득 칸에 공백을 억지로 섞으면
        모델이 추정한 것과 다른 값이 되고, 그게 모델 값처럼 보인다.

        그래서 월소득 줄은 모델 그대로 두고, "그래서 3년 동안 손에 쥔 돈은
        얼마인가" 를 따로 답한다. 같은 문서가 제안한 해법이기도 하다
        ("A/B 의 3년 누적 소득 격차로 표시").

    계산
        연차 사이는 사다리꼴로 잇는다(0년=현재 소득). 공백 개월은 앞에서부터
        0원으로 깎고, 창업 초기비용은 t=0 에 한 번 뺀다.
    """
    if base_income is None:
        return [IndicatorPoint(year=y, available=False,
                               note="현재 소득이 없어 누적 소득을 계산할 수 없음")
                for y in SNAPSHOTS]

    known = [(0.0, float(base_income))]
    known += [(float(p.year), float(p.value))
              for p in income_points if p.available and p.value is not None]
    known.sort()

    def monthly_at(t_years: float) -> float:
        """연 단위 소득 궤적을 월 시점으로 선형 보간."""
        if t_years <= known[0][0]:
            return known[0][1]
        for (y0, v0), (y1, v1) in zip(known, known[1:]):
            if t_years <= y1:
                span = y1 - y0
                return v0 if span <= 0 else v0 + (v1 - v0) * (t_years - y0) / span
        return known[-1][1]

    gap_m = float(gap or 0.0)
    cost = float(startup_cost or 0.0)
    parts = []
    if gap_m:
        parts.append(f"공백 {gap_m:g}개월 무소득")
    if cost:
        parts.append(f"초기비용 {cost:g}만원")
    src = "월소득 궤적 적분" + (" · " + " · ".join(parts) if parts else "")

    max_year = known[-1][0]
    out = []
    for y in SNAPSHOTS:
        if y > max_year:
            out.append(IndicatorPoint(year=y, available=False,
                                      note="해당 연차까지 추적된 소득 궤적 없음"))
            continue
        total = -cost
        for m in range(int(y * 12)):
            if m < gap_m:
                continue                       # 공백 기간은 0원
            total += monthly_at((m + 0.5) / 12)
        out.append(IndicatorPoint(year=y, value=round(total, 1), unit="만원(누적)",
                                  source=src))
    return out


# ---------------------------------------------------------------- 주인공: 후회
def _regret(pr: PredictResponse, kind: str) -> list[IndicatorPoint]:
    out = []
    rt = pr.risk_timeline  # 이직=이탈확률 / 창업=자영 이탈(또는 폐업)확률
    if not rt:
        note = ("진학은 개인단위 이탈 추적 데이터 없음 — choice_context 의 계열 "
                "취업률/진학률로 대체" if kind == "진학"
                else f"'{kind}' 는 이탈을 정의할 개인단위 스펠 데이터가 없음")
        return [IndicatorPoint(year=y, available=False, note=note) for y in SNAPSHOTS]

    label, src = _regret_meta(pr, kind)
    unit = f"%({label})"
    for y in SNAPSHOTS:
        v = rt.get(y)
        if v is None:
            out.append(IndicatorPoint(year=y, available=False,
                                      note="모델 신뢰 관측범위 밖(과대추정 방지로 미제공)"))
        else:
            out.append(IndicatorPoint(year=y, value=round(float(v) * 100, 1),
                                      unit=unit, source=src))
    return out


# ---------------------------------------------------------------- 맥락 필터
def _choice_context(pr: PredictResponse, kind: str) -> list:
    """선택 유형에 맞는 맥락만 (이직은 없음, 창업=생존율, 진학=취업률/진학률)."""
    if kind == "창업":
        return [li for li in pr.life_indicators if li.dimension == "창업"]
    if kind == "진학":
        return [li for li in pr.life_indicators if li.dimension == "진학/취업"]
    return []


def _scenario_view(profile_dict: dict, choice: str,
                   detail: str | None = None,
                   shared: dict | None = None,
                   context: dict | None = None) -> ScenarioView:
    model_choice = detail.strip() if detail and choice_kind(detail) == choice_kind(choice) else choice
    req = PredictRequest(**profile_dict, choice=model_choice)
    # 비교는 A/B 2회 호출 → 서사는 생략(3번 RAG가 최종 화면에서 담당)
    # shared 로 선택 무관 계산(L1·L5 소득궤적·L2·매칭축)을 A/B 가 나눠 쓴다.
    pr = run_prediction(req, with_narrative=False, shared=shared)
    # 분류는 run_prediction 이 이미 한 번 했다. 여기서 다시 부르면 커버리지 통계가
    # 요청당 2번씩 세어져 '기타 비율' 이 왜곡된다 → 결과를 그대로 받아 쓴다.
    kind = pr.kind

    features = build_feature_vector(req)
    income_path = _income_path(pr, kind)

    # 사용자가 적은 조건을 수치에 반영한다. 예전엔 서사 프롬프트에만 들어가서,
    # 린의 서사는 "월급 3배" 라고 말하는데 그래프는 2배도 안 되는 상태였다.
    cond = parse_conditions(detail, context)
    base_income = profile_dict.get("monthly_wage")
    anchor = income_anchor(cond, base_income, kind)
    gap = gap_months(cond, kind)

    income_points = _income(income_path, kind, anchor=anchor)
    cumulative = _income_cumulative(income_points, base_income, gap,
                                    cond.startup_cost_manwon)

    # 해외 선택지는 국내 패널로 답할 수 없다. 분류기가 '유지' 로 잘못 본 뒤에도
    # 숫자는 나오기 때문에, 여기서 한 번 더 막는다.
    out_of_scope = _is_out_of_scope_region(choice, detail)
    if out_of_scope:
        income_points = _blank(income_points, _OUT_OF_SCOPE_NOTE)
        cumulative = _blank(cumulative, _OUT_OF_SCOPE_NOTE)

    applied = None
    if anchor is not None or gap or cond.startup_cost_manwon:
        applied = {
            "income_anchor": anchor,
            "gap_months": gap,
            "startup_cost_manwon": cond.startup_cost_manwon,
            "source": cond.source,
            "raw_income_text": (cond.income or {}).get("raw"),
            "note": "수준·공백·초기비용은 사용자가 적은 값이다(모델 예측 아님). "
                    "연차별 증가율만 모델 궤적을 따른다.",
        }
    elif cond.unparsed:
        applied = {
            "income_anchor": None, "gap_months": None, "startup_cost_manwon": None,
            "source": cond.source, "ignored": cond.unparsed,
            "note": "적어주신 조건을 수치로 읽지 못해 반영하지 않았다(추정하지 않음).",
        }

    confidence: dict = {}
    treatment = KIND_TREATMENT.get(kind)
    if treatment:
        mc = model_confidence(features, treatment)
        if mc:
            confidence["survival_c_index"] = mc
        ec = effect_confidence(features, treatment)
        if ec:
            confidence["causal_effect_ci"] = ec
    if pr.causal_effect_profile:
        confidence["causal_effect_by_year"] = pr.causal_effect_profile
    confidence["choice_classification"] = {"kind": kind,
                                           "confidence": pr.choice_confidence}

    coverage = pr.coverage
    if out_of_scope:
        coverage = f"⚠관측범위 밖 — {_OUT_OF_SCOPE_NOTE} / {coverage}"

    return ScenarioView(
        choice=choice,
        kind=kind,
        coverage=coverage,
        satisfaction=(_blank(_satisfaction(pr), _OUT_OF_SCOPE_NOTE) if out_of_scope
                      else _satisfaction(pr)),
        satisfaction_summary=(None if out_of_scope else _satisfaction_summary(pr)),
        satisfaction_facets=([] if out_of_scope else _satisfaction_facets(pr)),
        income=income_points,
        income_cumulative=cumulative,
        regret=(_blank(_regret(pr, kind), _OUT_OF_SCOPE_NOTE) if out_of_scope
                else _regret(pr, kind)),
        regret_summary=(None if out_of_scope else _regret_summary(pr, kind)),
        growth_potential=(_blank(_growth_potential(income_path, income_points),
                                 _OUT_OF_SCOPE_NOTE) if out_of_scope
                          else _growth_potential(income_path, income_points)),
        applied_conditions=applied,
        out_of_scope=({"reason": _OUT_OF_SCOPE_NOTE} if out_of_scope else None),
        health_context=[li for li in pr.life_indicators if li.dimension in HEALTH_DIMS],
        choice_context=_choice_context(pr, kind),
        confidence=confidence,
        raw=pr,
    )


def build_comparison(req: CompareRequest) -> CompareResponse:
    profile_dict = req.profile.model_dump()
    shared = new_profile_cache()          # A/B 가 선택 무관 계산을 공유
    a = _scenario_view(profile_dict, req.choice_a, req.choice_a_detail, shared,
                       req.choice_a_context)
    b = _scenario_view(profile_dict, req.choice_b, req.choice_b_detail, shared,
                       req.choice_b_context)

    notes = []
    if a.kind == b.kind:
        notes.append(f"두 선택지가 같은 유형({a.kind})으로 분류돼 비교 결과가 거의 동일할 수 있음")
    no_causal = [sc.choice for sc in (a, b) if not KIND_TREATMENT.get(sc.kind)]
    if len(no_causal) == 2:
        notes.append("두 선택 모두 개인단위 인과(L3) 미적용 — 소득 궤적은 '그 선택을 한 비슷한 사람들'의 "
                     "관측 경로이지 선택이 만든 순효과가 아님(후회·선택맥락 카드로 비교 권장)")
    elif no_causal:
        notes.append(f"'{no_causal[0]}' 에만 개인단위 인과(L3)가 없음 — 한쪽은 인과 반영 경로, "
                     "다른 쪽은 관측 경로라 소득 격차를 그대로 빼서 읽으면 안 됨")

    # 만족도 분기 여부를 A/B 각각에 대해 사실대로 (예전엔 항상 '분기 안 됨' 이었다)
    for tag, sc in (("A", a), ("B", b)):
        br = (sc.raw.wellbeing_branch or {})
        if not sc.satisfaction_summary:
            continue
        if br.get("branched"):
            notes.append(f"{tag}('{sc.choice}') 만족도는 실제로 '{br['label']}' 한 유사인 "
                         f"{br['branch_n']}명의 관측 경로 — 그 선택을 한 사람과 안 한 사람은 "
                         "애초에 다를 수 있음(자기선택). 인과효과로 읽지 말 것")
        else:
            notes.append(f"{tag}('{sc.choice}') 만족도는 프로필 기준 배경 궤적"
                         f"({br.get('reason', '분기 미적용')})")

    # 분류 확신도가 낮으면 유형 자체를 의심하라고 알린다(기존엔 조용히 '기타' 였다)
    for tag, sc in (("A", a), ("B", b)):
        cc = sc.confidence.get("choice_classification") or {}
        if sc.kind == "기타":
            notes.append(f"{tag}('{sc.choice}')를 알려진 선택 유형으로 분류하지 못함 — "
                         "개인단위 레이어(L2/L3/L4) 미적용. 표현을 바꿔 다시 시도 권장")
        elif cc.get("confidence", 1.0) < 0.6:
            notes.append(f"{tag}('{sc.choice}') 유형 분류 확신도 {cc['confidence']:.2f} — "
                         f"'{sc.kind}' 로 본 결과이니 의도와 다르면 표현을 구체화할 것")

    # 인과효과 95% CI 가 0 을 포함하면 소득 격차를 단정하지 말라고 경고
    for sc in (a, b):
        ci = sc.confidence.get("causal_effect_ci")
        if ci and ci.get("ci95_low") is not None and ci["ci95_low"] < 0 < ci["ci95_high"]:
            notes.append(f"'{sc.choice}' 인과효과 95% CI가 0을 포함"
                         f"({ci['ci95_low']:+.1f}~{ci['ci95_high']:+.1f}만) — "
                         "소득 격차를 '확실한 효과'로 단정 말 것(점추정 대신 구간으로 표현)")
        if ci and ci.get("caveat"):
            notes.append(f"'{sc.choice}' 인과효과 해석 주의 — {ci['caveat']}")

    # 사용자 조건을 반영했으면 그 사실을 밝힌다. 밝히지 않으면 사용자가 적은 값과
    # 모델이 추정한 값이 한 그래프에서 구분되지 않는다.
    for tag, sc in (("A", a), ("B", b)):
        ac = sc.applied_conditions
        if not ac:
            continue
        if ac.get("ignored"):
            notes.append(f"{tag}('{sc.choice}') 적어주신 조건을 수치로 읽지 못해 "
                         f"반영하지 않음({', '.join(ac['ignored'])[:80]}) — 추정하지 않음")
            continue
        bits = []
        if ac.get("income_anchor") is not None:
            bits.append(f"월소득 수준 {ac['income_anchor']:g}만원")
        if ac.get("gap_months"):
            bits.append(f"무소득 공백 {ac['gap_months']:g}개월")
        if ac.get("startup_cost_manwon"):
            bits.append(f"초기비용 {ac['startup_cost_manwon']:g}만원")
        notes.append(f"{tag}('{sc.choice}') 사용자가 적은 조건을 반영함({', '.join(bits)}) — "
                     "이 값은 모델 예측이 아니라 입력이며, 연차별 증가율만 모델 궤적을 따름")

    # 공백·초기비용이 한쪽에만 있으면 월소득 줄만 보면 안 된다고 알린다.
    if any((sc.applied_conditions or {}).get("gap_months") or
           (sc.applied_conditions or {}).get("startup_cost_manwon") for sc in (a, b)):
        notes.append("월소득 줄에는 공백 기간과 초기비용이 들어 있지 않음 — "
                     "income_cumulative(누적 소득)로 비교할 것")

    return CompareResponse(
        profile=req.profile,
        snapshots=SNAPSHOTS,
        choice_a=req.choice_a,
        choice_b=req.choice_b,
        scenarios={"A": a, "B": b},
        note=" / ".join(notes),
    )
