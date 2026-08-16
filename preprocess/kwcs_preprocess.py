"""
KWCS 근로환경조사 제7차(2023) 전처리 스크립트
─────────────────────────────────────────────
대상: 취업자 (19세 이상)  ※ 전 국민 지표와 직접 비교 불가
지표 (KWCS 고유)
  1) 업무스트레스        (work_stress)      wsituation12: 1·2(항상+대부분)=있음
  2) 불안감 유병          (anxiety)          heal_prob5: 1=있음
  3) 우울함 유병          (depress)          heal_prob8: 1=있음
  4) 수면장애            (sleep_problem)    sleep1~3 중 하나라도 1·2=있음

KWCS 특수사항
  - 집락(PSU) 변수 없음 → 층화(stratification)+가중치(wt2)만 반영하는 근사 복합표본 분석.
  - 결측 코드: 7(해당없음)·8(모름/무응답)·9(거절).
  - 리커트 방향 주의: 1=항상/매일(가장 잦음), 5=전혀.
  - 대상이 취업자이므로 출처·대상을 명확히 표기.

사용법
  pip install pyreadstat pandas numpy samplics
  python kwcs_preprocess.py
"""

from pathlib import Path
import numpy as np
import pandas as pd
import pyreadstat

# ─────────────────────────────────────────────
# 0. 설정
# ─────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent

DATA_DIR   = ROOT / "data/raw/kwcs"
PERSON_OUT = ROOT / "data/processed/kwcs7_person_level.csv"
LOOKUP_OUT = ROOT / "data/lanollab/산업안전보건연구원_근로환경조사/lookup_kwcs_indicators_v1.csv"

SURVEY_ROUND = "7차"
SURVEY_YEAR = 2023
AGE_MIN = 19

STRATA_VAR = "stratification"   # 조사구층ID (층화)
WEIGHT_VAR = "wt2"              # 최종가중치
# 집락(PSU) 없음 → None
PSU_VAR = None

SEX_VAR = "gender"
AGE_VAR = "age"

STRESS_VAR   = "wsituation12"                   # 1~5 (1·2=스트레스 있음)
ANXIETY_VAR  = "heal_prob5"                     # 1=있음, 2=없음
DEPRESS_VAR  = "heal_prob8"                     # 1=있음, 2=없음
SLEEP_VARS   = ["sleep1", "sleep2", "sleep3"]   # 1~5 (1·2=자주)

MISSING_CODES = [7, 8, 9]   # 해당없음/모름·무응답/거절


# ─────────────────────────────────────────────
# 1. 로드
# ─────────────────────────────────────────────
def find_file():
    savs = list(DATA_DIR.glob("*.sav"))
    if not savs:
        raise FileNotFoundError(f"{DATA_DIR} 에 .sav 파일이 없습니다.")
    return str(savs[0])


def load_data():
    path = find_file()
    usecols = ([STRATA_VAR, WEIGHT_VAR, SEX_VAR, AGE_VAR,
                STRESS_VAR, ANXIETY_VAR, DEPRESS_VAR] + SLEEP_VARS)
    try:
        df, meta = pyreadstat.read_sav(path, usecols=usecols)
    except UnicodeDecodeError:
        df, meta = pyreadstat.read_sav(path, usecols=usecols, encoding="euc-kr")
    df = df.rename(columns={SEX_VAR: "sex", AGE_VAR: "age"})
    print(f"[로드] {Path(path).name}: {df.shape[0]:,}행 × {df.shape[1]:,}열")
    return df


def _to_missing(s):
    return s.where(~s.isin(MISSING_CODES), np.nan)


# ─────────────────────────────────────────────
# 2. 파생변수
# ─────────────────────────────────────────────
def derive_work_stress(df):
    """업무스트레스: 1~5 유효, 1·2(항상+대부분 그렇다)=스트레스 있음."""
    s = pd.Series(np.nan, index=df.index)
    if STRESS_VAR in df.columns:
        v = _to_missing(df[STRESS_VAR])
        valid = v.isin([1, 2, 3, 4, 5])
        s.loc[valid] = v.loc[valid].isin([1, 2]).astype(float)
    df["work_stress"] = s
    return df


def derive_binary(df, src, out):
    """이진 건강문제(불안/우울): 1=있음, 2=없음."""
    s = pd.Series(np.nan, index=df.index)
    if src in df.columns:
        v = _to_missing(df[src])
        valid = v.isin([1, 2])
        s.loc[valid] = (v.loc[valid] == 1).astype(float)
    df[out] = s
    return df


