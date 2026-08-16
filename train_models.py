"""
Layer 2~4 모델 학습 스크립트 (v3 — 매칭 피처 확장판).

v2 대비 변경:
  - KNN 매칭 피처 확장: 스펙(나이·성별·전공·임금)에
    상태·성향(직무만족, 삶의만족, 행복감, 정규직여부, 기업규모) 추가
  - EconML 이질성 변수(X)에 satis_overall 추가
    -> "현재 만족도가 낮은 사람일수록 이직 효과가 어떻게 다른가"까지 추정
  - 결측(is_regular 3.7%, firm_size 9.4%)은 중앙값 대체, 중앙값을
    encoders.pkl 에 저장해 서빙 시 입력 누락 기본값으로 재사용

사용법:
    python train_models.py                  # data/clean/goms_clean.csv (실데이터)
    python train_models.py --synthetic      # 파이프라인 검증용
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler

DATA_PATH = Path("data/clean/goms_clean.csv")
ARTIFACTS = Path("backend/models/artifacts")

RENAME = {
    "income_now": "monthly_wage",
    "changed_job": "job_changed",
    "major_cat": "major",
    "occupation_name": "job_name",
}

# 매칭 피처: 스펙 4 + 상태·성향 5
NUMERIC_FEATURES = [
    "age", "monthly_wage",
    "satis_overall", "life_satis", "happy",   # 만족도 (1-5, 1-7, 1-7)
    "is_regular", "firm_size",                # 고용형태·기업규모
]
FEATURE_COLS = ["sex_enc", "major_enc"] + NUMERIC_FEATURES
ECONML_X = ["age", "sex_enc", "major_enc", "satis_overall"]
REQUIRED = ["age", "sex", "major", "monthly_wage", "job_changed"]


# ---------------------------------------------------------------- data
def make_synthetic(n: int = 3000, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    age = rng.integers(23, 35, n)
    sex = rng.choice(["남", "여"], n)
    major = rng.choice(["공학", "인문", "사회", "자연", "예체능", "교육"], n)
    job_changed = rng.binomial(1, 0.35, n)
    base = 180 + (age - 23) * 6 + (major == "공학") * 40
    wage = base + job_changed * 20 + rng.normal(0, 30, n)
    return pd.DataFrame({
        "age": age, "sex": sex, "major": major, "job_name": major,
        "monthly_wage": wage.round(1), "job_changed": job_changed,
        "satis_overall": rng.integers(1, 6, n),
        "life_satis": rng.integers(1, 8, n),
        "happy": rng.integers(1, 8, n),
        "is_regular": rng.choice([1, 2], n, p=[0.7, 0.3]),
        "firm_size": rng.integers(1, 10, n),
        "tenure_months": rng.exponential(24, n).clip(1, 120).round(),
    })


def load_data(synthetic: bool) -> pd.DataFrame:
    if synthetic:
        print("[data] --synthetic: 합성 데이터 3000행 생성")
        return make_synthetic()
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"{DATA_PATH} 없음. sohyun 브랜치 CSV를 배치하세요.")
    df = pd.read_csv(DATA_PATH).rename(columns=RENAME)
    if "job_name" not in df.columns:
        df["job_name"] = df["major"].astype(str)

    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"필수 컬럼 누락: {missing}")

    for c in NUMERIC_FEATURES + ["job_changed"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df[df["monthly_wage"] > 0]
    df = df[df["monthly_wage"] <= df["monthly_wage"].quantile(0.995)]
    df = df.dropna(subset=REQUIRED)
    df["job_changed"] = df["job_changed"].astype(int)
    print(f"[data] 실데이터 {len(df)} rows (이직 비율 {df['job_changed'].mean():.1%})")
    return df


def encode_and_impute(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    df = df.copy()
    sex_map = {v: i for i, v in enumerate(sorted(df["sex"].astype(str).unique()))}
    major_map = {v: i for i, v in enumerate(sorted(df["major"].astype(str).unique()))}
    df["sex_enc"] = df["sex"].astype(str).map(sex_map)
    df["major_enc"] = df["major"].astype(str).map(major_map)

    medians = {}
    for c in NUMERIC_FEATURES:
        if c not in df.columns:
            df[c] = np.nan
        med = float(df[c].median())
        medians[c] = med
        df[c] = df[c].fillna(med)

    return df, {"sex_map": sex_map, "major_map": major_map,
                "medians": medians, "feature_cols": FEATURE_COLS,
                "econml_x": ECONML_X}


# ---------------------------------------------------------------- layer 2
def evaluate_knn(df: pd.DataFrame, X: np.ndarray, knn: NearestNeighbors,
                 k: int = 5, sample_n: int = 500, seed: int = 42) -> dict:
    """학습 행 자체를 제외한 이웃들이 실제로 얼마나 비슷한지 진단한다."""
    rng = np.random.default_rng(seed)
    picked = rng.choice(len(df), size=min(sample_n, len(df)), replace=False)
    _, indices = knn.kneighbors(X[picked], n_neighbors=min(k + 1, len(df)))

    age_gap, wage_gap, same_major, same_sex = [], [], [], []
    for row_idx, candidates in zip(picked, indices):
        neighbors = [i for i in candidates if i != row_idx][:k]
        if not neighbors:
            continue
        target = df.iloc[row_idx]
        near = df.iloc[neighbors]
        age_gap.append(float((near["age"] - target["age"]).abs().mean()))
        wage_gap.append(float((near["monthly_wage"] - target["monthly_wage"]).abs().mean()))
        same_major.append(float((near["major"].astype(str) == str(target["major"])).mean()))
        same_sex.append(float((near["sex"].astype(str) == str(target["sex"])).mean()))

    report = {
        "evaluated_queries": len(age_gap),
        "neighbors_per_query": k,
        "mean_age_gap_years": round(float(np.mean(age_gap)), 3),
        "mean_wage_gap_manwon": round(float(np.mean(wage_gap)), 3),
        "same_major_rate": round(float(np.mean(same_major)), 4),
        "same_sex_rate": round(float(np.mean(same_sex)), 4),
    }
    print(
        "[L2 KNN 평가] "
        f"나이차 {report['mean_age_gap_years']:.2f}세 | "
        f"임금차 {report['mean_wage_gap_manwon']:.1f}만원 | "
        f"동일전공 {report['same_major_rate']:.1%} | 동일성별 {report['same_sex_rate']:.1%}"
    )
    return report


def train_knn(df: pd.DataFrame, eval_samples: int = 500) -> dict:
    scaler = StandardScaler()
    X = scaler.fit_transform(df[FEATURE_COLS])
    knn = NearestNeighbors(n_neighbors=10, metric="euclidean").fit(X)
    print(f"[L2 KNN] fit 완료 (n={len(df)}, 피처 {len(FEATURE_COLS)}개: 스펙4 + 상태·성향5)")
    evaluation = evaluate_knn(df, X, knn, sample_n=eval_samples)
    return {
        "model": knn,
        "scaler": scaler,
        "feature_cols": FEATURE_COLS,
        "ref": df[["age", "sex", "job_name", "monthly_wage", "job_changed",
                   "satis_overall", "life_satis"]]
        .rename(columns={"job_name": "major"})
        .reset_index(drop=True),
        "evaluation": evaluation,
        "source": "GOMS",
        "trained_rows": len(df),
    }


# ---------------------------------------------------------------- layer 3
def train_econml(df: pd.DataFrame) -> dict:
    from econml.dml import CausalForestDML
    from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier

    Y = df["monthly_wage"].to_numpy()
    T = df["job_changed"].to_numpy()
    X = df[ECONML_X].to_numpy()

    est = CausalForestDML(
        model_y=RandomForestRegressor(n_estimators=100, min_samples_leaf=10, random_state=42),
        model_t=RandomForestClassifier(n_estimators=100, min_samples_leaf=10, random_state=42),
        discrete_treatment=True,
        n_estimators=200,
        random_state=42,
    )
    est.fit(Y, T, X=X)
    ate = float(est.ate(X))
    lb, ub = est.ate_interval(X, alpha=0.05)
    print(f"[L3 EconML] ATE(이직→임금) = {ate:+.2f} 만원 (95% CI {float(lb):+.2f} ~ {float(ub):+.2f})")

    # 이질성 미리보기: 현재 만족도별 CATE
    for s in (1, 3, 5):
        Xs = X.copy(); Xs[:, ECONML_X.index("satis_overall")] = s
        print(f"           만족도={s} 가정 시 CATE 평균 = {float(est.ate(Xs)):+.2f} 만원")
    return {
        "model": est,
        "x_cols": ECONML_X,
        "ate": ate,
        "ate_ci": (float(lb), float(ub)),
        "source": "GOMS 단면",
        "n": len(df),
        "treatment_rate": float(T.mean()),
    }


# ---------------------------------------------------------------- layer 4
def train_lifelines(df: pd.DataFrame) -> dict | None:
    if "tenure_months" not in df.columns or df["tenure_months"].isna().all():
        print("[L4 lifelines] tenure_months 없음 -> 스킵 (기존 artifact 유지)")
        return None
    from lifelines import KaplanMeierFitter, CoxPHFitter

    d = df.dropna(subset=["tenure_months"])
    km = KaplanMeierFitter()
    km.fit(d["tenure_months"], event_observed=d["job_changed"], label="all")
    cox = CoxPHFitter()
    cox.fit(
        d[["tenure_months", "job_changed", "age", "sex_enc", "major_enc"]],
        duration_col="tenure_months",
        event_col="job_changed",
    )
    print(f"[L4 lifelines] KM median={km.median_survival_time_:.1f}개월, CoxPH fit 완료")
    return {"km": km, "cox": cox, "cov_cols": ["age", "sex_enc", "major_enc"]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--synthetic", action="store_true")
    parser.add_argument("--eval-samples", type=int, default=500)
    args = parser.parse_args()

    df = load_data(args.synthetic)
    df, encoders = encode_and_impute(df)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)

    joblib.dump(encoders, ARTIFACTS / "encoders.pkl")
    knn_artifact = train_knn(df, eval_samples=max(1, args.eval_samples))
    econml_artifact = train_econml(df)
    joblib.dump(knn_artifact, ARTIFACTS / "knn.pkl")
    joblib.dump(econml_artifact, ARTIFACTS / "econml.pkl")
    lf = train_lifelines(df)
    if lf is not None:
        joblib.dump(lf, ARTIFACTS / "lifelines.pkl")
    report = {
        # ⚠ 이 리포트는 **이 스크립트(GOMS 단면)** 산출물만 설명한다.
        # 서빙은 연령대에 따라 econml_yp / econml_klips 를 먼저 고르므로,
        # "지금 무엇이 서빙되는가" 는 artifacts/manifest.json 을 볼 것
        # (scripts/build_artifact_manifest.py 가 생성).
        "scope": "GOMS 단면 — L2 KNN + L3 EconML (+ 가능 시 L4). 서빙 전체 명세는 manifest.json",
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "synthetic": args.synthetic,
        "rows": len(df),
        "knn": knn_artifact["evaluation"],
        "econml": {
            "ate_manwon": econml_artifact["ate"],
            "ci95_manwon": list(econml_artifact["ate_ci"]),
            "treatment_rate": econml_artifact["treatment_rate"],
            "source": econml_artifact["source"],
        },
        "lifelines_available": lf is not None,
    }
    (ARTIFACTS / "training_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[done] artifacts -> {ARTIFACTS}/")


if __name__ == "__main__":
    main()
