"""
KNHANES · CHS · KWCS 참조 테이블 통합 + 교차검증 뷰
─────────────────────────────────────────────
입력 (같은 폴더에 있어야 함)
  - knhanes9_reference_table.csv
  - chs2025_reference_table.csv
  - kwcs7_reference_table.csv

출력
  1) lanollab_reference_master.csv   : 세 조사 통합 마스터 (라놀랩이 참조하는 단일 테이블)
  2) lanollab_crosscheck.csv         : KNHANES vs CHS 교차검증 뷰

교차검증 원칙 (중요)
  같은 '방식'으로 잰 지표끼리만 비교한다.
  - 스트레스인지율 / 우울장애유병률(PHQ-9) / 주중평균수면시간 / EQ-5D
    → KNHANES·CHS 둘 다 동일 정의라 비교 가능.
  - KWCS의 업무스트레스·불안·우울·수면장애는 정의가 달라(취업자·다른 척도)
    교차검증에서 제외하고, 마스터에는 '취업자 전용 지표'로만 싣는다.
"""

from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
LANOLLAB = ROOT / "data/lanollab"

FILES = {
    "KNHANES 제9기": LANOLLAB / "질병관리청_국민건강영양조사/lookup_knhanes_indicators_v1.csv",
    "CHS 2025":      LANOLLAB / "질병관리청_지역사회건강조사/lookup_chs_indicators_v1.csv",
    "KWCS 7차":      LANOLLAB / "산업안전보건연구원_근로환경조사/lookup_kwcs_indicators_v1.csv",
}

MASTER_OUT     = LANOLLAB / "lookup_lanollab_master_v1.csv"
CROSSCHECK_OUT = LANOLLAB / "raw2tidy_lanollab_crosscheck_v1.csv"

# 공통 스키마 (마스터 컬럼 순서)
MASTER_COLS = ["지표명", "구분유형", "sex", "agegroup", "값", "단위",
               "se", "n", "출처", "대상", "기간"]

# KNHANES·CHS 간 동일 정의로 교차검증 가능한 지표
CROSSCHECK_INDICATORS = [
    "스트레스인지율", "우울장애유병률", "주중평균수면시간",
    "EQ5D_불안우울문제", "EQ5D_통증문제",
]


# ─────────────────────────────────────────────
# 1. 세 테이블 로드 + 스키마 통일
# ─────────────────────────────────────────────
def load_and_normalize():
    frames = []
    for src, path in FILES.items():
        if not path.exists():
            print(f"  [경고] {path.relative_to(ROOT)} 없음 → 건너뜀")
            continue
        df = pd.read_csv(path)

        # '기간' 컬럼 통일 (KNHANES=통합연도, CHS/KWCS=조사연도)
        if "통합연도" in df.columns:
            df["기간"] = df["통합연도"].astype(str)
        elif "조사연도" in df.columns:
            df["기간"] = df["조사연도"].astype(str)
        else:
            df["기간"] = ""

        # '대상' 컬럼 통일 (KWCS만 있음, 나머지는 전국민)
        if "대상" not in df.columns:
            df["대상"] = "전국민"

        # 출처 컬럼이 이미 있지만 파일별로 확실히 세팅
        if "출처" not in df.columns:
            df["출처"] = src

        # 없는 컬럼 채우기
        for c in MASTER_COLS:
            if c not in df.columns:
                df[c] = np.nan

        frames.append(df[MASTER_COLS])
        print(f"  [로드] {src}: {len(df)}행")

    if not frames:
        raise FileNotFoundError("참조 테이블을 하나도 찾지 못했습니다.")
    return pd.concat(frames, ignore_index=True)


# ─────────────────────────────────────────────
# 2. 교차검증 뷰 (KNHANES vs CHS)
# ─────────────────────────────────────────────
def build_crosscheck(master):
    # 교차검증 대상 지표 + KNHANES·CHS만
    m = master[
        master["지표명"].isin(CROSSCHECK_INDICATORS) &
        master["출처"].isin(["KNHANES 제9기", "CHS 2025"])
    ].copy()

    # 지표 × 구분유형 × 성별 × 연령대 키로 두 출처 값을 나란히
    key = ["지표명", "구분유형", "sex", "agegroup"]
    knh = (m[m["출처"] == "KNHANES 제9기"]
           .set_index(key)[["값", "단위", "n"]]
           .rename(columns={"값": "KNHANES_값", "n": "KNHANES_n"}))
    chs = (m[m["출처"] == "CHS 2025"]
           .set_index(key)[["값", "n"]]
           .rename(columns={"값": "CHS_값", "n": "CHS_n"}))

    cc = knh.join(chs, how="outer").reset_index()

    # 두 조사 차이(절대차) 계산 — 같은 단위일 때만 의미 있음
    cc["차이(KNHANES-CHS)"] = (cc["KNHANES_값"] - cc["CHS_값"]).round(2)

    # 정렬: 지표 → 구분유형 → 성별 → 연령대
    cc = cc.sort_values(key).reset_index(drop=True)
    return cc


# ─────────────────────────────────────────────
# 실행
# ─────────────────────────────────────────────
def main():
    print("[통합] 세 참조 테이블 로드")
    master = load_and_normalize()

    # 마스터 저장
    MASTER_OUT.parent.mkdir(parents=True, exist_ok=True)
    master.to_csv(MASTER_OUT, index=False, encoding="utf-8-sig")
    print(f"\n[저장] {MASTER_OUT.relative_to(ROOT)} ({len(master)}행)")

    # 교차검증 뷰
    cc = build_crosscheck(master)
    cc.to_csv(CROSSCHECK_OUT, index=False, encoding="utf-8-sig")
    print(f"[저장] {CROSSCHECK_OUT.relative_to(ROOT)} ({len(cc)}행)")

    # 요약 출력: 전체 기준 교차검증
    print("\n[교차검증 - '전체' 기준 KNHANES vs CHS]")
    overall = cc[cc["구분유형"] == "전체"][
        ["지표명", "KNHANES_값", "CHS_값", "차이(KNHANES-CHS)", "단위"]]
    print(overall.to_string(index=False))

    # 출처별 지표 수 요약
    print("\n[마스터 구성]")
    summary = (master.groupby(["출처", "대상"])["지표명"]
               .nunique().reset_index(name="지표수"))
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
