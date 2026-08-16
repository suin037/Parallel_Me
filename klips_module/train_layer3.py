# train_layer3.py — Layer 3: EconML 인과추론 (이직의 순수 소득효과)
import pandas as pd, numpy as np
from econml.dml import CausalForestDML
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
import joblib, os

os.makedirs("backend/models/artifacts", exist_ok=True)
b = pd.read_pickle("data/klips_base.pkl")
b = b.sort_values(["pid", "wave"])

# pid별 pre(첫 임금관측) / post(마지막 임금관측)로 인과표 구성
def build(g):
    g = g.dropna(subset=["월임금_실질"])
    if len(g) < 2:
        return None
    pre, post = g.iloc[0], g.iloc[-1]
    if pre["월임금_실질"] <= 0:
        return None
    return pd.Series({
        "treat": int((g["이직"] == 1).any()),
        "ychg": (post["월임금_실질"] - pre["월임금_실질"]) / pre["월임금_실질"],
        "나이": pre["나이"], "학력": pre["학력"],
        "초임_실질": pre["월임금_실질"], "종업원규모": pre["종업원규모"],
        "직종대분류": int(pre["직종"] // 100) if pd.notna(pre["직종"]) else -1,
        "종사상지위": pre["종사상지위"],
    })

c = b.groupby("pid").apply(build, include_groups=False).dropna().reset_index(drop=True)
c = c[(c["ychg"] > -0.9) & (c["ychg"] < 3.0)]      # 이상치 제거
c = c[c["직종대분류"] >= 1].dropna(subset=["학력", "종업원규모", "종사상지위"])
print("인과분석 표본:", len(c), "| 이직비율:", round(c["treat"].mean()*100, 1), "%")

Y = c["ychg"].values
T = c["treat"].values
X = pd.get_dummies(
    c[["나이", "학력", "초임_실질", "종업원규모", "직종대분류", "종사상지위"]].astype(float),
    columns=["직종대분류"], drop_first=True,
).values.astype(float)

est = CausalForestDML(
    model_y=RandomForestRegressor(n_estimators=150, min_samples_leaf=20, random_state=0),
    model_t=RandomForestClassifier(n_estimators=150, min_samples_leaf=20, random_state=0),
    discrete_treatment=True, n_estimators=400, min_samples_leaf=25, random_state=0,
)
est.fit(Y, T, X=X)
ate = est.ate(X); lo, hi = est.ate_interval(X, alpha=0.05)

print("\n=== 이직의 순수 인과효과 (혼재변수 통제 후) ===")
print(f"naive 차이: {(Y[T==1].mean() - Y[T==0].mean())*100:+.1f}%p (통제 전)")
print(f"ATE(순수효과): {ate*100:+.1f}%  (95% CI {lo*100:+.1f}% ~ {hi*100:+.1f}%)")

joblib.dump(est, "backend/models/artifacts/layer3_econml.pkl")
print("\n[저장됨] layer3_econml.pkl")