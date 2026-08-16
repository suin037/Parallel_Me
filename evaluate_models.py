"""모델 검증 — 홀드아웃 성능 고정 + baseline 비교 + 버전·데이터기간 기록. (로드맵 항목5)

train_models.py 와 같은 데이터·피처를 쓰되, **train/test 를 고정 분할**해
테스트셋에서만 성능을 재고 baseline 과 비교한다. "C-index 0.58 이라 강한 개인
예측으로 표현하기 어렵다"는 점을 숫자로 못박고, 겉보기(교란) 효과와 인과효과의
차이·신뢰구간을 함께 남긴다.

사용법:
    python evaluate_models.py                      # 실데이터(GOMS)
    python evaluate_models.py --synthetic          # 파이프라인 검증
    python evaluate_models.py --test-size 0.25 --seed 42
결과: backend/models/artifacts/eval_report.json (+ 콘솔 요약표)
"""
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler

from train_models import ECONML_X, FEATURE_COLS, encode_and_impute, load_data

ARTIFACTS = Path("backend/models/artifacts")
DATA_SOURCE = "GOMS2019 · YP2021 (생존모델은 KLIPS 별도)"


def git_version() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        return "nogit"


# ── L3 인과: 겉보기(교란) vs CausalForest vs LinearDML, 테스트셋 ATE+CI ──────────
def eval_causal(tr: pd.DataFrame, te: pd.DataFrame) -> dict:
    from econml.dml import CausalForestDML, LinearDML
    from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor

    Ytr, Ttr, Xtr = (tr["monthly_wage"].to_numpy(), tr["job_changed"].to_numpy(),
                     tr[ECONML_X].to_numpy())
    Xte = te[ECONML_X].to_numpy()

    # 겉보기 효과(baseline): 단순 평균차 — 교란 포함, '인과 아님'을 대비로 보여준다.
    desc = float(tr.loc[tr.job_changed == 1, "monthly_wage"].mean()
                 - tr.loc[tr.job_changed == 0, "monthly_wage"].mean())
    out = {"descriptive_diff_manwon": round(desc, 2)}

    def _mk_yt():
        return (RandomForestRegressor(n_estimators=100, min_samples_leaf=10, random_state=42),
                RandomForestClassifier(n_estimators=100, min_samples_leaf=10, random_state=42))

    my, mt = _mk_yt()
    cf = CausalForestDML(model_y=my, model_t=mt, discrete_treatment=True,
                         n_estimators=200, random_state=42).fit(Ytr, Ttr, X=Xtr)
    lb, ub = cf.ate_interval(Xte, alpha=0.05)
    out["causal_forest"] = {"ate_test_manwon": round(float(cf.ate(Xte)), 2),
                            "ci95": [round(float(lb), 2), round(float(ub), 2)]}

    my2, mt2 = _mk_yt()
    ld = LinearDML(model_y=my2, model_t=mt2, discrete_treatment=True,
                   random_state=42).fit(Ytr, Ttr, X=Xtr)
    lb2, ub2 = ld.ate_interval(Xte, alpha=0.05)
    out["linear_dml"] = {"ate_test_manwon": round(float(ld.ate(Xte)), 2),
                         "ci95": [round(float(lb2), 2), round(float(ub2), 2)],
                         "distinguishable_from_zero": not (lb2 <= 0 <= ub2)}
    return out


# ── L2 유사인물 KNN: 임금예측 MAE vs 중앙값 baseline + 이웃 유사도 ──────────────
def eval_knn(tr: pd.DataFrame, te: pd.DataFrame, k: int = 10) -> dict:
    scaler = StandardScaler().fit(tr[FEATURE_COLS])
    knn = NearestNeighbors(n_neighbors=k, metric="euclidean").fit(scaler.transform(tr[FEATURE_COLS]))
    _, idx = knn.kneighbors(scaler.transform(te[FEATURE_COLS]))
    tr_wage = tr["monthly_wage"].to_numpy()
    true = te["monthly_wage"].to_numpy()
    pred = tr_wage[idx].mean(axis=1)
    mae = float(np.abs(pred - true).mean())
    base = float(np.abs(np.median(tr_wage) - true).mean())  # baseline: 전체 중앙값 예측

    near = tr.iloc[idx.ravel()].copy()
    tgt = te.iloc[np.repeat(np.arange(len(te)), k)]
    age_gap = float(np.abs(near["age"].to_numpy() - tgt["age"].to_numpy()).mean())
    same_major = float((near["major"].astype(str).to_numpy() == tgt["major"].astype(str).to_numpy()).mean())
    return {
        "wage_mae_manwon": round(mae, 1),
        "baseline_median_mae_manwon": round(base, 1),
        "improvement_vs_baseline_pct": round((base - mae) / base * 100, 1) if base else None,
        "neighbor_age_gap_yr": round(age_gap, 2),
        "neighbor_same_major_ratio": round(same_major, 3),
    }


