"""
CHS 지역사회건강조사 2025 전처리 스크립트
─────────────────────────────────────────────
대상 지표 (KNHANES와 동일 4종)
  1) 스트레스인지율        (mh_stress)
  2) 우울장애유병률 PHQ-9  (mh_PHQ_S10)
  3) 주중 평균 수면시간    (sleep_wk, 단위=시간)
  4) 삶의 질 EQ-5D 5개 차원 (eq5d_*)

CHS와 KNHANES의 핵심 차이 (반드시 유의)
  - 단일 연도(2025)라 통합가중치(÷N) 로직이 불필요.
  - PHQ-9 척도가 1~4점(KNHANES는 0~3점) → 각 문항에서 1을 빼 0~3으로 변환 후 합산.
  - 결측 코드가 7(응답거부)·9(모름)  (KNHANES는 8·9).
  - 설계변수: kstrata(층) / SPOT_NO(집락) / wt_p(개인가중치).
  - 수면은 직접응답형(시간 단위) 단일 변수.

사용법
  1) DATA_PATH 확인
  2) pip install pyreadstat pandas numpy samplics
  3) python chs_preprocess.py
"""

from pathlib import Path
import numpy as np
import pandas as pd
import pyreadstat

# ─────────────────────────────────────────────
# 0. 설정
# ─────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent

DATA_PATH  = ROOT / "data/raw/chs/chs25_all.sas7bdat"
PERSON_OUT = ROOT / "data/processed/chs2025_person_level.csv"
LOOKUP_OUT = ROOT / "data/lanollab/질병관리청_지역사회건강조사/lookup_chs_indicators_v1.csv"

SURVEY_YEAR = 2025

# 설계변수 (CHS)
STRATA_VAR  = "kstrata"    # 층화
PSU_VAR     = "SPOT_NO"    # 집락(표본지점)
WEIGHT_VAR  = "wt_p"       # 개인가중치

# 지표 원문항 (메타데이터 확인 결과 기준)
STRESS_VAR  = "mta_01z1"                              # 주관적 스트레스 (1~4점, 1·2=많이)
PHQ_VARS    = [f"mtb_07{c}1" for c in "abcdefghi"]    # mtb_07a1 ~ mtb_07i1 (1~4점)
SLEEP_VAR   = "mtc_17z1"                              # 주중 평균 수면시간(시간)
EQ5D_VARS   = {                                       # 1/2/3 = 문제수준, 7·9=결측
    "mobility": "qoc_01z1",
    "selfcare": "qoc_02z1",
    "usual":    "qoc_03z1",
    "pain":     "qoc_04z1",
    "anxiety":  "qoc_05z1",
}

# 결측 코드 (CHS 공통)
MISSING_CODES = [7, 9]   # 7=응답거부, 9=모름
# ※ 일부 변수는 77/99, 7.7/9.9 등을 쓸 수 있으니 값 분포로 재확인 권장

# 성별·연령 변수 후보 (자동 탐색)
SEX_CANDIDATES = ["sex", "SEX", "sexn", "sex_n"]
AGE_CANDIDATES = ["age", "AGE", "agen", "age_n"]


# ─────────────────────────────────────────────
# 1. 로드 (필요 변수만)
# ─────────────────────────────────────────────
def resolve_var(meta_cols, candidates, kind):
    for c in candidates:
        if c in meta_cols:
            return c
    raise KeyError(f"{kind} 변수를 찾지 못했습니다. 후보: {candidates}")


def load_data():
    # 먼저 메타만 읽어 성별·연령 변수명 확정
    try:
        _, meta = pyreadstat.read_sas7bdat(str(DATA_PATH), metadataonly=True)
    except UnicodeDecodeError:
        _, meta = pyreadstat.read_sas7bdat(str(DATA_PATH), metadataonly=True,
                                           encoding="euc-kr")
    cols = set(meta.column_names)
    sex_var = resolve_var(cols, SEX_CANDIDATES, "성별")
    age_var = resolve_var(cols, AGE_CANDIDATES, "연령")
    print(f"[변수확정] 성별={sex_var}, 연령={age_var}")

    usecols = ([STRATA_VAR, PSU_VAR, WEIGHT_VAR, sex_var, age_var,
                STRESS_VAR, SLEEP_VAR] + PHQ_VARS + list(EQ5D_VARS.values()))
    usecols = [c for c in usecols if c in cols]

    try:
        df, meta = pyreadstat.read_sas7bdat(str(DATA_PATH), usecols=usecols)
    except UnicodeDecodeError:
        df, meta = pyreadstat.read_sas7bdat(str(DATA_PATH), usecols=usecols,
                                            encoding="euc-kr")
    df = df.rename(columns={sex_var: "sex", age_var: "age"})
    df["year"] = SURVEY_YEAR
    print(f"[로드] {df.shape[0]:,}행 × {df.shape[1]:,}열")
    return df


