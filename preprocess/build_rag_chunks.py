"""
lookup 마스터 → RAG 청크(JSON) 변환.

사용법:
    python preprocess/build_rag_chunks.py

입력:  data/lanollab/lookup_lanollab_master_v1.csv
출력:  data/lanollab/<조사폴더>/rag_<약칭>_chunks_v1.json

청크 스키마는 팀 표준(dgroup README 3절)을 따른다.
청크 1개 = 통계 문장 1개이며, 문장 안에 연도·연령·출처가 들어가
임베딩만으로도 검색되도록 한다.

지표당 생성하는 청크:
  1) by_age  — 전체값 + 전 연령대 나열      (age_group="전체")
  2) by_sex  — 성별 비교 + 최고 성별×연령대  (age_group="전체")
  3) 19-29 / 30-39 — 해당 연령대 상세        (age_group=해당값)

'성별×연령대' 168행은 청크로 만들지 않는다. 서사 생성에는 너무 잘고,
정확한 수치가 필요하면 lookup 테이블을 직접 조회하는 쪽이 맞다.
"""

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
LANOLLAB = ROOT / "data/lanollab"
MASTER = LANOLLAB / "lookup_lanollab_master_v1.csv"

# 서사 생성 대상 연령대 (청년층)
FOCUS_AGES = ["19-29", "30-39"]

SEX_LABEL = {1.0: "남성", 2.0: "여성"}

SOURCES = {
    "KNHANES 제9기": dict(
        abbrev="knhanes",
        folder="질병관리청_국민건강영양조사",
        source="국민건강영양조사 제9기 (질병관리청)",
        year=2024,
        population="19세 이상 성인",
    ),
    "CHS 2025": dict(
        abbrev="chs",
        folder="질병관리청_지역사회건강조사",
        source="지역사회건강조사 2025 (질병관리청)",
        year=2025,
        population="19세 이상 성인",
    ),
    "KWCS 7차": dict(
        abbrev="kwcs",
        folder="산업안전보건연구원_근로환경조사",
        source="근로환경조사 제7차 (산업안전보건연구원)",
        year=2023,
        population="19세 이상 취업자",
    ),
}

# 지표명 → (검색 필터용 topic, id 슬러그, 문장에 넣을 조작적 정의)
INDICATORS = {
    "스트레스인지율": (
        "스트레스", "stress",
        "평소 스트레스를 '대단히 많이' 또는 '많이' 느낀다고 응답한 비율",
    ),
    "우울장애유병률": (
        "우울", "depression",
        "우울증 선별도구 PHQ-9 총점이 10점 이상인 비율",
    ),
    "주중평균수면시간": (
        "수면", "sleep_hours",
        "주중 하루 평균 수면시간",
    ),
    "EQ5D_불안우울문제": (
        "불안우울", "eq5d_anxiety",
        "삶의 질 측정도구 EQ-5D의 불안·우울 차원에서 문제가 있다고 응답한 비율",
    ),
    "EQ5D_통증문제": (
        "통증", "eq5d_pain",
        "삶의 질 측정도구 EQ-5D의 통증·불편 차원에서 문제가 있다고 응답한 비율",
    ),
    "업무스트레스": (
        "직무스트레스", "work_stress",
        "업무 중 스트레스를 '항상' 또는 '대부분' 느낀다고 응답한 비율",
    ),
    "불안감유병": (
        "불안", "anxiety",
        "불안감이 있다고 응답한 비율",
    ),
    "우울함유병": (
        "우울", "depress",
        "우울함이 있다고 응답한 비율",
    ),
    "수면장애": (
        "수면", "sleep_problem",
        "입면 곤란·야간 각성·피로 회복 안 됨 중 하나 이상을 '매일' 또는 '주 여러 번' 겪는 비율",
    ),
}


