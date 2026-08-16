"""
preprocess_goms.py  —  GOMS 2019 (.SAV) → data/clean/goms_clean.csv
====================================================================
[팀 표준변수명 사전 v1 준수]
  각 데이터셋 담당자는 자기 데이터를 '표준변수명'으로 rename 해서
  자기 clean.csv를 만든다. (개인단위로 데이터셋을 합치지 않는다)
  → L1/L2 모델 코드는 표준변수명만 알면 어느 데이터든 읽을 수 있다.

이 스크립트가 하는 일:
  1) SAV 로드 → 표준변수명으로 rename
  2) 결측코드(-1 등) 정리 · 이상치 컷
  3) 파생변수 생성 (changed_job, income_change_pct ...)
  4) ★진단: 25~35 연령 커버리지 + 셀 크기
     → "2019 하나로 충분한가, 2018/2017을 더 받아야 하나" 결론 출력
  5) data/clean/goms_clean.csv 저장

실행:  python preprocess_goms.py      (repo 루트에서)
필요:  pip install pyreadstat pandas numpy
"""

from pathlib import Path
import numpy as np
import pandas as pd
import pyreadstat

RAW = Path("data/raw/GP19__2020.SAV")
OUT = Path("data/clean/goms_clean.csv")

SURVEY, SURVEY_YEAR = "GOMS", 2019

# ---------------------------------------------------------------------------
# 팀 표준변수명 사전 — GOMS 열
#   (다른 데이터셋 담당자는 이 dict만 자기 것으로 갈아끼우면 된다)
# ---------------------------------------------------------------------------
VAR_MAP = {
    # --- 공통 인구통계 (표준사전) ---
    "g191age":        "age",            # 연령(조사기준일)
    "g191birthy":     "birth_year",     # 출생년
    "g191sex":        "sex",            # 1=남 2=여
    "g191school":     "school_type",    # 학교유형 1=2~3년제 2=4년제 3=교육대
                                        # ※표준 edu_level(1~7)은 GOMS에 없음(대졸자만) → NA
    "g191majorcat":   "major_cat",      # 전공계열 1~7
    # --- 직업/직종 ---
    "g191a007a_2018": "occupation",     # 직업 대분류(2018 KECO) 1~10
    "g191a011":       "firm_size",      # 사업체 종사자수 1~9
    "g191a059":       "is_regular",     # 정규직 1=예 2=아니오
    # --- 경제 (지표1) ---
    "g191a122":       "income_now",       # 현직장 현재 월평균 소득(만원)
    "g191a125":       "income_now_start", # ★현직장 '초임' 월평균 소득(만원)
                                          #   → 잔류자도 응답! 변화율 계산의 핵심
    "g191d112":       "income_first",     # 첫직장 월평균 소득(만원) — 이직자만 응답
    # --- 이직 ---
    "g191a388":       "is_first_job",   # 현직=첫직인지(예/아니오)
    "g191a389":       "job_seq",        # 졸업 후 몇 번째 직장인가
    # --- 성장 (지표2) ---
    "g191a140":       "satis_overall",  # 전반적 만족도 1~5 (높을수록 좋음)
    "g191a131":       "satis_growth",   # 발전가능성 만족도 1~5
    # --- 삶의 질 (지표3) ---
    "g191q001":       "health",         # 건강상태 (높을수록 좋음)
    "g191q015":       "life_satis",     # 삶의 만족도 1~7
    "g191q019":       "happy",          # 지난달 행복 1~7
    # --- 사유 ---
    "g191d249":       "quit_reason",    # 첫직장 그만둔 이유
    "g191a298":       "move_reason",    # 이직 이유 1순위
}

# 코드북 확인 완료:
#  - 소득은 '만원' 단위 (변환 불필요)
#  - 만족도/건강/삶만족/행복 전부 '높을수록 좋음' → reverse 불필요
#    (단 척도범위 상이: 만족도 1~5, 삶만족·행복 1~7 → 점수화 시 정규화 필요)
#  - 결측/무응답 = -1 (일부 변수는 큰 sentinel 값)

MISSING_CODES = [-1, -8, -9]
CATEGORICAL = ["sex", "school_type", "major_cat", "occupation",
               "firm_size", "is_regular", "quit_reason", "move_reason"]
INCOME_MIN, INCOME_MAX = 50, 2000     # 만원/월
AGE_MIN, AGE_MAX = 20, 45

TARGET_AGE = (25, 35)                 # 서비스 타겟
MIN_CELL = 30                         # 셀당 최소 표본(평균 신뢰 하한)

