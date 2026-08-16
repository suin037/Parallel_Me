"""
kedi_preprocess.py — KEDI 고등교육기관 졸업자 학과별 '졸업 후 상황' → 계열별 취업률 lookup.

입력 (원본, 재배포 이슈로 레포 미포함 → data/raw/kedi/ 에 배치):
    한국교육개발원_고등교육기관 졸업자 학과별 졸업 후 상황_*.csv  (cp949 인코딩)

출력:
    data/dgroup/한국교육개발원_고등교육기관_졸업자_학과별_상황/lookup_kedi_emp_rate_by_field_v1.csv

산식 (교육부 공식 정의, dict_kedi_v3 준용):
    취업자   = 건보가입+교내+해외+농림어업+개인창작+1인창업+프리랜서 (남+여)
    취업대상 = 졸업자 − 진학자 − 입대자 − 취업불가능자 − 외국인유학생 − 제외인정자
    취업률   = 취업자 / 취업대상 × 100
    진학률   = 진학자 / 졸업자 × 100
계열(major_field) = 단과대학명 → 학과명 키워드 근사분류 (인문/사회/교육/공학/자연/의약/예체능/기타)

사용법:
    python preprocess/kedi_preprocess.py
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

RAW_DIR = Path("data/raw/kedi")
OUT = Path("data/dgroup/한국교육개발원_고등교육기관_졸업자_학과별_상황/lookup_kedi_emp_rate_by_field_v1.csv")

# 취업자 7개 항목 (교육부 공식 취업자 정의) — 남/여 각각
EMPLOYED_COLS = [
    "건보가입취업자_남", "건보가입취업자_여", "교내취업자_남", "교내취업자_여",
    "해외취업자_남", "해외취업자_여", "농림어업종사자_남", "농림어업종사자_여",
    "개인창작활동종사자_남", "개인창작활동종사자_여", "1인창사업자_남", "1인창사업자_여",
    "프리랜서_남", "프리랜서_여",
]

# 계열 분류 키워드 (앞에서부터 우선 적용; 단과대학명+학과명 텍스트에 매칭)
FIELD_KEYWORDS = [
    ("의약", r"의(학|예|과대)|간호|약학|치의|한의|보건|물리치료|재활|방사선|치위생|임상병리|수의"),
    ("교육", r"교육|사범|교직"),
    ("공학", r"공학|공과|기계|전기|전자|컴퓨터|소프트|건축|토목|화공|신소재|산업공|정보통신|반도체|로봇|자동차|항공|에너지"),
    ("예체능", r"예술|체육|음악|미술|디자인|무용|연극|영화|만화|애니|스포츠|패션|뷰티|공예|실용음악|조형|회화"),
    ("자연", r"자연|수학|물리|화학|생물|통계|지구|천문|생명과학|식품영양|농학|원예|산림|해양"),
    ("인문", r"인문|국어국문|영어영문|문헌정보|사학|철학|언어|문학|어(문|학)|통번역|중어|일어|독어|불어|노어|종교|신학"),
    ("사회", r"사회|경영|경제|행정|정치|법(학|과)|무역|회계|관광|미디어|광고|신문방송|커뮤니|심리|복지|부동산|세무|국제|물류|금융"),
]


def _num(df: pd.DataFrame, *cols) -> pd.Series:
    t = 0
    for c in cols:
        t = t + pd.to_numeric(df[c], errors="coerce").fillna(0)
    return t


def _classify(college: str, dept: str) -> str:
    text = f"{college} {dept}"
    for field, pat in FIELD_KEYWORDS:
        if re.search(pat, text):
            return field
    return "기타"


def load_raw() -> pd.DataFrame:
    hits = sorted(RAW_DIR.glob("*.csv"))
    if not hits:
        raise FileNotFoundError(f"{RAW_DIR}/*.csv 없음 — KEDI 원본을 배치하세요.")
    return pd.read_csv(hits[0], encoding="cp949")


def build_lookup(df: pd.DataFrame) -> pd.DataFrame:
    grads = _num(df, "졸업자_남", "졸업자_여")
    employed = _num(df, *EMPLOYED_COLS)
    jinhak = _num(df, "진학자_남", "진학자_여")
    exclude = (_num(df, "입대자")
               + _num(df, "취업불가능자_남", "취업불가능자_여")
               + _num(df, "외국인유학생_남", "외국인유학생_여")
               + _num(df, "제외인정자_남", "제외인정자_여"))
    denom = grads - jinhak - exclude

    year = str(df["조사회차"].iloc[0])[:4] if "조사회차" in df.columns else ""
    work = pd.DataFrame({
        "major_field": [_classify(c, d) for c, d in zip(df["단과대학명"], df["학과명"])],
        "grads": grads, "employed": employed, "jinhak": jinhak, "denom": denom,
    })

    def agg(g: pd.DataFrame, label: str) -> dict:
        gr, em, jh, de = g["grads"].sum(), g["employed"].sum(), g["jinhak"].sum(), g["denom"].sum()
        return {"major_field": label, "year": year,
                "grads": int(gr), "employed": int(em),
                "emp_rate": round(em / de * 100, 1) if de else None,
                "advance_rate": round(jh / gr * 100, 1) if gr else None}

    rows = [agg(work[work["major_field"] == f], f) for f in sorted(work["major_field"].unique())]
    rows.append(agg(work, "전체"))
    return pd.DataFrame(rows)


def main() -> None:
    df = load_raw()
    out = build_lookup(df)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(out.to_string(index=False))
    print(f"\n[done] {len(df):,} 학과 → {OUT} ({len(out)} 계열)")


if __name__ == "__main__":
    main()
