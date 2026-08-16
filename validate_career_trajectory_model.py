"""과거 기준시점에서 만든 경로 요약을 이후 기준시점에 시간순 검증한다."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "data" / "clean" / "career_future_panel.parquet"
OUTPUT = ROOT / "data" / "clean" / "career_trajectory_validation.json"
CUTOFFS = {1: 2021, 3: 2019, 5: 2017}


def wage_change(frame: pd.DataFrame, horizon: int) -> pd.Series:
    future = frame[f"real_wage_y{horizon}"]
    return (future - frame.real_wage_t) / frame.real_wage_t * 100


def validate_horizon(rows: pd.DataFrame, horizon: int, new_people_only: bool = False) -> dict:
    cutoff = CUTOFFS[horizon]
    eligible = rows[rows[f"observed_y{horizon}"].eq(1)].copy()
    train = eligible[eligible.year_t.le(cutoff)].copy()
    test = eligible[eligible.year_t.gt(cutoff)].copy()
    if new_people_only:
        test = test[~test.pid.isin(train.pid)].copy()
    keys = ["choice", "state", "occupation_group"]
    state_lookup = (
        train.dropna(subset=[f"state_y{horizon}"]).groupby(keys)[f"state_y{horizon}"]
        .agg(lambda x: x.mode().iloc[0]).rename("predicted_state")
    )
    wage_train = train.assign(wage_change=wage_change(train, horizon)).replace([np.inf, -np.inf], np.nan)
    wage_lookup = wage_train.groupby(keys).wage_change.median().rename("predicted_wage_change")
    scored = test.join(state_lookup, on=keys).join(wage_lookup, on=keys)
    state_valid = scored.dropna(subset=["predicted_state", f"state_y{horizon}"])
    accuracy = float(state_valid.predicted_state.eq(state_valid[f"state_y{horizon}"]).mean()) if len(state_valid) else None
    global_mode = train[f"state_y{horizon}"].mode().iloc[0]
    baseline_accuracy = float(test[f"state_y{horizon}"].eq(global_mode).mean())
    actual_wage = wage_change(scored, horizon).replace([np.inf, -np.inf], np.nan)
    wage_valid = scored.predicted_wage_change.notna() & actual_wage.notna()
    mae = float((scored.loc[wage_valid, "predicted_wage_change"] - actual_wage[wage_valid]).abs().mean()) if wage_valid.any() else None
    global_median = float(wage_train.wage_change.median())
    baseline_mae = float((actual_wage.dropna() - global_median).abs().mean())
    return {
        "horizon_years": horizon, "cutoff": cutoff, "train_n": int(len(train)), "test_n": int(len(test)),
        "protocol": "recent_year_new_people" if new_people_only else "recent_year",
        "state_scored_n": int(len(state_valid)), "state_top1_accuracy": round(accuracy, 4) if accuracy is not None else None,
        "state_global_baseline": round(baseline_accuracy, 4),
        "wage_scored_n": int(wage_valid.sum()), "wage_change_mae": round(mae, 3) if mae is not None else None,
        "wage_global_median_mae": round(baseline_mae, 3),
        "state_improves_baseline": bool(accuracy is not None and accuracy > baseline_accuracy),
        "wage_improves_baseline": bool(mae is not None and mae < baseline_mae),
    }


def main() -> None:
    rows = pd.read_parquet(SOURCE)
    results = [
        validate_horizon(rows, horizon, new_people_only)
        for horizon in (1, 3, 5) for new_people_only in (False, True)
    ]
    report = {
        "method": "과거 기준시점의 선택·현재상태·직종별 대표 결과를 이후 기준시점에 적용",
        "results": results,
        "limitations": [
            "관측 경로 검증이며 선택의 인과효과 검증이 아니다.",
            "5년 결과는 2015~2024의 짧은 관측창 때문에 학습·검증 연도가 제한된다.",
            "Optimal Matching 군집 자체는 전체 시퀀스에서 탐색됐으므로 별도 외부표본 안정성 검증이 필요하다.",
        ],
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
