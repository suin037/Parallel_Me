"""검증 중인 이직 재정 모델을 서비스 응답에 안전하게 노출한다.

중요: 개인 조건 예측은 실험값이고, 시간 검증을 통과한 값은 집단 평균 방향성이다.
기존 배포 모델과 indicators 점수를 이 모듈이 자동으로 덮어쓰지 않는다.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from config import ROOT
from models.job_change_trajectory import trajectory_for_choice


ARTIFACT = ROOT / "backend" / "models" / "candidates" / "job_change_3indicators_candidate.joblib"
TEMPORAL_REPORT = ROOT / "data" / "clean" / "job_change_model_temporal_validation.json"
SENSITIVITY_REPORT = ROOT / "data" / "clean" / "job_change_financial_sensitivity.json"
TRANSITION_REPORT = ROOT / "data" / "clean" / "job_transition_matrix.json"
OBSERVED_OUTCOMES_REPORT = ROOT / "data" / "clean" / "job_change_observed_outcomes.json"
KLIPS_PANEL = ROOT / "data" / "clean" / "klips_job_change_panel.csv"
MODEL_KEY = "wage_change_pct"


@lru_cache(maxsize=1)
def _load_artifact() -> dict:
    if not ARTIFACT.exists():
        raise FileNotFoundError(ARTIFACT)
    artifact = joblib.load(ARTIFACT)
    if MODEL_KEY not in artifact.get("models", {}):
        raise RuntimeError(f"후보 artifact에 {MODEL_KEY} 모델이 없습니다")
    return artifact


@lru_cache(maxsize=1)
def _validated_population_result() -> dict | None:
    if not TEMPORAL_REPORT.exists():
        return None
    report = json.loads(TEMPORAL_REPORT.read_text(encoding="utf-8"))
    for result in report.get("results", []):
        if result.get("column") == MODEL_KEY and result.get("protocol") == "recent_year":
            return result
    return None


@lru_cache(maxsize=1)
def _sensitivity_result() -> dict | None:
    if not SENSITIVITY_REPORT.exists():
        return None
    report = json.loads(SENSITIVITY_REPORT.read_text(encoding="utf-8"))
    return report.get("summary")


@lru_cache(maxsize=1)
def _transition_report() -> dict | None:
    if not TRANSITION_REPORT.exists():
        return None
    return json.loads(TRANSITION_REPORT.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _observed_outcomes_report() -> dict | None:
    if not OBSERVED_OUTCOMES_REPORT.exists():
        return None
    return json.loads(OBSERVED_OUTCOMES_REPORT.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _personalization_panel() -> pd.DataFrame:
    """서비스 매칭에 필요한 KLIPS 열과 파생 결과만 메모리에 보관한다."""
    report = _observed_outcomes_report() or {}
    metric_columns = {item["column"] for item in report.get("metrics", [])}
    source_columns = {
        "pid", "age_t", "moved_t1", "occupation_t", "employment_status_t",
        "employment_status_t1", "real_wage_t", "real_wage_t1", "firm_size_t",
        "firm_size_t1", "tenure_t", "wage_outlier", "occupation_t1",
        "health_peer_t", "health_peer_t1", "future_optimism_t", "future_optimism_t1",
        "limit_work_t1", "limit_other_t1", *metric_columns,
    }
    header = pd.read_csv(KLIPS_PANEL, nrows=0).columns
    df = pd.read_csv(KLIPS_PANEL, usecols=[c for c in header if c in source_columns], low_memory=False)
    employed = df.employment_status_t.notna() & df.employment_status_t1.notna()
    df = df[employed & df.wage_outlier.eq(0)].copy()
    df["occupation_group_t"] = pd.to_numeric(df.occupation_t, errors="coerce").floordiv(100)
    df["occupation_changed"] = np.where(
        df.occupation_t.notna() & df.occupation_t1.notna(),
        (df.occupation_t != df.occupation_t1).astype(float), np.nan,
    )
    df["employment_improved"] = np.where(
        df.employment_status_t.isin([2, 3]), df.employment_status_t1.eq(1).astype(float), np.nan,
    )
    df["firm_size_up"] = np.where(
        df.firm_size_t.notna() & df.firm_size_t1.notna(),
        (df.firm_size_t1 > df.firm_size_t).astype(float), np.nan,
    )
    valid_wage = df.real_wage_t.gt(0) & df.real_wage_t1.gt(0)
    wage_edges = df.loc[df.real_wage_t.gt(0), "real_wage_t"].quantile([0, .2, .4, .6, .8, 1]).to_numpy()
    wage_edges = np.unique(wage_edges)
    df["wage_band_t"] = pd.cut(df.real_wage_t, wage_edges, labels=False, include_lowest=True)
    df["wage_band_t1"] = pd.cut(df.real_wage_t1, wage_edges, labels=False, include_lowest=True)
    df["wage_band_up"] = np.where(valid_wage, (df.wage_band_t1 > df.wage_band_t).astype(float), np.nan)
    df["health_peer_improvement"] = np.where(
        df.health_peer_t.notna() & df.health_peer_t1.notna(), df.health_peer_t - df.health_peer_t1, np.nan,
    )
    df["future_optimism_change"] = df.future_optimism_t1 - df.future_optimism_t
    df["work_limitation_t1"] = np.where(df.limit_work_t1.notna(), df.limit_work_t1.eq(1).astype(float), np.nan)
    df["other_limitation_t1"] = np.where(df.limit_other_t1.notna(), df.limit_other_t1.gt(0).astype(float), np.nan)
    return df


def _summary(values: pd.Series, kind: str) -> dict:
    values = pd.to_numeric(values, errors="coerce").dropna()
    if values.empty:
        return {"n": 0, "available": False}
    result = {"n": int(len(values)), "available": True}
    if kind == "rate":
        return {**result, "rate": round(float(values.mean()), 4)}
    quantiles = values.quantile([.25, .5, .75])
    return {
        **result, "mean": round(float(values.mean()), 4),
        "p25": round(float(quantiles.loc[.25]), 4), "median": round(float(quantiles.loc[.5]), 4),
        "p75": round(float(quantiles.loc[.75]), 4),
        "improved_rate": round(float(values.gt(0).mean()), 4),
        "unchanged_rate": round(float(values.eq(0).mean()), 4),
        "worsened_rate": round(float(values.lt(0).mean()), 4),
    }


def _matched_cases(profile: dict, scenario: str, minimum_n: int = 40) -> tuple[pd.DataFrame, list[str], list[str]]:
    """표본을 보존하면서 현재 상태와 일치하는 조건을 단계적으로 적용한다."""
    df = _personalization_panel()
    moved = 1 if scenario == "move" else 0
    pool = df[df.moved_t1.eq(moved)].copy()
    age = pd.to_numeric(profile.get("age"), errors="coerce")
    applied, relaxed = [], []
    if pd.notna(age):
        age_match = pool[pool.age_t.between(max(20, age - 3), min(45, age + 3))]
        if len(age_match) >= minimum_n:
            pool = age_match
            applied.append(f"나이 {int(age)-3}~{int(age)+3}세")
        else:
            relaxed.append("나이")

    occupation = profile.get("occupation_group")
    employment = profile.get("employment_status")
    wage = pd.to_numeric(profile.get("monthly_wage"), errors="coerce")
    tenure = pd.to_numeric(profile.get("tenure_years"), errors="coerce")
    firm = profile.get("firm_size")
    wage_band = None
    if pd.notna(wage):
        edges = df.loc[df.real_wage_t.gt(0), "real_wage_t"].quantile([0, .2, .4, .6, .8, 1]).to_numpy()
        wage_band = int(np.clip(np.searchsorted(edges, wage, side="right") - 1, 0, 4))
    tenure_band = None if pd.isna(tenure) else (0 if tenure < 1 else 1 if tenure < 3 else 2)
    firm_band = None if firm is None else (0 if int(firm) <= 3 else 1 if int(firm) <= 6 else 2)
    candidates = [
        ("직종", occupation, lambda x: x.occupation_group_t.eq(int(occupation))) if occupation is not None else None,
        ("고용형태", employment, lambda x: x.employment_status_t.eq(int(employment))) if employment is not None else None,
        ("임금구간", wage_band, lambda x: x.wage_band_t.eq(wage_band)) if wage_band is not None else None,
        ("근속구간", tenure_band, lambda x: ((x.tenure_t < 1) if tenure_band == 0 else (x.tenure_t.between(1, 3, inclusive="left") if tenure_band == 1 else x.tenure_t.ge(3)))) if tenure_band is not None else None,
        ("기업규모", firm_band, lambda x: ((x.firm_size_t <= 3) if firm_band == 0 else (x.firm_size_t.between(4, 6) if firm_band == 1 else x.firm_size_t.ge(7)))) if firm_band is not None else None,
    ]
    for candidate in (item for item in candidates if item is not None):
        name, _, condition = candidate
        narrowed = pool[condition(pool)]
        if len(narrowed) >= minimum_n:
            pool = narrowed
            applied.append(name)
        else:
            relaxed.append(name)
    return pool, applied, relaxed


def _observed_outcomes(choice_kind: str, profile: dict) -> dict:
    report = _observed_outcomes_report()
    if not report:
        return {"status": "unavailable"}
    scenario = "move" if choice_kind == "이직" else "stay"
    cases, applied, relaxed = _matched_cases(profile, scenario)
    domains: dict[str, list[dict]] = {}
    for metric in report.get("metrics", []):
        personalized = _summary(cases[metric["column"]], metric["kind"])
        population = metric["scenarios"][scenario]
        domains.setdefault(metric["domain"], []).append({
            "key": metric["column"], "label": metric["label"], "kind": metric["kind"],
            **personalized, "population_reference": population["all_years"],
            "direction_stable": population["direction_stable"],
        })
    return {
        "status": "available", "claim_type": report["claim_type"], "scenario": scenario,
        "domains": domains, "source": report["source"], "caution": report["caution"],
        "matching": {
            "method": "current_state_progressive_matching", "sample_n": int(len(cases)),
            "people_n": int(cases.pid.nunique()), "applied_conditions": applied,
            "relaxed_conditions": relaxed, "minimum_sample_n": 40,
        },
    }


def _observed_transitions(profile: dict, limit: int = 5) -> dict:
    """현재 직종에서 실제로 관측된 이직 도착 분포를 반환한다."""
    report = _transition_report()
    raw_code = profile.get("occupation_group")
    try:
        code = str(int(raw_code))
    except (TypeError, ValueError):
        code = ""
    origin = report.get("origins", {}).get(code) if report else None
    if not origin:
        return {
            "status": "unavailable",
            "reason": "현재 직종을 선택하면 실제 이직자의 주요 이동 직종을 볼 수 있습니다.",
        }
    return {
        "status": "available",
        "claim_type": report["claim_type"],
        "title": "비슷한 연령대 이직자들의 실제 이동 경로",
        "origin": {"code": origin["code"], "label": origin["label"]},
        "sample_n": origin["sample_n"],
        "distinct_people": origin["distinct_people"],
        "age_range": [report["population"]["age_min"], report["population"]["age_max"]],
        "destinations": origin["destinations"][:limit],
        "source": report["source"],
        "evidence_grade": "observed",
        "caution": "과거 관측 빈도이며 개인의 이동 가능성이나 이직 효과를 뜻하지 않습니다.",
    }


def _input_frame(profile: dict, model: dict) -> tuple[pd.DataFrame, list[str], list[str]]:
    """Profile을 KLIPS t시점 후보 모델 입력으로 변환한다.

    전공명은 KLIPS 직종코드와 다른 값이므로 occupation_t에 억지 매핑하지 않는다.
    종사상지위·근속기간도 현재 Profile에 정확한 입력이 없어 학습 중앙값/결측 범주를 쓴다.
    """
    mapping = {
        "age_t": profile.get("age"),
        "real_wage_t": profile.get("monthly_wage"),
        "firm_size_t": profile.get("firm_size"),
        "tenure_t": profile.get("tenure_years"),
        "sex_t": profile.get("sex"),
        "edu_t": profile.get("edu_level"),
        "employment_status_t": profile.get("employment_status"),
        "occupation_group_t": profile.get("occupation_group"),
        "jobtype_t": (
            1 if profile.get("employment_status") in {1, 2, 3}
            else 2 if profile.get("employment_status") in {4, 5}
            else None
        ),
    }
    numeric = model["numeric"]
    categorical = model["categorical"]
    row = {}
    used, imputed = [], []
    for col in numeric:
        value = mapping.get(col)
        row[col] = pd.to_numeric(value, errors="coerce")
        (used if pd.notna(row[col]) else imputed).append(col)
    for col in categorical:
        value = mapping.get(col)
        if value is None or pd.isna(value):
            row[col] = "__MISSING__"
            imputed.append(col)
        else:
            row[col] = str(value)
            used.append(col)
    return pd.DataFrame([row], columns=[*numeric, *categorical]), used, imputed


def financial_impact(profile: dict) -> dict:
    """이직 재정 영향의 검증 근거와 실험적 개인 조건 추정치를 반환한다."""
    try:
        artifact = _load_artifact()
        model = artifact["models"][MODEL_KEY]
        x, used, imputed = _input_frame(profile, model)
    except Exception as exc:
        return {
            "status": "unavailable",
            "reason": str(exc),
            "growth_potential": {"status": "insufficient_evidence"},
            "quality_of_life": {"status": "insufficient_evidence"},
        }

    validated = _validated_population_result()
    sensitivity = _sensitivity_result()
    population = None
    if validated:
        population = {
            "effect": validated["adjusted_effect_move_minus_stay"],
            "unit": "%p 실질임금 변화율",
            "ci95": validated["cluster_bootstrap_ci95"],
            "test_move_n": validated["test_move"],
            "overlap": validated["overlap_fraction"],
            "train_years": validated["train_years"],
            "test_years": validated["test_years"],
            "verdict": validated["temporal_verdict"],
        }

    return {
        "status": (
            "directional_evidence_not_deployment_approved"
            if sensitivity and sensitivity.get("decision") == "보류"
            else "supported_direction" if population else "candidate_only"
        ),
        "indicator": "경제적안정도",
        "outcome": "실질임금 변화율",
        "observed_transitions": _observed_transitions(profile),
        "population_evidence": population,
        "sensitivity_validation": sensitivity,
        "personalized_estimate": {
            "status": "disabled_insufficient_individual_validation",
            "reason": "관찰 패널로 개인별 반사실 효과를 직접 검증할 수 없어 수치 제공을 중단했습니다.",
        },
        "input_quality": {
            "used_features": used,
            "imputed_features": imputed,
            "warning": (
                "일부 입력은 학습 중앙값 또는 결측 범주로 대체되었습니다. 개인 추정치를 확정 미래로 해석하지 마세요."
                if imputed else "핵심 직업 입력을 모두 사용했습니다. 그래도 개인 추정치는 실험값입니다."
            ),
        },
        "growth_potential": {
            "status": "insufficient_evidence",
            "reason": "최근 연도 검증에서 자기발전·장래성 효과가 재현되지 않음",
        },
        "quality_of_life": {
            "status": "insufficient_evidence",
            "reason": "반복 검증에서 삶의 만족·행복·건강·웰빙 효과가 안정적이지 않음",
        },
        "message": (
            "여러 검증에서 긍정 방향은 유지됐지만 불확실성이 남아, 현재는 참고 근거로만 제공합니다."
            if sensitivity and sensitivity.get("decision") == "보류"
            else "유사 조건 집단에서 이직 후 실질임금 변화가 긍정적인 방향으로 관측됐습니다."
        ),
    }


def prediction_for_choice(choice_kind: str, profile: dict) -> dict:
    if choice_kind not in {"이직", "유지"}:
        return {
            "status": "not_applicable",
            "reason": "현재 검증된 후보는 이직과 현상 유지 비교에만 적용됩니다.",
        }
    result = financial_impact(profile)
    result["selected_scenario"] = "move" if choice_kind == "이직" else "stay"
    result["observed_outcomes"] = _observed_outcomes(choice_kind, profile)
    result["parallel_trajectory"] = trajectory_for_choice(choice_kind, profile)
    return result
