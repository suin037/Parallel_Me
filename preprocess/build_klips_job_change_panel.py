"""KLIPS 이직 전후 분석표를 생성한다.

입력(t)은 이직 결정 이전 시점, 처치와 결과는 다음 조사(t+1)에서 가져온다.
현재 배포 모델을 재학습하거나 artifact를 덮어쓰지 않는다.

출력:
  data/clean/klips_job_change_panel.csv
  data/clean/klips_job_change_panel_report.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "klips"
OUT = ROOT / "data" / "clean"

BASE_REQUIRED = {
    "pid", "wave", "조사연도", "성별", "나이", "학력", "종사상지위", "직종",
    "jobtype", "월임금_실질", "종업원규모", "근속기간", "이직",
}

HEALTH_VARS = [
    "건강_현재", "건강_1년전대비", "건강_또래대비", "제약_직업활동", "제약_비직업",
    "삶의만족도_현재", "행복도_현재", "삶의만족도_5년후예상", "건강점수", "웰빙지수",
    "미래낙관점수", "기대격차_5년",
    "만족_가족수입", "만족_여가활동", "만족_주거환경", "만족_가족관계",
    "만족_친인척관계", "만족_사회적친분", "만족_전반적",
]

WORK_CONTEXT_VARS = [
    "스트레스", "우울", "수면시간", "불면지수", "BMI", "실근무시간", "장시간근무", "야간근무",
    "저녁근무", "주말근무", "교대근무", "유연근무제", "출퇴근시간",
    "피로_지장", "휴식_필요", "짧은휴식", "유해근무_개수",
]

BASE_INPUTS = [
    "age_t", "sex_t", "edu_t", "employment_status_t", "occupation_t", "jobtype_t",
    "real_wage_t", "firm_size_t", "tenure_t",
]

OUTCOMES = [
    "real_wage_t1", "wage_change", "wage_change_pct", "wage_down_t1",
    "employment_status_t1", "health_current_t1", "life_satisfaction_t1",
    "happiness_t1", "health_score_t1", "wellbeing_index_t1",
    "health_current_change", "life_satisfaction_change", "happiness_change",
    "health_score_change", "wellbeing_index_change",
]

# The raw KLIPS domain-satisfaction items use 1=most satisfied and
# 5=least satisfied. Model-facing changes are reversed so positive always
# means that satisfaction improved between t and t+1.
SATISFACTION_DOMAINS = {
    "satisfaction_family_income": "\ub9cc\uc871_\uac00\uc871\uc218\uc785",
    "satisfaction_leisure": "\ub9cc\uc871_\uc5ec\uac00\ud65c\ub3d9",
    "satisfaction_housing": "\ub9cc\uc871_\uc8fc\uac70\ud658\uacbd",
    "satisfaction_family_relationship": "\ub9cc\uc871_\uac00\uc871\uad00\uacc4",
    "satisfaction_social_relationship": "\ub9cc\uc871_\uc0ac\ud68c\uc801\uce5c\ubd84",
    "satisfaction_overall": "\ub9cc\uc871_\uc804\ubc18\uc801",
}


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, low_memory=False)


def _assert_columns(df: pd.DataFrame, required: set[str], name: str) -> None:
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"{name} 필수 열 누락: {missing}")


def _select_existing(df: pd.DataFrame, columns: list[str]) -> list[str]:
    return [c for c in columns if c in df.columns]


def build_panel(age_min: int = 20, age_max: int = 45) -> tuple[pd.DataFrame, dict]:
    base = _read_csv(RAW / "klips_base.csv")
    health = _read_csv(RAW / "klips_health.csv")
    work = _read_csv(RAW / "klips_health26a.csv")
    _assert_columns(base, BASE_REQUIRED, "klips_base")
    _assert_columns(health, {"pid", "wave"}, "klips_health")
    _assert_columns(work, {"pid", "wave"}, "klips_health26a")

    health_cols = _select_existing(health, HEALTH_VARS)
    work_cols = _select_existing(work, WORK_CONTEXT_VARS)
    current = base.merge(
        health[["pid", "wave", *health_cols]].drop_duplicates(["pid", "wave"]),
        on=["pid", "wave"], how="left", validate="one_to_one",
    )
    current = current.merge(
        work[["pid", "wave", *work_cols]].drop_duplicates(["pid", "wave"]),
        on=["pid", "wave"], how="left", validate="one_to_one",
    )
    current = current.sort_values(["pid", "wave"]).reset_index(drop=True)

    next_values = current.groupby("pid", sort=False).shift(-1)
    panel = pd.DataFrame({
        "pid": current["pid"],
        "wave_t": current["wave"],
        "year_t": current["조사연도"],
        "wave_t1": next_values["wave"],
        "year_t1": next_values["조사연도"],
        "age_t": current["나이"],
        "sex_t": current["성별"],
        "edu_t": current["학력"],
        "employment_status_t": current["종사상지위"],
        "occupation_t": current["직종"],
        "jobtype_t": current["jobtype"],
        "real_wage_t": current["월임금_실질"],
        "firm_size_t": current["종업원규모"],
        "tenure_t": current["근속기간"],
        # 기존 KLIPS 학습 정의와 일치: 다음 조사에서 보고된 이직 여부
        "moved_t1": next_values["이직"],
        "employment_status_t1": next_values["종사상지위"],
        "occupation_t1": next_values["직종"],
        "real_wage_t1": next_values["월임금_실질"],
        "firm_size_t1": next_values["종업원규모"],
        "tenure_t1": next_values["근속기간"],
    })

    for source, prefix in ((HEALTH_VARS, ""), (WORK_CONTEXT_VARS, "work_")):
        for col in source:
            if col not in current.columns:
                continue
            safe = {
                "건강_현재": "health_current", "삶의만족도_현재": "life_satisfaction",
                "행복도_현재": "happiness", "건강점수": "health_score", "웰빙지수": "wellbeing_index",
                "건강_1년전대비": "health_year_change", "건강_또래대비": "health_peer",
                "제약_직업활동": "limit_work", "제약_비직업": "limit_other",
                "삶의만족도_5년후예상": "future_satisfaction", "미래낙관점수": "future_optimism",
                "기대격차_5년": "future_expectation_gap",
                "스트레스": "stress", "우울": "depression", "수면시간": "sleep_hours",
                "불면지수": "insomnia", "BMI": "bmi",
                "실근무시간": "actual_work_hours", "장시간근무": "long_hours",
                "야간근무": "night_work", "저녁근무": "evening_work", "주말근무": "weekend_work",
                "교대근무": "shift_work", "유연근무제": "flexible_work", "출퇴근시간": "commute_time",
                "피로_지장": "fatigue_interference", "휴식_필요": "need_rest",
                "짧은휴식": "short_rest", "유해근무_개수": "harmful_work_count",
            }.get(col, col)
            panel[f"{prefix}{safe}_t"] = current[col]
            panel[f"{prefix}{safe}_t1"] = next_values[col]

    panel["wave_gap"] = panel["wave_t1"] - panel["wave_t"]
    panel["year_gap"] = panel["year_t1"] - panel["year_t"]
    panel = panel[(panel["wave_gap"] == 1) & (panel["year_gap"] == 1)]
    panel = panel[panel["age_t"].between(age_min, age_max)]
    panel = panel.dropna(subset=["moved_t1"])
    panel["moved_t1"] = panel["moved_t1"].astype(int)

    panel["wage_change"] = panel["real_wage_t1"] - panel["real_wage_t"]
    valid_wage = panel["real_wage_t"].gt(0) & panel["real_wage_t1"].gt(0)
    panel["wage_change_pct"] = np.where(
        valid_wage,
        panel["wage_change"] / panel["real_wage_t"] * 100,
        np.nan,
    )
    panel["wage_down_t1"] = np.where(
        valid_wage, (panel["real_wage_t1"] < panel["real_wage_t"]).astype(int), np.nan,
    )

    for stem in (
        "health_current", "life_satisfaction", "happiness", "health_score", "wellbeing_index",
    ):
        before, after = f"{stem}_t", f"{stem}_t1"
        if before in panel.columns and after in panel.columns:
            panel[f"{stem}_change"] = panel[after] - panel[before]

    for safe, source in SATISFACTION_DOMAINS.items():
        before, after = f"{source}_t", f"{source}_t1"
        if before in panel.columns and after in panel.columns:
            panel[f"{safe}_t"] = panel[before]
            panel[f"{safe}_t1"] = panel[after]
            panel[f"{safe}_change"] = panel[before] - panel[after]

    # 극단적 임금 변화는 삭제하지 않고 품질 플래그만 남긴다.
    panel["wage_outlier"] = panel["wage_change_pct"].abs().gt(300).fillna(False).astype(int)
    panel = panel.sort_values(["pid", "wave_t"]).reset_index(drop=True)

    report = build_report(panel, len(base), health_cols, work_cols, age_min, age_max)
    return panel, report


def _coverage(df: pd.DataFrame, columns: list[str]) -> dict[str, dict[str, float | int]]:
    result = {}
    for col in columns:
        if col not in df.columns:
            continue
        n = int(df[col].notna().sum())
        result[col] = {"n": n, "coverage": round(n / len(df), 4) if len(df) else 0.0}
    return result


def build_report(
    panel: pd.DataFrame,
    base_rows: int,
    health_cols: list[str],
    work_cols: list[str],
    age_min: int,
    age_max: int,
) -> dict:
    groups = {}
    for moved, group in panel.groupby("moved_t1"):
        wage_valid = group.dropna(subset=["real_wage_t", "real_wage_t1"])
        summary = {
            "n": int(len(group)),
            "wage_pair_n": int(len(wage_valid)),
            "wage_change_median": round(float(wage_valid["wage_change"].median()), 2) if len(wage_valid) else None,
            "wage_change_pct_median": round(float(wage_valid["wage_change_pct"].median()), 2) if len(wage_valid) else None,
            "wage_down_rate": round(float(wage_valid["wage_down_t1"].mean()), 4) if len(wage_valid) else None,
        }
        for col in (
            "life_satisfaction_change", "happiness_change", "health_current_change",
            "health_score_change", "wellbeing_index_change",
        ):
            values = group[col].dropna() if col in group else pd.Series(dtype=float)
            summary[col] = {
                "n": int(len(values)),
                "median": round(float(values.median()), 3) if len(values) else None,
                "mean": round(float(values.mean()), 3) if len(values) else None,
            }
        groups[str(int(moved))] = summary

    outcome_cols = [c for c in OUTCOMES if c in panel.columns]
    outcome_cols += [c for c in panel if c.endswith("_t1") and c.startswith("work_")]
    return {
        "definition": "입력=t, 처치(moved_t1)와 결과=t+1; 연속 조사(wave/year gap=1)만 포함",
        "age_range": [age_min, age_max],
        "base_rows": base_rows,
        "panel_rows": int(len(panel)),
        "unique_people": int(panel["pid"].nunique()),
        "move_rate": round(float(panel["moved_t1"].mean()), 4) if len(panel) else None,
        "groups": groups,
        "input_coverage": _coverage(panel, BASE_INPUTS),
        "outcome_coverage": _coverage(panel, outcome_cols),
        "merged_health_columns": health_cols,
        "merged_work_context_columns": work_cols,
        "warnings": [
            "단순 이직/유지 평균 차이는 인과효과가 아니다.",
            "health26a는 특정 부가조사 시점 자료이므로 t→t+1 결과 커버리지가 낮거나 0일 수 있다.",
            "임금 변화율 절대값 300% 초과는 wage_outlier=1로 표시했으며 모델링 전 별도 처리해야 한다.",
            "개인 단위 train/test 분리와 overlap 검증 전에는 모델을 배포하지 않는다.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--age-min", type=int, default=20)
    parser.add_argument("--age-max", type=int, default=45)
    parser.add_argument("--output-dir", type=Path, default=OUT)
    args = parser.parse_args()

    panel, report = build_panel(args.age_min, args.age_max)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    panel_path = args.output_dir / "klips_job_change_panel.csv"
    report_path = args.output_dir / "klips_job_change_panel_report.json"
    panel.to_csv(panel_path, index=False, encoding="utf-8-sig")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[완료] 분석표 {panel_path} ({len(panel):,}행, {panel['pid'].nunique():,}명)")
    print(f"[완료] 품질보고서 {report_path}")
    print(f"[요약] 이직률 {report['move_rate']:.1%} | 이직 {report['groups'].get('1', {}).get('n', 0):,}행")


if __name__ == "__main__":
    main()
