"""
KNHANES 제9기(2022-2024) 전처리 스크립트
─────────────────────────────────────────────
대상 지표
  1) 스트레스인지율        (mh_stress)
  2) 우울장애유병률 PHQ-9  (mh_PHQ_S10)
  3) 주중 평균 수면시간    (Total_slp_wk)
  4) 삶의 질 EQ-5D 5개 차원 (eq5d_*)  ※ '22·'24 순환문항

설계 원칙
  - 질병관리청 원시자료 이용지침서 표 18(건강설문 주요지표)의
    SAS 조건문을 그대로 Python으로 포팅한다.
    → 유효응답 필터(IF ... in (...))가 곧 결측처리이므로,
      일괄 결측치환을 하지 않고 지표별 조건을 그대로 적용한다.
  - 복합표본설계(kstrata=층, psu=집락, wt_itvex=가중치)를 반영한다.
  - 지표별로 조사된 연도가 다르므로(순환문항) 통합가중치를
    지표별로 따로 계산한다.

사용법
  1) 아래 DATA_DIR 를 .sav 3개가 있는 폴더로 수정
  2) pip install pyreadstat pandas numpy samplics
  3) python knhanes_preprocess.py
"""

from pathlib import Path
import numpy as np
import pandas as pd
import pyreadstat

# ─────────────────────────────────────────────
# 0. 설정
# ─────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent

DATA_DIR   = ROOT / "data/raw/knhanes"
PERSON_OUT = ROOT / "data/processed/knhanes9_person_level.csv"
LOOKUP_OUT = ROOT / "data/lanollab/질병관리청_국민건강영양조사/lookup_knhanes_indicators_v1.csv"

# 파일명 대소문자는 배포본 그대로 (HN24만 _ALL 대문자).
# Windows는 무시하지만 Linux/macOS에서는 정확히 일치해야 함.
FILES = {
    2022: "HN22_all.sav",
    2023: "HN23_all.sav",
    2024: "HN24_ALL.sav",
}

# 분석에 필요한 변수 목록 (설계변수 + 지표 원문항)
DESIGN_VARS = ["ID", "sex", "age", "kstrata", "psu", "wt_itvex"]

STRESS_VARS = ["BP1"]
PHQ_VARS    = [f"BP_PHQ_{i}" for i in range(1, 10)]
# 수면(주중): 연도별로 변수 구조가 다름
#  2022·2023 → BP16_1 (직접 응답한 주중 평균 수면시간, 단위=시간, 88/99=결측)
#  2024      → BP16_11~14 (취침/기상 시각으로 계산, 아래에서 시간 단위로 환산)
SLEEP_VARS_DIRECT = ["BP16_1"]                                  # '22·'23
SLEEP_VARS_CLOCK  = ["BP16_11", "BP16_12", "BP16_13", "BP16_14"]  # '24
# EQ-5D: 제9기 표준 변수명은 LQ_#EQL (값 1/2/3=문제수준, 8/9=비해당/모름).
# 주의: LQ1_mn, LQ2_mn 등은 EQ-5D가 아닌 다른 문항이므로 후보에서 제외한다.
EQ5D_CANDIDATES = {
    "mobility":   ["LQ_1EQL"],       # 운동능력
    "selfcare":   ["LQ_2EQL"],       # 자기관리
    "usual":      ["LQ_3EQL"],       # 일상활동
    "pain":       ["LQ_4EQL"],       # 통증/불편
    "anxiety":    ["LQ_5EQL"],       # 불안/우울
}
BEHAVIOR_VARS = ["pa_aerobic", "sm_presnt", "BD1_11", "HE_BMI"]


# ─────────────────────────────────────────────
# 1. 로드 + 세로 결합
# ─────────────────────────────────────────────
def load_year(year: int, path: Path) -> pd.DataFrame:
    df, meta = pyreadstat.read_sav(str(path))
    df.columns = [c.strip() for c in df.columns]  # 혹시 모를 공백 제거
    df["year"] = year
    return df, meta


def load_all() -> pd.DataFrame:
    frames, metas = [], {}
    for year, fname in FILES.items():
        path = DATA_DIR / fname
        if not path.exists():
            raise FileNotFoundError(f"{path} 를 찾을 수 없습니다.")
        df, meta = load_year(year, path)
        frames.append(df)
        metas[year] = meta
        print(f"[로드] {year}: {df.shape[0]:,}행 × {df.shape[1]:,}열")
    # 세 해의 열 합집합 기준으로 결합 (없는 변수는 자동 NaN)
    combined = pd.concat(frames, ignore_index=True, sort=False)
    return combined, metas


