"""
YP2021(청년패널) 종단 데이터 학습 스크립트 (시뮬레이션 모델 고도화).

klips_train.py 와 동일한 (t, t+1) 전이 구조를 쓰되, 데이터가 청년(19~31세)이라
서비스 타겟(25~35)에 더 적합한 L3/L4 산출물을 만든다.

Layer 3: 이직 -> 익년 소득 인과효과.
          이전 소득·기업규모·종사지위·직종을 혼재변수(W)로 통제한 종단 인과추론.
Layer 4: 일자리 spell 생존분석 (실데이터 근속 -> N년 후 이직 확률).

입력 (preprocess_yp.py 산출물, data/clean/ 에 배치):
    yp_clean.csv    사람×웨이브 long 패널 (person_id, wave, age, sex, edu_level,
                    firm_size, emp_status, occupation_raw, income_now, changed_job ...)
    yp_spells.csv   일자리 spell (duration_months, event, 공변량)

출력 (서빙에서 청년(≤31세)에 우선 사용):
    backend/models/artifacts/econml_yp.pkl
    backend/models/artifacts/lifelines_yp.pkl

사용법:
    python train_yp.py
"""

from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd

CLEAN_DIR = Path("data/clean")
ARTIFACTS = Path("backend/models/artifacts")

# YP 표본은 19~31세. 타겟(25~35)보다 약간 넓게 잡아 표본 확보(데이터 밖은 자동 무효).
AGE_MIN, AGE_MAX = 19, 34

# L2 매칭 피처: GOMS 와 요청이 공유하는 항목만 (YP 엔 전공 major 가 없어 제외)
YP_KNN_FEATURES = ["sex", "age", "monthly_wage", "satis_overall", "firm_size"]


# ---------------------------------------------------------------- L3
def build_causal_panel() -> pd.DataFrame:
    """연속 관측 (t, t+1) 쌍 -> 인과추론용 행.

    T = t+1 이직 여부, Y = t+1 월소득(만원)
    W(혼재변수) = t 시점 소득·기업규모·종사지위·직종
    X(이질성)   = 나이·성별·학력
    """
    p = pd.read_csv(CLEAN_DIR / "yp_clean.csv")
    p = p[["person_id", "wave", "year", "age", "sex", "edu_level",
           "firm_size", "emp_status", "occupation_raw",
           "income_now", "changed_job"]].copy()
    p = p.dropna(subset=["income_now"])
    p = p[p["income_now"] > 0]
    p = p.sort_values(["person_id", "wave"])

    nxt = p.groupby("person_id").shift(-1)
    d = pd.DataFrame({
        "pid": p["person_id"],
        "age": p["age"],
        "sex": p["sex"],                     # 1=남 2=여 (GOMS·KLIPS 와 동일 코딩)
        "edu": p["edu_level"],
        "firm_size": p["firm_size"],
        "emp_status": p["emp_status"],
        "occ": p["occupation_raw"],
        "wage_now": p["income_now"],
        "wage_next": nxt["income_now"],
        "T_move": nxt["changed_job"],
        "wave_gap": nxt["wave"] - p["wave"],
    })
    d = d[d["wave_gap"] == 1]                 # 연속 파동만
    d = d.dropna(subset=["wage_next", "T_move", "age", "sex", "edu", "wage_now"])
    d = d[d["age"].between(AGE_MIN, AGE_MAX)]
    d["T_move"] = d["T_move"].astype(int)
    d["occ"] = d["occ"].fillna(0)
    d["emp_status"] = d["emp_status"].fillna(d["emp_status"].median())
    d["firm_size"] = d["firm_size"].fillna(d["firm_size"].median())
    print(f"[L3 panel] {len(d):,} 개 (사람-연도 전이쌍), 이직 비율 {d['T_move'].mean():.1%}")
    return d


