"""KNN(L2): 입력과 유사한 실제 응답자(평행우주의 나) 탐색.

v3: 청년(age ≤ YOUTH_MAX)은 GOMS(전공 포함 매칭)와 YP(청년패널) 풀을 '섞어서'
    돌려준다. GOMS 는 전공까지 매칭하는 강점, YP 는 청년 실소득·이직 이력을 보강.
    그 외 연령은 GOMS 단독. 각 이웃에 source('GOMS'/'YP') 를 붙인다.
"""

from functools import lru_cache

import joblib
import numpy as np

from config import settings
from schemas import NeighborCase

YOUTH_MAX = 31


@lru_cache(maxsize=1)
def _load_goms():
    return (
        joblib.load(settings.artifacts_abspath / "knn.pkl"),
        joblib.load(settings.artifacts_abspath / "encoders.pkl"),
    )


@lru_cache(maxsize=1)
def _load_yp():
    p = settings.artifacts_abspath / "knn_yp.pkl"
    return joblib.load(p) if p.exists() else None


def _goms_vector(features: dict, enc: dict) -> np.ndarray:
    med = enc["medians"]
    row = []
    for col in enc["feature_cols"]:
        if col == "sex_enc":
            row.append(enc["sex_map"].get(str(features.get("sex")), 0))
        elif col == "major_enc":
            row.append(enc["major_map"].get(str(features.get("major")), 0))
        else:
            v = features.get(col)
            row.append(med[col] if v is None else float(v))
    return np.array([row], dtype=float)


def _goms_neighbors(features: dict, k: int) -> list[NeighborCase]:
    if k <= 0:
        return []
    art, enc = _load_goms()
    x = art["scaler"].transform(_goms_vector(features, enc))
    n = min(k, len(art["ref"]))
    dist, idx = art["model"].kneighbors(x, n_neighbors=n)
    ref = art["ref"]
    out = []
    for d, i in zip(dist[0], idx[0]):
        row = ref.iloc[int(i)]
        out.append(NeighborCase(
            source="GOMS",
            similarity=float(1 / (1 + d)),
            monthly_wage=float(row["monthly_wage"]),
            job_category=str(row["major"]),
            satis_overall=float(row["satis_overall"]),
            life_satis=float(row["life_satis"]),
            job_changed=int(row["job_changed"]),
        ))
    return out


def _yp_vector(features: dict, art: dict) -> np.ndarray:
    med = art["medians"]
    row = []
    for col in art["feature_cols"]:
        if col == "sex":
            try:
                row.append(float(features.get("sex")))
            except (TypeError, ValueError):
                row.append(med["sex"])
        else:
            v = features.get(col)
            row.append(med[col] if v is None else float(v))
    return np.array([row], dtype=float)


def _yp_neighbors(features: dict, k: int) -> list[NeighborCase]:
    art = _load_yp()
    if art is None or k <= 0:
        return []
    x = art["scaler"].transform(_yp_vector(features, art))
    n = min(k, len(art["ref"]))
    dist, idx = art["model"].kneighbors(x, n_neighbors=n)
    ref = art["ref"]
    out = []
    for d, i in zip(dist[0], idx[0]):
        row = ref.iloc[int(i)]
        out.append(NeighborCase(
            source="YP",
            similarity=float(1 / (1 + d)),
            monthly_wage=float(row["monthly_wage"]),
            job_category=None,                    # YP 엔 전공 없음
            satis_overall=float(row["satis_overall"]),
            life_satis=None,
            job_changed=int(row["changed_job"]),
        ))
    return out


def find_neighbors(features: dict, k: int = 5) -> list[NeighborCase]:
    age = features.get("age")
    # 청년: GOMS(전공 매칭) 절반 + YP(청년패널) 절반
    if age is not None and float(age) <= YOUTH_MAX and _load_yp() is not None:
        n_yp = k // 2
        return _goms_neighbors(features, k - n_yp) + _yp_neighbors(features, n_yp)
    return _goms_neighbors(features, k)
