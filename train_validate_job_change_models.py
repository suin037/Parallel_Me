"""이직 3지표 후보 모델을 학습하고 개인 단위 홀드아웃에서 검증한다.

배포 artifact는 변경하지 않는다. KLIPS(재정·삶의 질)와 YP(성장)를 각각
개인 단위로 train/test 분리한 뒤 propensity + outcome 모델로 AIPW 보정 효과를
계산하고, overlap·예측 성능·cluster bootstrap 구간을 보고한다.
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import (
    brier_score_loss,
    mean_absolute_error,
    r2_score,
    roc_auc_score,
)
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from evaluate_job_change_indicators import build_yp_growth_panel


ROOT = Path(__file__).resolve().parent
CLEAN = ROOT / "data" / "clean"
CANDIDATES = ROOT / "backend" / "models" / "candidates"
REPORT_JSON = CLEAN / "job_change_model_validation.json"
REPORT_MD = ROOT / "docs" / "JOB_CHANGE_MODEL_VALIDATION.md"
ARTIFACT = CANDIDATES / "job_change_3indicators_candidate.joblib"
SEED = 42


DATASETS = {
    "klips": {
        "path": CLEAN / "klips_job_change_panel.csv",
        "numeric": ["age_t", "real_wage_t", "firm_size_t", "tenure_t"],
        "categorical": ["sex_t", "edu_t", "employment_status_t", "occupation_group_t", "jobtype_t"],
    },
    "yp": {
        "numeric": ["age_t", "income_t", "growth_t", "future_t", "work_t", "stability_t"],
        "categorical": ["sex_t", "edu_t", "firm_size_t", "emp_status_t"],
    },
}

METRICS = [
    {"dataset": "klips", "indicator": "financial_stability", "column": "wage_change_pct", "label": "실질임금 변화율", "kind": "continuous", "baseline": "real_wage_t"},
    {"dataset": "klips", "indicator": "financial_stability", "column": "wage_down_t1", "label": "소득 감소 확률", "kind": "binary", "baseline": "real_wage_t"},
    {"dataset": "yp", "indicator": "growth_potential", "column": "growth_change", "label": "자기발전 만족도 변화", "kind": "continuous", "baseline": "growth_t"},
    {"dataset": "yp", "indicator": "growth_potential", "column": "future_change", "label": "장래성 만족도 변화", "kind": "continuous", "baseline": "future_t"},
    {"dataset": "yp", "indicator": "growth_potential", "column": "work_change", "label": "직무 만족도 변화", "kind": "continuous", "baseline": "work_t"},
    {"dataset": "klips", "indicator": "quality_of_life", "column": "life_satisfaction_change", "label": "삶의 만족도 변화", "kind": "continuous", "baseline": "life_satisfaction_t"},
    {"dataset": "klips", "indicator": "quality_of_life", "column": "happiness_change", "label": "행복도 변화", "kind": "continuous", "baseline": "happiness_t"},
    {"dataset": "klips", "indicator": "quality_of_life", "column": "health_score_change", "label": "건강점수 변화", "kind": "continuous", "baseline": "health_score_t"},
    {"dataset": "klips", "indicator": "quality_of_life", "column": "wellbeing_index_change", "label": "웰빙지수 변화", "kind": "continuous", "baseline": "wellbeing_index_t"},
]


ACTIVE_METRICS = [
    metric for metric in METRICS
    if metric["column"] in {"wage_change_pct", "wage_down_t1"}
] + [
    {"dataset": "klips", "indicator": "quality_of_life", "column": column,
     "label": label, "kind": "continuous", "baseline": column.replace("_change", "_t")}
    for column, label in {
        "satisfaction_overall_change": "전반적 만족 변화",
        "satisfaction_family_income_change": "가족수입 만족 변화",
        "satisfaction_leisure_change": "여가 만족 변화",
        "satisfaction_housing_change": "주거 만족 변화",
        "satisfaction_family_relationship_change": "가족관계 만족 변화",
        "satisfaction_kin_relationship_change": "친인척관계 만족 변화",
        "satisfaction_social_relationship_change": "사회적 친분 만족 변화",
    }.items()
]

MODEL_SCOPE = {"age_min": 25, "age_max": 35, "treatment": "job_to_job"}

for _metric in ACTIVE_METRICS:
    _metric["favorable_direction"] = (
        "negative" if _metric["column"] == "wage_down_t1" else "positive"
    )


def split_people(df: pd.DataFrame, test_size: float = 0.25, seed: int = SEED) -> tuple[pd.DataFrame, pd.DataFrame]:
    """동일 pid가 양쪽에 섞이지 않는 재현 가능한 분리."""
    splitter = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=seed)
    train_idx, test_idx = next(splitter.split(df, groups=df["pid"]))
    train, test = df.iloc[train_idx].copy(), df.iloc[test_idx].copy()
    if set(train.pid).intersection(test.pid):
        raise AssertionError("개인 단위 분리 실패: train/test pid 중복")
    return train, test


def _prepare_frame(df: pd.DataFrame, numeric: list[str], categorical: list[str]) -> pd.DataFrame:
    out = df[[*numeric, *categorical]].copy()
    for col in numeric:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    for col in categorical:
        out[col] = out[col].astype("string").fillna("__MISSING__")
    return out


def make_preprocessor(numeric: list[str], categorical: list[str]) -> ColumnTransformer:
    return ColumnTransformer([
        ("num", Pipeline([
            ("impute", SimpleImputer(strategy="median", add_indicator=True)),
            ("scale", StandardScaler()),
        ]), numeric),
        ("cat", Pipeline([
            ("impute", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore", min_frequency=5)),
        ]), categorical),
    ])


def _outcome_model(kind: str, preprocessor: ColumnTransformer) -> Pipeline:
    estimator = (
        LogisticRegression(max_iter=1200, class_weight="balanced", random_state=SEED)
        if kind == "binary" else Ridge(alpha=5.0)
    )
    return Pipeline([("pre", clone(preprocessor)), ("model", estimator)])


def _predict_outcome(model: Pipeline, x: pd.DataFrame, kind: str) -> np.ndarray:
    if kind == "binary":
        return model.predict_proba(x)[:, 1]
    return model.predict(x)


def _cluster_ci(pseudo: np.ndarray, pid: np.ndarray, iterations: int = 500) -> list[float]:
    work = pd.DataFrame({"pid": pid, "pseudo": pseudo})
    clusters = work.groupby("pid", sort=False).pseudo.agg(["sum", "count"])
    sums = clusters["sum"].to_numpy()
    counts = clusters["count"].to_numpy()
    rng = np.random.default_rng(SEED)
    draws = []
    for _ in range(iterations):
        sampled = rng.integers(0, len(clusters), size=len(clusters))
        draws.append(float(sums[sampled].sum() / counts[sampled].sum()))
    return [round(float(v), 4) for v in np.percentile(draws, [2.5, 97.5])]


def fit_metric(train: pd.DataFrame, test: pd.DataFrame, spec: dict, base_features: dict) -> tuple[dict, dict]:
    outcome = spec["column"]
    numeric = list(dict.fromkeys([*base_features["numeric"], spec["baseline"]]))
    categorical = base_features["categorical"]
    required = ["pid", "moved_t1", outcome, *numeric, *categorical]
    train = train[[c for c in required if c in train]].dropna(subset=[outcome, "moved_t1"])
    test = test[[c for c in required if c in test]].dropna(subset=[outcome, "moved_t1"])
    numeric = [c for c in numeric if c in train]
    categorical = [c for c in categorical if c in train]
    features = [*numeric, *categorical]

    x_train = _prepare_frame(train, numeric, categorical)
    x_test = _prepare_frame(test, numeric, categorical)
    t_train = train.moved_t1.astype(int).to_numpy()
    t_test = test.moved_t1.astype(int).to_numpy()
    y_train = train[outcome].astype(float).to_numpy()
    y_test = test[outcome].astype(float).to_numpy()

    pre = make_preprocessor(numeric, categorical)
    propensity = Pipeline([
        ("pre", clone(pre)),
        ("model", LogisticRegression(max_iter=1200, class_weight="balanced", random_state=SEED)),
    ]).fit(x_train, t_train)
    outcome0 = _outcome_model(spec["kind"], pre).fit(x_train.iloc[t_train == 0], y_train[t_train == 0])
    outcome1 = _outcome_model(spec["kind"], pre).fit(x_train.iloc[t_train == 1], y_train[t_train == 1])

    raw_p = propensity.predict_proba(x_test)[:, 1]
    p = np.clip(raw_p, 0.05, 0.95)
    mu0 = _predict_outcome(outcome0, x_test, spec["kind"])
    mu1 = _predict_outcome(outcome1, x_test, spec["kind"])
    pseudo = mu1 - mu0 + t_test * (y_test - mu1) / p - (1 - t_test) * (y_test - mu0) / (1 - p)
    ate = float(np.mean(pseudo))

    lower = max(np.quantile(raw_p[t_test == 0], 0.01), np.quantile(raw_p[t_test == 1], 0.01))
    upper = min(np.quantile(raw_p[t_test == 0], 0.99), np.quantile(raw_p[t_test == 1], 0.99))
    overlap_fraction = float(np.mean((raw_p >= lower) & (raw_p <= upper))) if lower < upper else 0.0
    ci = _cluster_ci(pseudo, test.pid.to_numpy())

    observed_pred = np.where(t_test == 1, mu1, mu0)
    if spec["kind"] == "binary":
        predictive = {
            "roc_auc": round(float(roc_auc_score(y_test, observed_pred)), 4),
            "brier": round(float(brier_score_loss(y_test, observed_pred)), 4),
        }
    else:
        predictive = {
            "mae": round(float(mean_absolute_error(y_test, observed_pred)), 4),
            "r2": round(float(r2_score(y_test, observed_pred)), 4),
        }

    report = {
        **{k: spec[k] for k in ("dataset", "indicator", "column", "label", "kind")},
        "favorable_direction": spec.get("favorable_direction", "positive"),
        "features": features,
        "train_rows": int(len(train)), "test_rows": int(len(test)),
        "train_people": int(train.pid.nunique()), "test_people": int(test.pid.nunique()),
        "test_stay": int((t_test == 0).sum()), "test_move": int((t_test == 1).sum()),
        "propensity_auc": round(float(roc_auc_score(t_test, raw_p)), 4),
        "propensity_range": [round(float(raw_p.min()), 4), round(float(raw_p.max()), 4)],
        "common_support_01_99": [round(float(lower), 4), round(float(upper), 4)],
        "overlap_fraction": round(overlap_fraction, 4),
        "adjusted_effect_move_minus_stay": round(ate, 4),
        "cluster_bootstrap_ci95": ci,
        "direction_supported": bool(ci[0] > 0 or ci[1] < 0),
        "predictive_test": predictive,
        "gate": (
            "evidence_candidate"
            if len(test[t_test == 1]) >= 200 and overlap_fraction >= 0.8
            and (ci[0] > 0 or ci[1] < 0)
            else "insufficient_evidence"
        ),
        "causal_claim": False,
    }
    artifact = {
        "spec": spec, "features": features, "numeric": numeric, "categorical": categorical,
        "propensity": propensity, "outcome_stay": outcome0, "outcome_move": outcome1,
    }
    return report, artifact


def load_datasets() -> dict[str, pd.DataFrame]:
    klips = pd.read_csv(DATASETS["klips"]["path"], low_memory=False)
    klips = klips[klips.wage_outlier.eq(0)].copy()
    employed_both = klips["employment_status_t"].notna() & klips["employment_status_t1"].notna()
    klips = klips[
        employed_both & klips["age_t"].between(MODEL_SCOPE["age_min"], MODEL_SCOPE["age_max"])
    ].copy()
    klips["transition_type"] = np.where(klips["moved_t1"].eq(1), "job_to_job", "same_job")
    # 서비스에서는 이해 가능한 KSCO 대분류(1~9)를 받으므로 학습도 3자리 소분류 대신 대분류로 통일한다.
    klips["occupation_group_t"] = (pd.to_numeric(klips["occupation_t"], errors="coerce") // 100)
    klips.loc[~klips["occupation_group_t"].between(1, 9), "occupation_group_t"] = np.nan
    yp = build_yp_growth_panel()
    return {"klips": klips, "yp": yp}


def train_and_validate() -> tuple[dict, dict]:
    frames = load_datasets()
    splits = {name: split_people(df) for name, df in frames.items()}
    metric_reports, artifacts = [], {}
    for spec in ACTIVE_METRICS:
        train, test = splits[spec["dataset"]]
        report, artifact = fit_metric(train, test, spec, DATASETS[spec["dataset"]])
        metric_reports.append(report)
        artifacts[spec["column"]] = artifact
    split_report = {
        name: {
            "train_rows": int(len(parts[0])), "test_rows": int(len(parts[1])),
            "train_people": int(parts[0].pid.nunique()), "test_people": int(parts[1].pid.nunique()),
            "pid_overlap": int(len(set(parts[0].pid).intersection(parts[1].pid))),
        }
        for name, parts in splits.items()
    }
    report = {
        "method": "개인 단위 75/25 홀드아웃 + logistic propensity + 처치별 outcome model + AIPW",
        "scope": "20~45세 관측 패널; 관측자료 보정 추정이며 무작위실험 인과효과가 아님",
        "splits": split_report,
        "metrics": metric_reports,
        "deployment_ready": False,
        "next_gate": [
            "연도 기준 외부 검증 또는 반복 교차검증",
            "민감도 분석과 모델 사양 비교",
            "공식 코드북으로 척도 방향 재확인",
            "승인된 지표만 서비스 점수 및 API에 연결",
        ],
    }
    return report, artifacts


def render_markdown(report: dict) -> str:
    title = {"financial_stability": "재정 안정도", "growth_potential": "성장 가능성", "quality_of_life": "삶의 질"}
    lines = [
        "# 이직 3지표 후보 모델 검증", "", f"> {report['scope']}", "",
        "## 방법", "", report["method"], "", "## 개인 단위 분리", "",
        "| 데이터 | 학습 인원 | 테스트 인원 | 중복 인원 |", "|---|---:|---:|---:|",
    ]
    for name, split in report["splits"].items():
        lines.append(f"| {name.upper()} | {split['train_people']:,} | {split['test_people']:,} | {split['pid_overlap']} |")
    lines += ["", "## 홀드아웃 결과", "", "| 지표 | 결과변수 | 테스트 이직 n | overlap | 보정 효과 | 95% CI | 방향 지지 | 게이트 |", "|---|---|---:|---:|---:|---|---|---|"]
    for m in report["metrics"]:
        ci = m["cluster_bootstrap_ci95"]
        lines.append(
            f"| {title[m['indicator']]} | {m['label']} | {m['test_move']:,} | {m['overlap_fraction']:.1%} | "
            f"{m['adjusted_effect_move_minus_stay']:+.4f} | {ci[0]:+.4f} ~ {ci[1]:+.4f} | "
            f"{'예' if m['direction_supported'] else '아니오'} | {m['gate']} |"
        )
    lines += [
        "", "## 해석 제한", "",
        "- 보정 효과는 관측된 혼재변수에 조건부인 추정치이며 무작위실험의 인과효과가 아니다.",
        "- 후보 통과는 표본과 overlap 기준이며 즉시 배포 가능하다는 뜻이 아니다.",
        "- 예측 성능이 낮은 결과는 방향성이 있더라도 개인별 수치 예측에 사용하면 안 된다.",
        "", "## 다음 게이트", "",
    ]
    lines += [f"{i}. {item}" for i, item in enumerate(report["next_gate"], 1)]
    return "\n".join(lines) + "\n"


def main() -> None:
    report, artifacts = train_and_validate()
    CLEAN.mkdir(parents=True, exist_ok=True)
    CANDIDATES.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_MD.write_text(render_markdown(report), encoding="utf-8")
    joblib.dump({"version": 1, "report": report, "models": artifacts}, ARTIFACT, compress=3)
    print(f"[완료] {REPORT_JSON}")
    print(f"[완료] {REPORT_MD}")
    print(f"[후보 artifact] {ARTIFACT}")
    for metric in report["metrics"]:
        print(f"[{metric['indicator']}] {metric['label']}: {metric['adjusted_effect_move_minus_stay']:+.4f} {metric['cluster_bootstrap_ci95']} / {metric['gate']}")


if __name__ == "__main__":
    main()