# ─────────────────────────────────────────────
# 2. 순환문항 존재 여부 진단
# ─────────────────────────────────────────────
def diagnose_availability(df: pd.DataFrame) -> dict:
    """지표별로 어느 연도에 데이터가 실제로 있는지 확인."""
    report = {}

    def years_present(cols):
        present = {}
        for y in FILES:
            sub = df[df["year"] == y]
            # 컬럼이 존재하고, 유효값(NaN 아님)이 1개라도 있으면 True
            ok = all(c in df.columns for c in cols) and \
                 sub[cols].notna().any().any()
            present[y] = ok
        return present

    report["stress"] = years_present(STRESS_VARS)
    report["phq"]    = years_present(PHQ_VARS)
    report["aerobic"] = years_present(["pa_aerobic"])
    report["smoking"] = years_present(["sm_presnt"])
    report["alcohol"] = years_present(["BD1_11"])
    report["bmi"] = years_present(["HE_BMI"])

    # 수면: 연도별로 형식이 달라 별도 판정
    #  - 직접응답형(BP16_1) 또는 시각계산형(BP16_11~14) 중 하나라도 있으면 조사된 것으로 간주
    def sleep_present():
        present = {}
        for y in FILES:
            sub = df[df["year"] == y]
            has_direct = all(c in df.columns for c in SLEEP_VARS_DIRECT) and \
                         sub[SLEEP_VARS_DIRECT].notna().any().any()
            has_clock = all(c in df.columns for c in SLEEP_VARS_CLOCK) and \
                        sub[SLEEP_VARS_CLOCK].notna().any().any()
            present[y] = bool(has_direct or has_clock)
        return present
    report["sleep"] = sleep_present()

    # EQ-5D: 후보 중 실제 존재하는 변수명 확정
    eq5d_resolved = {}
    for dim, cands in EQ5D_CANDIDATES.items():
        found = next((c for c in cands if c in df.columns), None)
        eq5d_resolved[dim] = found
    report["eq5d_vars"] = eq5d_resolved
    if all(v is not None for v in eq5d_resolved.values()):
        report["eq5d"] = years_present(list(eq5d_resolved.values()))
    else:
        report["eq5d"] = {y: False for y in FILES}

    print("\n[순환문항 진단]")
    for k in ["stress", "phq", "sleep", "eq5d", "aerobic", "smoking", "alcohol", "bmi"]:
        print(f"  {k:8s}: {report[k]}")
    print(f"  eq5d 변수 매핑: {report['eq5d_vars']}")
    return report


# ─────────────────────────────────────────────
# 3. 파생변수 생성  (지침서 표 18 포팅)
# ─────────────────────────────────────────────
def derive_stress(df):
    """스트레스인지율: BP1 in (1,2,3,4) 유효, (1,2)면 인지."""
    s = pd.Series(np.nan, index=df.index)
    if "BP1" in df.columns:
        valid = df["BP1"].isin([1, 2, 3, 4])
        s.loc[valid] = df.loc[valid, "BP1"].isin([1, 2]).astype(float)
    df["mh_stress"] = s
    return df


def derive_phq(df):
    """우울장애유병률: 9문항 모두 0-3 유효응답일 때만 합산, 총점>=10."""
    if not all(c in df.columns for c in PHQ_VARS):
        df["mh_PHQ_S10"] = np.nan
        return df
    valid = np.ones(len(df), dtype=bool)
    for c in PHQ_VARS:
        valid &= df[c].isin([0, 1, 2, 3])
    total = df[PHQ_VARS].sum(axis=1)
    s = pd.Series(np.nan, index=df.index)
    s.loc[valid] = (total[valid] >= 10).astype(float)
    df["mh_PHQ_S10"] = s
    return df


