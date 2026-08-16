"""L5 궤적 매칭 품질 측정 — "이웃이 좋아졌다"를 주장이 아니라 수치로.

## 무엇을 재는가
KLIPS 패널에서 (사람, 시작 웨이브)를 무작위로 뽑아 **질의**로 쓰고, 그 사람을 제외한
패널에서 이웃 k명을 찾아 h년 뒤 소득을 예측한 뒤 **실제 값과 비교**한다.

  · MAE / MdAE — 중앙값 예측이 실제에서 얼마나 벗어나는가
  · band_hit   — 실제 값이 p25~p75 밴드 안에 들어온 비율.
                 서비스가 파는 건 점추정이 아니라 분포다. 밴드가 정직하면 이 값이
                 0.5 근처여야 한다. 훨씬 낮으면 밴드가 좁고(과신), 높으면 넓다(무의미).
  · band_width — 밴드 폭 중앙값. 같은 정확도면 좁을수록 정보가 많다.

같은 사람(pid)을 이웃에서 제외해 자기 자신을 맞히는 누수를 막는다.

## 왜 필요한가
매칭 피처를 늘리는 건 쉽지만, 늘렸다고 좋아졌는지는 재 봐야 안다. 학습된 거리나
성향점수 매칭으로 갈지도 이 하네스 위에서 비교해 판단할 문제다(먼저 자를 만든다).

사용법:
    python scripts/eval_matching.py
    python scripts/eval_matching.py --n 600 --k 300 --seed 7
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

import trajectory as T                                    # noqa: E402

HORIZONS = (1, 3, 5)

# 비교할 피처 조합. None = 그 축을 질의에서 빼서 매칭에 안 쓰이게 한다.
#   baseline  = 티어2 이전(나이·성별·임금·학력 + 정규여부)
#   +규모     = 요청 스키마에 이미 있던 firm_size 까지 (프론트 변경 없이 가능)
#   +근속직종 = 근속·직종까지 (Profile 에 새로 연 선택 입력)
CONFIGS = {
    "baseline(나이·성별·임금·학력·정규)": ["firm_size", "tenure_years", "job_category"],
    "+기업규모": ["tenure_years", "job_category"],
    "+기업규모+근속": ["job_category"],
    "+기업규모+근속+직종": [],
}

# --tune 이 탐색할 축과 후보 가중치. 손으로 정하던 값을 측정으로 정하기 위한 것.
TUNE_GRID = {
    "월임금_실질": [0.8, 1.2, 1.6, 2.0],
    "직종소득지수": [0.0, 0.3, 0.6, 1.0],
    "근속기간_log": [0.0, 0.3, 0.6, 1.0],
    "종업원규모": [0.0, 0.3, 0.6, 1.0],
    "학력": [0.3, 0.6, 0.9],
    "나이": [0.5, 1.0, 1.5],
}


def sample_queries(b: pd.DataFrame, n: int, seed: int) -> pd.DataFrame:
    """h년 뒤 소득이 실제로 관측된 (pid, wave) 질의점."""
    idx = b.set_index(["pid", "wave"])["월임금_실질"]
    ok = b.copy()
    for h in HORIZONS:
        key = pd.MultiIndex.from_arrays([ok["pid"], ok["wave"] + h])
        ok[f"y{h}"] = idx.reindex(key).to_numpy()
    ok = ok.dropna(subset=[f"y{h}" for h in HORIZONS])
    ok = ok[ok["나이"].between(22, 45)]
    return ok.sample(min(n, len(ok)), random_state=seed)


def legacy_distance(cand: pd.DataFrame, feats: dict, P: dict) -> np.ndarray:
    """티어2 이전에 실제로 서빙되던 거리 — 비교 기준점.

    나이·성별·임금·학력·정규여부를 **가중치 없이** z-score 유클리드로 재고,
    결측은 중앙값으로 채웠다. '개선했다'를 이 선 위에서 말해야 정직하다.
    """
    cols = ["나이", "성별", "월임금_실질", "학력", "정규여부"]
    b = P["b"]
    med = {c: float(b[c].median()) for c in cols}
    C = cand[cols].astype(float).fillna(pd.Series(med))
    mu, sd = b[cols].astype(float).mean(), b[cols].astype(float).std().replace(0, 1)
    q = {"나이": feats["age"], "성별": feats["sex"],
         "월임금_실질": feats["monthly_wage"],
         "학력": feats.get("edu_level") if feats.get("edu_level") is not None else med["학력"],
         "정규여부": feats.get("is_regular") if feats.get("is_regular") is not None
                     else med["정규여부"]}
    zq = np.array([(q[c] - mu[c]) / sd[c] for c in cols])
    Z = ((C - mu) / sd).to_numpy()
    return np.sqrt(((Z - zq) ** 2).sum(axis=1))


def predict_for(row: pd.Series, drop: list[str], k: int, P: dict,
                legacy: bool = False) -> dict:
    """이 질의점의 이웃을 찾아 h년 뒤 소득 분위수를 예측. 자기 pid 는 제외."""
    feats = {
        "age": float(row["나이"]), "sex": float(row["성별"]),
        "monthly_wage": float(row["월임금_실질"]), "edu_level": float(row["학력"]),
        "is_regular": row.get("정규여부"), "firm_size": row.get("종업원규모"),
        "tenure_years": row.get("근속기간"), "job_category": row.get("직종"),
    }
    for key in drop:
        feats[key] = None
    feats = {kk: (None if (v is not None and isinstance(v, float) and np.isnan(v)) else v)
             for kk, v in feats.items()}

    b = P["b"]
    A = feats["age"]
    cand = b[(b["나이"].between(A - 1, A + 1)) & (b["pid"] != row["pid"])]
    if len(cand) < 30:
        return {}
    if legacy:
        dist = legacy_distance(cand, feats, P)
    else:
        dist = T._match_distance(cand, T._query_vector(feats, P), P)
    starts = (cand.assign(_d=dist).nsmallest(k, "_d")[["pid", "wave"]]
              .rename(columns={"wave": "start_wave"}))
    follow = starts.merge(b[["pid", "wave", "월임금_실질"]], on="pid", how="left")
    follow["h"] = follow["wave"] - follow["start_wave"]

    out = {}
    for h in HORIZONS:
        v = follow.loc[follow["h"] == h, "월임금_실질"].dropna().to_numpy()
        if len(v) >= 15:
            out[h] = (float(np.percentile(v, 25)), float(np.percentile(v, 50)),
                      float(np.percentile(v, 75)))
    return out


def evaluate(qs: pd.DataFrame, drop: list[str], k: int, P: dict,
             legacy: bool = False) -> dict:
    """질의별 오차까지 함께 돌려준다 — 설정 간 **짝지은** 비교를 하기 위해서.

    같은 질의에 두 설정을 돌린 것이므로 짝지어 차이를 보면 질의 난이도 분산이
    상쇄돼, 1~2% 차이가 실제인지 표본 흔들림인지 구분할 수 있다.
    """
    err = {h: {} for h in HORIZONS}
    hit = {h: [] for h in HORIZONS}
    wid = {h: [] for h in HORIZONS}
    for qi, (_, row) in enumerate(qs.iterrows()):
        pred = predict_for(row, drop, k, P, legacy=legacy)
        for h, (p25, p50, p75) in pred.items():
            actual = float(row[f"y{h}"])
            err[h][qi] = abs(p50 - actual)
            hit[h].append(p25 <= actual <= p75)
            wid[h].append(p75 - p25)
    out = {h: {"n": len(err[h]),
               "mae": float(np.mean(list(err[h].values()))) if err[h] else None,
               "mdae": float(np.median(list(err[h].values()))) if err[h] else None,
               "band_hit": float(np.mean(hit[h])) if hit[h] else None,
               "band_width": float(np.median(wid[h])) if wid[h] else None}
           for h in HORIZONS}
    out["_err"] = err
    return out


def paired_delta(new: dict, base: dict, h: int) -> tuple[float, float, int]:
    """(평균 오차 차이, 95% 신뢰반경, 짝 수). 음수면 개선."""
    a, b = new["_err"][h], base["_err"][h]
    keys = sorted(set(a) & set(b))
    if not keys:
        return 0.0, 0.0, 0
    d = np.array([a[i] - b[i] for i in keys], dtype=float)
    return float(d.mean()), float(1.96 * d.std(ddof=1) / np.sqrt(len(d))), len(d)


def _score(r: dict) -> float:
    """탐색 목적함수 — 전 시점 MAE 평균. 낮을수록 좋다."""
    v = [r[h]["mae"] for h in HORIZONS if r[h]["mae"] is not None]
    return float(np.mean(v)) if v else float("inf")


def tune(qs: pd.DataFrame, k: int, P: dict) -> dict:
    """좌표하강으로 가중치 탐색. 한 축씩 최선값으로 고정하며 2회 순회한다.

    전역 최적을 보장하진 않지만, '손으로 정한 상수' 를 '측정으로 고른 값' 으로
    바꾸는 게 목적이다. 과적합 방지로 탐색은 tune seed, 보고는 다른 seed 로 한다.
    """
    best = dict(T.NUM_FEATS)
    cur = _score(evaluate(qs, [], k, P))
    print(f"  시작 MAE {cur:.2f}만  (가중치 {best})")
    for sweep in range(2):
        for col, grid in TUNE_GRID.items():
            if col not in P["num"]:
                continue
            trials = []
            for w in grid:
                T.NUM_FEATS[col] = w
                trials.append((_score(evaluate(qs, [], k, P)), w))
            T.NUM_FEATS[col] = best[col]
            s, w = min(trials)
            if s < cur - 1e-9:
                cur, best[col] = s, w
                T.NUM_FEATS[col] = w
                print(f"  [sweep {sweep + 1}] {col:12s} → {w}  MAE {cur:.2f}만")
    T.NUM_FEATS.update(best)
    print(f"  탐색 결과 MAE {cur:.2f}만  가중치 {best}")
    return best


def main() -> int:
    ap = argparse.ArgumentParser(description="L5 궤적 매칭 품질 hold-out 평가")
    ap.add_argument("--n", type=int, default=400, help="질의 표본 수")
    ap.add_argument("--k", type=int, default=300, help="이웃 수")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--tune", action="store_true",
                    help="가중치 좌표하강 탐색(별도 seed) 후 보고")
    ap.add_argument("--tune-seed", type=int, default=7)
    ap.add_argument("--tune-n", type=int, default=250)
    args = ap.parse_args()

    P = T._panel()
    if P is None:
        print("klips_base.pkl 없음 — preprocess/preprocess_klips.py 먼저 실행")
        return 1

    if args.tune:
        tq = sample_queries(P["b"], args.tune_n, args.tune_seed)
        print(f"[tune] 탐색 표본 {len(tq):,}개 (seed {args.tune_seed}) — "
              f"보고는 seed {args.seed} 의 별도 표본으로 한다\n")
        tune(tq, args.k, P)
        print()

    qs = sample_queries(P["b"], args.n, args.seed)
    print(f"[eval] 질의 {len(qs):,}개 · 이웃 k={args.k} · 패널 {len(P['b']):,}행")
    print(f"       band_hit 은 0.5 에 가까울수록 정직한 밴드(p25~p75 구간이므로)\n")

    rows = [("기존 서빙(티어2 이전)", evaluate(qs, [], args.k, P, legacy=True))]
    for label, drop in CONFIGS.items():
        rows.append((label, evaluate(qs, drop, args.k, P)))

    for label, r in rows:
        print(f"  {label}")
        for h in HORIZONS:
            m = r[h]
            if m["mae"] is None:
                print(f"    t+{h}: (표본 부족)")
                continue
            print(f"    t+{h}: MAE {m['mae']:6.1f}만  MdAE {m['mdae']:6.1f}만  "
                  f"밴드적중 {m['band_hit']:.3f}  밴드폭 {m['band_width']:5.1f}만  "
                  f"(n={m['n']})")
        print()

    base = rows[0][1]
    print("  === 기존 서빙 대비 짝지은 차이 (음수=개선, ± 는 95% 신뢰반경) ===")
    print("      신뢰반경이 차이보다 크면 '측정 못 함' 이지 '개선' 이 아니다.")
    for label, r in rows[1:]:
        parts = []
        for h in HORIZONS:
            d, ci, n = paired_delta(r, base, h)
            mark = "*" if abs(d) > ci and ci > 0 else " "
            parts.append(f"t+{h} {d:+6.1f}±{ci:4.1f}{mark}")
        print(f"    {label:30s} {'  '.join(parts)}")
    print("\n      * = 95% 구간이 0을 넘지 않음(=표본 흔들림으로 보기 어려움)")

    report = {
        "measured_at": pd.Timestamp.utcnow().isoformat(),
        "queries": int(len(qs)), "k": args.k, "seed": args.seed,
        "panel_rows": int(len(P["b"])),
        "weights": dict(T.NUM_FEATS),
        "cat_penalty": dict(T.CAT_PENALTY),
        "horizons": list(HORIZONS),
        "metric_note": "MAE=중앙값 예측의 절대오차(만원), band_hit=실제값이 p25~p75 "
                       "안에 든 비율(정직하면 ≈0.5), band_width=밴드 폭 중앙값",
        "configs": {label: {str(h): {kk: r[h][kk] for kk in
                                     ("n", "mae", "mdae", "band_hit", "band_width")}
                            for h in HORIZONS}
                    for label, r in rows},
        "paired_vs_legacy": {label: {str(h): dict(zip(("delta_mae", "ci95", "n"),
                                                     paired_delta(r, base, h)))
                                     for h in HORIZONS}
                             for label, r in rows[1:]},
    }
    out = ROOT / "backend/models/artifacts/matching_eval.json"
    out.write_text(__import__("json").dumps(report, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(f"\n  → {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