def train_econml_yp(d: pd.DataFrame) -> dict:
    from econml.dml import CausalForestDML, LinearDML
    from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier

    X_COLS = ["age", "sex", "edu"]
    W_COLS = ["wage_now", "firm_size", "emp_status", "occ"]

    Y = d["wage_next"].to_numpy()
    T = d["T_move"].to_numpy()
    X = d[X_COLS].to_numpy()
    W = d[W_COLS].to_numpy()

    est = CausalForestDML(
        model_y=RandomForestRegressor(n_estimators=150, min_samples_leaf=20),
        model_t=RandomForestClassifier(n_estimators=150, min_samples_leaf=20),
        discrete_treatment=True,
        n_estimators=300,
        random_state=42,
    )
    est.fit(Y, T, X=X, W=W)
    ate = float(est.ate(X))
    lb, ub = (float(v) for v in est.ate_interval(X, alpha=0.05))
    mean_wage = float(d["wage_now"].mean())
    print(f"[L3 YP] ATE(이직→익년소득) = {ate:+.2f} 만원 "
          f"(95% CI {lb:+.2f} ~ {ub:+.2f}) | 평균소득 대비 {ate / mean_wage:+.1%}")

    # 비교용 LinearDML - 해석 가능한 분석적 신뢰구간
    lin = LinearDML(
        model_y=RandomForestRegressor(n_estimators=150, min_samples_leaf=20),
        model_t=RandomForestClassifier(n_estimators=150, min_samples_leaf=20),
        discrete_treatment=True, random_state=42,
    )
    lin.fit(Y, T, X=X, W=W)
    lin_ate = float(lin.ate(X))
    llb, lub = (float(v) for v in lin.ate_interval(X, alpha=0.05))
    print(f"[L3 YP/LinearDML] ATE = {lin_ate:+.2f} 만원 (95% CI {llb:+.2f} ~ {lub:+.2f})")

    medians = {c: float(d[c].median()) for c in X_COLS}
    return {"model": est, "x_cols": X_COLS, "medians": medians,
            "ate": ate, "ate_ci": (lb, ub),
            "linear_ate": lin_ate, "linear_ci": (llb, lub),
            "source": "YP2021 청년패널 종단"}


# ---------------------------------------------------------------- L4
def _cv_concordance(df, cov_cols, dur="duration_months", ev="event", k=5, seed=42):
    """5-fold 교차검증 C-index → (학습평균, 테스트평균, 테스트표준편차, 갭)."""
    from lifelines import CoxPHFitter

    d = df[cov_cols + [dur, ev]].dropna()
    d = d.sample(frac=1, random_state=seed).reset_index(drop=True)
    folds = np.array_split(np.arange(len(d)), k)
    tr, te = [], []
    for i in range(k):
        te_idx = folds[i]
        tr_idx = np.concatenate([folds[j] for j in range(k) if j != i])
        m = CoxPHFitter().fit(d.iloc[tr_idx], dur, ev)
        tr.append(float(m.score(d.iloc[tr_idx], scoring_method="concordance_index")))
        te.append(float(m.score(d.iloc[te_idx], scoring_method="concordance_index")))
    return (float(np.mean(tr)), float(np.mean(te)), float(np.std(te)),
            float(np.mean(tr) - np.mean(te)))


