"""
preprocess.py  —  GOMS GP19(.SAV)  →  data/goms_clean.csv
==========================================================
Parallel Me 데이터 파이프라인의 1단계. 단 한 번만 실행한다.
모든 모델(KNN / EconML / lifelines)은 이 스크립트가 만든
goms_clean.csv 한 파일만 읽는다.

실행 전:
    pip install pyreadstat pandas numpy

실행:
    python preprocess.py

★ 처음 실행하면 STEP 2에서 핵심 변수들의 '값 라벨(코드 → 의미)'이
   화면에 출력된다. 코드북 없이 코드를 추측하면 점수가 통째로 뒤집힐 수
   있으므로, 출력을 보고 아래 ★확인필요 표시된 상수 3개를 맞춘 뒤
   다시 실행할 것.
"""

from pathlib import Path
import numpy as np
import pandas as pd
import pyreadstat

# ---------------------------------------------------------------------------
# 경로
# ---------------------------------------------------------------------------
OUT = Path("data/goms_clean.csv")

# ---------------------------------------------------------------------------
# 처리할 연도(조사차수)들.
#   GOMS는 차수마다 변수 접두사가 다르다:  2020=g191, 2019=g181, 2018=g171 ...
#   prefix 만 바꾸면 나머지 suffix(COLS)는 공유된다.
#   suffix 가 연도마다 다른 변수(예: 직업분류 _2018/_2017)는 overrides 로 보정.
# ---------------------------------------------------------------------------
SOURCES = [
    {"year": 2020, "file": "GP19__2020.SAV", "prefix": "g191", "overrides": {}},
    {"year": 2019, "file": "GP18__2019.SAV", "prefix": "g181", "overrides": {
        # 예) 직업분류 코드의 연도 suffix가 다르면 여기서 교체:
        # "a007a_2018": "a007a_2017",
    }},
]

# ---------------------------------------------------------------------------
# 핵심 변수: 접두사(g191/g181)를 뗀 suffix  →  읽기 쉬운 이름
#   (필요하면 여기에 변수만 추가하면 된다. 30개까지 부담 없음)
# ---------------------------------------------------------------------------
COLS = {
    # 소득 / 이직
    "a122":        "income_now",        # 현직장 월평균 소득
    "d112":        "income_first",      # 첫직장 월평균 소득
    "a388":        "is_first_job",      # 현직장이 첫직장인지 여부(이직 판별용)
    # 직군
    "a007a_2018":  "job_major",         # 현직장 직업 대분류
    # 성장 가능성
    "a140":        "satis_overall",     # 현직장 전반적 만족도
    "a131":        "satis_growth",      # 발전가능성 만족도
    # 삶의 질
    "q001":        "health",            # 현재 건강상태
    "q015":        "life_satis",        # 삶의 만족도(개인)
    "q019":        "happy_last_month",  # 지난달 행복 감정
    # 사유(텍스트화/분류용)
    "d249":        "quit_reason_first", # 첫직장 그만둔 이유
    "a298":        "move_reason_1",     # 이직 이유 1순위
}

# 코드북 보고 검증할 라벨들(STEP 2에서 자동 출력됨) — suffix 기준
LABELS_TO_INSPECT = [
    "a388", "a007a_2018", "a140",
    "a131", "q001", "q015", "q019",
]

# ★확인필요 1 — g191a388에서 "첫직장 = 현직장(=이직 안 함)"을 뜻하는 코드.
#   대개 1=예 / 2=아니오. STEP 2 출력으로 반드시 확인할 것.
FIRST_JOB_YES = 1

# ★확인필요 2 — 소득 단위. 보통 만원 단위로 저장됨.
#   STEP 4가 중앙값을 보고 자동 판별하지만, 결과 로그를 꼭 확인할 것.

# ★확인필요 3 — 만족도/건강/행복 척도의 '방향'.
#   GOMS는 문항에 따라 1=매우만족 … 5=매우불만족 처럼 '낮을수록 좋음'인 경우가 있다.
#   STEP 2 라벨을 보고, 낮을수록 좋은 변수는 아래 집합에 코드명을 넣어라.
#   (Layer 1 점수 산출 단계에서 reverse 처리할 때 사용)
LOWER_IS_BETTER = {
    # 예: "satis_overall", "satis_growth", "health", "life_satis",
}

# 소득 이상치 컷(만원/월). 분포 보고 조정 가능.
INCOME_MIN, INCOME_MAX = 50, 2000


# ---------------------------------------------------------------------------
def resolve_columns(requested, actual_cols):
    """SAV의 실제 컬럼명과 대소문자 무관하게 매칭."""
    lut = {c.lower(): c for c in actual_cols}
    found, missing = {}, []
    for code in requested:
        real = lut.get(code.lower())
        if real:
            found[code] = real
        else:
            missing.append(code)
    return found, missing


def requested_codes(src):
    """이 연도의 실제 원본변수코드 -> 읽기 쉬운 이름.
    prefix 적용 + overrides 보정."""
    out = {}
    for suffix, name in COLS.items():
        suf = src["overrides"].get(suffix, suffix)
        out[src["prefix"] + suf] = name
    return out


