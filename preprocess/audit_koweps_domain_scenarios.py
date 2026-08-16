"""KOWEPS에서 9개 삶 영역의 A/B 선택 후보와 후속 결과 커버리지를 계산한다.

이 스크립트는 예측 모델을 학습하지 않는다. 25~35세 개인-차수 패널에서 실제로
관측 가능한 전환(event), 비전환 비교군, 1/3/5차 뒤 결과 표본을 세어 기획 후보를
``사용 가능 / 보류 / 결과 전용``으로 구분하기 위한 감사 도구다.

실행:
    python preprocess/audit_koweps_domain_scenarios.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "koweps" / "long" / "koweps_hp01_20_long_260331.dta"
OUT = ROOT / "data" / "clean" / "koweps"
HORIZONS = (1, 3, 5)
TARGET_AGE = (25, 35)

# mode는 현재차수와 직전차수를 사용해 사건을 만드는 규칙이다.
SCENARIOS = [
    {"domain": "career", "key": "occupation_change", "label": "직종 변경", "source": "h_eco9", "mode": "change"},
    {"domain": "career", "key": "employment_entry", "label": "미취업→취업", "source": "h_eco9", "mode": "became_observed"},
    {"domain": "education", "key": "education_level_change", "label": "교육수준 변화", "source": "h_g6", "mode": "change"},
    # 개인 자영업소득의 새 발생은 창업의 완전한 정의가 아니라 후보 proxy다.
    {"domain": "business", "key": "self_income_entry", "label": "자영업소득 새 발생(후보)", "source": "h_pers_income3", "mode": "positive_entry", "proxy": True},
    {"domain": "housing", "key": "residential_move", "label": "지난 1년 이사", "source": "h06_aq1", "mode": "yes"},
    {"domain": "housing", "key": "housing_tenure_change", "label": "주거 점유형태 변화", "source": "h06_3", "mode": "change"},
    {"domain": "relationship", "key": "marriage_change", "label": "혼인상태 변화", "source": "h_g10", "mode": "change"},
    {"domain": "relationship", "key": "household_size_change", "label": "가구원 수 변화", "source": "h01_1", "mode": "change"},
    {"domain": "lifestyle", "key": "work_schedule_change", "label": "근로시간형태 변화", "source": "h_eco6", "mode": "change"},
]

# finance/health/long_term_values는 KOWEPS에 결과는 풍부하지만 현재 정의된
# '사용자가 선택하는 사건'이 없다. 상태 악화를 선택으로 위장하지 않고 결과 전용으로 둔다.
OUTCOME_ONLY = {
    "finance": "소득·자산·부채는 결과로 사용 가능하나 명확한 선택 사건을 추가 정의해야 함",
    "health": "건강·우울은 결과로 사용 가능하나 질병 발생을 사용자 선택으로 취급할 수 없음",
    "long_term_values": "삶의 만족·가치관은 결과/개인화 변수이며 직접 선택 사건이 아님",
}

OUTCOMES = {
    "finance.disposable_income": "h_din",
    "career.job_satisfaction": "p03_9",
    "health.health_status": "h_med2",
    "health.health_satisfaction": "p03_5",
    "health.depressive_feeling": "p05_11",
    "housing.housing_type": "h06_1",
    "housing.housing_tenure": "h06_3",
    "housing.housing_satisfaction": "p03_7",
    "relationship.family_satisfaction": "p03_8",
    "relationship.social_satisfaction": "p03_10",
    "lifestyle.leisure_satisfaction": "p03_11",
    "long_term_values.overall_satisfaction": "p03_12",
}

BASE = ["h_pid", "h_merkey", "year", "wv", "h_g3", "h_g4"]


def required_columns() -> list[str]:
    return list(dict.fromkeys([
        *BASE,
        *[item["source"] for item in SCENARIOS],
        *OUTCOMES.values(),
    ]))


def load_source() -> pd.DataFrame:
    """원본에서 감사에 명시된 열만 읽는다(키워드 기반 298열 제한과 독립)."""
    columns = required_columns()
    frame = pd.read_stata(RAW, columns=columns, convert_categoricals=False)
    for column in frame.select_dtypes(include=["number"]).columns:
        if column not in {"year", "wv"}:
            frame[column] = frame[column].mask(frame[column] < 0)
    frame["age"] = frame["year"] - frame["h_g4"]
    return frame.sort_values(["h_pid", "wv"]).reset_index(drop=True)


def event_series(data: pd.DataFrame, source: str, mode: str) -> pd.Series:
    current = data[source]
    grouped = data.groupby("h_pid", sort=False)
    previous = grouped[source].shift(1)
    previous_wave = grouped["wv"].shift(1)
    consecutive = data["wv"].sub(previous_wave).eq(1)

    if mode == "yes":
        # 공식 KOWEPS 이분형 문항의 일반 코딩. 분포는 결과 JSON에도 남긴다.
        result = current.eq(1).where(current.notna())
    elif mode == "change":
        known = current.notna() & previous.notna() & consecutive
        result = current.ne(previous).where(known)
    elif mode == "became_observed":
        known = consecutive
        result = (current.notna() & previous.isna()).where(known)
    elif mode == "positive_entry":
        known = consecutive & current.notna() & previous.notna()
        result = (current.gt(0) & previous.le(0)).where(known)
    else:
        raise ValueError(f"지원하지 않는 사건 mode: {mode}")
    return result.astype("float64")


def verdict(event_n: int, control_n: int, followups: dict) -> tuple[str, str]:
    min_followup = min(
        (cell["event_outcome_n"] for horizon in followups.values() for cell in horizon.values()),
        default=0,
    )
    if event_n < 100:
        return "hold", "25~35세 사건 표본 100건 미만"
    if control_n < 500:
        return "hold", "비사건 비교군 500건 미만"
    if min_followup < 30:
        return "hold", "일부 1·3·5차 결과의 사건 표본 30건 미만"
    return "candidate", "관측분포/추가 검증 후보(인과효과 또는 개인예측을 의미하지 않음)"


def build_report(data: pd.DataFrame) -> tuple[dict, pd.DataFrame]:
    # 사건 전 상태와 사건 후 1/3/5차 결과는 연령 경계 밖 관측도 필요하다. 따라서
    # lag/lead는 전체 패널에서 계산하고, 기준시점(baseline)만 25~35세로 제한한다.
    baseline_mask = data["age"].between(*TARGET_AGE)
    target = data.loc[baseline_mask]
    grouped = data.groupby("h_pid", sort=False)
    scenario_rows = []
    flat_rows = []

    for spec in SCENARIOS:
        event_all = event_series(data, spec["source"], spec["mode"])
        event = event_all.loc[baseline_mask]
        known = event.notna()
        event_mask = event.eq(1)
        control_mask = event.eq(0)
        followups = {}

        for horizon in HORIZONS:
            future_wave_all = grouped["wv"].shift(-horizon)
            exact_wave = future_wave_all.sub(data["wv"]).eq(horizon).loc[baseline_mask]
            followups[str(horizon)] = {}
            for outcome, source in OUTCOMES.items():
                future = grouped[source].shift(-horizon).loc[baseline_mask]
                observed = exact_wave & future.notna()
                cell = {
                    "event_outcome_n": int((event_mask & observed).sum()),
                    "control_outcome_n": int((control_mask & observed).sum()),
                }
                followups[str(horizon)][outcome] = cell
                flat_rows.append({
                    "domain": spec["domain"], "scenario": spec["key"], "scenario_label": spec["label"],
                    "source_variable": spec["source"], "horizon": horizon, "outcome": outcome,
                    **cell,
                })

        status, reason = verdict(int(event_mask.sum()), int(control_mask.sum()), followups)
        if spec.get("proxy") and status == "candidate":
            status, reason = "hold", "소득 발생은 창업의 proxy이므로 고용형태 코드 교차검증 필요"
        scenario_rows.append({
            **spec,
            "known_rows": int(known.sum()),
            "event_rows": int(event_mask.sum()),
            "event_people": int(target.loc[event_mask, "h_pid"].nunique()),
            "control_rows": int(control_mask.sum()),
            "source_top_values": {str(k): int(v) for k, v in target[spec["source"]].value_counts(dropna=False).head(12).items()},
            "followup": followups,
            "status": status,
            "reason": reason,
        })

    report = {
        "purpose": "9개 삶 영역의 선택 사건 및 후속 결과 데이터 적합성 감사",
        "claim_limit": "표본·커버리지 계산이며 인과효과나 개인별 미래예측 결과가 아님",
        "source": RAW.name,
        "target_age": list(TARGET_AGE),
        "target_rows": int(len(target)),
        "target_people": int(target["h_pid"].nunique()),
        "horizons_in_waves": list(HORIZONS),
        "scenarios": scenario_rows,
        "outcome_only_domains": OUTCOME_ONLY,
        "outcomes": OUTCOMES,
    }
    return report, pd.DataFrame(flat_rows)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    report, flat = build_report(load_source())
    (OUT / "koweps_domain_scenario_audit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    flat.to_csv(OUT / "koweps_domain_scenario_followup.csv", index=False, encoding="utf-8-sig")
    print(f"[target] {report['target_people']:,}명 / {report['target_rows']:,} 개인-차수")
    for item in report["scenarios"]:
        print(
            f"[{item['status']:<9}] {item['domain']}.{item['key']}: "
            f"사건 {item['event_rows']:,} / 비교 {item['control_rows']:,} — {item['reason']}"
        )
    for domain, reason in OUTCOME_ONLY.items():
        print(f"[outcome] {domain}: {reason}")


if __name__ == "__main__":
    main()
