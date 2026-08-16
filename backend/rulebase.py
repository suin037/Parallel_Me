"""Layer 1 — 룰베이스 '생활지표 조회' 엔진.

사용자 프로필(나이·성별·선택)로 연결된 공공통계 lookup 을 조회해
'인생 여러 차원'의 지표 패널을 만든다:
    경제(또래 임금·이직 소득변화) · 삶의질 · 정신건강 · 신체건강 ·
    직업환경 · 창업 …

설계 원칙(확장형):
  - 각 소스(_src_*)는 list[dict] 를 반환하고, 파일이 없거나 매칭이 실패하면
    '조용히' 빈 리스트를 돌려준다. -> 데이터가 더 붙을수록 패널이 저절로 넓어진다.
  - 심리학적 해석은 여기서 하지 않는다. 이 숫자 패널을 받아 RAG(팀 3)가 해석한다.

반환 dict 스키마:
  {dimension, indicator, value, unit, group, source}
"""

from __future__ import annotations

from dataclasses import replace
from functools import lru_cache
from pathlib import Path

import pandas as pd

from choice_classifier import SCALE_ALL, classify, extract_startup_context
from config import settings

DATA = settings.data_abspath                       # <ROOT>/data
# ⚠ 예전엔 goms_clean_abspath.parent 로 잡았는데, goms_clean 이 data/clean/ 로
#   옮겨지면서 data/clean/dgroup 을 가리키게 됐다. _csv() 가 없는 경로를 조용히
#   None 으로 넘겨 L1 생활지표가 통째로 빈 채 서빙됐다. data_dir 기준으로 고정.
DGROUP = DATA / "dgroup"
LANOLLAB = DATA / "lanollab"

ELFS_AGE = DGROUP / "kosis_고용형태별근로실태조사_연령별/lookup_elfs_wage_by_age_v1.csv"
BIZSURV = DGROUP / "kosis_기업생멸행정통계/lookup_bizsurvival_survival_v1.csv"
QOL = DGROUP / "kosis_사회통합실태조사/lookup_qol_indicators_v2.csv"
YOUTHQOL = DGROUP / "국가데이터처_청년삶의질2025/lookup_youthqol_indicators_v1.csv"
KEDI = DGROUP / "한국교육개발원_고등교육기관_졸업자_학과별_상황/lookup_kedi_emp_rate_by_field_v1.csv"
MASTER = LANOLLAB / "lookup_lanollab_master_v1.csv"

# 계열명 목록 (profile.major 매칭용)
_FIELDS = ["인문", "사회", "교육", "공학", "자연", "의약", "예체능", "기타"]


@lru_cache(maxsize=16)
def _csv(path_str: str):
    p = Path(path_str)
    return pd.read_csv(p) if p.exists() else None


# ---------------------------------------------------------------- 나이 → 연령구간
def _elfs_ageband(age: float) -> str:
    if age <= 29: return "29세이하"
    if age <= 39: return "30~39세"
    if age <= 49: return "40~49세"
    if age <= 59: return "50~59세"
    return "60세이상"


def _lanollab_ageband(age: float) -> str:
    if age <= 29: return "19-29"
    if age <= 39: return "30-39"
    if age <= 49: return "40-49"
    if age <= 59: return "50-59"
    if age <= 69: return "60-69"
    return "70+"


def _qol_ageband(age: float):
    if age < 30: return "20대"
    if age < 40: return "30대"
    return None                      # qol 은 20/30대만 -> 전체로 폴백


def _youthqol_ageband(age: float) -> str:
    if 25 <= age <= 29: return "25-29"
    if 30 <= age <= 34: return "30-34"
    return "19-34"