OCC_NAMES = {
    1: "경영·사무·금융·보험", 2: "연구·공학기술", 3: "교육·법률·복지·공공",
    4: "보건·의료", 5: "예술·디자인·방송·스포츠", 6: "미용·여행·숙박·음식·경비·청소",
    7: "영업·판매·운전·운송", 8: "건설·채굴", 9: "설치·정비·생산", 10: "농림어업",
}


def main():
    if not RAW.exists():
        raise FileNotFoundError(f"원본 없음: {RAW.resolve()}")

    # ---- 1. 로드 + rename --------------------------------------------------
    print("[1] SAV 로딩...")
    df, meta = pyreadstat.read_sav(str(RAW), apply_value_formats=False)
    print(f"    원본 {df.shape[0]:,}행 × {df.shape[1]:,}변수")

    lut = {c.lower(): c for c in df.columns}
    found = {lut[k.lower()]: v for k, v in VAR_MAP.items() if k.lower() in lut}
    missing = [k for k in VAR_MAP if k.lower() not in lut]
    if missing:
        print(f"    [경고] SAV에 없는 변수: {missing}")

    d = df[list(found)].rename(columns=found).copy()
    d["survey"] = SURVEY
    d["survey_year"] = SURVEY_YEAR     # ★다년 결합 대비: 항상 넣어둘 것

    # ---- 2. 결측코드 정리 ---------------------------------------------------
    print("[2] 결측코드 정리...")
    for c in d.columns:
        if c in ("survey", "survey_year"):
            continue
        d.loc[d[c].isin(MISSING_CODES), c] = np.nan

    for c in ["income_now", "income_now_start", "income_first"]:
        if c in d:
            d.loc[~d[c].between(INCOME_MIN, INCOME_MAX), c] = np.nan
    if "age" in d:
        d.loc[~d["age"].between(AGE_MIN, AGE_MAX), "age"] = np.nan

    # ---- 3. 파생변수 --------------------------------------------------------
    print("[3] 파생변수 생성...")
    # 이직여부: is_first_job의 '예'(=현직이 첫직장) 코드를 값라벨에서 자동 인식
    real388 = next((k for k, v in found.items() if v == "is_first_job"), None)
    labels = meta.variable_value_labels.get(real388, {}) if real388 else {}
    yes = next((c for c, l in labels.items() if str(l).strip() == "예"), 1)
    print(f"    '첫직장=예' 코드 = {yes} (이 값이면 이직 안 함)")

    d["changed_job"] = np.where(d["is_first_job"] == yes, 0,
                        np.where(d["is_first_job"].notna(), 1, np.nan))

    # ★소득 변화율 — 잔류/이직 모두 계산되도록 baseline을 분기
    #   이직자: 첫직장 소득 기준  (income_first)   → '이직에 따른 변화'
    #   잔류자: 현직장 초임 기준  (income_now_start) → '한 직장 내 상승'
    #   ※기존 버그: income_first가 이직자만 응답하는 문항이라
    #     잔류자의 변화율이 전부 NaN → A/B 비교 자체가 불가능했음
    d["income_base"] = np.where(
        d["changed_job"] == 1, d["income_first"], d["income_now_start"]
    )
    d["income_base"] = pd.to_numeric(d["income_base"], errors="coerce")

    with np.errstate(divide="ignore", invalid="ignore"):
        d["income_change_pct"] = (
            (d["income_now"] - d["income_base"]) / d["income_base"] * 100
        )
    # 극단값 winsorize (상하위 1%) — 평균 왜곡 방지
    lo, hi = d["income_change_pct"].quantile([0.01, 0.99])
    d["income_change_pct"] = d["income_change_pct"].clip(lo, hi)

    for c in CATEGORICAL:
        if c in d:
            d[c] = d[c].astype("Int64")

    if "occupation" in d:
        d["occupation_name"] = d["occupation"].map(OCC_NAMES)
        d["occupation_scheme"] = "KECO2018"   # ※KSCO 아님. 타 조사와 붙이려면 crosswalk 필요

    # ---- 4. 분석표본 필터 ---------------------------------------------------
    # ★수정: income_first를 필수로 걸면 잔류자(첫직장=현직장이라 D섹션 미응답)가
    #   전부 탈락함. 분석표본 기준은 income_now만.
    clean = d[d["income_now"].notna()].copy()
    print(f"[4] 현직소득 유효 필터: {len(d):,} → {len(clean):,}행")
    ok = clean["income_change_pct"].notna()
    print(f"    변화율 계산 가능: {ok.sum():,}행 "
          f"(잔류 {(ok & (clean.changed_job==0)).sum():,} / "
          f"이직 {(ok & (clean.changed_job==1)).sum():,})")

    # ---- 5. Sanity check ----------------------------------------------------
    print("\n[5] Sanity check (기존 확인치 대조)")
    stay, move = clean[clean.changed_job == 0], clean[clean.changed_job == 1]
    print(f"    이직안함 {len(stay):,}명 / 평균 {stay.income_now.mean():.0f}만원")
    print(f"    이직경험 {len(move):,}명 / 평균 {move.income_now.mean():.0f}만원")
    if len(move):
        print(f"    이직자 소득증가 {(move.income_change_pct>0).mean()*100:.1f}% / "
              f"감소 {(move.income_change_pct<0).mean()*100:.1f}%")
        print(f"    평균변화 {move.income_change_pct.mean():+.1f}% / "
              f"중앙값 {move.income_change_pct.median():+.1f}%")
    print("    (기대: 9,153/230만, 2,705/206만, 62%/29%, +25.7%)")

    # ★핵심 비교 — 이제 잔류자도 변화율이 있으므로 A/B 대조 가능
    print("\n    [소득 변화율 A/B 비교] ※중앙값 기준(평균은 극단값에 왜곡)")
    for lbl, g in [("잔류", stay), ("이직", move)]:
        v = g["income_change_pct"].dropna()
        if len(v):
            print(f"      {lbl}: n={len(v):,} / 중앙값 {v.median():+.1f}% / "
                  f"평균 {v.mean():+.1f}% / 증가 {(v>0).mean()*100:.0f}%")

    # ---- 6. ★진단: 데이터 얼마나 나오나 -------------------------------------
    diagnose(clean)

    # ---- 7. 저장 ------------------------------------------------------------
    OUT.parent.mkdir(parents=True, exist_ok=True)
    clean.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(f"\n[7] 저장 → {OUT}  ({len(clean):,}행 × {clean.shape[1]}열)")


