"""이직 실질임금 효과의 선형/비선형 모델 민감도 검증."""

from __future__ import annotations

import json

import numpy as np
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, r2_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder

from robustness_validate_job_change_models import SEEDS
from temporal_validate_job_change_models import temporal_split
from train_validate_job_change_models import (
    DATASETS,
    METRICS,
    ROOT,
    _cluster_ci,
    _prepare_frame,
    fit_metric,
    load_datasets,
    split_people,
)


REPORT_JSON = ROOT / "data" / "clean" / "job_change_financial_sensitivity.json"
REPORT_MD = ROOT / "docs" / "JOB_CHANGE_FINANCIAL_SENSITIVITY.md"
WAGE_SPEC = next(item for item in METRICS if item["column"] == "wage_change_pct")


def nonlinear_preprocessor(numeric: list[str], categorical: list[str]) -> ColumnTransformer:
    return ColumnTransformer([
        ("num", SimpleImputer(strategy="median", add_indicator=True), numeric),
        ("cat", Pipeline([
            ("impute", SimpleImputer(strategy="most_frequent")),
            ("ordinal", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)),
        ]), categorical),
    ], sparse_threshold=0.0)


def fit_nonlinear(train, test) -> dict:
    spec = WAGE_SPEC
    base = DATASETS["klips"]
    outcome = spec["column"]
    numeric = list(dict.fromkeys([*base["numeric"], spec["baseline"]]))
    categorical = base["categorical"]
    required = ["pid", "moved_t1", outcome, *numeric, *categorical]
    train = train[required].dropna(subset=[outcome, "moved_t1"])
    test = test[required].dropna(subset=[outcome, "moved_t1"])
    x_train = _prepare_frame(train, numeric, categorical)
    x_test = _prepare_frame(test, numeric, categorical)
    t_train = train.moved_t1.astype(int).to_numpy()
    t_test = test.moved_t1.astype(int).to_numpy()
    y_train = train[outcome].astype(float).to_numpy()
    y_test = test[outcome].astype(float).to_numpy()
    pre = nonlinear_preprocessor(numeric, categorical)

    propensity = Pipeline([
        ("pre", clone(pre)),
        ("model", HistGradientBoostingClassifier(
            max_iter=150, max_leaf_nodes=15, min_samples_leaf=50,
            learning_rate=0.05, l2_regularization=1.0, random_state=42,
        )),
    ]).fit(x_train, t_train)
    outcome0 = Pipeline([
        ("pre", clone(pre)),
        ("model", HistGradientBoostingRegressor(
            max_iter=150, max_leaf_nodes=15, min_samples_leaf=50,
            learning_rate=0.05, l2_regularization=2.0, random_state=42,
        )),
    ]).fit(x_train.iloc[t_train == 0], y_train[t_train == 0])
    outcome1 = clone(outcome0).fit(x_train.iloc[t_train == 1], y_train[t_train == 1])

    raw_p = propensity.predict_proba(x_test)[:, 1]
    p = np.clip(raw_p, 0.05, 0.95)
    mu0, mu1 = outcome0.predict(x_test), outcome1.predict(x_test)
    pseudo = mu1 - mu0 + t_test * (y_test - mu1) / p - (1 - t_test) * (y_test - mu0) / (1 - p)
    lower = max(np.quantile(raw_p[t_test == 0], 0.01), np.quantile(raw_p[t_test == 1], 0.01))
    upper = min(np.quantile(raw_p[t_test == 0], 0.99), np.quantile(raw_p[t_test == 1], 0.99))
    observed = np.where(t_test == 1, mu1, mu0)
    ci = _cluster_ci(pseudo, test.pid.to_numpy())
    return {
        "effect": round(float(pseudo.mean()), 4),
        "ci95": ci,
        "positive_supported": bool(ci[0] > 0),
        "overlap": round(float(np.mean((raw_p >= lower) & (raw_p <= upper))), 4) if lower < upper else 0.0,
        "propensity_auc": round(float(roc_auc_score(t_test, raw_p)), 4),
        "test_rows": int(len(test)), "test_move": int(t_test.sum()),
        "predictive_test": {
            "mae": round(float(mean_absolute_error(y_test, observed)), 4),
            "r2": round(float(r2_score(y_test, observed)), 4),
        },
    }