def _sex_int(profile: dict):
    try:
        return int(float(profile.get("sex")))
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- 소스 어댑터
def _src_job_change_income(profile: dict) -> list[dict]:
    """이직자 소득변화(GOMS 단면) — Layer1 대표 지표."""
    df = _csv(str(settings.goms_clean_abspath))
    if df is None or "income_change_pct" not in df.columns or "changed_job" not in df.columns:
        return []
    d = df[df["changed_job"] == 1]
    ic = pd.to_numeric(d["income_change_pct"], errors="coerce").dropna()
    if ic.empty:
        return []
    return [{"dimension": "경제", "indicator": "이직자 소득변화(중앙값)",
             "value": round(float(ic.median()), 1), "unit": "%",
             "group": f"이직 경험자 {len(ic):,}명", "source": "대졸자직업이동경로조사(GOMS)"}]


def _src_wage(profile: dict) -> list[dict]:
    """또래(연령대) 평균 월임금 벤치마크."""
    df = _csv(str(ELFS_AGE))
    if df is None:
        return []
    band = _elfs_ageband(profile.get("age", 30))
    d = df[(df["age_group"] == band) & (df["emp_type"] == "전체근로자")]
    if d.empty:
        return []
    d = d[d["year"] == d["year"].max()]
    return [{"dimension": "경제", "indicator": "또래 평균 월임금(전체근로자)",
             "value": round(float(d["월임금총액_만원"].iloc[0]), 1), "unit": "만원",
             "group": f"{band}·{int(d['year'].iloc[0])}",
             "source": "고용형태별근로실태조사(KOSIS)"}]


def _match_master(df, indicator: str, sex, age):
    """lanollab 통일스키마: 성별×연령대 → 연령대 → 성별 → 전체 순 폴백."""
    band = _lanollab_ageband(age)
    sub = df[df["지표명"] == indicator]
    if sub.empty:
        return None
    candidates = [
        ("성별×연령대", (sub["sex"] == sex) & (sub["agegroup"] == band)),
        ("연령대", sub["agegroup"] == band),
        ("성별", sub["sex"] == sex),
        ("전체", pd.Series(True, index=sub.index)),
    ]
    for gtype, cond in candidates:
        m = sub[(sub["구분유형"] == gtype) & cond]
        if not m.empty:
            r = m.iloc[0]
            return float(r["값"]), str(r["단위"]), gtype, str(r.get("출처", ""))
    return None


def _src_health(profile: dict) -> list[dict]:
    """정신건강·신체건강·직업환경 (KNHANES/CHS/KWCS 통합 마스터)."""
    df = _csv(str(MASTER))
    if df is None:
        return []
    sex, age = _sex_int(profile), profile.get("age", 30)
    dims = {"스트레스인지율": "정신건강", "우울장애유병률": "정신건강",
            "불안감유병": "정신건강", "수면장애": "신체건강",
            "업무스트레스": "직업환경"}
    out = []
    for ind, dim in dims.items():
        r = _match_master(df, ind, sex, age)
        if r:
            v, unit, gtype, src = r
            out.append({"dimension": dim, "indicator": ind, "value": round(v, 1),
                        "unit": unit, "group": gtype, "source": src or "KNHANES/CHS/KWCS"})
    return out


def _src_qol(profile: dict) -> list[dict]:
    """삶의 질(사회통합실태조사) — 삶의만족도·행복감·계층상승 인식."""
    df = _csv(str(QOL))
    if df is None:
        return []
    band = _qol_ageband(profile.get("age", 30))
    picks = ["삶의 만족도", "행복감(어제)", "계층 상승 가능성 인식(본인)"]
    out = []
    for ind in picks:
        sub = df[df["indicator_name"] == ind]
        if sub.empty:
            continue
        m = sub[sub["group"] == band] if band else sub[sub["group"] == "전체"]
        if m.empty:
            m = sub[sub["group"] == "전체"]
        if m.empty:
            continue
        m = m[m["year"] == m["year"].max()]
        r = m.iloc[0]
        out.append({"dimension": "삶의질", "indicator": ind, "value": float(r["value"]),
                    "unit": str(r["unit"]), "group": str(r["group"]),
                    "source": "사회통합실태조사"})
    return out