# ── L4 생존 CoxPH: 테스트셋 C-index vs 무작위 0.5 (데이터 없으면 정직하게 스킵) ──
def eval_survival(tr: pd.DataFrame, te: pd.DataFrame) -> dict:
    if "tenure_months" not in tr.columns or tr["tenure_months"].isna().all():
        return {"skipped": "tenure_months 없음 — 생존모델은 KLIPS 데이터 필요"}
    from lifelines import CoxPHFitter
    from lifelines.utils import concordance_index

    cols = ["tenure_months", "job_changed", "age", "sex_enc", "major_enc"]
    d_tr = tr.dropna(subset=["tenure_months"])[cols]
    d_te = te.dropna(subset=["tenure_months"])[cols]
    cox = CoxPHFitter().fit(d_tr, duration_col="tenure_months", event_col="job_changed")
    risk = cox.predict_partial_hazard(d_te)  # 위험 높을수록 짧은 생존 → 부호 반전
    c = concordance_index(d_te["tenure_months"], -risk, d_te["job_changed"])
    return {
        "c_index_test": round(float(c), 3),
        "baseline_random": 0.5,
        "n_test": int(len(d_te)),
        "reading": "0.5=무작위 · 0.6 근방=약함(강한 개인예측 부적절) · 0.7+=쓸만",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--test-size", type=float, default=0.25)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()

    df = load_data(a.synthetic)
    df, _ = encode_and_impute(df)
    tr, te = train_test_split(df, test_size=a.test_size, random_state=a.seed,
                              stratify=df["job_changed"])

    report = {
        "version": git_version(),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "data_source": ("합성데이터(파이프라인검증)" if a.synthetic else DATA_SOURCE),
        "n_total": int(len(df)), "n_train": int(len(tr)), "n_test": int(len(te)),
        "treatment_rate": round(float(df["job_changed"].mean()), 3),
        "test_size": a.test_size, "seed": a.seed,
        "features": {"knn": FEATURE_COLS, "econml_X": ECONML_X},
    }
    for name, fn in (("causal", eval_causal), ("knn", eval_knn), ("survival", eval_survival)):
        try:
            report[name] = fn(tr, te)
        except Exception as exc:  # 한 모델 실패해도 나머지는 남긴다
            report[name] = {"error": f"{type(exc).__name__}: {exc}"[:200]}

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    (ARTIFACTS / "eval_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # ── 콘솔 요약 ──
    print("=" * 64)
    print(f"모델 검증 리포트  v{report['version']}  ({report['generated_at_utc'][:19]}Z)")
    print(f"데이터: {report['data_source']}")
    print(f"표본: n_total={report['n_total']} (train {report['n_train']} / test {report['n_test']}), "
          f"이직률 {report['treatment_rate']}, seed {a.seed}")
    c = report.get("causal", {})
    if "linear_dml" in c:
        print("\n[인과 · 이직→월임금]  (겉보기≠인과 를 대비로 보여줌)")
        print(f"  겉보기 효과(단순 평균차, 교란 포함) : {c['descriptive_diff_manwon']:+} 만원")
        cf, ld = c["causal_forest"], c["linear_dml"]
        print(f"  CausalForest ATE(test)            : {cf['ate_test_manwon']:+} 만원  CI95 {cf['ci95']}")
        print(f"  LinearDML   ATE(test)             : {ld['ate_test_manwon']:+} 만원  CI95 {ld['ci95']}"
              f"  · 0과 구분={ld['distinguishable_from_zero']}")
    elif "error" in c:
        print(f"\n[인과] 실패: {c['error']}")
    k = report.get("knn", {})
    if "wage_mae_manwon" in k:
        print("\n[유사인물 KNN · L2]")
        print(f"  임금예측 MAE {k['wage_mae_manwon']} 만원  vs  baseline(중앙값) "
              f"{k['baseline_median_mae_manwon']} 만원  →  개선 {k['improvement_vs_baseline_pct']}%")
        print(f"  이웃 나이차 {k['neighbor_age_gap_yr']}세, 동일전공 비율 {k['neighbor_same_major_ratio']}")
    s = report.get("survival", {})
    if "c_index_test" in s:
        print(f"\n[생존 CoxPH · L4]  C-index(test) = {s['c_index_test']}  (무작위 0.5)")
        print(f"  → {s['reading']}")
    elif s:
        print(f"\n[생존] {s.get('skipped') or s.get('error')}")
    print("=" * 64)
    print(f"저장: {ARTIFACTS}/eval_report.json")


if __name__ == "__main__":
    main()
