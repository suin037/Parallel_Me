# train_layer2.py — Layer 2: KNN 유사인물 매칭 (수정판)
import pandas as pd
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
import joblib, os

os.makedirs("backend/models/artifacts", exist_ok=True)
g = pd.read_csv("data/clean/goms_clean.csv")

# 결측 적은 피처로 교체 (income_first 뺌 → income_now 사용)
num = ["age", "income_now"]
cat = ["sex", "school_type", "major_cat", "occupation", "is_regular"]
feat = num + cat

# 매칭엔 안 쓰지만 결과 확인용으로 changed_job, income_change_pct 도 살려둠
keep = feat + ["changed_job", "income_change_pct"]
df = g.dropna(subset=feat).reset_index(drop=True)
print("KNN 학습 표본:", len(df), "/ 전체", len(g))

pre = ColumnTransformer([
    ("num", StandardScaler(), num),
    ("cat", OneHotEncoder(handle_unknown="ignore"), cat),
])
X = pre.fit_transform(df[feat])
knn = NearestNeighbors(n_neighbors=200, metric="euclidean").fit(X)

# 테스트: 랜덤한 사람 3명으로 매칭 확인
import numpy as np
np.random.seed(0)
for i in np.random.randint(0, len(df), 3):
    dist, idx = knn.kneighbors(X[i:i+1])
    neigh = df.iloc[idx[0]]
    p = df.iloc[i]
    n_moved = int((neigh["changed_job"] == 1).sum())
    print(f"\n[{i}번] {p['age']:.0f}세/직종{p['occupation']:.0f}/소득{p['income_now']:.0f}만")
    print(f"  비슷한 200명 중 이직: {n_moved}명")
    if n_moved > 0:
        print(f"  이직자 평균 소득변화: {neigh[neigh['changed_job']==1]['income_change_pct'].mean():+.1f}%")
    print(f"  잔류자 평균 소득변화: {neigh[neigh['changed_job']==0]['income_change_pct'].mean():+.1f}%")

joblib.dump({"knn": knn, "pre": pre, "feat": feat}, "backend/models/artifacts/layer2_knn.pkl")
df.to_parquet("backend/models/artifacts/layer2_neighbors.parquet")
print("\n[저장됨] layer2_knn.pkl + layer2_neighbors.parquet")