# ─────────────────────────────────────────────
# 2. 파생변수
# ─────────────────────────────────────────────
def _to_missing(s):
    """CHS 결측코드(7·9)를 NaN으로."""
    return s.where(~s.isin(MISSING_CODES), np.nan)


def derive_stress(df):
    """스트레스인지율: 1~4점 유효, 1·2(대단히많이/많이)=인지."""
    s = pd.Series(np.nan, index=df.index)
    if STRESS_VAR in df.columns:
        v = _to_missing(df[STRESS_VAR])
        valid = v.isin([1, 2, 3, 4])
        s.loc[valid] = v.loc[valid].isin([1, 2]).astype(float)
    df["mh_stress"] = s
    return df


def derive_phq(df):
    """우울장애유병률: CHS는 1~4점 → 1을 빼 0~3으로 변환 후 합산, 총점>=10.
    9문항 모두 유효(1~4)일 때만 산출.
    """
    if not all(c in df.columns for c in PHQ_VARS):
        df["mh_PHQ_S10"] = np.nan
        return df
    valid = np.ones(len(df), dtype=bool)
    converted = pd.DataFrame(index=df.index)
    for c in PHQ_VARS:
        v = _to_missing(df[c])
        valid &= v.isin([1, 2, 3, 4])
        converted[c] = v - 1            # 1~4 → 0~3
    total = converted.sum(axis=1)       # 0~27
    s = pd.Series(np.nan, index=df.index)
    s.loc[valid] = (total[valid] >= 10).astype(float)
    df["mh_PHQ_S10"] = s
    return df


def derive_sleep(df):
    """주중 평균 수면시간(시간). 직접응답형, 결측코드 제거.
    비현실값(예: 0 또는 24 초과)은 결측 처리.
    """
    s = pd.Series(np.nan, index=df.index)
    if SLEEP_VAR in df.columns:
        v = _to_missing(df[SLEEP_VAR])
        # 77/99 같은 2자리 결측이 섞일 수 있어 방어
        v = v.where(v.between(1, 24), np.nan)
        s = v
    df["sleep_wk"] = s
    return df


def derive_eq5d(df):
    """EQ-5D 5개 차원. 1/2/3 유효, 7·9 결측. 코드>=2 = 문제있음."""
    for dim, col in EQ5D_VARS.items():
        prob = f"eq5d_{dim}_problem"
        if col not in df.columns:
            df[prob] = np.nan
            continue
        v = _to_missing(df[col])
        v = v.where(v.isin([1, 2, 3]), np.nan)
        df[prob] = np.where(v.notna(), (v >= 2).astype(float), np.nan)
    return df


def add_agegroup(df):
    bins   = [0, 18, 29, 39, 49, 59, 69, 200]
    labels = ["0-18", "19-29", "30-39", "40-49", "50-59", "60-69", "70+"]
    df["agegroup"] = pd.cut(df["age"], bins=bins, labels=labels, right=True)
    return df


# ─────────────────────────────────────────────
# 3. 복합표본 가중 추정 (samplics 0.6.0)
# ─────────────────────────────────────────────
def _scalarize(v):
    if isinstance(v, dict):
        return float(next(iter(v.values())))
    if isinstance(v, (list, tuple, np.ndarray)):
        return float(np.asarray(v).ravel()[0])
    return float(v)