# 단위를 소리내어 읽은 형태 — 조사(은/는, 이다/다, 로/으로) 판정에 쓴다.
# "%" 는 '퍼센트'로 읽으므로 받침이 없고, "시간" 은 받침이 있다.
UNIT_READING = {"%": "퍼센트", "%p": "퍼센트포인트", "시간": "시간"}

AGE_LABEL = {"70+": "70세 이상"}


def has_batchim(word: str) -> bool:
    ch = word[-1]
    if "가" <= ch <= "힣":
        return (ord(ch) - 0xAC00) % 28 != 0
    return False


def josa(word: str, with_b: str, without_b: str) -> str:
    """받침 유무에 따라 조사를 붙인다. josa('수면장애', '은', '는') -> '수면장애는'"""
    return word + (with_b if has_batchim(word) else without_b)


def unit_josa(unit: str, with_b: str, without_b: str) -> str:
    """단위로 끝나는 값 뒤에 붙일 조사만 반환."""
    r = UNIT_READING.get(unit, unit)
    return with_b if has_batchim(r) else without_b


def age_label(ag: str) -> str:
    return AGE_LABEL.get(ag, f"{ag}세")


def fmt(v, unit):
    """값을 단위에 맞게 문자열로. 6.0 -> '6', 6.87 -> '6.87'."""
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return f"{s}{unit}"


def diff_words(unit):
    """단위별 비교 서술어. (높다/낮다) vs (길다/짧다)"""
    if unit == "시간":
        return dict(hi="길다", lo="짧다", hi_conj="가장 길고", lo_adj="가장 짧다",
                    hi_most="가장 길다", pp="시간")
    return dict(hi="높다", lo="낮다", hi_conj="가장 높고", lo_adj="가장 낮다",
                hi_most="가장 높다", pp="%p")


