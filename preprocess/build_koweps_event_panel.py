"""KOWEPS 경량 패널 → 선택 사건과 1·3·5년 결과 패널.

이 단계는 효과를 추정하지 않는다. 사건 발생 수, 추적 가능 표본과 결과변수 커버리지를
확인하기 위한 분석 준비물이다. 개인별 산출물은 ``data/clean`` 아래에만 저장한다.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "clean" / "koweps" / "koweps_life_panel.parquet"
OUT = ROOT / "data" / "clean" / "koweps"
HORIZONS = (1, 3, 5)

EVENTS = {
    "residential_move": {"source": "h06_aq1", "mode": "yes", "label": "지난 1년 이사"},
    "marriage_change": {"source": "h_g10", "mode": "change", "label": "혼인상태 변화"},
    "employment_change": {"source": "h_eco9", "mode": "employment_state", "label": "취업상태 변화"},
    "household_size_change": {"source": "h01_1", "mode": "change", "label": "가구원 수 변화"},
}

OUTCOMES = {
    "disposable_income": "h_din",
    "health_status": "h_med2",
    "housing_type": "h06_1",
    "housing_tenure": "h06_3",
    "family_relationship_satisfaction": "p03_8",
    "leisure_satisfaction": "p03_11",
    "overall_satisfaction": "p03_12",
    "depressive_feeling": "p05_11",
}


def _yes(series: pd.Series) -> pd.Series:
    # KOWEPS의 일반적인 이분형 코딩 1=예, 2=아니오. 실제 분포를 보고서에 남긴다.
    return series.eq(1).where(series.notna())


def build() -> tuple[pd.DataFrame, dict]:
    frame = pd.read_parquet(SOURCE)
    needed = ["h_pid", "h_merkey", "year", "wv", *[x["source"] for x in EVENTS.values()], *OUTCOMES.values()]
    missing = [c for c in needed if c not in frame]
    if missing:
        raise KeyError(f"경량 패널에 필요한 열이 없습니다: {missing}")
    data = frame[needed].sort_values(["h_pid", "wv"]).copy()
    grouped = data.groupby("h_pid", sort=False)

    for key, spec in EVENTS.items():
        current = data[spec["source"]]
        previous = grouped[spec["source"]].shift(1)
        consecutive = data["wv"].sub(grouped["wv"].shift(1)).eq(1)
        if spec["mode"] == "yes":
            data[key] = _yes(current).astype("float64")
        elif spec["mode"] == "employment_state":
            # 직종 응답이 있으면 취업, 없으면 미취업으로 둔다. 두 연도가 연속 관측된
            # 경우에만 상태 전환을 정의한다. 직종 자체 변경은 KLIPS 커리어 모듈 담당.
            employed = current.notna()
            previous_employed = grouped[spec["source"]].shift(1).notna()
            data[key] = (employed.ne(previous_employed) & consecutive).astype("float64")
            data.loc[~consecutive, key] = np.nan
        else:
            data[key] = (current.ne(previous) & current.notna() & previous.notna() & consecutive).astype("float64")
            data.loc[~consecutive | current.isna() | previous.isna(), key] = np.nan

    long_rows = []
    for horizon in HORIZONS:
        for outcome, source in OUTCOMES.items():
            future = grouped[source].shift(-horizon)
            future_wave = grouped["wv"].shift(-horizon)
            observed = future_wave.sub(data["wv"]).eq(horizon) & future.notna()
            block = data[["h_pid", "h_merkey", "year", "wv", *EVENTS]].copy()
            block["horizon"] = horizon
            block["outcome"] = outcome
            block["outcome_value"] = future.where(observed)
            block["outcome_observed"] = observed.astype("int8")
            long_rows.append(block)
    result = pd.concat(long_rows, ignore_index=True)

    event_report = {}
    for key, spec in EVENTS.items():
        known = data[key].notna()
        event_report[key] = {
            "label": spec["label"], "source_variable": spec["source"],
            "known_rows": int(known.sum()), "event_rows": int(data.loc[known, key].eq(1).sum()),
            "event_people": int(data.loc[data[key].eq(1), "h_pid"].nunique()),
            "source_values": {str(k): int(v) for k, v in data[spec["source"]].value_counts(dropna=False).head(12).items()},
            "followup": {
                str(h): {
                    outcome: int(result[
                        result[key].eq(1) & result.horizon.eq(h) & result.outcome.eq(outcome)
                    ].outcome_observed.sum())
                    for outcome in OUTCOMES
                } for h in HORIZONS
            },
        }
    report = {
        "built_at": datetime.now(timezone.utc).isoformat(), "source": SOURCE.name,
        "rows": int(len(data)), "people": int(data.h_pid.nunique()),
        "events": event_report,
        "caution": "사건·결과 커버리지 감사용. 효과 추정이나 개인 예측 결과가 아님.",
    }
    return result, report


def main() -> None:
    result, report = build()
    result.to_parquet(OUT / "koweps_event_outcomes.parquet", index=False)
    (OUT / "koweps_event_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[done] event-outcomes {len(result):,}행")
    for key, item in report["events"].items():
        print(f"  {key}: {item['event_rows']:,}건 / {item['event_people']:,}명")


if __name__ == "__main__":
    main()
