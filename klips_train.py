"""
KLIPS 종단 데이터 학습 스크립트 (작업 3).

Layer 3: 이직 -> 임금 인과효과, 이전 임금·근속·직종을 혼재변수(W)로 통제 (진짜 종단 인과추론)
Layer 4: 직장 스펠 생존분석 (실데이터 근속 -> N년 후 이직 확률)

입력 (팀원 가공 파일, data/raw/klips/ 에 배치):
    klips_base.pkl        개인-연도 패널 (pid, wave, 성별, 나이, 학력, 직종,
                          월임금_실질, 근속기간, 이직 ...)
    klips_base_생존.csv    직장 스펠 (pid, jobseq, 시작wave, duration(년), event)

출력:
    backend/models/artifacts/econml_klips.pkl     (서빙 시 GOMS 버전보다 우선 사용)
    backend/models/artifacts/lifelines_klips.pkl

사용법:
    python klips_train.py
"""

from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd

KLIPS_DIR = Path("data/raw/klips")
ARTIFACTS = Path("backend/models/artifacts")

AGE_MIN, AGE_MAX = 20, 45  # 서비스 타겟(25~35)보다 약간 넓게 -> 표본 확보


def find_file(stem: str) -> Path:
    """한글 파일명이 NFD 등으로 변형돼도 찾도록 부분일치 탐색."""
    hits = [p for p in KLIPS_DIR.iterdir() if p.name.startswith(stem)]
    if not hits:
        raise FileNotFoundError(f"{KLIPS_DIR}/{stem}* 없음")
    return hits[0]


# ---------------------------------------------------------------- L3
# 학습에 실제로 쓰인 차수 범위. artifact 의 `source` 는 여기서 만든다 —
# 문자열로 박아두면 --waves 를 바꿔 재빌드했을 때 틀린 출처가 서빙까지 흘러간다.
PANEL_LABEL = "KLIPS"


def _set_panel_label(b) -> None:
    global PANEL_LABEL
    PANEL_LABEL = f"KLIPS {int(b['wave'].min())}-{int(b['wave'].max())}차"


def build_causal_panel() -> pd.DataFrame:
    """연속 관측 (t, t+1) 쌍 -> 인과추론용 행 구성.

    T = t+1 시점 이직 여부, Y = t+1 실질임금
    W(혼재변수) = t 시점 임금·근속·직종·종업원규모
    X(이질성)   = 나이·성별·학력
    """
    b = pd.read_pickle(find_file("klips_base.pkl"))
    _set_panel_label(b)
    b = b[["pid", "wave", "성별", "나이", "학력", "직종", "종업원규모",
           "월임금_실질", "근속기간", "이직"]].copy()
    b = b.dropna(subset=["월임금_실질"])
    b = b[b["월임금_실질"] > 0]
    b = b.sort_values(["pid", "wave"])

    nxt = b.groupby("pid").shift(-1)
    d = pd.DataFrame({
        "pid": b["pid"],
        "age": b["나이"],
        "sex": b["성별"],                    # 1=남 2=여 (GOMS 와 동일 코딩)
        "edu": b["학력"],
        "occ": b["직종"],
        "firm_size": b["종업원규모"],
        "wage_now": b["월임금_실질"],
        "tenure": b["근속기간"],
        "wage_next": nxt["월임금_실질"],
        "T_move": nxt["이직"],
        "wave_gap": nxt["wave"] - b["wave"],
    })
    d = d[(d["wave_gap"] == 1)]              # 연속 파동만
    d = d.dropna(subset=["wage_next", "T_move", "age", "sex", "edu",
                         "wage_now", "tenure"])
    d = d[d["age"].between(AGE_MIN, AGE_MAX)]
    d["T_move"] = d["T_move"].astype(int)
    d["occ"] = d["occ"].fillna(0)
    d["firm_size"] = d["firm_size"].fillna(d["firm_size"].median())
    print(f"[L3 panel] {len(d):,} 개 (사람-연도 전이쌍), 이직 비율 {d['T_move'].mean():.1%}")
    return d


