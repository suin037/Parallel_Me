"""KLIPS 2015~2024를 개인별 커리어 상태 시퀀스와 장기 후속 패널로 변환한다."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
RAW = ROOT / "data" / "raw" / "klips"
CLEAN = ROOT / "data" / "clean"
SEQUENCE_ROWS = CLEAN / "career_sequence_rows.parquet"
SEQUENCES = CLEAN / "career_sequences.json"
FUTURES = CLEAN / "career_future_panel.parquet"


def career_state(row: pd.Series) -> str:
    status = row["종사상지위"]
    if pd.isna(status):
        return "not_employed"
    if status in (4, 5):
        return "self_employed"
    if status in (2, 3):
        return "non_regular"
    firm = row["firm_for_state"]
    if pd.isna(firm):
        return "regular_unknown"
    if firm <= 3:
        return "regular_small"
    if firm <= 6:
        return "regular_medium"
    return "regular_large"


def load_rows() -> pd.DataFrame:
    base = pd.read_csv(RAW / "klips_base.csv", low_memory=False)
    health = pd.read_csv(RAW / "klips_health.csv", low_memory=False)
    health_cols = [
        "pid", "wave", "삶의만족도_현재", "행복도_현재", "웰빙지수", "건강점수",
        "만족점수_전반적", "미래낙관점수",
    ]
    rows = base.merge(health[[c for c in health_cols if c in health]], on=["pid", "wave"], how="left")
    rows = rows.sort_values(["pid", "wave"]).copy()
    rows["firm_for_state"] = rows.groupby("pid")["종업원규모"].transform(lambda x: x.ffill().bfill())
    rows["state"] = rows.apply(career_state, axis=1)
    rows["occupation_group"] = pd.to_numeric(rows["직종"], errors="coerce").floordiv(100)
    rows["employed"] = rows["종사상지위"].notna().astype(int)
    return rows


def sequence_population(rows: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    eligible = []
    sequence_records = []
    for pid, group in rows.groupby("pid", sort=False):
        group = group.sort_values("wave")
        young = group[group["나이"].between(25, 35)]
        if young.empty:
            continue
        start_wave = int(young.wave.iloc[0])
        seq = group[group.wave.ge(start_wave)].copy()
        if len(seq) < 5:
            continue
        eligible.append(seq)
        sequence_records.append({
            "pid": int(pid), "start_age": int(seq["나이"].iloc[0]),
            "start_year": int(seq["조사연도"].iloc[0]), "observations": int(len(seq)),
            "states": seq.state.tolist(), "years": seq["조사연도"].astype(int).tolist(),
        })
    return pd.concat(eligible, ignore_index=True), sequence_records


def future_panel(rows: pd.DataFrame) -> pd.DataFrame:
    rows = rows.sort_values(["pid", "wave"]).copy()
    rows["choice_next"] = rows.groupby("pid")["이직"].shift(-1)
    indexed = rows.set_index(["pid", "wave"])
    anchors = rows[rows["나이"].between(25, 35) & rows["종사상지위"].notna()].copy()
    anchors = anchors[anchors.choice_next.notna()].copy()
    anchors["choice"] = np.where(anchors.choice_next.eq(1), "move", "stay")
    keep = [
        "pid", "wave", "조사연도", "나이", "성별", "학력", "state", "occupation_group",
        "종사상지위", "종업원규모", "월임금_실질", "근속기간", "choice",
    ]
    out = anchors[keep].rename(columns={
        "조사연도": "year_t", "나이": "age_t", "성별": "sex_t", "학력": "edu_t",
        "종사상지위": "employment_status_t", "종업원규모": "firm_size_t",
        "월임금_실질": "real_wage_t", "근속기간": "tenure_t",
    }).copy()
    target_cols = {
        "state": "state", "occupation_group": "occupation_group", "종사상지위": "employment_status",
        "종업원규모": "firm_size", "월임금_실질": "real_wage", "근속기간": "tenure",
        "삶의만족도_현재": "life_satisfaction", "행복도_현재": "happiness",
        "웰빙지수": "wellbeing", "건강점수": "health", "만족점수_전반적": "overall_satisfaction",
        "미래낙관점수": "future_optimism",
    }
    for horizon in (1, 3, 5):
        keys = pd.MultiIndex.from_arrays([out.pid, out.wave + horizon])
        target = indexed.reindex(keys)
        for source, safe in target_cols.items():
            out[f"{safe}_y{horizon}"] = target[source].to_numpy()
        out[f"observed_y{horizon}"] = target["조사연도"].notna().astype(int).to_numpy()
    return out


def main() -> None:
    CLEAN.mkdir(parents=True, exist_ok=True)
    rows = load_rows()
    seq_rows, sequences = sequence_population(rows)
    futures = future_panel(rows)
    seq_rows.to_parquet(SEQUENCE_ROWS, index=False)
    FUTURES.parent.mkdir(parents=True, exist_ok=True)
    futures.to_parquet(FUTURES, index=False)
    SEQUENCES.write_text(json.dumps({
        "version": 1, "state_definition": {
            "not_employed": "미취업", "non_regular": "비상용 임금근로", "regular_small": "소규모 상용",
            "regular_medium": "중간규모 상용", "regular_large": "대규모 상용",
            "regular_unknown": "규모미상 상용", "self_employed": "자영업·고용주",
        }, "people": len(sequences), "sequences": sequences,
    }, ensure_ascii=False), encoding="utf-8")
    print(f"[시퀀스] {len(sequences):,}명 / {len(seq_rows):,}행")
    print(f"[후속 패널] {len(futures):,} 기준시점")
    print({h: int(futures[f'observed_y{h}'].sum()) for h in (1, 3, 5)})


if __name__ == "__main__":
    main()