def _compact_linear(metric: dict) -> dict:
    return {
        "effect": metric["adjusted_effect_move_minus_stay"],
        "ci95": metric["cluster_bootstrap_ci95"],
        "positive_supported": bool(metric["cluster_bootstrap_ci95"][0] > 0),
        "overlap": metric["overlap_fraction"],
        "propensity_auc": metric["propensity_auc"],
        "test_rows": metric["test_rows"], "test_move": metric["test_move"],
        "predictive_test": metric["predictive_test"],
    }


def compare_protocol(train, test, protocol: str) -> dict:
    linear, _ = fit_metric(train, test, WAGE_SPEC, DATASETS["klips"])
    nonlinear = fit_nonlinear(train, test)
    linear = _compact_linear(linear)
    same_direction = np.sign(linear["effect"]) == np.sign(nonlinear["effect"])
    both_supported = linear["positive_supported"] and nonlinear["positive_supported"]
    return {
        "protocol": protocol,
        "linear": linear,
        "nonlinear": nonlinear,
        "same_direction": bool(same_direction),
        "both_positive_supported": bool(both_supported),
    }


def run_sensitivity() -> dict:
    frame = load_datasets()["klips"]
    protocols = []
    for seed in SEEDS:
        train, test = split_people(frame, seed=seed)
        protocols.append(compare_protocol(train, test, f"person_split_seed_{seed}"))
    train, test = temporal_split(frame, 2021)
    protocols.append(compare_protocol(train, test, "recent_year_2022_2023"))
    strict_train, strict_test = temporal_split(frame, 2021, strict_people=True)
    protocols.append(compare_protocol(strict_train, strict_test, "recent_year_new_people"))

    same_rate = float(np.mean([p["same_direction"] for p in protocols]))
    support_rate = float(np.mean([p["both_positive_supported"] for p in protocols]))
    min_overlap = float(min(min(p["linear"]["overlap"], p["nonlinear"]["overlap"]) for p in protocols))
    approved = same_rate == 1.0 and support_rate >= 0.7 and min_overlap >= 0.8
    return {
        "method": "동일 분할에서 선형 AIPW와 HistGradientBoosting AIPW 비교",
        "protocols": protocols,
        "summary": {
            "same_direction_rate": round(same_rate, 4),
            "both_positive_supported_rate": round(support_rate, 4),
            "minimum_overlap": round(min_overlap, 4),
            "decision": "제한적 승인" if approved else "보류",
        },
        "usage_if_approved": "집단 방향성 근거로만 사용; 개인별 정확한 상승률 보장 금지",
    }


def render_markdown(report: dict) -> str:
    lines = [
        "# 이직 재정 모델 민감도 검증", "", f"> {report['method']}", "",
        "| 검증 | 선형 효과 (95% CI) | 비선형 효과 (95% CI) | 같은 방향 | 둘 다 양의 구간 |",
        "|---|---|---|---|---|",
    ]
    for p in report["protocols"]:
        l, n = p["linear"], p["nonlinear"]
        lines.append(
            f"| {p['protocol']} | {l['effect']:+.3f} ({l['ci95'][0]:+.3f}~{l['ci95'][1]:+.3f}) | "
            f"{n['effect']:+.3f} ({n['ci95'][0]:+.3f}~{n['ci95'][1]:+.3f}) | "
            f"{'예' if p['same_direction'] else '아니오'} | {'예' if p['both_positive_supported'] else '아니오'} |"
        )
    s = report["summary"]
    lines += [
        "", "## 판정", "",
        f"- 동일 방향: {s['same_direction_rate']:.0%}",
        f"- 두 모델 모두 양의 신뢰구간: {s['both_positive_supported_rate']:.0%}",
        f"- 최소 overlap: {s['minimum_overlap']:.1%}",
        f"- 최종 판정: **{s['decision']}**", "",
        f"> {report['usage_if_approved']}",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    report = run_sensitivity()
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_MD.write_text(render_markdown(report), encoding="utf-8")
    print(f"[완료] {REPORT_JSON}")
    print(f"[완료] {REPORT_MD}")
    print(json.dumps(report["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
