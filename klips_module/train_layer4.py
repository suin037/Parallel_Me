# train_layer4.py — Layer 4 확정본: RSF 9피처 + 5-fold 검증 (0.643)
import pandas as pd, numpy as np
from lifelines import KaplanMeierFitter
from sksurv.ensemble import RandomSurvivalForest
from sksurv.metrics import concordance_index_censored
from sklearn.model_selection import KFold
import joblib, os

os.makedirs("backend/models/artifacts", exist_ok=True)
s = pd.read_pickle("data/klips_base_생존.pkl")
b = pd.read_pickle("data/klips_base.pkl")
h = pd.read_pickle("data/klips_health.pkl")

# --- (1) KM 후회곡선 (UI 타임라인에 나갈 숫자) ---
kmf = KaplanMeierFitter().fit(s["duration"], event_observed=s["event"])
print("=== 후회 리스크 곡선 (타임라인 UI용) ===")
for t in [1, 3, 5, 10]:
    surv = float(kmf.survival_function_at_times(t).iloc[0])
    print(f"{t:>2}년: {(1-surv)*100:4.1f}%")

# --- (2) 공변량: base + health 만족도 ---
hcols = [c for c in ["삶의만족도_현재","만족점수_전반적","건강점수","웰빙지수"] if c in h.columns]
hh = h[["pid","wave"]+hcols]
cov = b[["pid","wave","나이","학력","직종","종사상지위","월임금_실질"]].copy()
cov["직종대분류"] = cov["직종"]//100
cov = cov.merge(hh, on=["pid","wave"], how="left")
m = s.merge(cov, left_on=["pid","시작wave"], right_on=["pid","wave"], how="left")
m = m[m["직종대분류"]>=1]

feat = ["나이","학력","직종대분류","종사상지위","월임금_실질"]+hcols
for c in feat: m[c] = m[c].fillna(m[c].median())
m = m.dropna(subset=["duration","event"])
print(f"\n분석 표본: {len(m)}건 | 피처 {len(feat)}개")

def to_surv(ev,dur): return np.array([(bool(e),float(d)) for e,d in zip(ev,dur)],
                                     dtype=[("event",bool),("time",float)])
X, y = m[feat].values.astype(float), to_surv(m["event"], m["duration"])

# --- (3) 5-fold 과적합 검증 ---
print("\n=== 5-fold 교차검증 ===")
tr_s, te_s = [], []
for tr,te in KFold(5, shuffle=True, random_state=0).split(X):
    rsf = RandomSurvivalForest(n_estimators=100, min_samples_leaf=30, max_depth=6,
                               max_features="sqrt", n_jobs=-1, random_state=0).fit(X[tr],y[tr])
    tr_s.append(concordance_index_censored(y[tr]["event"],y[tr]["time"],rsf.predict(X[tr]))[0])
    te_s.append(concordance_index_censored(y[te]["event"],y[te]["time"],rsf.predict(X[te]))[0])
gap = np.mean(tr_s)-np.mean(te_s)
print(f"학습 {np.mean(tr_s):.3f} / 테스트 {np.mean(te_s):.3f}±{np.std(te_s):.3f} | 갭 {gap:.3f} {'⚠️과적합' if gap>0.05 else '✓안정'}")

# --- (4) 최종 모델 저장 ---
rsf = RandomSurvivalForest(n_estimators=200, min_samples_leaf=30, max_depth=6,
                           max_features="sqrt", n_jobs=-1, random_state=0).fit(X,y)
joblib.dump({"km":kmf, "rsf":rsf, "feat":feat}, "backend/models/artifacts/layer4_survival.pkl")
print("\n[저장됨] layer4_survival.pkl")