def diagnose(c):
    """타겟 커버리지 + 셀 크기 진단 → 연도 추가 필요 여부 판단"""
    lo, hi = TARGET_AGE
    print("\n" + "=" * 62)
    print("  ★ 진단 — 2019 한 해로 충분한가?")
    print("=" * 62)

    if "age" not in c or c["age"].isna().all():
        print("  [건너뜀] age 없음")
        return

    # (a) 연령 커버리지
    print(f"\n  (a) 연령 분포 — 타겟 {lo}~{hi}세")
    print(f"      중앙값 {c.age.median():.0f}세 / "
          f"25~28세 {(c.age.between(25,28)).sum():,}명 / "
          f"29~31세 {(c.age.between(29,31)).sum():,}명 / "
          f"32~35세 {(c.age.between(32,35)).sum():,}명")
    tgt = c[c.age.between(lo, hi)]
    print(f"      타겟 총 {len(tgt):,}명 ({len(tgt)/len(c)*100:.1f}%)")
    old = c.age.between(32, 35).sum()
    if old < 500:
        print(f"      ⚠ 32~35세 {old:,}명뿐 → 상단 연령 얇음. "
              f"YP2021/KLIPS로 보강 검토")

    # (b) 셀 크기: 직종 × 이직여부 (타겟 연령 내)
    print(f"\n  (b) 셀 크기 — 직종 × 이직여부 (타겟 {lo}~{hi}세, 최소 {MIN_CELL}명)")
    if "occupation" in tgt:
        tab = tgt.pivot_table(index="occupation_name", columns="changed_job",
                              values="income_now", aggfunc="count").fillna(0)
        tab.columns = ["잔류", "이직"][:len(tab.columns)]
        tab["합계"] = tab.sum(axis=1)
        print(tab.astype(int).to_string())
        thin = tab[(tab.get("이직", 0) < MIN_CELL)]
        if len(thin):
            print(f"\n      ⚠ 이직 표본 {MIN_CELL}명 미만 직종: "
                  f"{list(thin.index)}")
            print(f"        → 이 직종은 L1 점수/L2 매칭 불안정. "
                  f"UI에서 경고하거나 직종 통합 필요")

    # (c) 결론
    thin_n = len(thin) if "occupation" in tgt and len(thin) else 0
    print("\n  (c) 결론")
    if thin_n >= 4 or len(tgt) < 3000:
        print("      → 2019만으로 부족. 2018·2017 추가 다운로드 권장")
        print("        (결합 시 변수 접두어 g18/g17 + 직업분류 체계 확인 필수)")
    else:
        print("      → 2019 단독으로 충분. 연도 추가 불필요.")
        print(f"        (얇은 직종 {thin_n}개는 UI에서 표본수 함께 표시)")
    print("=" * 62)


if __name__ == "__main__":
    main()