def process_one(src):
    """SAV 한 개(=한 연도)를 읽어 정제 후 'year' 컬럼 붙여 반환. 파일 없으면 None."""
    raw = Path("data/raw") / src["file"]
    year = src["year"]
    print(f"\n{'='*60}\n[{year}]  {src['file']}\n{'='*60}")
    if not raw.exists():
        print(f"  [건너뜀] 파일 없음: {raw.resolve()}")
        return None

    # -- STEP 1. SAV 읽기 (값은 코드 그대로, 라벨은 meta로 따로 보존) --------
    print("STEP 1  SAV 로딩...")
    df, meta = pyreadstat.read_sav(str(raw), apply_value_formats=False)
    print(f"        전체 {df.shape[0]:,}행 × {df.shape[1]:,}변수")

    # -- STEP 2. 핵심 변수 라벨 출력 (코드 의미 검증용) ----------------------
    print(f"STEP 2  ▼ [{year}] 핵심 변수 라벨 (코드북과 대조) ▼")
    for suffix in LABELS_TO_INSPECT:
        code = src["prefix"] + src["overrides"].get(suffix, suffix)
        real = next((c for c in df.columns if c.lower() == code.lower()), None)
        if real is None:
            print(f"  [없음] {code}")
            continue
        var_label = meta.column_names_to_labels.get(real, "")
        val_labels = meta.variable_value_labels.get(real, {})
        print(f"  {code}  —  {var_label}")
        print(f"        {val_labels}")
    print("  ▲ 검증 끝 ▲")

    # -- STEP 3. 변수 선택 + 이름 변경 --------------------------------------
    req = requested_codes(src)
    found, missing = resolve_columns(req.keys(), df.columns)
    if missing:
        print(f"STEP 3  [경고][{year}] SAV에 없는 변수: {missing}")
    sub = df[[found[c] for c in found]].copy()
    sub.columns = [req[c] for c in found]

    # -- STEP 4. 소득 단위 자동 판별 (만원으로 통일) ------------------------
    med = sub["income_now"].median(skipna=True)
    if med and med > 10000:                       # 원 단위로 저장된 경우
        print(f"STEP 4  소득 중앙값 {med:,.0f} → '원' 단위로 판단, /10000 적용")
        sub["income_now"]   = sub["income_now"]   / 10000
        sub["income_first"] = sub["income_first"] / 10000
    else:
        print(f"STEP 4  소득 중앙값 {med:,.1f} → '만원' 단위로 판단(변환 없음)")

    # -- STEP 5. 파생변수 ---------------------------------------------------
    # 이직 여부: 첫직장==현직장 코드면 0, 그 외 유효값이면 1, 결측이면 NaN
    sub["changed_job"] = np.where(
        sub["is_first_job"] == FIRST_JOB_YES, 0,
        np.where(sub["is_first_job"].notna(), 1, np.nan),
    )
    # 소득 변화율(%) = (현직 - 첫직) / 첫직 × 100
    with np.errstate(divide="ignore", invalid="ignore"):
        sub["income_change_pct"] = (
            (sub["income_now"] - sub["income_first"]) / sub["income_first"] * 100
        )
    # 소득 증가/감소 플래그
    sub["income_up"]   = (sub["income_change_pct"] > 0).astype("Int64")
    sub["income_down"] = (sub["income_change_pct"] < 0).astype("Int64")

    # -- STEP 6. 분석용 클린 필터 (양쪽 소득 유효한 행만) ------------------
    valid = (
        sub["income_now"].between(INCOME_MIN, INCOME_MAX)
        & sub["income_first"].between(INCOME_MIN, INCOME_MAX)
    )
    clean = sub[valid].copy()
    clean.insert(0, "year", year)                 # 어느 조사차수인지 표시
    print(f"STEP 6  소득 유효 필터: {len(sub):,} → {len(clean):,}행")
    return clean


def sanity_check(clean, label):
    """이직 여부별 요약 출력."""
    print(f"\nSTEP 7  ▼ [{label}] 요약 ▼")
    stay = clean[clean["changed_job"] == 0]
    move = clean[clean["changed_job"] == 1]
    print(f"  이직 안 함 : {len(stay):,}명 / 평균 현직소득 {stay['income_now'].mean():.0f}만원")
    print(f"  이직 경험 : {len(move):,}명 / 평균 현직소득 {move['income_now'].mean():.0f}만원")
    if len(move):
        up   = (move["income_change_pct"] > 0).mean() * 100
        down = (move["income_change_pct"] < 0).mean() * 100
        print(f"  이직자 소득증가 {up:.1f}% / 감소 {down:.1f}%")
        print(f"  이직자 평균 변화율 {move['income_change_pct'].mean():+.1f}% "
              f"(중앙값 {move['income_change_pct'].median():+.1f}%)")


def main():
    parts = []
    for src in SOURCES:
        clean = process_one(src)
        if clean is not None and len(clean):
            sanity_check(clean, str(src["year"]))
            parts.append(clean)

    if not parts:
        raise RuntimeError("처리된 데이터가 없습니다. data/raw 의 .SAV 파일을 확인하세요.")

    # -- 연도별 결과 세로 결합 ---------------------------------------------
    merged = pd.concat(parts, ignore_index=True)
    sanity_check(merged, "전체 통합")
    print(f"\n  연도별 행수: "
          f"{merged['year'].value_counts().sort_index().to_dict()}")

    # -- STEP 8. 저장 ------------------------------------------------------
    OUT.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(f"\nSTEP 8  저장 완료 → {OUT.resolve()}  "
          f"({len(merged):,}행 × {merged.shape[1]}열)")


if __name__ == "__main__":
    main()