"""KOWEPS(한국복지패널) 기반 창업 처치효과 — 20~30대 표본을 KLIPS 대비 3.8배로 넓힌다.

## 왜 KOWEPS 를 더 붙이는가
KLIPS 로 만든 창업 모델은 20~31세 처치군이 147건뿐이다. 그런데 모델은 나이를 X(이질성)로
받으므로 표본이 얇아도 개인별 효과(CATE)를 만들어낸다 — 실제로 기존 artifact 에서 25세
CATE 가 +195만원(CI +19.7~+370.4)으로 전체 ATE(+47.2)의 4배가 나오고, 33세엔 -92만원으로
부호가 뒤집힌다. 나이 세 살 차이로 부호가 바뀌는 건 패턴이 아니라 잡음이다.

KOWEPS 는 20차(2006~2025)라 KLIPS(16차)보다 길고, 같은 전이 정의에서 처치군이

    20~45세  914건 (KLIPS 703)      20~39세  566건 (KLIPS 20~31세 147)

로 나온다. 서비스 타겟인 20~30대에서 3.8배다.

## 처치 정의 — 코드북으로 확정됐다
`p02_1`(근로유형)의 공식 코딩이 코드북 문항에 그대로 적혀 있다:

    1=임금근로자  2=자영업·고용주  3=무급가족종사자  4·5=미취업

처치 = 연속 차수에서 1 → 2. 대조 = 1 → 1(임금근로 유지). 다른 상태로 간 행은 처치도
대조도 아니다. KLIPS(종사상지위 1·2·3→4)·YP(emp_status 1·2·3→4·5)와 같은 구조다.
KLIPS·YP 는 .sav 에 값 라벨이 없어 실증으로 코드를 추론해야 했지만 여기는 문서 근거가 있다.

**기존 first-event 패널의 대조군을 쓰지 않는다.** 그쪽은 '25~35세 동안 한 번도 창업하지
않은 사람'이라 대조군에 애초에 창업 성향이 없는 사람이 몰린다. 여기서는 KLIPS 와 같은
전이쌍 기준 — '그 해에 창업할 수도 있었는데 임금근로를 유지한 사람'이 대조군이다.

## 결과변수 — 개인 단위 셋이 정본
| 컬럼 | 단위 | 비고 |
|---|---|---|
| `전반만족` (p03_12) | 1~5, 클수록 좋음 | 개인 응답. 정방향(역코딩 없음) |
| `건강` (h_med2) | 1~5, 클수록 좋음 | 개인 응답. **역코딩(6−x)** |
| `정신건강` (p05_11) | 1~4, 클수록 좋음(=덜 우울) | 개인 응답. **역코딩(5−x)**. KLIPS 에 없던 축 |
| `가처분소득` (h_din) | 만원/년 | **가구 단위** — 참고용. 아래 caveat |

## ⚠ 척도 방향과 무응답 코드
`.dta` 에도 코드북에도 값 라벨이 없어 방향을 데이터로 확인했다. 그 전에 **9(무응답)를
반드시 빼야 한다** — 안 빼면 만족↔우울 상관이 +0.111 로 나와 부호를 거꾸로 읽게 된다
(우울 문항은 무응답이 10,669건, 전체의 4%다).

    9 포함:  corr(만족, 우울) = +0.111   ← 무응답이 만든 가짜 신호
    9 제외:  corr(만족, 우울) = -0.343   corr(소득, 만족) = +0.249
             corr(나이, 건강) = +0.573   corr(소득, 우울) = -0.174

산출:
    backend/models/artifacts/koweps_startup_effects.json

사용법:
    python train_koweps_startup.py
    python train_koweps_startup.py --horizon 3
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

_RAW_NAME = "koweps_hp01_20_long_260331.dta"
# 배포자가 받은 위치가 갈린다(zip 을 풀면 long/ 이 생기고, 개별 파일로 받으면 안 생긴다).
# 원본을 옮기게 하지 않고 양쪽을 다 본다 — 1.4GB 를 사람이 나르게 할 이유가 없다.
_RAW_CANDIDATES = [
    Path("data/raw/koweps/long") / _RAW_NAME,
    Path("data/raw/koweps") / _RAW_NAME,
]
RAW = next((p for p in _RAW_CANDIDATES if p.exists()), _RAW_CANDIDATES[0])
CACHE = Path("data/clean/koweps/_startup_cols.pkl")
ARTIFACTS = Path("backend/models/artifacts")
OUT_PATH = ARTIFACTS / "koweps_startup_effects.json"

MIN_TREATED = 200          # train_treatments.py 와 동일한 게이트
MISSING_CODE = 9           # 모름/무응답. 5점 척도 밖의 값이라 반드시 제거

X_COLS = ["age", "sex", "edu"]
W_COLS = ["income_now", "occ", "work_hours_type", "household_size"]

# 결과변수: (원본컬럼, 라벨, 척도상한, 역코딩여부). 역코딩은 (상한+1)-x.
OUTCOMES = {
    "전반만족": {"src": "p03_12", "unit": "점(1~5)", "top": 5, "reverse": False,
                 "scale": "likert5", "level": "개인",
                 "note": "정방향 — 소득과 +0.249 상관으로 확인"},
    "건강": {"src": "h_med2", "unit": "점(1~5)", "top": 5, "reverse": True,
             "scale": "likert5", "level": "개인",
             "note": "원본은 클수록 나쁨 — 나이와 +0.573 상관으로 확인 후 역코딩"},
    "정신건강": {"src": "p05_11", "unit": "점(1~4)", "top": 4, "reverse": True,
                 "scale": "likert4", "level": "개인",
                 "note": "'상당히 우울' 문항. 원본은 클수록 우울 — 만족과 -0.343 상관으로 "
                         "확인 후 역코딩해 '덜 우울할수록 높음'으로 통일. KLIPS 에 없던 축"},
    "가처분소득": {"src": "h_din", "unit": "만원/년", "top": None, "reverse": False,
                   "scale": "continuous", "level": "가구",
                   "note": "가구 단위 연간 소득 — 개인 월소득인 KLIPS 값과 직접 비교 불가"},
}
PRIMARY = ["전반만족", "건강", "정신건강"]      # 개인 단위 = 정본

CAVEATS = {
    "household_income": (
        "`h_din` 은 **가구** 가처분소득이다. 창업한 본인의 소득이 아니라 배우자·동거가구원의 "
        "소득이 함께 들어가므로 개인 창업효과가 희석된다. KLIPS 창업효과(+47.2만원/월, 개인 "
        "월소득)와 **단위도 대상도 달라 나란히 비교하면 안 된다.** 다만 KLIPS 처럼 '자영이 "
        "되면 임금 문항이 결측이 되어 표본에서 빠지는' 생존편의는 여기엔 없다 — 가구소득은 "
        "폐업해도 관측된다."
    ),
    "self_report": (
        "만족·건강·정신건강은 자기보고 척도다. 등간 척도가 아니므로 점 단위보다 `ate_sd`"
        "(대조군 표준편차 대비)로 읽을 것. 창업 직후엔 같은 처지를 더 후하게 평가하는 쪽으로 "
        "기준이 이동할 수 있다(response shift)."
    ),
    "control_group": (
        "대조군은 '그 해에 임금근로를 유지한 사람'이다. 기존 first-event 패널의 대조군"
        "('25~35세 내내 한 번도 창업하지 않은 사람')과 다르며, 그쪽을 쓰면 창업 성향이 없는 "
        "사람이 대조군에 몰려 효과가 부풀려진다."
    ),
}


# 창업 + 생활사건(train_koweps_life.py)이 함께 쓰는 열. 1.4GB 를 두 번 읽지 않도록
# 한 벌로 모아 캐시한다.
COLUMNS = [
    "h_pid", "wv", "year",
    "h_g3", "h_g4", "h_g6",                       # 성별·출생연도·교육수준
    "p02_1",                                      # 근로유형(창업 처치)
    "h_g10", "h06_3", "h06_aq1", "h01_1",         # 혼인·점유형태·이사·가구원수
    "h_eco9", "h_eco6",                           # 직종·근로시간형태
    "h_din",                                      # 가구 가처분소득
    "h_med2", "p05_11",                           # 건강·우울
    "p03_7", "p03_8", "p03_10", "p03_12",         # 주거·가족·사회관계·전반 만족
]


def load_columns() -> pd.DataFrame:
    """필요한 열만 읽는다(1.4GB 전체를 올리지 않는다). 한 번 읽으면 캐시한다."""
    if CACHE.exists():
        cached = pd.read_pickle(CACHE)
        if set(COLUMNS) <= set(cached.columns):
            return cached                          # 열이 늘면 아래에서 다시 읽는다
    cols = COLUMNS
    df = pd.read_stata(RAW, columns=cols, convert_categoricals=False)
    for c in df.select_dtypes("number").columns:
        if c not in ("year", "wv", "h_g4"):
            df[c] = df[c].mask(df[c] < 0)
    df["age"] = df["year"] - df["h_g4"]
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    df.to_pickle(CACHE)
    return df


def clean_outcome(s: pd.Series, meta: dict) -> pd.Series:
    """무응답(9) 제거 → 척도 범위 확인 → 필요 시 역코딩(클수록 좋음)."""
    if meta["top"] is None:                      # 연속형(소득)
        return s.mask(s <= 0)
    v = s.mask(s >= MISSING_CODE)
    v = v.where(v.between(1, meta["top"]))
    return (meta["top"] + 1) - v if meta["reverse"] else v


def transition_frame(df: pd.DataFrame, outcome: str, horizon: int,
                     age_band: tuple[int, int]) -> pd.DataFrame:
    """t 시점 임금근로자 + t+1 전이 + t+horizon 결과."""
    meta = OUTCOMES[outcome]
    d = df.sort_values(["h_pid", "wv"]).copy()
    d["_y"] = clean_outcome(d[meta["src"]], meta)
    g = d.groupby("h_pid", sort=False)
    nxt_type = g["p02_1"].shift(-1)
    nxt_wv = g["wv"].shift(-1)
    out_y = g["_y"].shift(-horizon)
    out_wv = g["wv"].shift(-horizon)

    frame = pd.DataFrame({
        "pid": d["h_pid"],
        "age": d["age"], "sex": d["h_g3"], "edu": d["h_g6"],
        "income_now": d["h_din"], "occ": d["h_eco9"],
        "work_hours_type": d["h_eco6"], "household_size": d["h01_1"],
        "outcome_now": d["_y"],
        "type_now": d["p02_1"], "type_next": nxt_type,
        "gap1": nxt_wv - d["wv"], "gap_h": out_wv - d["wv"],
        "y": out_y,
    })
    frame = frame[(frame["gap1"] == 1) & (frame["gap_h"] == horizon)]
    # 처치 = 임금근로 → 자영·고용주, 대조 = 임금근로 유지. 그 외는 제외.
    at_risk = frame["type_now"] == 1
    frame = frame[at_risk & frame["type_next"].isin([1, 2])]
    frame["T"] = (frame["type_next"] == 2).astype(int)
    frame = frame.dropna(subset=["y", "age", "sex", "edu", "income_now"])
    frame = frame[frame["age"].between(*age_band)]
    for c in ("occ", "work_hours_type", "household_size"):
        frame[c] = frame[c].fillna(frame[c].median())
    return frame


def fit(d: pd.DataFrame, w_cols: list[str], label: str) -> dict | None:
    from econml.dml import LinearDML
    from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier

    n_t = int(d["T"].sum())
    if n_t < MIN_TREATED:
        print(f"    {label} 처치 {n_t} < {MIN_TREATED} → 생략")
        return None
    y = d["y"].to_numpy(dtype=float)
    t = d["T"].to_numpy()
    ctrl_sd = float(np.std(y[t == 0], ddof=1))
    naive = float(y[t == 1].mean() - y[t == 0].mean())

    est = LinearDML(
        model_y=RandomForestRegressor(n_estimators=100, min_samples_leaf=20,
                                      random_state=42),
        model_t=RandomForestClassifier(n_estimators=100, min_samples_leaf=20,
                                       random_state=42),
        discrete_treatment=True, random_state=42,
    )
    X = d[X_COLS].to_numpy()
    try:
        est.fit(y, t, X=X, W=d[w_cols].to_numpy())
        ate = float(est.ate(X))
        lo, hi = (float(v) for v in est.ate_interval(X, alpha=0.05))
    except Exception as exc:                      # noqa: BLE001
        print(f"    {label} 적합 실패({type(exc).__name__}) → 생략")
        return None

    sig = "유의" if lo > 0 or hi < 0 else "비유의"
    print(f"    {label} ATE {ate:+9.3f} (CI {lo:+9.3f}~{hi:+9.3f}) {sig} | "
          f"표준화 {ate / ctrl_sd:+.3f}SD | 단순차 {naive:+.3f} | "
          f"n={len(d):,} 처치 {n_t:,}")
    return {
        "ate": round(ate, 4), "ci": [round(lo, 4), round(hi, 4)],
        "significant": bool(lo > 0 or hi < 0),
        "ate_sd": round(ate / ctrl_sd, 4), "control_sd": round(ctrl_sd, 4),
        "control_mean": round(float(y[t == 0].mean()), 4),
        "naive_diff": round(naive, 4),
        "n": int(len(d)), "n_treated": n_t, "w_cols": list(w_cols),
    }


def measure(df, outcome: str, horizon: int, age_band, with_comparison: bool) -> dict | None:
    d = transition_frame(df, outcome, horizon, age_band)
    is_income = OUTCOMES[outcome]["level"] == "가구"
    if is_income:
        # 가구소득은 W 의 income_now 가 곧 직전 Y 라 이미 통제돼 있다.
        return fit(d, W_COLS, f"[{outcome}]")
    plain = fit(d, W_COLS, f"[{outcome} 통제전]") if with_comparison else None
    main = fit(d.dropna(subset=["outcome_now"]), [*W_COLS, "outcome_now"],
               f"[{outcome} 정본]  ")
    if main is None:
        return None
    main["baseline_controlled"] = True
    if plain:
        main["without_baseline_control"] = plain
    return main


def main() -> None:
    ap = argparse.ArgumentParser(description="KOWEPS 창업 처치효과")
    ap.add_argument("--horizon", type=int, default=1)
    args = ap.parse_args()

    df = load_columns()
    report = {
        "built_at": datetime.now(timezone.utc).isoformat(),
        "source": "KOWEPS 1~20차 (2006~2025) Long Form",
        "treatment": "p02_1 1(임금근로자) → 2(자영업·고용주). 대조 = 임금근로 유지",
        "treatment_coding_source": "결합데이터(1-20차) 코드북 문항내용 — 추론이 아님",
        "horizon": args.horizon,
        "estimator": "LinearDML (RF nuisance, 분석적 95% CI)",
        "min_treated": MIN_TREATED,
        "x_cols": X_COLS, "w_cols": W_COLS,
        "primary_outcomes": PRIMARY,
        "outcomes": OUTCOMES,
        "caveats": CAVEATS,
        "bands": {},
    }

    # 20-45 = KLIPS 와 같은 밴드(직접 비교용) / 20-39 = 서비스 타겟(20~30대)
    for band, with_cmp in [((20, 45), True), ((20, 39), False)]:
        key = f"{band[0]}-{band[1]}"
        print(f"\n=== 연령 {key} (t+{args.horizon}) ===")
        got = {}
        for outcome in OUTCOMES:
            if (res := measure(df, outcome, args.horizon, band, with_cmp)) is not None:
                got[outcome] = res
        report["bands"][key] = got

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    print(f"\n[done] → {OUT_PATH}")


if __name__ == "__main__":
    main()