def weighted_estimate(df, y_col, domain_cols=None, age_min=19):
    sub = df.copy()
    if age_min is not None:
        sub = sub[sub["age"] >= age_min]
    sub = sub[sub[y_col].notna() & sub[WEIGHT_VAR].notna() &
              sub[STRATA_VAR].notna() & sub[PSU_VAR].notna()]
    if sub.empty:
        return None

    try:
        from samplics.estimation import TaylorEstimator
        from samplics.utils.types import PopParam

        def _one(g):
            w, y = g[WEIGHT_VAR].values, g[y_col].values
            n = len(g)
            try:
                est = TaylorEstimator(PopParam.mean)
                est.estimate(y=y, samp_weight=w,
                             stratum=g[STRATA_VAR].values,
                             psu=g[PSU_VAR].values, remove_nan=True)
                point = _scalarize(est.point_est)
                se = _scalarize(est.stderror)
            except Exception:
                point = float(np.average(y, weights=w))
                se = np.nan
            return pd.Series({"estimate": point, "se": se, "n": n})

        if domain_cols:
            return (sub.groupby(domain_cols, observed=True)
                       .apply(_one, include_groups=False).reset_index())
        return _one(sub).to_frame().T
    except ImportError:
        print("  [알림] samplics 미설치 → 가중평균만 계산.")

        def _wmean(g):
            w, y = g[WEIGHT_VAR].values, g[y_col].values
            return pd.Series({"estimate": np.average(y, weights=w),
                              "se": np.nan, "n": len(g)})
        if domain_cols:
            return (sub.groupby(domain_cols, observed=True)
                       .apply(_wmean, include_groups=False).reset_index())
        return _wmean(sub).to_frame().T


# ─────────────────────────────────────────────
# 4. 참조 테이블
# ─────────────────────────────────────────────
def build_reference_table(df):
    specs = [
        ("스트레스인지율",    "mh_stress",            "%"),
        ("우울장애유병률",    "mh_PHQ_S10",           "%"),
        ("주중평균수면시간",  "sleep_wk",             "시간"),
        ("EQ5D_불안우울문제", "eq5d_anxiety_problem", "%"),
        ("EQ5D_통증문제",     "eq5d_pain_problem",    "%"),
    ]
    rows = []
    for label, ycol, unit in specs:
        if ycol not in df.columns:
            continue
        for domain, dcols in [("전체", None), ("성별", ["sex"]),
                              ("연령대", ["agegroup"]),
                              ("성별×연령대", ["sex", "agegroup"])]:
            res = weighted_estimate(df, ycol, dcols)
            if res is None:
                continue
            res = res.copy()
            res["지표명"] = label
            res["구분유형"] = domain
            res["단위"] = unit
            res["출처"] = f"CHS {SURVEY_YEAR}"
            res["조사연도"] = str(SURVEY_YEAR)
            rows.append(res)
    if not rows:
        return pd.DataFrame()
    table = pd.concat(rows, ignore_index=True, sort=False)

    def to_display(r):
        if r["단위"] == "시간":
            return round(r["estimate"], 2)
        return round(r["estimate"] * 100, 1)
    table["값"] = table.apply(to_display, axis=1)
    return table


# ─────────────────────────────────────────────
# 실행
# ─────────────────────────────────────────────
def main():
    df = load_data()
    df = derive_stress(df)
    df = derive_phq(df)
    df = derive_sleep(df)
    df = derive_eq5d(df)
    df = add_agegroup(df)

    keep = [STRATA_VAR, PSU_VAR, WEIGHT_VAR, "sex", "age", "agegroup", "year",
            "mh_stress", "mh_PHQ_S10", "sleep_wk"] + \
           [f"eq5d_{d}_problem" for d in EQ5D_VARS]
    keep = [c for c in keep if c in df.columns]
    PERSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    df[keep].to_csv(PERSON_OUT, index=False, encoding="utf-8-sig")
    print(f"[저장] {PERSON_OUT.relative_to(ROOT)}")

    ref = build_reference_table(df)
    if not ref.empty:
        out_cols = ["지표명", "구분유형", "sex", "agegroup",
                    "값", "단위", "se", "n", "출처", "조사연도"]
        out_cols = [c for c in out_cols if c in ref.columns]
        LOOKUP_OUT.parent.mkdir(parents=True, exist_ok=True)
        ref[out_cols].to_csv(LOOKUP_OUT, index=False, encoding="utf-8-sig")
        print(f"[저장] {LOOKUP_OUT.relative_to(ROOT)}")
        print("\n[미리보기 - 전체 지표]")
        prev = ref[ref["구분유형"] == "전체"][["지표명", "값", "단위", "n"]]
        print(prev.to_string(index=False))


if __name__ == "__main__":
    main()