def derive_sleep(df):
    """주중 평균 수면시간(단위: 시간).

    연도별 측정 방식이 달라 분기 처리한다.
      2022·2023: BP16_1 = 응답자가 직접 답한 주중 평균 수면시간(시간).
                 88·99 = 모름/무응답 → 결측.
      2024:      BP16_11~14 = 취침/기상 시각 → 시각차로 계산 후 60분으로 나눠 시간 환산.
                 자정 넘김(오전 1~12시는 +24) 및 음수 보정 포함.
    세 해 모두 최종 단위를 '시간'으로 통일해 통합 가능하게 한다.
    """
    total = pd.Series(np.nan, index=df.index)

    # ── 2022·2023: 직접응답형 ──
    if all(c in df.columns for c in SLEEP_VARS_DIRECT):
        direct_mask = df["year"].isin([2022, 2023])
        v = df["BP16_1"].where(~df["BP16_1"].isin([88, 99]), np.nan)
        total.loc[direct_mask] = v.loc[direct_mask]

    # ── 2024: 시각계산형 ──
    if all(c in df.columns for c in SLEEP_VARS_CLOCK):
        clock_mask = df["year"] == 2024
        d = df[SLEEP_VARS_CLOCK].copy()
        for c in SLEEP_VARS_CLOCK:
            d.loc[d[c].isin([88, 99]), c] = np.nan
        # 오전(1~12시)은 +24시간 처리하여 밤 시간대와 연속되게 함
        bed_h  = d["BP16_11"].where(~d["BP16_11"].between(1, 12), d["BP16_11"] + 24)
        wake_h = d["BP16_13"].where(~d["BP16_13"].between(1, 12), d["BP16_13"] + 24)
        bed_min  = bed_h  * 60 + d["BP16_12"]
        wake_min = wake_h * 60 + d["BP16_14"]
        mins = (wake_min - bed_min)
        mins = mins.where(~(mins < 0), mins + 1440)   # 음수 보정
        hours = (mins / 60).round(4)                  # 분 → 시간
        total.loc[clock_mask] = hours.loc[clock_mask]

    df["Total_slp_wk"] = total
    return df


def derive_eq5d(df, eq5d_vars):
    """EQ-5D 5개 차원.
    응답 코드는 보통 1=문제없음, 2=다소문제, 3=심한문제(기수별 3수준/5수준 상이).
    여기서는 원 코드를 보존하되, 유효응답만 남기고 8/9류는 결측 처리.
    각 차원을 'any problem'(코드>=2) 이진 지표로도 생성.
    """
    for dim, col in eq5d_vars.items():
        raw_name  = f"eq5d_{dim}"
        prob_name = f"eq5d_{dim}_problem"
        if col is None or col not in df.columns:
            df[raw_name] = np.nan
            df[prob_name] = np.nan
            continue
        raw = df[col].copy()
        # EQ-5D(3수준): 유효값은 1/2/3 뿐. 8(비해당)·9(모름)은 결측 처리.
        raw = raw.where(raw.isin([1, 2, 3]), np.nan)
        df[raw_name] = raw
        # 1=문제없음, 2·3=문제있음  →  problem 이진지표
        df[prob_name] = np.where(raw.notna(), (raw >= 2).astype(float), np.nan)
    return df


def derive_health_behaviors(df):
    """공식 공개 파생변수와 음주빈도 문항을 분석용 공통 스키마로 정리."""
    df["aerobic_guideline"] = df["pa_aerobic"].where(df["pa_aerobic"].isin([0, 1]))
    df["current_smoking"] = df["sm_presnt"].where(df["sm_presnt"].isin([0, 1]))
    # BD1_11: 1=최근 1년 전혀 안 마심, 2=월 1회 미만, 3~6=월 1회 이상,
    # 8=비해당, 9=모름/무응답. 단면적 음주 빈도이며 절주의 효과가 아니다.
    alcohol = df["BD1_11"]
    df["monthly_drinking"] = np.where(
        alcohol.isin([1, 2, 3, 4, 5, 6]), alcohol.isin([3, 4, 5, 6]).astype(float), np.nan
    )
    df["bmi"] = pd.to_numeric(df["HE_BMI"], errors="coerce").where(
        pd.to_numeric(df["HE_BMI"], errors="coerce").between(10, 70)
    )
    return df


