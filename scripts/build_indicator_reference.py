"""3지표(경제적안정도·성장가능성·삶의질)의 **기준 분포**를 만든다.

## 왜 필요한가
`backend/indicators.py` 의 3지표는 손으로 튜닝한 상수 덩어리였다.

    econ = 0.35 + (income-250)/300*0.40 + max(change,0)*0.8 - regret/100*0.15
    grow = 0.25 + growth5/40*0.9 + max(change,0)*0.4

문제가 두 겹이다.

1. **의미가 없다.** 0.62 가 좋은 건지 나쁜 건지 말할 수 없고, 캘리브레이션할 대상도
   없다. 250·300·0.40 같은 숫자의 근거가 어디에도 없다.
2. **지표 간 비교가 깨진다.** `rag/psych_narrative.select_focus()` 는 세 지표 중
   **가장 낮은 것**을 골라 심리카드를 검색한다. 그런데 세 공식의 상수가 서로 달라
   척도가 안 맞으니, 어떤 지표가 '가장 낮게' 나오는지는 사용자 상태가 아니라
   공식의 절편이 결정한다. 즉 **어떤 이론카드가 뽑히는지가 매직넘버에 좌우됐다.**

그래서 각 구성요소를 실제 분포의 **백분위 순위**로 바꾼다. 그러면
  · 0.62 = "같은 나이대에서 상위 38%" 라는 해석이 생기고,
  · 세 지표가 같은 척도(백분위)에 놓여 '가장 낮은 지표' 비교가 의미를 갖고,
  · 분포가 바뀌면 이 스크립트만 다시 돌려 재캘리브레이션할 수 있다.

## 만드는 분포 (나이대별)
| 키 | 내용 | 출처 |
|---|---|---|
| `income_level`  | 월 실질임금(만원)                 | KLIPS 패널(빌드 차수) |
| `income_growth` | 5년 뒤 소득 증가율(%)             | KLIPS 같은 사람 t → t+5 |
| `satisfaction`  | 종합 만족도(1~5)                  | YP 청년패널 5개 facet 평균 |
| `exit_risk`     | N년 이탈 누적확률(0~1), 연차별     | 서빙 중인 Cox 모델 예측 분포 |

각 분포는 101개 분위점 격자로 저장한다(백분위 순위를 보간으로 구하기 위해).

사용법:
    python scripts/build_indicator_reference.py
출력:
    backend/models/artifacts/indicator_reference.json
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

KLIPS = ROOT / "data/raw/klips/klips_base.pkl"
YP = ROOT / "data/clean/yp_clean.csv"
ARTIFACTS = ROOT / "backend/models/artifacts"

# 서비스 타겟(25~35)을 가운데 두고 양쪽을 넓게. 나이대별로 재는 이유는
# "29살 320만원" 이 잘 버는 건지가 나이대 없이는 판정 불가하기 때문.
AGE_BANDS = [(22, 26), (27, 31), (32, 36), (37, 45)]
RISK_YEARS = (1, 3, 5, 10)
GRID = 101          # 0~100 백분위


def _panel_label() -> str:
    """기준 분포가 실제로 어느 차수에서 나왔는지. 차수를 바꿔 재빌드하면 따라 바뀐다."""
    try:
        w = pd.read_pickle(KLIPS)["wave"]
        return f"KLIPS {int(w.min())}-{int(w.max())}차"
    except Exception:
        return "KLIPS"


def band_label(lo: int, hi: int) -> str:
    return f"{lo}-{hi}"


def quantile_grid(v: np.ndarray) -> list[float] | None:
    """값 배열 → 101개 분위점. 표본이 적으면 None(그 나이대는 전체 분포로 폴백)."""
    v = np.asarray(v, dtype=float)
    v = v[np.isfinite(v)]
    if len(v) < 100:
        return None
    return [round(float(x), 4) for x in np.percentile(v, np.linspace(0, 100, GRID))]


def by_band(df: pd.DataFrame, age_col: str, val: np.ndarray) -> dict:
    """나이대별 분위 격자 + 전체(`all`) 격자."""
    out: dict = {}
    age = df[age_col].to_numpy(dtype=float)
    for lo, hi in AGE_BANDS:
        g = quantile_grid(val[(age >= lo) & (age <= hi)])
        if g:
            out[band_label(lo, hi)] = g
    g = quantile_grid(val)
    if g:
        out["all"] = g
    return out


# ---------------------------------------------------------------- KLIPS
def income_dists() -> tuple[dict, dict]:
    b = pd.read_pickle(KLIPS)
    b = b[b["월임금_실질"] > 0].dropna(subset=["나이", "월임금_실질"])
    b = b.sort_values(["pid", "wave"])
    level = by_band(b, "나이", b["월임금_실질"].to_numpy(dtype=float))

    # 5년 뒤 소득 증가율(%): 같은 사람의 t → t+5
    idx = b.set_index(["pid", "wave"])["월임금_실질"]
    key = pd.MultiIndex.from_arrays([b["pid"], b["wave"] + 5])
    fut = idx.reindex(key).to_numpy()
    ok = np.isfinite(fut) & (b["월임금_실질"].to_numpy() > 0)
    g = b[ok].copy()
    growth = (fut[ok] / g["월임금_실질"].to_numpy(dtype=float) - 1.0) * 100.0
    # 극단값 절단 — 분위 격자가 몇 건의 이상치로 휘는 걸 막는다(±300% 밖은 버림)
    keep = np.abs(growth) <= 300
    growth_d = by_band(g[keep], "나이", growth[keep])
    print(f"  income_level  n={len(b):,}  나이대 {sorted(k for k in level if k != 'all')}")
    print(f"  income_growth n={int(keep.sum()):,} (5년 쌍) "
          f"중앙값 {np.median(growth[keep]):+.1f}%")
    return level, growth_d


# ---------------------------------------------------------------- YP
def satisfaction_dist() -> dict:
    y = pd.read_csv(YP)
    cols = [c for c in ("satis_work", "satis_growth", "satis_income",
                        "satis_stability", "satis_future") if c in y.columns]
    if not cols:
        return {}
    for c in cols + ["age"]:
        y[c] = pd.to_numeric(y[c], errors="coerce")
    y["만족도"] = y[cols].mean(axis=1)
    y = y.dropna(subset=["age", "만족도"])
    d = by_band(y, "age", y["만족도"].to_numpy(dtype=float))
    print(f"  satisfaction  n={len(y):,}  중앙값 {y['만족도'].median():.2f} "
          f"나이대 {sorted(k for k in d if k != 'all')}")
    return d


# ---------------------------------------------------------------- 이탈위험
def exit_risk_dist() -> dict:
    """서빙 중인 Cox 모델이 실제로 뱉는 이탈확률의 분포.

    후회 리스크 값을 백분위로 읽으려면 '이 모델이 사람들에게 내는 값들' 이 기준이어야
    한다. 이론적 분포가 아니라 서빙 모델의 출력 분포를 쓴다.
    """
    import joblib
    from models.lifelines_model import _value

    out: dict = {}
    for name in ("lifelines_klips.pkl", "lifelines_yp.pkl"):
        p = ARTIFACTS / name
        if not p.exists():
            continue
        art = joblib.load(p)
        cov = art["cov_cols"]
        b = pd.read_pickle(KLIPS).dropna(subset=["나이", "성별", "학력"])
        b = b[b["나이"].between(20, 45)].sample(min(4000, len(b)), random_state=42)
        rows = [{"age": r["나이"], "sex": r["성별"], "edu_level": r["학력"]}
                for _, r in b.iterrows()]
        X = pd.DataFrame([[_value(c, f, art) for c in cov] for f in rows], columns=cov)
        sf = art["cox"].predict_survival_function(X)
        t = np.asarray(sf.index, dtype=float)
        max_yr = art.get("max_horizon_years", 10)
        for yr in RISK_YEARS:
            if yr > max_yr:
                continue
            risk = 1.0 - sf.iloc[int(np.abs(t - yr * 12).argmin())].to_numpy(dtype=float)
            out.setdefault(str(yr), {})
            g = quantile_grid(risk)
            if g:
                out[str(yr)][name.replace("lifelines_", "").replace(".pkl", "")] = g
        print(f"  exit_risk({name}) 연차 {sorted(out)}")
    return out


def main() -> int:
    if not KLIPS.exists():
        print(f"{KLIPS} 없음 — preprocess/preprocess_klips.py 먼저 실행")
        return 1
    print("[reference] 3지표 기준 분포 산출")
    level, growth = income_dists()
    satis = satisfaction_dist() if YP.exists() else {}
    risk = exit_risk_dist()

    ref = {
        "built_at": datetime.now(timezone.utc).isoformat(),
        "age_bands": [list(b) for b in AGE_BANDS],
        "grid_points": GRID,
        "note": "각 값은 0~100 백분위에 대응하는 분위점 격자. 백분위 순위는 보간으로 구한다. "
                "'all' 은 나이대 표본이 부족할 때의 폴백.",
        "sources": {"income_level": f"{_panel_label()} 월임금_실질(2024년 기준 실질)",
                    "income_growth": "KLIPS 같은 사람 t→t+5 소득 증가율(%), ±300% 절단",
                    "satisfaction": "YP 청년패널 5개 facet 평균(1~5)",
                    "exit_risk": "서빙 Cox 모델의 연차별 이탈확률 예측 분포"},
        "dists": {"income_level": level, "income_growth": growth,
                  "satisfaction": satis, "exit_risk": risk},
    }
    out = ARTIFACTS / "indicator_reference.json"
    out.write_text(json.dumps(ref, ensure_ascii=False), encoding="utf-8")
    print(f"[done] → {out.relative_to(ROOT)} ({out.stat().st_size / 1024:.0f}KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