def train_lifelines_yp() -> dict:
    from lifelines import KaplanMeierFitter, CoxPHFitter

    s = pd.read_csv(CLEAN_DIR / "yp_spells.csv")
    s = s.rename(columns={"edu_level": "edu"})
    s = s.dropna(subset=["duration_months", "event", "age", "sex", "edu"])
    s = s[s["age"].between(AGE_MIN, AGE_MAX)]
    s["duration_months"] = s["duration_months"].clip(lower=0.5)
    print(f"[L4 panel] 스펠 {len(s):,}개 (이직 이벤트 {int(s['event'].sum()):,}건, "
          f"{s['event'].mean():.1%})")

    km = KaplanMeierFitter()
    km.fit(s["duration_months"], event_observed=s["event"], label="all")

    cov_cols = ["age", "sex", "edu"]
    cox = CoxPHFitter()
    cox.fit(s[["duration_months", "event"] + cov_cols],
            duration_col="duration_months", event_col="event")

    # 예측력 검증: 5-fold 교차검증 C-index
    cv = _cv_concordance(s, cov_cols)
    stable = "✓안정" if cv[3] < 0.05 else "⚠과적합 의심"
    print(f"[L4 YP/CV] 5-fold C-index 학습 {cv[0]:.3f} / 테스트 {cv[1]:.3f}±{cv[2]:.3f} "
          f"| 갭 {cv[3]:.3f} {stable}")

    # 서비스 멘트용: N년 시점 이직(이탈) 누적확률 (YP는 4웨이브라 관측 범위 내만 유효)
    surv = km.survival_function_
    idx = np.asarray(surv.index, dtype=float)
    for yr in (1, 3, 5):
        m = yr * 12
        p = 1 - float(surv.iloc[int(np.abs(idx - m).argmin())].iloc[0])
        print(f"           {yr}년 후 이직 누적확률 = {p:.1%}")

    medians = {"age": float(s["age"].median()),
               "sex": float(s["sex"].median()),
               "edu": float(s["edu"].median())}
    return {"km": km, "cox": cox, "cov_cols": cov_cols, "medians": medians,
            "source": "YP2021 스펠", "n": len(s), "n_features": len(cov_cols),
            "max_horizon_years": 5,       # YP 4웨이브 → 5년까지만 신뢰(그 이상은 희박)
            "cv_concordance": {"train": round(cv[0], 3), "test": round(cv[1], 3),
                               "test_std": round(cv[2], 3), "gap": round(cv[3], 3)}}


# ---------------------------------------------------------------- L2
def train_knn_yp() -> dict:
    """청년 매칭 풀 — YP 응답자 중 유효 소득자로 KNN 구성.

    GOMS 매칭(전공 포함)을 대체하지 않고, 서빙에서 청년에게 GOMS 와 '섞어서'
    제공된다. YP 엔 전공이 없어 매칭 피처에서 major 를 뺀다.
    """
    from sklearn.neighbors import NearestNeighbors
    from sklearn.preprocessing import StandardScaler

    p = pd.read_csv(CLEAN_DIR / "yp_clean.csv")
    d = p.rename(columns={"income_now": "monthly_wage", "satis_work": "satis_overall"})
    keep = ["sex", "age", "monthly_wage", "satis_overall", "firm_size",
            "changed_job", "occupation_raw"]
    d = d[[c for c in keep if c in d.columns]].copy()
    d = d.dropna(subset=["sex", "age", "monthly_wage"])
    d = d[d["monthly_wage"] > 0]
    d = d[d["age"].between(AGE_MIN, AGE_MAX)]
    for c in ("satis_overall", "firm_size"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
        d[c] = d[c].fillna(d[c].median())
    d["changed_job"] = pd.to_numeric(d["changed_job"], errors="coerce").fillna(0).astype(int)

    scaler = StandardScaler()
    X = scaler.fit_transform(d[YP_KNN_FEATURES])
    knn = NearestNeighbors(n_neighbors=10, metric="euclidean").fit(X)
    print(f"[L2 YP KNN] fit 완료 (n={len(d):,}, 피처 {YP_KNN_FEATURES})")

    ref = d[["monthly_wage", "satis_overall", "changed_job"]].reset_index(drop=True)
    medians = {c: float(d[c].median()) for c in YP_KNN_FEATURES}
    return {"model": knn, "scaler": scaler, "feature_cols": YP_KNN_FEATURES,
            "ref": ref, "medians": medians, "source": "YP2021 청년패널"}


def main() -> None:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    d = build_causal_panel()
    joblib.dump(train_econml_yp(d), ARTIFACTS / "econml_yp.pkl")
    joblib.dump(train_lifelines_yp(), ARTIFACTS / "lifelines_yp.pkl")
    joblib.dump(train_knn_yp(), ARTIFACTS / "knn_yp.pkl")
    print(f"[done] YP artifacts -> {ARTIFACTS}/")


if __name__ == "__main__":
    main()