# ─────────────────────────────────────────────
# 4. 지표별 통합가중치 생성
# ─────────────────────────────────────────────
def make_pooled_weights(df, avail):
    """지표별로 '실제 조사된 연도'만 묶어 통합가중치 산출.

    제5기 이후 연도별 조사구수가 동일하므로(지침서),
    N개년 통합가중치 = wt_itvex / N  (표 15 예제 방식).
    단 조사구수가 다르면 조사구수 비율로 바꿔야 함(표 7).
    """
    def pooled(indicator_key, out_col):
        years = [y for y, ok in avail[indicator_key].items() if ok]
        n = len(years)
        w = pd.Series(np.nan, index=df.index)
        if n == 0:
            df[out_col] = w
            print(f"  [경고] {indicator_key}: 조사된 연도 없음 → 통합가중치 생략")
            return
        mask = df["year"].isin(years) & df["wt_itvex"].notna()
        w.loc[mask] = df.loc[mask, "wt_itvex"] / n
        df[out_col] = w
        print(f"  {out_col}: 통합연도 {years} (÷{n})")

    print("\n[통합가중치]")
    pooled("stress", "wt_pool_stress")
    pooled("phq",    "wt_pool_phq")
    pooled("sleep",  "wt_pool_sleep")
    pooled("eq5d",   "wt_pool_eq5d")
    pooled("aerobic", "wt_pool_aerobic")
    pooled("smoking", "wt_pool_smoking")
    pooled("alcohol", "wt_pool_alcohol")
    pooled("bmi", "wt_pool_bmi")
    return df


# ─────────────────────────────────────────────
# 5. 연령대 파생 (참조 테이블용 그룹)
# ─────────────────────────────────────────────
def add_agegroup(df):
    bins   = [0, 18, 29, 39, 49, 59, 69, 200]
    labels = ["0-18", "19-29", "30-39", "40-49", "50-59", "60-69", "70+"]
    df["agegroup"] = pd.cut(df["age"], bins=bins, labels=labels, right=True)
    return df


# ─────────────────────────────────────────────
# 6. 복합표본 가중 추정  (samplics 사용)
# ─────────────────────────────────────────────
def _scalarize(v):
    """samplics가 point_est/stderror를 dict나 배열로 돌려줄 때 스칼라로 정규화."""
    if isinstance(v, dict):
        # 이진지표 mean은 보통 {value: estimate} 형태 → 첫 값 사용
        return float(next(iter(v.values())))
    if isinstance(v, (list, tuple, np.ndarray)):
        return float(np.asarray(v).ravel()[0])
    return float(v)


def weighted_estimate(df, y_col, weight_col, domain_cols=None, age_min=19):
    """복합표본설계를 반영한 가중 평균/비율 + 표준오차.

    samplics 0.6.0 기준. 이진(0/1) 지표의 mean = 유병/인지 비율.
    samplics 미설치 시 단순 가중평균으로 폴백(점추정치만).
    """
    sub = df.copy()
    if age_min is not None:
        sub = sub[sub["age"] >= age_min]
    sub = sub[sub[y_col].notna() & sub[weight_col].notna() &
              sub["kstrata"].notna() & sub["psu"].notna()]
    if sub.empty:
        return None

    try:
        from samplics.estimation import TaylorEstimator
        from samplics.utils.types import PopParam

        def _one(g):
            # 층 내 PSU가 1개뿐인 경우가 섞이면 분산추정이 불안정하므로
            # 점추정은 항상 내되, SE 계산이 실패하면 NaN 처리.
            w, y = g[weight_col].values, g[y_col].values
            n = len(g)
            try:
                est = TaylorEstimator(PopParam.mean)
                est.estimate(
                    y=y,
                    samp_weight=w,
                    stratum=g["kstrata"].values,
                    psu=g["psu"].values,
                    remove_nan=True,
                )
                point = _scalarize(est.point_est)
                se = _scalarize(est.stderror)
            except Exception:
                # SE 계산 실패 시 가중평균으로 점추정만 확보
                point = float(np.average(y, weights=w))
                se = np.nan
            return pd.Series({"estimate": point, "se": se, "n": n})

        if domain_cols:
            return (sub.groupby(domain_cols, observed=True)
                       .apply(_one, include_groups=False)
                       .reset_index())
        else:
            return _one(sub).to_frame().T
    except ImportError:
        print("  [알림] samplics 미설치 → 가중평균만 계산(표준오차 없음).")

        def _wmean(g):
            w, y = g[weight_col].values, g[y_col].values
            return pd.Series({"estimate": np.average(y, weights=w),
                              "se": np.nan, "n": len(g)})

        if domain_cols:
            return (sub.groupby(domain_cols, observed=True)
                       .apply(_wmean, include_groups=False)
                       .reset_index())
        else:
            return _wmean(sub).to_frame().T


