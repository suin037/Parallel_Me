"""삶의 영역(domain) → 데이터 라우터. (로드맵 항목3)

'행동(choice) + 삶의 영역(domain)' 구조에서, 영역별로 어느 실측 데이터를 쓸지
라우팅해 집단통계 지표를 돌려준다. 데이터가 없는 영역은 정직하게 비운다
(근거수준: 항목4 evidence 와 정합).

- career            : 기존 엔진(GOMS/YP + 인과·생존) 이 처리 → 여기선 지표 추가 안 함
- finance           : KOSIS 고용형태별 임금(연령별) → 월임금 중앙수준
- business          : 기업생멸 생존율(연차별)
- education         : KEDI 학과별 취업률·진학률
- health / lifestyle: KNHANES·CHS·KWCS 통합표(우울·불안·수면·스트레스·업무스트레스)
- long_term_values  : 사회통합/삶의질(삶의 만족도·여가)
- relationship      : 심리 RAG(정량 없음) — 기존 psych 카드가 담당
- housing           : 데이터 부족
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pandas as pd

from config import ROOT
from rulebase import bizsurv_rows

DATA = ROOT / "data"

DOMAIN_LABELS = {
    "career": "직업", "education": "교육", "business": "사업", "finance": "재무",
    "health": "건강", "housing": "주거", "relationship": "관계",
    "lifestyle": "생활방식", "long_term_values": "장기 가치",
}


# ── 연령대 버킷 (데이터별 구간 표기가 달라 각각 매핑) ──────────────────────────
def _b_lanollab(age: int) -> str:
    return ("19-29" if age < 30 else "30-39" if age < 40 else "40-49"
            if age < 50 else "50-59" if age < 70 else "70+")


def _b_wage(age: int) -> str:
    return ("29세이하" if age <= 29 else "30~39세" if age < 40 else "40~49세"
            if age < 50 else "50~59세" if age < 60 else "60세이상")


def _b_qol(age: int) -> str:
    return "20대" if age < 30 else "30대" if age < 40 else "전체"


@lru_cache(maxsize=None)
def _csv(rel: str) -> pd.DataFrame:
    return pd.read_csv(DATA / rel)


@lru_cache(maxsize=1)
def _klips_work_health_panel() -> pd.DataFrame:
    """KLIPS 26차 부가조사에 같은 차수의 연령·성별을 결합한다."""
    detail = pd.read_pickle(DATA / "raw/klips/klips_health26a.pkl")
    base = pd.read_pickle(DATA / "raw/klips/klips_base.pkl")
    demographics = base[["pid", "wave", "나이", "성별"]].drop_duplicates(["pid", "wave"])
    return detail.merge(demographics, on=["pid", "wave"], how="left")


def _sex_value(profile) -> float | None:
    """프로필의 성별 코드 → 1.0/2.0. 없거나 못 읽으면 None(=성별로 나누지 않는다).

    예전엔 `float(profile.get("sex") or 2)` 로 비어 있으면 여성을 채웠다. 성별은
    선택 입력이라 그냥 안 고른 사용자가 많은데, 그 사람들에게 고른 적 없는 성별의
    유사집단 수치가 '내 조건과 비슷한 집단'이라는 이름으로 나갔다.
    """
    value = (profile or {}).get("sex")
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _klips_matched(profile, specs: list[tuple[str, str, str]]) -> list[dict]:
    """사용자와 같은 성별·±5세 KLIPS 26차 집단의 근로·건강 상태.

    성별이 없으면 성별 축을 열지 않고 연령대만으로 매칭한다(전체 표본 폴백).
    """
    try:
        panel = _klips_work_health_panel()
    except Exception:
        return []
    age = int(profile.get("age") or 29)
    sex = _sex_value(profile)
    in_age = panel[panel["나이"].between(age - 5, age + 5)]
    if sex is None:
        matched = in_age
        conditions = f"{age - 5}~{age + 5}세·성별 구분 없음"
    else:
        matched = in_age[in_age["성별"].eq(sex)]
        conditions = f"{age - 5}~{age + 5}세·동일 성별"
    if len(matched) < 100:
        matched = in_age
        conditions = f"{age - 5}~{age + 5}세"
    out = []
    for column, label, kind in specs:
        values = pd.to_numeric(matched.get(column), errors="coerce").dropna()
        if len(values) < 40:
            continue
        if kind == "rate":
            value, unit = values.mean() * 100, "%"
        else:
            value, unit = values.mean(), kind
        out.append(_ind(label, value, unit, len(values), "KLIPS 26차 부가조사",
                        note=f"{conditions} 유사 조건 관측"))
    return out


def _ind(name, value, unit, n=None, source=None, note=None) -> dict:
    return {"name": name, "value": (None if value is None else round(float(value), 1)),
            "unit": unit, "sample_n": (int(n) if n and n == n else None),
            "source": source, "note": note}


# ── 로더 (영역별) ────────────────────────────────────────────────────────────
LANOLLAB = "lanollab/lookup_lanollab_master_v1.csv"
HEALTH_INDS = ["우울장애유병률", "불안감유병", "수면장애", "스트레스인지율",
               "EQ5D_통증문제", "우울함유병", "유산소신체활동실천율",
               "현재흡연율", "월간음주율", "평균BMI"]
LIFESTYLE_INDS = ["업무스트레스", "주중평균수면시간", "스트레스인지율"]


def _lanollab(profile, names) -> list[dict]:
    try:
        df = _csv(LANOLLAB)
    except Exception:
        return []
    age = int(profile.get("age") or 29)
    ag = _b_lanollab(age)
    sex = _sex_value(profile)
    sx = None if sex is None else str(sex)
    out = []
    for nm in names:
        sub = df[df["지표명"] == nm]
        if sub.empty:
            continue
        # 성별×연령대 → 연령대 → 전체 순으로 가장 구체적인 값을 고른다.
        # 성별이 없으면 첫 단계를 건너뛴다(찍지 않고 연령대·전체로 내려간다).
        pick = sub.iloc[0:0] if sx is None else sub[
            (sub["구분유형"] == "성별×연령대") & (sub["agegroup"].astype(str) == ag)
            & (sub["sex"].astype(str) == sx)]
        if pick.empty:
            pick = sub[(sub["구분유형"] == "연령대") & (sub["agegroup"].astype(str) == ag)]
        if pick.empty:
            pick = sub[sub["구분유형"] == "전체"]
        if pick.empty:
            continue
        r = pick.iloc[0]
        out.append(_ind(nm, r["값"], r["단위"], r.get("n"), r.get("출처")))
    return out


def _finance(profile) -> list[dict]:
    try:
        df = _csv("dgroup/kosis_고용형태별근로실태조사_연령별/lookup_elfs_wage_by_age_v1.csv")
    except Exception:
        return []
    age = int(profile.get("age") or 29)
    sub = df[(df["age_group"].astype(str) == _b_wage(age))
             & (df["emp_type"].astype(str) == "정규근로자")]
    if sub.empty:
        return []
    r = sub.sort_values("year").iloc[-1]
    return [_ind(f"또래 정규직 월임금총액({int(r['year'])})", r["월임금총액_만원"], "만원",
                 source="KOSIS 고용형태별근로실태조사")]


def _education(profile) -> list[dict]:
    try:
        df = _csv("dgroup/한국교육개발원_고등교육기관_졸업자_학과별_상황/lookup_kedi_emp_rate_by_field_v1.csv")
    except Exception:
        return []
    major = str(profile.get("major") or "전체")
    sub = df[df["major_field"].astype(str) == major]
    if sub.empty:
        sub = df[df["major_field"].astype(str) == "전체"]
    if sub.empty:
        return []
    r = sub.sort_values("year").iloc[-1]
    return [_ind(f"{r['major_field']} 취업률({int(r['year'])})", r["emp_rate"], "%",
                 source="KEDI 고등교육기관 졸업자"),
            _ind(f"{r['major_field']} 진학률", r["advance_rate"], "%",
                 source="KEDI 고등교육기관 졸업자")]


def _business(profile) -> list[dict]:
    """창업 생존율 — 업종·규모는 자유입력(profile['choice'])에서 뽑는다.

    필터를 여기서 직접 쓰지 않고 `rulebase.bizsurv_rows` 를 부른다. 예전엔 이 함수와
    rulebase 가 각자 '전체·계' 를 하드코딩하고 있었는데, 한쪽만 업종축을 열면 같은
    창업에 대해 화면마다 다른 생존율이 나온다.
    """
    try:
        sub, ctx = bizsurv_rows(profile or {})
    except Exception:
        return []
    if sub is None or sub.empty:
        return []
    out = []
    for h in (1, 3, 5):
        row = sub[sub["survival_horizon_yr"] == h]
        if not row.empty:
            r = row.sort_values("ref_year").iloc[-1]
            out.append(_ind(f"창업 {h}년 생존율", r["survival_rate"], "%",
                            source="KOSIS 기업생멸행정통계",
                            note=f"{ctx.label()} 기준"))
    return out


def _values(profile) -> list[dict]:
    try:
        df = _csv("dgroup/kosis_사회통합실태조사/lookup_qol_indicators_v2.csv")
    except Exception:
        return []
    grp = _b_qol(int(profile.get("age") or 29))
    want = ["삶의 만족도", "여가생활 만족도", "하루 평균 여가시간"]
    out = []
    for nm in want:
        sub = df[df["indicator_name"] == nm]
        if sub.empty:
            continue
        pick = sub[sub["group"].astype(str) == grp]
        if pick.empty:
            pick = sub[sub["group"].astype(str) == "전체"]
        if pick.empty:
            continue
        r = pick.sort_values("year").iloc[-1]
        out.append(_ind(nm, r["value"], r["unit"], source="사회통합실태조사"))
    return out


def _qol(profile, names: list[str]) -> list[dict]:
    """사회통합실태조사의 영역별 현재 집단 기준값."""
    try:
        df = _csv("dgroup/kosis_사회통합실태조사/lookup_qol_indicators_v2.csv")
    except Exception:
        return []
    grp = _b_qol(int(profile.get("age") or 29))
    out = []
    for name in names:
        sub = df[df["indicator_name"].astype(str) == name]
        pick = sub[sub["group"].astype(str) == grp]
        if pick.empty:
            pick = sub[sub["group"].astype(str) == "전체"]
        if pick.empty:
            continue
        row = pick.sort_values("year").iloc[-1]
        out.append(_ind(name, row["value"], row["unit"], source="사회통합실태조사"))
    return out


def _relationship(profile) -> list[dict]:
    return _qol(profile, ["사회적 고립도"])


def _lifestyle(profile) -> list[dict]:
    work = _klips_matched(profile, [
        ("실근무시간", "주간 실근무시간", "시간"),
        ("야간근무", "야간근무 비율", "rate"),
        ("교대근무", "교대근무 비율", "rate"),
        ("장시간근무", "장시간근무 비율", "rate"),
        ("짧은휴식", "짧은 휴식 비율", "rate"),
        ("출퇴근시간", "평균 출퇴근시간", "분"),
    ])
    return work + _lanollab(profile, LIFESTYLE_INDS) + _qol(
        profile, ["여가생활 만족도", "하루 평균 여가시간"]
    )


def _health(profile) -> list[dict]:
    health = _klips_matched(profile, [
        ("수면시간", "평균 수면시간", "시간"),
        ("불면지수", "평균 불면지수", "점"),
        ("스트레스", "평균 스트레스", "점"),
        ("우울2주지속", "2주 이상 우울 경험 비율", "rate"),
        ("휴식_필요", "평균 휴식 필요도", "점"),
        ("BMI", "평균 BMI", "kg/㎡"),
    ])
    return health + _lanollab(profile, HEALTH_INDS) + _qol(
        profile, ["스트레스 인지율", "주관적 건강상태 양호율"]
    )


def _business_for_choice(profile) -> list[dict]:
    """자유입력에서 해석한 업종·규모 기준의 창업 생존율."""
    rows, context = bizsurv_rows(profile)
    if rows is None or rows.empty or context is None:
        return []
    year = int(rows["ref_year"].iloc[0])
    out = []
    for horizon in (1, 3, 5):
        picked = rows[rows["survival_horizon_yr"] == horizon]
        if not picked.empty:
            out.append(_ind(
                f"창업 {horizon}년 생존율", picked.iloc[0]["survival_rate"], "%",
                source="KOSIS 기업생멸행정통계", note=f"{context.label()}·{year}",
            ))
    return out


# domain → (근거수준, 로더). 로더 None = 정량 지표 없음(기존 파이프라인/ RAG/ 데이터부족).
_ROUTES = {
    "career": ("model", None),
    "finance": ("group_stat", _finance),
    "business": ("group_stat", _business_for_choice),
    "education": ("group_stat", _education),
    "health": ("group_stat", _health),
    "lifestyle": ("group_stat", _lifestyle),
    "long_term_values": ("group_stat", _values),
    "relationship": ("group_stat", _relationship),
    "housing": ("insufficient", None),
}

_ROUTE_NOTE = {
    "career": "GOMS/YP 유사인물·인과·생존 모델(기존 엔진)이 담당",
    "relationship": "사회적 고립도 집단통계 + 기록 기반 관계 해석. 선택의 인과효과는 아님",
    "housing": "현재 뒷받침 데이터 없음 — 수치 대신 신중히 안내",
    "health": "KLIPS 유사 조건 건강·수면 관측 + KNHANES/CHS 연령집단 기준값. 선택 효과는 아님",
    "lifestyle": "KLIPS 유사 조건 근무시간·야간·교대·휴식 관측 + 공공 집단 기준값",
    "long_term_values": "예측 대상이 아니라 사용자가 중요하게 보는 결과의 정렬·강조 기준",
}

DOMAIN_OUTCOMES = {
    "career": ["소득·고용 안정", "직종·고용형태 변화", "직무·삶 만족"],
    "education": ["학비·소득 공백", "학력·취업 전환", "교육·삶 만족"],
    "business": ["사업소득·생존", "자영 전환·지속", "직무·건강·삶 만족"],
    "finance": ["가처분소득·자산·부채", "선택 가능 여력", "재무 스트레스·삶 만족"],
    "health": ["의료·근로 부담", "활동·기능 변화", "수면·스트레스·주관 건강"],
    "housing": ["주거비·자산·부채", "통근·생활 기회", "주거·삶 만족"],
    "relationship": ["가구 재정 변화", "관계 행동 지속", "가족·사회관계 만족·고립"],
    "lifestyle": ["소득·생활비", "시간 활용 변화", "수면·여가·스트레스"],
    "long_term_values": ["경제적 감당 가능성", "가치와 선택의 정합성", "장기 만족·후회 신호"],
}


def route_domains(domains, profile: dict, choice: str | None = None) -> dict:
    """domain 리스트 → {domain: {label, evidence, indicators[], source_note}}."""
    prof = {**(profile or {})}
    if choice:
        prof["choice"] = choice
    result = {}
    for d in domains or []:
        evidence, loader = _ROUTES.get(d, ("insufficient", None))
        inds = loader(prof) if loader else []
        # 로더가 데이터를 못 찾으면 근거수준을 강등(정직).
        if loader and not inds and evidence == "group_stat":
            evidence = "insufficient"
        result[d] = {
            "domain": d,
            "label": DOMAIN_LABELS.get(d, d),
            "status": "available" if inds or evidence in {"model", "rag"} else "unavailable",
            "evidence": evidence,
            "claim_type": (
                "model_output" if evidence == "model" else
                "population_reference_not_choice_effect" if evidence == "group_stat" else
                "qualitative_interpretation" if evidence == "rag" else
                "insufficient_evidence"
            ),
            "indicators": inds,
            "outcome_contract": DOMAIN_OUTCOMES.get(d, []),
            "source_note": _ROUTE_NOTE.get(d),
            "limitation": (
                "현재 조건과 유사한 집단의 참고값이며 이 선택이 만든 개인 효과가 아닙니다."
                if evidence == "group_stat" else
                "현재 연결된 정량 데이터가 없어 숫자를 만들지 않습니다."
                if evidence == "insufficient" else None
            ),
        }
    return result