def train_econml_klips(d: pd.DataFrame) -> dict:
    from econml.dml import CausalForestDML
    from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier

    X_COLS = ["age", "sex", "edu"]
    W_COLS = ["wage_now", "tenure", "occ", "firm_size"]

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
    print(f"[L3 KLIPS] ATE(이직→익년 실질임금) = {ate:+.2f} 만원 "
          f"(95% CI {lb:+.2f} ~ {ub:+.2f}) | 평균임금 대비 {ate/mean_wage:+.1%}")

    # 비교용: LinearDML (조합 3) - 해석 가능한 분석적 신뢰구간
    from econml.dml import LinearDML
    lin = LinearDML(
        model_y=RandomForestRegressor(n_estimators=150, min_samples_leaf=20),
        model_t=RandomForestClassifier(n_estimators=150, min_samples_leaf=20),
        discrete_treatment=True, random_state=42,
    )
    lin.fit(Y, T, X=X, W=W)
    lin_ate = float(lin.ate(X))
    llb, lub = (float(v) for v in lin.ate_interval(X, alpha=0.05))
    print(f"[L3 KLIPS/LinearDML] ATE = {lin_ate:+.2f} 만원 (95% CI {llb:+.2f} ~ {lub:+.2f})")

    medians = {c: float(d[c].median()) for c in X_COLS}
    return {"model": est, "x_cols": X_COLS, "medians": medians,
            "ate": ate, "ate_ci": (lb, ub),
            "linear_ate": lin_ate, "linear_ci": (llb, lub),
            "source": f"{PANEL_LABEL} 종단"}


# ---------------------------------------------------------------- L4
def _cv_concordance(df, cov_cols, dur="duration_months", ev="event", k=5, seed=42):
    """5-fold 교차검증 C-index → (학습평균, 테스트평균, 테스트표준편차, 갭). 예측력 검증용."""
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


def train_lifelines_klips() -> dict:
    from lifelines import KaplanMeierFitter, CoxPHFitter

    s = pd.read_csv(find_file("klips_base_"))       # klips_base_생존.csv
    b = pd.read_pickle(find_file("klips_base.pkl"))
    _set_panel_label(b)          # 이 함수만 단독 호출돼도 출처가 맞도록
    cov = (b.sort_values("wave")
             .groupby("pid")
             .agg(sex=("성별", "first"), edu=("학력", "last"),
                  first_age=("나이", "first"), first_wave=("wave", "first"))
             .reset_index())

    s = s.merge(cov, on="pid", how="left")
    # 스펠 시작 시점 나이 근사: 첫 관측 나이 + (시작wave - 첫 관측 wave)
    s["age_start"] = s["first_age"] + (s["시작wave"] - s["first_wave"])
    s["duration_months"] = s["duration"].clip(lower=0.5) * 12
    s = s.dropna(subset=["sex", "edu", "age_start"])
    s = s[s["age_start"].between(AGE_MIN, AGE_MAX)]
    print(f"[L4 panel] 스펠 {len(s):,}개 (이직 이벤트 {int(s['event'].sum()):,}건)")

    km = KaplanMeierFitter()
    km.fit(s["duration_months"], event_observed=s["event"], label="all")

    cov_cols = ["age_start", "sex", "edu"]
    cox = CoxPHFitter()
    cox.fit(s[["duration_months", "event"] + cov_cols],
            duration_col="duration_months", event_col="event")

    # 예측력 검증: 5-fold 교차검증 C-index
    cv = _cv_concordance(s, cov_cols)
    stable = "✓안정" if cv[3] < 0.05 else "⚠과적합 의심"
    print(f"[L4 KLIPS/CV] 5-fold C-index 학습 {cv[0]:.3f} / 테스트 {cv[1]:.3f}±{cv[2]:.3f} "
          f"| 갭 {cv[3]:.3f} {stable}")

    # 서비스 멘트용 요약: N년 시점 이직(이탈) 누적확률 (10년까지)
    surv = km.survival_function_
    idx = np.asarray(surv.index, dtype=float)
    for yr in (1, 3, 5, 10):
        m = yr * 12
        p = 1 - float(surv.iloc[int(np.abs(idx - m).argmin())].iloc[0])
        print(f"           {yr}년 후 이직 누적확률 = {p:.1%}")

    medians = {"age_start": float(s["age_start"].median()),
               "sex": float(s["sex"].median()), "edu": float(s["edu"].median())}
    return {"km": km, "cox": cox, "cov_cols": cov_cols, "medians": medians,
            "source": f"{PANEL_LABEL} 스펠", "n": len(s), "n_features": len(cov_cols),
            "max_horizon_years": 10,      # 관측 10년 초과 구간은 과대추정 방지로 스킵
            "cv_concordance": {"train": round(cv[0], 3), "test": round(cv[1], 3),
                               "test_std": round(cv[2], 3), "gap": round(cv[3], 3)}}


def main() -> None:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    d = build_causal_panel()
    joblib.dump(train_econml_klips(d), ARTIFACTS / "econml_klips.pkl")
    joblib.dump(train_lifelines_klips(), ARTIFACTS / "lifelines_klips.pkl")
    print(f"[done] KLIPS artifacts -> {ARTIFACTS}/")


if __name__ == "__main__":
    main()
