"""현재 상태와 유사 커리어 궤적에서 A/B 1·3·5년 관측 경로를 만든다."""

from __future__ import annotations

import json
from functools import lru_cache

import numpy as np
import pandas as pd

from config import ROOT


FUTURE_PANEL = ROOT / "data" / "clean" / "career_future_panel.parquet"
CLUSTERS = ROOT / "data" / "clean" / "career_trajectory_clusters.json"
STATE_LABELS = {
    "not_employed": "미취업", "non_regular": "비상용 임금근로", "regular_small": "소규모 상용",
    "regular_medium": "중간규모 상용", "regular_large": "대규모 상용",
    "regular_unknown": "규모미상 상용", "self_employed": "자영업·고용주",
}


@lru_cache(maxsize=1)
def _cluster_artifact() -> dict:
    return json.loads(CLUSTERS.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _future_rows() -> pd.DataFrame:
    rows = pd.read_parquet(FUTURE_PANEL)
    assignments = pd.DataFrame(_cluster_artifact()["assignments"])[["pid", "cluster_id"]]
    return rows.merge(assignments, on="pid", how="left")


def _profile_state(profile: dict) -> str:
    status = profile.get("employment_status")
    firm = profile.get("firm_size")
    if status is None:
        return "regular_unknown"
    if int(status) in (4, 5):
        return "self_employed"
    if int(status) in (2, 3):
        return "non_regular"
    if firm is None:
        return "regular_unknown"
    if int(firm) <= 3:
        return "regular_small"
    if int(firm) <= 6:
        return "regular_medium"
    return "regular_large"


def _closest_cluster(profile: dict) -> dict:
    artifact = _cluster_artifact()
    state = _profile_state(profile)
    cluster = max(artifact["clusters"], key=lambda item: item.get("state_share", {}).get(state, 0))
    return {
        "id": cluster["id"], "label": cluster["label"], "current_state": state,
        "current_state_label": STATE_LABELS[state], "cluster_member_n": cluster["member_n"],
        "match_basis": "현재 고용상태와 기업규모에 가장 가까운 Optimal Matching 궤적",
        "model_silhouette": artifact["sample_silhouette"],
    }


def _matched_rows(profile: dict, choice: str, cluster_id: int, minimum: int = 35) -> tuple[pd.DataFrame, list[str], list[str]]:
    rows = _future_rows()
    pool = rows[rows.choice.eq(choice)].copy()
    applied, relaxed = [], []
    clustered = pool[pool.cluster_id.eq(cluster_id)]
    if len(clustered) >= minimum:
        pool = clustered
        applied.append("유사 커리어 궤적")
    else:
        relaxed.append("유사 커리어 궤적")
    age = pd.to_numeric(profile.get("age"), errors="coerce")
    occupation = profile.get("occupation_group")
    employment = profile.get("employment_status")
    wage = pd.to_numeric(profile.get("monthly_wage"), errors="coerce")
    tenure = pd.to_numeric(profile.get("tenure_years"), errors="coerce")
    candidates = []
    if pd.notna(age):
        candidates.append(("나이 ±3세", lambda x: x.age_t.between(age - 3, age + 3)))
    if occupation is not None:
        candidates.append(("현재 직종", lambda x: x.occupation_group.eq(int(occupation))))
    if employment is not None:
        candidates.append(("현재 고용형태", lambda x: x.employment_status_t.eq(int(employment))))
    if pd.notna(wage):
        candidates.append(("현재 임금 ±30%", lambda x: x.real_wage_t.between(wage * .7, wage * 1.3)))
    if pd.notna(tenure):
        candidates.append(("근속기간 ±2년", lambda x: x.tenure_t.between(max(0, tenure - 2), tenure + 2)))
    for name, condition in candidates:
        narrowed = pool[condition(pool)]
        if len(narrowed) >= minimum:
            pool = narrowed
            applied.append(name)
        else:
            relaxed.append(name)
    return pool, applied, relaxed


def _number_distribution(values: pd.Series) -> dict:
    values = pd.to_numeric(values, errors="coerce").dropna()
    if values.empty:
        return {"available": False, "n": 0}
    q = values.quantile([.25, .5, .75])
    return {"available": True, "n": int(len(values)), "p25": round(float(q.loc[.25]), 2),
            "median": round(float(q.loc[.5]), 2), "p75": round(float(q.loc[.75]), 2)}


def trajectory_for_choice(choice_kind: str, profile: dict) -> dict:
    if choice_kind not in {"이직", "유지"}:
        return {"status": "not_applicable"}
    choice = "move" if choice_kind == "이직" else "stay"
    trajectory_type = _closest_cluster(profile)
    rows, applied, relaxed = _matched_rows(profile, choice, trajectory_type["id"])
    timeline = []
    for horizon in (1, 3, 5):
        observed = rows[rows[f"observed_y{horizon}"].eq(1)].copy()
        states = observed[f"state_y{horizon}"].dropna().value_counts(normalize=True).head(3)
        wage_change = np.where(
            observed.real_wage_t.gt(0) & observed[f"real_wage_y{horizon}"].gt(0),
            (observed[f"real_wage_y{horizon}"] - observed.real_wage_t) / observed.real_wage_t * 100, np.nan,
        )
        occupation_changed = (
            observed[f"occupation_group_y{horizon}"].notna() & observed.occupation_group.notna()
            & observed[f"occupation_group_y{horizon}"].ne(observed.occupation_group)
        )
        timeline.append({
            "year": horizon, "sample_n": int(len(observed)),
            "state_distribution": [
                {"state": state, "label": STATE_LABELS.get(state, state), "share": round(float(share), 4)}
                for state, share in states.items()
            ],
            "wage_change_pct": _number_distribution(pd.Series(wage_change)),
            "occupation_change_rate": round(float(occupation_changed.mean()), 4) if len(observed) else None,
            "regular_employment_rate": round(float(observed[f"employment_status_y{horizon}"].eq(1).mean()), 4) if len(observed) else None,
            "life_satisfaction_level": _number_distribution(observed[f"life_satisfaction_y{horizon}"]),
            "happiness_level": _number_distribution(observed[f"happiness_y{horizon}"]),
            "wellbeing_level": _number_distribution(observed[f"wellbeing_y{horizon}"]),
        })
    return {
        "status": "available", "scenario": choice, "trajectory_type": trajectory_type,
        "matching": {"sample_n": int(len(rows)), "people_n": int(rows.pid.nunique()),
                     "applied_conditions": applied, "relaxed_conditions": relaxed, "minimum_sample_n": 35},
        "timeline": timeline, "claim_type": "matched_observed_trajectory_not_causal_prediction",
        "caution": "비슷한 관측 경로의 대표 분포이며 개인의 확정 미래가 아닙니다.",
    }