def _src_youth(profile: dict) -> list[dict]:
    """청년(≤34) 전용 삶의질 지표 — 번아웃·외로움·소득만족 등."""
    df = _csv(str(YOUTHQOL))
    age = profile.get("age", 30)
    if df is None or age > 34:
        return []
    band = _youthqol_ageband(age)
    picks = ["번아웃 경험률", "외로움 경험률", "소득 만족도", "삶의 만족도(청년삶실태)"]
    out = []
    for ind in picks:
        sub = df[df["indicator_name"] == ind]
        if sub.empty:
            continue
        m = sub[sub["group"] == band]
        if m.empty:
            m = sub
        m = m[m["year"] == m["year"].max()]
        r = m.iloc[0]
        out.append({"dimension": "삶의질(청년)", "indicator": ind, "value": float(r["value"]),
                    "unit": str(r["unit"]), "group": str(r["group"]),
                    "source": "청년 삶의 질(국가데이터처)"})
    return out


def _src_education(profile: dict) -> list[dict]:
    """계열별 취업률·진학률 (KEDI 고등교육 졸업 후 상황).

    진학 vs 취업 저울질에 핵심. profile.major 가 계열명과 매칭되면 그 계열,
    아니면 '전체' 기준값을 제공한다.
    """
    df = _csv(str(KEDI))
    if df is None:
        return []
    major = str(profile.get("major", ""))
    field = next((f for f in _FIELDS if f in major), None)
    row = df[df["major_field"] == field] if field else df[df["major_field"] == "전체"]
    if row.empty:
        row = df[df["major_field"] == "전체"]
    if row.empty:
        return []
    r = row.iloc[0]
    label = str(r["major_field"])
    out = []
    if pd.notna(r.get("emp_rate")):
        out.append({"dimension": "진학/취업", "indicator": f"{label} 계열 취업률",
                    "value": round(float(r["emp_rate"]), 1), "unit": "%",
                    "group": f"{label}·{r.get('year', '')}", "source": "KEDI 고등교육 졸업 후 상황"})
    if pd.notna(r.get("advance_rate")):
        out.append({"dimension": "진학/취업", "indicator": f"{label} 계열 진학률(대학원 등)",
                    "value": round(float(r["advance_rate"]), 1), "unit": "%",
                    "group": f"{label}·{r.get('year', '')}", "source": "KEDI 고등교육 졸업 후 상황"})
    return out


def bizsurv_rows(profile: dict):
    """생존율 테이블에서 이 프로필에 맞는 (최신연도 행들, 적용된 맥락) 을 고른다.

    `domain_router` 도 같은 축으로 조회해야 해서 공개 함수로 둔다 — 창업 생존율의
    필터 규칙이 두 군데로 갈라지면 화면마다 다른 숫자가 나온다.

    예전엔 `전체 업종 × 전 규모(계)` 한 조합만 읽었다. 테이블에는 업종 19개 ×
    규모 5개 × 연차 5개가 다 들어 있는데 4,718행 중 3행만 쓴 셈이고, 그래서
    "카페 창업" 과 "IT 창업" 이 같은 숫자를 받았다. 실제 차이는 작지 않다
    (5년 생존율: 숙박·음식점 26.1% vs 보건·복지 67.4%, 전체 평균 35.4%).

    요청한 조합이 테이블에 없으면 **업종보다 규모를 먼저 포기**한다. 업종별
    차이가 규모별 차이보다 크기 때문이다. 실제로 완화가 필요한 건 표본이 얇은
    광업·전기가스의 대규모 칸 정도다.
    """
    df = _csv(str(BIZSURV))
    if df is None:
        return None, None
    ctx = extract_startup_context(str(profile.get("choice", "")))

    for industry, scale, applied in (
        (ctx.industry_or_all, ctx.scale, ctx),
        (ctx.industry_or_all, SCALE_ALL, replace(ctx, scale=SCALE_ALL, scale_inferred=False)),
        ("전체", ctx.scale, replace(ctx, ksic_section=None, industry=None)),
        ("전체", SCALE_ALL, replace(ctx, ksic_section=None, industry=None,
                                    scale=SCALE_ALL, scale_inferred=False)),
    ):
        d = df[(df["industry"].astype(str) == industry)
               & (df["firm_size"].astype(str) == scale)]
        if not d.empty:
            return d[d["ref_year"] == d["ref_year"].max()], applied
    return None, None