def build_chunks(df, src_key):
    meta_src = SOURCES[src_key]
    sub = df[df["출처"] == src_key]
    period = str(sub["기간"].iloc[0])
    chunks = []

    for name in sub["지표명"].unique():
        if name not in INDICATORS:
            print(f"  [건너뜀] 지표 정의 없음: {name}")
            continue
        topic, slug, desc = INDICATORS[name]
        g = sub[sub["지표명"] == name]
        unit = g["단위"].iloc[0]
        w = diff_words(unit)
        pp = w["pp"]
        name_j = josa(name, "은", "는")          # 스트레스인지율은 / 수면장애는
        desc_s = josa(desc, "이다", "다")        # …비율이다 / …수면시간이다
        ida = unit_josa(unit, "이다", "다")      # 6.2시간이다 / 25.7%다
        ro = unit_josa(unit, "으로", "로")       # 6.2시간으로 / 25.7%로

        overall_row = g[g["구분유형"] == "전체"]
        if overall_row.empty:
            continue
        overall = overall_row["값"].iloc[0]
        n_total = overall_row["n"].iloc[0]

        base_meta = dict(
            indicator="삶의질",
            source=meta_src["source"],
            year=meta_src["year"],
            topic=topic,
            doc_type="통계",
            period=period,
            population=meta_src["population"],
        )

        # ── 1) 연령대별 ──────────────────────────────
        ages = g[g["구분유형"] == "연령대"].dropna(subset=["값"])
        if not ages.empty:
            parts = [f"{age_label(r.agegroup)} {fmt(r.값, unit)}" for r in ages.itertuples()]
            top = ages.loc[ages["값"].idxmax()]
            bot = ages.loc[ages["값"].idxmin()]
            doc = (
                f"{meta_src['source']} {period} 기준, {meta_src['population']}의 "
                f"{name_j} {fmt(overall, unit)}{ida}. {desc_s}. "
                f"연령대별로는 {', '.join(parts)}{ro}, "
                f"{age_label(top.agegroup)}에서 {w['hi_conj']} "
                f"{age_label(bot.agegroup)}에서 {w['lo_adj']}. "
                f"(분석 대상 {int(n_total):,}명)"
            )
            chunks.append(dict(
                id=f"{meta_src['abbrev']}_{slug}_by_age",
                document=doc,
                metadata=dict(base_meta, age_group="전체"),
            ))

        # ── 2) 성별 ─────────────────────────────────
        sexes = g[g["구분유형"] == "성별"].dropna(subset=["값"])
        if len(sexes) == 2:
            m = sexes[sexes["sex"] == 1.0]["값"].iloc[0]
            f = sexes[sexes["sex"] == 2.0]["값"].iloc[0]
            gap = abs(f - m)
            if gap == 0:
                cmp_clause = "남녀가 같다"
            else:
                higher = "여성" if f > m else "남성"
                cmp_clause = f"{higher}이 {fmt(gap, pp)} 더 {w['hi']}"
            doc = (
                f"{meta_src['source']} {period} 기준, {meta_src['population']}의 "
                f"{name_j} 남성 {fmt(m, unit)}, 여성 {fmt(f, unit)}{ro} "
                f"{cmp_clause}. {desc_s}."
            )
            cross = g[g["구분유형"] == "성별×연령대"].dropna(subset=["값"])
            if not cross.empty:
                c = cross.loc[cross["값"].idxmax()]
                doc += (
                    f" 성별과 연령대를 함께 보면 {SEX_LABEL.get(c.sex, '')} "
                    f"{josa(age_label(c.agegroup), '이', '가')} "
                    f"{fmt(c.값, unit)}{ro} {w['hi_most']}."
                )
            chunks.append(dict(
                id=f"{meta_src['abbrev']}_{slug}_by_sex",
                document=doc,
                metadata=dict(base_meta, age_group="전체"),
            ))

        # ── 3) 청년층 연령대별 상세 ──────────────────
        for ag in FOCUS_AGES:
            row = g[(g["구분유형"] == "연령대") & (g["agegroup"] == ag)].dropna(subset=["값"])
            if row.empty:
                continue
            v = row["값"].iloc[0]
            gap = v - overall
            base = f"전체 평균({fmt(overall, unit)})"
            if gap > 0:
                rel = f"{base}보다 {fmt(gap, pp)} 더 {w['hi']}"
            elif gap < 0:
                rel = f"{base}보다 {fmt(-gap, pp)} 더 {w['lo']}"
            else:
                rel = f"{base}과 같다"
            pop_short = meta_src["population"].replace("19세 이상 ", "")
            doc = (
                f"{meta_src['source']} {period} 기준, {age_label(ag)} "
                f"{pop_short}의 {name_j} {fmt(v, unit)}{ro} {rel}. {desc_s}."
            )
            cx = g[(g["구분유형"] == "성별×연령대") & (g["agegroup"] == ag)].dropna(subset=["값"])
            if len(cx) == 2:
                cm = cx[cx["sex"] == 1.0]["값"].iloc[0]
                cf = cx[cx["sex"] == 2.0]["값"].iloc[0]
                doc += (
                    f" 같은 연령대에서 남성은 {fmt(cm, unit)}, "
                    f"여성은 {fmt(cf, unit)}{ida}."
                )
            chunks.append(dict(
                id=f"{meta_src['abbrev']}_{slug}_{ag}",
                document=doc,
                metadata=dict(base_meta, age_group=ag),
            ))

    return chunks


def main():
    if not MASTER.exists():
        raise FileNotFoundError(
            f"마스터 테이블이 없습니다: {MASTER.relative_to(ROOT)}\n"
            "먼저 python preprocess/merge_reference_tables.py 를 실행하세요."
        )
    df = pd.read_csv(MASTER)
    total = 0
    for src_key, meta in SOURCES.items():
        chunks = build_chunks(df, src_key)
        out = LANOLLAB / meta["folder"] / f"rag_{meta['abbrev']}_chunks_v1.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(chunks, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"[저장] {out.relative_to(ROOT)} — 청크 {len(chunks)}개")
        total += len(chunks)
    print(f"\n총 {total}개 청크")


if __name__ == "__main__":
    main()
