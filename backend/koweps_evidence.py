"""KOWEPS 최초 사건 패널의 관측 근거 조회 서비스.

개인 예측이나 인과효과를 만들지 않고, 전처리에서 생성·감사된 집단 기술통계만 반환한다.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from config import ROOT


REPORT = ROOT / "backend" / "models" / "artifacts" / "koweps_scenario_evidence.json"
REGISTRY = ROOT / "preprocess" / "koweps_domain_registry.json"
PANEL_DIR = ROOT / "data" / "clean" / "koweps"
MIN_MATCHED_PER_SIDE = 40
TARGET_MATCHED_PER_SIDE = 250

# 선택 사건(삶의 영역) → 공통 3지표 → 실제 KOWEPS 결과변수.
# strength는 수치를 새로 만드는 가중치가 아니라 근거의 직접성을 나타낸다.
# direct: 지표를 직접 구성하는 결과, proxy: 일부 측면만 관측, unavailable: 미측정.
_COMMON = {
    "경제적안정도": ["disposable_income", "bank_deposits", "installment_savings",
                  "stocks_bonds", "financial_loan", "card_debt", "living_expenses",
                  "housing_tenure"],
    "삶의질": ["health_satisfaction", "family_satisfaction", "social_satisfaction",
              "housing_satisfaction", "leisure_satisfaction", "overall_satisfaction",
              "depressive_feeling"],
}

SCENARIO_INDICATOR_MAP = {
    "finance.savings_increase": {
        "경제적안정도": ("direct", _COMMON["경제적안정도"]),
        "성장가능성": ("unavailable", []),
        "삶의질": ("direct", _COMMON["삶의질"]),
    },
    "finance.debt_start": {
        "경제적안정도": ("direct", _COMMON["경제적안정도"]),
        "성장가능성": ("unavailable", []),
        "삶의질": ("direct", _COMMON["삶의질"]),
    },
    "lifestyle.work_hours_decrease": {
        "경제적안정도": ("direct", ["disposable_income", "living_expenses"]),
        "성장가능성": ("proxy", ["job_satisfaction"]),
        "삶의질": ("direct", ["weekly_work_hours", "leisure_satisfaction",
                             "health_satisfaction", "family_satisfaction",
                             "overall_satisfaction", "depressive_feeling"]),
    },
    "career.occupation_change": {
        "경제적안정도": ("direct", _COMMON["경제적안정도"]),
        "성장가능성": ("direct", ["job_satisfaction"]),
        "삶의질": ("direct", _COMMON["삶의질"]),
    },
    "education.level_increase": {
        "경제적안정도": ("direct", _COMMON["경제적안정도"]),
        "성장가능성": ("direct", ["job_satisfaction"]),
        "삶의질": ("direct", _COMMON["삶의질"]),
    },
    "business.self_employment_start": {
        "경제적안정도": ("direct", _COMMON["경제적안정도"]),
        "성장가능성": ("proxy", ["job_satisfaction"]),
        "삶의질": ("direct", ["job_satisfaction", "health_satisfaction",
                             "family_satisfaction", "social_satisfaction",
                             "leisure_satisfaction", "overall_satisfaction",
                             "depressive_feeling"]),
    },
    "housing.move": {
        "경제적안정도": ("direct", _COMMON["경제적안정도"]),
        "성장가능성": ("unavailable", []),
        "삶의질": ("direct", ["housing_satisfaction", "health_satisfaction",
                             "overall_satisfaction", "depressive_feeling"]),
    },
    "housing.homeownership_start": {
        "경제적안정도": ("direct", _COMMON["경제적안정도"]),
        "성장가능성": ("unavailable", []),
        "삶의질": ("direct", ["housing_satisfaction", "health_satisfaction",
                             "overall_satisfaction", "depressive_feeling"]),
    },
    "relationship.marriage_start": {
        "경제적안정도": ("direct", _COMMON["경제적안정도"]),
        "성장가능성": ("proxy", ["job_satisfaction"]),
        "삶의질": ("direct", ["family_satisfaction", "social_satisfaction",
                             "health_satisfaction", "overall_satisfaction",
                             "depressive_feeling"]),
    },
    "relationship.household_increase": {
        "경제적안정도": ("direct", _COMMON["경제적안정도"]),
        "성장가능성": ("proxy", ["job_satisfaction"]),
        "삶의질": ("direct", _COMMON["삶의질"]),
    },
    "relationship.household_decrease": {
        "경제적안정도": ("direct", _COMMON["경제적안정도"]),
        "성장가능성": ("proxy", ["job_satisfaction"]),
        "삶의질": ("direct", _COMMON["삶의질"]),
    },
}


@lru_cache(maxsize=1)
def _data() -> tuple[dict, dict]:
    return (
        json.loads(REPORT.read_text(encoding="utf-8")),
        json.loads(REGISTRY.read_text(encoding="utf-8")),
    )


@lru_cache(maxsize=16)
def _panel(scenario: str) -> pd.DataFrame | None:
    """Load the non-redistributed person-level panel used only by the local API."""
    path = PANEL_DIR / f"koweps_{scenario.replace('.', '_')}_first_event_panel.parquet"
    if not path.exists():
        return None
    try:
        return pd.read_parquet(path)
    except (ImportError, OSError, ValueError):
        return None


def _profile_features(profile: dict | None) -> list[dict]:
    """Map app profile fields to pre-event KOWEPS columns.

    Diary/personality fields are intentionally excluded: they control presentation and
    interpretation, not the statistical neighbour set or numeric outcomes.
    """
    profile = profile or {}
    features: list[dict] = []

    def add(column: str, value, label: str, categorical: bool = False, weight: float = 1.0):
        if value is not None and value != "":
            try:
                features.append({"column": column, "value": float(value), "label": label,
                                 "categorical": categorical, "weight": weight})
            except (TypeError, ValueError):
                pass

    add("age", profile.get("age"), "나이", weight=1.4)
    add("h_g3_pre", profile.get("sex"), "성별", categorical=True, weight=.8)
    add("h_g6_pre", profile.get("edu_level"), "교육수준", weight=.8)
    monthly = profile.get("monthly_wage")
    if monthly is not None:
        # KOWEPS h_din is annual disposable income (만원); monthly wage is only an
        # approximate baseline, therefore it gets a lower weight.
        add("h_din_pre", float(monthly) * 12, "현재 소득", weight=.6)
    occupation = profile.get("occupation_group")
    if occupation is not None:
        add("h_eco9_pre", occupation, "직종 대분류", categorical=True, weight=.7)
    employment = profile.get("employment_status")
    if employment is not None:
        work_type = 2 if int(employment) in {4, 5} else 1
        add("p02_1_pre", work_type, "근로유형", categorical=True, weight=.7)
    return features


def _nearest(block: pd.DataFrame, features: list[dict]) -> tuple[pd.DataFrame, list[str], list[str]]:
    usable = [f for f in features if f["column"] in block and block[f["column"]].notna().sum() >= MIN_MATCHED_PER_SIDE]
    omitted = [f["label"] for f in features if f not in usable]
    if not usable:
        return block, [], omitted

    distance = pd.Series(0.0, index=block.index)
    available_count = pd.Series(0.0, index=block.index)
    for feature in usable:
        values = pd.to_numeric(block[feature["column"]], errors="coerce")
        known = values.notna()
        if feature["categorical"]:
            component = values.ne(feature["value"]).astype(float)
        else:
            scale = float(values.std())
            if not np.isfinite(scale) or scale <= 0:
                scale = 1.0
            component = (values - feature["value"]).abs().div(scale).clip(upper=4)
        distance = distance.add(component.where(known, 0) * feature["weight"], fill_value=0)
        available_count = available_count.add(known.astype(float) * feature["weight"], fill_value=0)
    distance = distance.div(available_count.replace(0, np.nan)).fillna(np.inf)
    n = min(TARGET_MATCHED_PER_SIDE, max(MIN_MATCHED_PER_SIDE, int(len(block) * .2)))
    return block.loc[distance.nsmallest(n).index], [f["label"] for f in usable], omitted


def _personalized_report(scenario: str, profile: dict | None, registry: dict) -> dict | None:
    panel = _panel(scenario)
    features = _profile_features(profile)
    if panel is None or not features:
        return None
    groups: dict[str, pd.DataFrame] = {}
    applied: set[str] = set()
    omitted: set[str] = set()
    for treatment in (0, 1):
        matched, used, skipped = _nearest(panel.loc[panel["treatment"].eq(treatment)], features)
        if len(matched) < MIN_MATCHED_PER_SIDE:
            return None
        groups[str(treatment)] = matched
        applied.update(used)
        omitted.update(skipped)

    followup = {}
    for horizon in registry["horizons"]:
        followup[str(horizon)] = {}
        for outcome in registry["outcomes"]:
            column = f"{outcome}_t{horizon}"
            if column not in panel:
                continue
            followup[str(horizon)][outcome] = {
                group: _numeric_summary(block[column]) for group, block in groups.items()
            }
    return {
        "followup": followup,
        "matching": {
            "method": "profile_nearest_observation",
            "claim_type": "personalized_matched_observation",
            "event_sample_n": int(len(groups["1"])),
            "comparison_sample_n": int(len(groups["0"])),
            "applied_features": sorted(applied),
            "omitted_features": sorted(omitted),
            "minimum_sample_n": MIN_MATCHED_PER_SIDE,
            "score_definition": "유사 조건 집단 안에서의 결과 분포 위치이며 성공확률이나 개인 확정값이 아님",
            "diary_policy": "일기 성향은 결과 수치를 바꾸지 않고 강조 순서와 해석에만 사용",
        },
    }


def _numeric_summary(series: pd.Series) -> dict:
    values = pd.to_numeric(series, errors="coerce").dropna()
    if values.empty:
        return {"n": 0}
    return {
        "n": int(len(values)), "mean": round(float(values.mean()), 4),
        "p25": round(float(values.quantile(.25)), 4),
        "median": round(float(values.median()), 4),
        "p75": round(float(values.quantile(.75)), 4),
    }


def _scenario(text: str, domains: list[str] | None = None) -> str | None:
    value = (text or "").replace(" ", "")
    domain_set = set(domains or [])
    if any(word in value for word in ("적금늘리기", "적금증가", "저축늘리기", "저축증가")):
        return "finance.savings_increase"
    if any(word in value for word in ("대출받기", "대출발생", "대출시작", "돈빌리기")):
        return "finance.debt_start"
    if any(word in value for word in ("근로시간줄이기", "근무시간줄이기", "주4일", "시간단축", "근로시간감소")):
        return "lifestyle.work_hours_decrease"
    if any(word in value for word in ("자가", "내집", "주택구입", "집구입")):
        return "housing.homeownership_start"
    if any(word in value for word in ("이사", "이주", "거주지변경", "독립")):
        return "housing.move"
    if any(word in value for word in ("결혼", "혼인")):
        return "relationship.marriage_start"
    if any(word in value for word in ("가구원증가", "합가", "출산")):
        return "relationship.household_increase"
    if any(word in value for word in ("가구원감소", "분가")):
        return "relationship.household_decrease"
    if any(word in value for word in ("진학", "학위", "대학원", "교육수준")):
        return "education.level_increase"
    if any(word in value for word in ("창업", "자영", "개업", "사업시작", "가게차리")):
        return "business.self_employment_start"
    if any(word in value for word in ("이직", "전직", "직종변경", "진로변경")):
        return "career.occupation_change"
    # 영역만 있고 구체 사건이 없으면 잘못된 수치를 붙이지 않는다.
    return None


def _build_evidence(key: str, profile: dict | None, report: dict, registry: dict,
                    event_side: str | None = None, comparison_side: str | None = None) -> dict:
    """Build one event-vs-non-event evidence object.

    When A and B are different active events this function is called once per side,
    so each choice keeps its own comparison cohort instead of borrowing the other
    choice's cohort.
    """
    item = report.get("reports", {}).get(key)
    spec = registry.get("scenarios", {}).get(key, {})
    if not item:
        return {"available": False, "scenario": key, "reason": "해당 사건 패널이 아직 생성되지 않음"}

    personalized = _personalized_report(key, profile, registry)
    followup_source = personalized["followup"] if personalized else item["followup"]
    outcomes = []
    for outcome, meta in registry["outcomes"].items():
        trajectory = []
        for horizon in registry["horizons"]:
            cell = followup_source[str(horizon)][outcome]
            trajectory.append({
                "wave": horizon,
                "event": cell.get("1", {}),
                "comparison": cell.get("0", {}),
            })
        outcomes.append({"key": outcome, **meta, "trajectory": trajectory})

    outcome_by_key = {outcome["key"]: outcome for outcome in outcomes}
    indicator_mapping = {}
    for indicator, (strength, keys) in SCENARIO_INDICATOR_MAP.get(key, {}).items():
        selected = [outcome_by_key[name] for name in keys if name in outcome_by_key]
        indicator_mapping[indicator] = {
            "strength": strength if selected else "unavailable",
            "outcome_keys": [item["key"] for item in selected],
            "outcomes": selected,
        }

    return {
        "available": True,
        "scenario": key,
        "label": spec.get("label", item.get("label")),
        "coding_note": spec.get("coding"),
        "target_age": report.get("target_age", [25, 35]),
        "event_people": item["event_people"],
        "comparison_people": item["control_people"],
        "evidence_level": "personalized_matched_observation" if personalized else "observed_group",
        "evidence_label": "KOWEPS 유사 조건 집단 관측" if personalized else "KOWEPS 종단 관측",
        "event_side": event_side,
        "comparison_side": comparison_side,
        "claim_limit": report.get("claim_limit"),
        "outcomes": outcomes,
        "indicator_mapping": indicator_mapping,
        "personalization": personalized["matching"] if personalized else {
            "method": "population_observation",
            "claim_type": "observed_group",
            "reason": "매칭용 프로필 정보 또는 개인 패널을 사용할 수 없어 전체 집단 통계를 제공",
            "score_definition": "집단 결과 분포이며 성공확률이나 개인 확정값이 아님",
            "diary_policy": "일기 성향은 결과 수치를 바꾸지 않고 강조 순서와 해석에만 사용",
        },
    }


def evidence_for_request(payload: dict) -> dict:
    try:
        report, registry = _data()
    except (OSError, ValueError) as exc:
        return {"available": False, "reason": f"KOWEPS 산출물 로드 실패: {type(exc).__name__}"}

    side_scenarios = {
        "A": (payload.get("choice_a_context") or {}).get("event") or _scenario(" ".join(str(payload.get(k) or "") for k in
                                  ("choice_a", "choice_a_detail")),
                       payload.get("choice_a_domains") or []),
        "B": (payload.get("choice_b_context") or {}).get("event") or _scenario(" ".join(str(payload.get(k) or "") for k in
                                  ("choice_b", "choice_b_detail")),
                       payload.get("choice_b_domains") or []),
    }
    # 행동 실험처럼 패널 레지스트리에 없는 사건은 관측 예측으로 위장하지 않는다.
    known = set((registry.get("scenarios") or {}).keys())
    side_scenarios = {side: key if key in known else None for side, key in side_scenarios.items()}
    found = {side: key for side, key in side_scenarios.items() if key}
    if not found:
        return {
            "available": False,
            "reason": "KOWEPS에서 검증된 구체 사건과 연결되지 않음",
            "domains": [*(payload.get("choice_a_domains") or []), *(payload.get("choice_b_domains") or [])],
        }

    unique = set(found.values())
    if len(unique) == 1:
        key = next(iter(unique))
        event_side = next(side for side, scenario in found.items() if scenario == key)
        comparison_side = {"A": "B", "B": "A"}[event_side]
        return _build_evidence(key, payload.get("profile"), report, registry,
                               event_side, comparison_side)

    # Two active choices are not each other's valid controls. Compare each event to
    # its own non-event cohort and let the UI show the two evidence panels side by side.
    side_evidence = {
        side: _build_evidence(key, payload.get("profile"), report, registry, event_side=side)
        for side, key in found.items()
    }
    return {
        "available": True,
        "comparison_mode": "independent_events",
        "scenario": "independent_events",
        "label": "각 선택의 유사 조건 기준선 비교",
        "target_age": report.get("target_age", [25, 35]),
        "evidence_level": "independent_matched_observations",
        "evidence_label": "선택별 독립 유사 조건 관측",
        "claim_limit": report.get("claim_limit"),
        "side_scenarios": found,
        "side_evidence": side_evidence,
    }


def indicator_statuses(evidence: dict, side: str) -> dict:
    """KOWEPS 영역 사건의 결과변수 매핑을 공통 3지표 근거 계약으로 변환."""
    if not evidence.get("available"):
        return {}
    if evidence.get("comparison_mode") == "independent_events":
        return indicator_statuses((evidence.get("side_evidence") or {}).get(side, {}), side)
    role = "사건 발생군" if evidence.get("event_side") == side else "비교 유지군"
    personalized = evidence.get("evidence_level") == "personalized_matched_observation"
    labels = {"direct": "matched_observation" if personalized else "observed_group", "proxy": "proxy_observation",
              "unavailable": "insufficient_evidence"}
    result = {}
    for indicator in ("경제적안정도", "성장가능성", "삶의질"):
        mapping = (evidence.get("indicator_mapping") or {}).get(indicator, {})
        strength = mapping.get("strength", "unavailable")
        keys = mapping.get("outcome_keys", [])
        if strength == "unavailable":
            reason = f"{evidence.get('label')}에서 {indicator}를 직접 나타내는 검증 결과변수는 아직 없음"
        else:
            qualifier = "직접 결과" if strength == "direct" else "부분 대리지표"
            cohort = "유사 조건 집단" if personalized else "25~35세 전체 집단"
            reason = (f"KOWEPS {cohort} {role}의 1·3·5·10년 뒤 종단 관측 · "
                      f"{qualifier}: {', '.join(keys)}")
        result[indicator] = {
            "status": labels[strength], "score": None,
            "eligible_for_psych_rag": False, "reason": reason,
            "outcome_keys": keys,
        }
    return result
