"""이직/유지 선택별로 화면에 사용할 관측 결과를 생성한다.

개인 인과효과를 주장하지 않고, 25~35세 직장→직장 패널에서 경제·경력 전환·
삶의 질 결과의 분포와 최근 연도 방향 안정성을 계산한다.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "data" / "clean" / "klips_job_change_panel.csv"
OUTPUT = ROOT / "data" / "clean" / "job_change_observed_outcomes.json"
CUTOFF = 2021

METRICS = [
    ("financial", "wage_change_pct", "실질임금 변화율", "distribution"),
    ("financial", "wage_down_t1", "임금 하락 비율", "rate"),
    ("growth", "occupation_changed", "직종 전환율", "rate"),
    ("growth", "employment_improved", "고용형태 개선율", "rate"),
    ("growth", "firm_size_up", "기업규모 코드 상승률", "rate"),
    ("growth", "wage_band_up", "실질임금 구간 상승률", "rate"),
    ("quality_of_life", "satisfaction_family_income_change", "가족수입 만족 변화", "distribution"),
    ("quality_of_life", "satisfaction_leisure_change", "여가 만족 변화", "distribution"),
    ("quality_of_life", "satisfaction_housing_change", "주거 만족 변화", "distribution"),
    ("quality_of_life", "satisfaction_family_relationship_change", "가족관계 만족 변화", "distribution"),
    ("quality_of_life", "satisfaction_social_relationship_change", "사회관계 만족 변화", "distribution"),
    ("quality_of_life", "satisfaction_overall_change", "전반적 만족 변화", "distribution"),
    ("quality_of_life", "health_score_change", "주관적 건강 변화", "distribution"),
    ("quality_of_life", "health_peer_improvement", "또래 대비 건강 변화", "distribution"),
    ("quality_of_life", "future_optimism_change", "5년 후 삶의 기대 변화", "distribution"),
    ("quality_of_life", "work_limitation_t1", "직업활동 제약 비율", "rate"),
    ("quality_of_life", "other_limitation_t1", "비직업 활동제약 비율", "rate"),
    ("quality_of_life", "happiness_change", "행복도 변화", "distribution"),
    ("quality_of_life", "wellbeing_index_change", "웰빙지수 변화", "distribution"),
]


def prepare() -> pd.DataFrame:
    df = pd.read_csv(SOURCE, low_memory=False)
    employed = df.employment_status_t.notna() & df.employment_status_t1.notna()
    df = df[employed & df.age_t.between(25, 35)].copy()
    df = df[df.wage_outlier.eq(0)].copy()
    df["occupation_changed"] = np.where(
        df.occupation_t.notna() & df.occupation_t1.notna(),
        (df.occupation_t != df.occupation_t1).astype(float), np.nan,
    )
    # KLIPS 종사상지위 코드상 1~3=상용/임시/일용 임금근로, 4~5=고용주/자영업.
    # '개선'의 보편적 서열을 강제하지 않고 임금근로 내 비상용(2/3)→상용(1)만 센다.
    df["employment_improved"] = np.where(
        df.employment_status_t.isin([2, 3]),
        df.employment_status_t1.eq(1).astype(float), np.nan,
    )
    df["firm_size_up"] = np.where(
        df.firm_size_t.notna() & df.firm_size_t1.notna(),
        (df.firm_size_t1 > df.firm_size_t).astype(float), np.nan,
    )
    valid_wage = df.real_wage_t.gt(0) & df.real_wage_t1.gt(0)
    # 매 연도 전체 표본의 실질임금 5분위 코드로 절대 금액 변화의 시대 효과를 완화한다.
    df["wage_band_t"] = df.groupby("year_t").real_wage_t.transform(
        lambda x: pd.qcut(x.rank(method="first"), 5, labels=False, duplicates="drop")
    )
    df["wage_band_t1"] = df.groupby("year_t1").real_wage_t1.transform(
        lambda x: pd.qcut(x.rank(method="first"), 5, labels=False, duplicates="drop")
    )
    df["wage_band_up"] = np.where(valid_wage, (df.wage_band_t1 > df.wage_band_t).astype(float), np.nan)
    df["health_peer_improvement"] = np.where(
        df.health_peer_t.notna() & df.health_peer_t1.notna(),
        df.health_peer_t - df.health_peer_t1, np.nan,
    )
    df["future_optimism_change"] = df.future_optimism_t1 - df.future_optimism_t
    df["work_limitation_t1"] = np.where(
        df.limit_work_t1.notna(), df.limit_work_t1.eq(1).astype(float), np.nan,
    )
    df["other_limitation_t1"] = np.where(
        df.limit_other_t1.notna(), df.limit_other_t1.gt(0).astype(float), np.nan,
    )
    return df


def summarize(values: pd.Series, kind: str) -> dict:
    values = pd.to_numeric(values, errors="coerce").dropna()
    if values.empty:
        return {"n": 0, "available": False}
    base = {"n": int(len(values)), "available": True}
    if kind == "rate":
        return {**base, "rate": round(float(values.mean()), 4)}
    q = values.quantile([.25, .5, .75])
    return {
        **base, "mean": round(float(values.mean()), 4),
        "p25": round(float(q.loc[.25]), 4), "median": round(float(q.loc[.5]), 4),
        "p75": round(float(q.loc[.75]), 4),
        "improved_rate": round(float((values > 0).mean()), 4),
        "unchanged_rate": round(float((values == 0).mean()), 4),
        "worsened_rate": round(float((values < 0).mean()), 4),
    }


def direction(summary: dict, kind: str) -> int | None:
    if not summary.get("available"):
        return None
    value = summary.get("rate") if kind == "rate" else summary.get("mean")
    return 0 if abs(value) < 1e-9 else (1 if value > 0 else -1)


def build() -> dict:
    df = prepare()
    results = []
    for domain, column, label, kind in METRICS:
        if column not in df:
            continue
        groups = {}
        for moved, scenario in ((1, "move"), (0, "stay")):
            group = df[df.moved_t1.eq(moved)]
            full = summarize(group[column], kind)
            early = summarize(group.loc[group.year_t <= CUTOFF, column], kind)
            recent = summarize(group.loc[group.year_t > CUTOFF, column], kind)
            stable = (
                direction(early, kind) == direction(recent, kind)
                if early.get("n", 0) >= 30 and recent.get("n", 0) >= 30 else None
            )
            groups[scenario] = {"all_years": full, "early_years": early, "recent_years": recent, "direction_stable": stable}
        results.append({"domain": domain, "column": column, "label": label, "kind": kind, "scenarios": groups})
    return {
        "version": 1, "claim_type": "observed_outcome_not_causal_effect",
        "population": {"age_min": 25, "age_max": 35, "rows": int(len(df)), "people": int(df.pid.nunique())},
        "temporal_cutoff": CUTOFF, "source": "KLIPS 패널 전처리본", "metrics": results,
        "caution": "A/B 선택과 일치하는 과거 관측 분포이며 개인의 확정 미래나 인과효과가 아닙니다.",
    }


def main() -> None:
    result = build()
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[완료] {OUTPUT}")
    for item in result["metrics"]:
        a, b = item["scenarios"]["move"]["all_years"], item["scenarios"]["stay"]["all_years"]
        print(item["label"], "move", a, "stay", b)


if __name__ == "__main__":
    main()