def _src_startup(profile: dict) -> list[dict]:
    """창업 선택 시 — 업종·규모별 창업 N년 생존율.

    ⚠ 예전엔 `"창업" in choice` 부분문자열로 걸렀다. 그래서 "식당 차리고 싶어",
      "한의원 개원" 처럼 '창업' 이라는 단어를 안 쓴 입력은 분류기가 창업으로
      판정해도 이 지표만 조용히 빠졌다. 분류는 분류기 한 곳에서만 한다.
      (record=False — 요청당 집계는 core 에서 이미 한 번 했다)
    """
    if classify(profile.get("choice", ""), record=False).kind != "창업":
        return []
    d, ctx = bizsurv_rows(profile)
    if d is None or d.empty:
        return []
    year = int(d["ref_year"].iloc[0])
    out = []
    # 패널이 넘치지 않게 지표는 1·3·5년만. 연차별 곡선은 타임라인이 5점 다 준다.
    for h in (1, 3, 5):
        m = d[d["survival_horizon_yr"] == h]
        if not m.empty:
            out.append({"dimension": "창업", "indicator": f"창업 {h}년 생존율",
                        "value": round(float(m["survival_rate"].iloc[0]), 1), "unit": "%",
                        "group": f"{ctx.label()}·{year}", "source": "기업생멸행정통계"})
    return out


# 등록된 소스(추가 데이터셋은 여기에 _src 함수 하나만 더 붙이면 패널 확장)
#
# ⚠ 선택(choice)에 따라 값이 달라지는 소스는 `_CHOICE_SOURCES` 로 분리한다.
#   A/B 비교는 `core.new_profile_cache()` 로 L1 을 한 번만 계산해 공유하는데,
#   선택 의존 소스가 여기 섞여 있으면 A 의 업종 생존율이 B 에도 그대로 실린다.
_SOURCES = [
    _src_job_change_income,   # 경제 — 이직 소득변화 (MVP 핵심)
    _src_wage,                # 경제 — 또래 임금
    _src_health,              # 정신/신체건강 · 직업환경
    _src_qol,                 # 삶의질
    _src_youth,               # 청년 삶의질
    _src_education,           # 진학/취업 — 계열별 취업률·진학률 (KEDI)
]

_CHOICE_SOURCES = [
    _src_startup,             # 창업 (choice=창업, 업종·규모별)
]


# --- 지표 → 삶의 영역(9개 domain) 태깅 -------------------------------------
#
# 예전엔 프론트(LifeView)가 지표 '이름 문자열'에 특정 단어가 있는지로 영역을 추측했다.
# 그 방식은 관계 선택에서 15개 중 14개(우울·불안·스트레스·삶의 만족도 등)를 조용히
# 버렸다. 영역 판단은 지표를 만드는 쪽이 알고 있으니 여기서 붙여서 내려보낸다.
#
# 여기서 domain 은 '소유'가 아니라 **"그 영역의 선택을 볼 때 참고할 값인가"** 다.
# 이 지표들은 어차피 선택의 인과효과가 아니라 참고 기준으로 표기되므로 다중 태그가 맞다.
_DIMENSION_DOMAINS = {
    "경제": ["finance", "career"],
    "정신건강": ["health", "relationship"],
    "신체건강": ["health", "lifestyle"],
    "직업환경": ["career", "health", "lifestyle"],
    # 삶의질 계열은 relationship 을 통으로 달지 않는다. '소득 만족도'·'계층 상승 가능성'
    # 까지 관계로 딸려와서다. 관계는 아래 지표명 키워드로만 좁혀 붙인다.
    "삶의질": ["long_term_values", "lifestyle"],
    "삶의질(청년)": ["long_term_values", "lifestyle"],
    "진학/취업": ["education", "career"],
    "창업": ["business"],
}