# ─────────────────────────────────────────────
# 7. 라놀랩 참조 테이블로 적재
# ─────────────────────────────────────────────
def build_reference_table(df, avail):
    """지표 × 성별 × 연령대 참조 테이블 생성."""
    specs = [
        ("스트레스인지율",   "mh_stress",   "wt_pool_stress", "stress"),
        ("우울장애유병률",   "mh_PHQ_S10",  "wt_pool_phq",    "phq"),
        ("주중평균수면시간", "Total_slp_wk","wt_pool_sleep",  "sleep"),
        ("EQ5D_불안우울문제","eq5d_anxiety_problem","wt_pool_eq5d","eq5d"),
        ("EQ5D_통증문제",    "eq5d_pain_problem",   "wt_pool_eq5d","eq5d"),
        ("유산소신체활동실천율", "aerobic_guideline", "wt_pool_aerobic", "aerobic"),
        ("현재흡연율", "current_smoking", "wt_pool_smoking", "smoking"),
        ("월간음주율", "monthly_drinking", "wt_pool_alcohol", "alcohol"),
        ("평균BMI", "bmi", "wt_pool_bmi", "bmi"),
    ]
    rows = []
    for label, ycol, wcol, key in specs:
        if ycol not in df.columns:
            continue
        years = [y for y, ok in avail[key].items() if ok]
        if not years:
            continue
        year_tag = "+".join(str(y) for y in years)

        # 전체 / 성별 / 연령대별 추정
        for domain, dcols in [("전체", None),
                              ("성별", ["sex"]),
                              ("연령대", ["agegroup"]),
                              ("성별×연령대", ["sex", "agegroup"])]:
            res = weighted_estimate(df, ycol, wcol, dcols)
            if res is None:
                continue
            res = res.copy()
            res["지표명"] = label
            res["구분유형"] = domain
            res["출처"] = "KNHANES 제9기"
            res["통합연도"] = year_tag
            rows.append(res)

    if not rows:
        return pd.DataFrame()
    table = pd.concat(rows, ignore_index=True, sort=False)
    # 값 단위: 유병/인지/문제 지표는 %로 환산 (수면은 시간 그대로)
    def to_display(r):
        if "수면" in r["지표명"] or "BMI" in r["지표명"]:
            return round(r["estimate"], 2)          # 시간
        return round(r["estimate"] * 100, 1)         # %
    table["값"] = table.apply(to_display, axis=1)
    table["단위"] = np.select(
        [table["지표명"].str.contains("수면"), table["지표명"].str.contains("BMI")],
        ["시간", "kg/㎡"], default="%"
    )
    return table


# ─────────────────────────────────────────────
# 실행
# ─────────────────────────────────────────────
def main():
    df, metas = load_all()
    avail = diagnose_availability(df)

    df = derive_stress(df)
    df = derive_phq(df)
    df = derive_sleep(df)
    df = derive_eq5d(df, avail["eq5d_vars"])
    df = derive_health_behaviors(df)
    df = make_pooled_weights(df, avail)
    df = add_agegroup(df)

    # 정제된 개인단위 데이터 저장 (검증·재현용)
    keep = (DESIGN_VARS + ["year", "agegroup",
            "mh_stress", "mh_PHQ_S10", "Total_slp_wk"] +
            ["aerobic_guideline", "current_smoking", "monthly_drinking", "bmi"] +
            [f"eq5d_{d}_problem" for d in EQ5D_CANDIDATES] +
            ["wt_pool_stress", "wt_pool_phq", "wt_pool_sleep", "wt_pool_eq5d",
             "wt_pool_aerobic", "wt_pool_smoking", "wt_pool_alcohol", "wt_pool_bmi"])
    keep = [c for c in keep if c in df.columns]
    PERSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    df[keep].to_csv(PERSON_OUT, index=False, encoding="utf-8-sig")
    print(f"\n[저장] {PERSON_OUT.relative_to(ROOT)} (개인단위 정제본)")

    # 참조 테이블 생성·저장
    ref = build_reference_table(df, avail)
    if not ref.empty:
        out_cols = ["지표명", "구분유형", "sex", "agegroup",
                    "값", "단위", "se", "n", "출처", "통합연도"]
        out_cols = [c for c in out_cols if c in ref.columns]
        LOOKUP_OUT.parent.mkdir(parents=True, exist_ok=True)
        ref[out_cols].to_csv(LOOKUP_OUT, index=False, encoding="utf-8-sig")
        print(f"[저장] {LOOKUP_OUT.relative_to(ROOT)} (라놀랩 참조 테이블)")
        print("\n[미리보기]")
        print(ref[out_cols].head(20).to_string(index=False))


if __name__ == "__main__":
    main()