def derive_sleep_problem(df):
    """수면장애 종합: sleep1~3 각 1~5 유효, 1·2(매일+주 여러번)=해당 증상.
    셋 중 하나라도 해당하면 수면장애 있음(1).
    세 문항 모두 결측이면 종합값도 결측.
    """
    present = [c for c in SLEEP_VARS if c in df.columns]
    if not present:
        df["sleep_problem"] = np.nan
        return df

    any_problem = pd.Series(0.0, index=df.index)
    all_missing = pd.Series(True, index=df.index)
    for c in present:
        v = _to_missing(df[c])
        valid = v.isin([1, 2, 3, 4, 5])
        all_missing &= ~valid                       # 하나라도 유효하면 False
        sym = valid & v.isin([1, 2])                # 이 문항에서 증상 있음
        any_problem = np.where(sym, 1.0, any_problem)
    any_problem = pd.Series(any_problem, index=df.index)
    any_problem[all_missing] = np.nan               # 전부 결측이면 종합도 결측
    df["sleep_problem"] = any_problem
    return df


def add_agegroup(df):
    bins   = [0, 18, 29, 39, 49, 59, 69, 200]
    labels = ["0-18", "19-29", "30-39", "40-49", "50-59", "60-69", "70+"]
    df["agegroup"] = pd.cut(df["age"], bins=bins, labels=labels, right=True)
    return df


# ─────────────────────────────────────────────
# 3. 복합표본 추정 (층화+가중치, 집락 없음)
# ─────────────────────────────────────────────
def _scalarize(v):
    if isinstance(v, dict):
        return float(next(iter(v.values())))
    if isinstance(v, (list, tuple, np.ndarray)):
        return float(np.asarray(v).ravel()[0])
    return float(v)


def weighted_estimate(df, y_col, domain_cols=None):
    sub = df.copy()
    sub = sub[sub["age"] >= AGE_MIN]
    sub = sub[sub[y_col].notna() & sub[WEIGHT_VAR].notna() &
              sub[STRATA_VAR].notna()]
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
                # 집락 없음: psu 인자를 생략(층화+가중치만)
                est.estimate(y=y, samp_weight=w,
                             stratum=g[STRATA_VAR].values, remove_nan=True)
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
        ("업무스트레스",   "work_stress"),
        ("불안감유병",     "anxiety"),
        ("우울함유병",     "depress"),
        ("수면장애",       "sleep_problem"),
    ]
    rows = []
    for label, ycol in specs:
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
            res["단위"] = "%"
            res["출처"] = f"KWCS {SURVEY_ROUND}"
            res["조사연도"] = str(SURVEY_YEAR)
            res["대상"] = "취업자"
            rows.append(res)
    if not rows:
        return pd.DataFrame()
    table = pd.concat(rows, ignore_index=True, sort=False)
    table["값"] = (table["estimate"] * 100).round(1)
    return table


# ─────────────────────────────────────────────
# 실행
# ─────────────────────────────────────────────
def main():
    df = load_data()
    df = derive_work_stress(df)
    df = derive_binary(df, ANXIETY_VAR, "anxiety")
    df = derive_binary(df, DEPRESS_VAR, "depress")
    df = derive_sleep_problem(df)
    df = add_agegroup(df)

    keep = [STRATA_VAR, WEIGHT_VAR, "sex", "age", "agegroup",
            "work_stress", "anxiety", "depress", "sleep_problem"]
    keep = [c for c in keep if c in df.columns]
    PERSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    df[keep].to_csv(PERSON_OUT, index=False, encoding="utf-8-sig")
    print(f"[저장] {PERSON_OUT.relative_to(ROOT)}")

    ref = build_reference_table(df)
    if not ref.empty:
        out_cols = ["지표명", "구분유형", "sex", "agegroup",
                    "값", "단위", "se", "n", "출처", "조사연도", "대상"]
        out_cols = [c for c in out_cols if c in ref.columns]
        LOOKUP_OUT.parent.mkdir(parents=True, exist_ok=True)
        ref[out_cols].to_csv(LOOKUP_OUT, index=False, encoding="utf-8-sig")
        print(f"[저장] {LOOKUP_OUT.relative_to(ROOT)}")
        print("\n[미리보기 - 전체 지표]")
        prev = ref[ref["구분유형"] == "전체"][["지표명", "값", "단위", "n"]]
        print(prev.to_string(index=False))


if __name__ == "__main__":
    main()