# dimension 만으로 안 잡히는 것을 지표명 키워드로 보강한다.
_INDICATOR_EXTRA_DOMAINS = [
    ("외로움", ["relationship"]),
    ("고립", ["relationship"]),
    ("관계", ["relationship"]),
    ("삶의 만족도", ["relationship"]),
    ("행복감", ["relationship"]),
    ("수면", ["health", "lifestyle"]),
    ("번아웃", ["health", "career"]),
    ("임금", ["finance", "career"]),
    ("소득", ["finance"]),
    ("취업률", ["education", "career"]),
    ("진학률", ["education"]),
    ("계층 상승", ["long_term_values", "finance"]),
    ("주거", ["housing"]),
    ("주택", ["housing"]),
    ("전세", ["housing"]),
    ("월세", ["housing"]),
]

# 값이 낮을수록 좋은 지표 — A/B 막대 비교에서 방향을 뒤집어 읽어야 한다.
_LOWER_IS_BETTER = (
    "스트레스", "우울", "불안", "수면장애", "고립", "외로움", "번아웃", "폐업",
)


def _tag_domains(item: dict) -> dict:
    """지표 1건에 domains / lower_is_better 를 붙인다 (원본 dict 를 수정하지 않는다)."""
    haystack = f"{item.get('dimension', '')} {item.get('indicator', '')}"
    domains = list(_DIMENSION_DOMAINS.get(item.get("dimension", ""), []))
    for keyword, extra in _INDICATOR_EXTRA_DOMAINS:
        if keyword in haystack:
            domains.extend(extra)
    # 순서 유지 중복 제거 — 첫 태그가 그 지표의 '주 영역'이라 순서에 의미가 있다.
    seen, ordered = set(), []
    for d in domains:
        if d not in seen:
            seen.add(d)
            ordered.append(d)
    return {
        **item,
        "domains": item.get("domains") or ordered,
        "lower_is_better": item.get(
            "lower_is_better", any(w in haystack for w in _LOWER_IS_BETTER)
        ),
    }


def _run(sources, profile: dict) -> list[dict]:
    out: list[dict] = []
    for src in sources:
        try:
            out.extend(src(profile))
        except Exception:
            continue
    return [_tag_domains(item) for item in out]


def query_life_indicators(profile: dict) -> list[dict]:
    """프로필 -> 인생 여러 차원의 지표 패널(**선택 무관**). 실패한 소스는 건너뛴다.

    선택에 따라 갈리는 지표는 `query_choice_indicators()` 가 따로 준다.
    """
    return _run(_SOURCES, profile)


def query_choice_indicators(profile: dict) -> list[dict]:
    """선택(choice)에 따라 갈리는 지표만. A/B 공유 캐시에 태우면 안 되는 쪽."""
    return _run(_CHOICE_SOURCES, profile)


def startup_closure_timeline(profile: dict, years=(1, 2, 3, 4, 5)) -> dict:
    """창업 폐업 누적확률 타임라인 (L4 '후회 리스크'의 창업판).

    창업은 개인단위 인과 데이터가 없어 이직의 L3/L4 를 못 쓴다. 대신 기업생멸통계
    생존율을 폐업확률(=1-생존율)로 바꿔 '시간이 지날수록 접을 확률' 을 준다.
    업종·규모는 자유입력에서 뽑는다(`_bizsurv_rows`).

    테이블에 1~5년이 다 있어서 5점을 그대로 쓴다(예전엔 1·3·5년 3점만 썼다).
    """
    d, _ = bizsurv_rows(profile)
    if d is None or d.empty:
        return {}
    out = {}
    for h in years:
        m = d[d["survival_horizon_yr"] == h]
        if not m.empty:
            out[h] = round(1 - float(m["survival_rate"].iloc[0]) / 100.0, 3)
    return out


def startup_context_meta(profile: dict) -> dict:
    """어떤 업종·규모 기준으로 창업 수치가 나갔는지 (커버리지 문구·프론트 표기용)."""
    _, ctx = bizsurv_rows(profile)
    if ctx is None:
        return {}
    return {**ctx.as_dict(), "label": ctx.label()}
