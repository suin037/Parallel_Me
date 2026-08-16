"""소득 외 결과변수(만족·건강)의 처치효과 — `train_treatments.py` 의 Y 확장판.

## 왜 필요한가
L3 의 결과변수는 오랫동안 `월소득_실질` 하나였다. 그런데 이직의 인과효과는 소득에서
**≈0(비유의)** 로 나온다. 그래서 "이직해도 소득은 그대로" 까지만 말할 수 있었고,
정작 사람들이 그 선택으로 바꾸려던 것(일이 견딜 만해지는가, 삶이 나아지는가,
몸이 상하지 않는가)에 대해서는 데이터가 침묵했다.

KLIPS 12~27차에는 전 차수 같은 코드로 만족·건강 5점 문항이 있다. 처치(T)·혼재변수(W)·
이질성(X) 정의는 결과변수와 무관하므로, `train_treatments.py` 의 뼈대를 그대로 import
해서 **Y 만 갈아끼운다.** 처치 정의가 두 벌로 갈라지면 소득 효과와 만족 효과가 서로
다른 모집단 위에서 나오게 되므로, 여기서는 새로 정의하지 않는다.

## 결과변수
| 컬럼 | 단위 | 응답 대상 |
|---|---|---|
| `월소득_실질` | 만원/월 | 소득 있는 사람 (기준선 — 기존 결과 재현 확인용) |
| `직무만족` | 1~5, **클수록 좋음** | 취업자만 |
| `생활만족` | 1~5, 클수록 좋음 | 전체 |
| `건강` | 1~5, 클수록 좋음 | 전체 |
| `근무환경만족` `근로시간만족` | 1~5, 클수록 좋음 | 취업자만 (`--outcomes` 로 추가) |

5점 척도는 `preprocess/preprocess_klips.py` 에서 이미 역코딩(6−x)돼 저장된다. 원본은
1=가장 좋음 이라 뒤집지 않으면 **모든 부호가 반대로 나온다.**

## 추정
`LinearDML`(분석적 95% CI)만 쓴다. `train_treatments.py` 가 이미 `prefer_linear=True`
로 두고 있고, 처치군이 작은 treatment 에서 CausalForest 구간은 참고용이기 때문이다.
결과가 5점 척도라 점 단위 효과는 크기 감이 안 잡히므로 **대조군 표준편차로 나눈
표준화 효과(`ate_sd`)** 를 함께 낸다.

`naive_diff`(처치군−대조군 원시 평균차)를 같이 싣는다. ATE 와 벌어지는 폭이 곧
"이 숫자를 그냥 평균 비교로 냈으면 얼마나 틀렸는가" 다.

## ⚠ 직전 Y 통제 (이 스크립트의 핵심 설계)
소득 모델의 W 에는 `income_now`(t 시점 소득)가 들어 있다 — 즉 **직전 Y 를 통제**한
설계다. 만족·건강에 같은 W 를 그대로 쓰면 그 통제가 사라진다. 그러면

    건강이 나빠서 쉰 사람  →  '쉬어서 건강이 나빠졌다'

처럼 **역인과가 효과로 잡힌다.** 그래서 소득 외 Y 에서는 t 시점의 같은 문항
(`outcome_now`)을 W 에 추가해 소득 모델과 대칭을 맞춘다.

두 설계를 **다 낸다.** `without_baseline_control` 에 통제 전 추정치를 함께 실어,
둘의 간격이 곧 "직전 상태를 안 잡았을 때 새는 양" 으로 읽히게 한다. 표본도 달라지는데
(직전 문항 무응답이 빠진다) 그 수치도 같이 남긴다.

산출:
    backend/models/artifacts/outcome_effects.json

사용법:
    python train_outcomes.py
    python train_outcomes.py --outcomes 직무만족,건강 --horizon 3
    python train_outcomes.py --outcomes 월소득_실질,직무만족,생활만족,건강,근무환경만족,근로시간만족
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

import numpy as np

import train_treatments as TT

ARTIFACTS = TT.ARTIFACTS
OUT_PATH = ARTIFACTS / "outcome_effects.json"

# 결과변수 메타 — 서빙이 단위와 방향을 알아야 문장을 만들 수 있다.
OUTCOMES = {
    "월소득_실질": {"label": "월소득", "unit": "만원", "scale": "continuous",
                    "higher_is_better": True,
                    "note": "기준선. 기존 econml_klips*.pkl 과 같은 Y"},
    "직무만족": {"label": "일자리 만족", "unit": "점(1~5)", "scale": "likert5",
                 "higher_is_better": True,
                 "note": "취업자만 응답 — t+h 에 일하고 있지 않으면 결과 미관측"},
    "생활만족": {"label": "생활 만족", "unit": "점(1~5)", "scale": "likert5",
                 "higher_is_better": True, "note": "전체 응답자"},
    "건강": {"label": "주관적 건강", "unit": "점(1~5)", "scale": "likert5",
             "higher_is_better": True, "note": "전체 응답자"},
    "근무환경만족": {"label": "근무환경 만족", "unit": "점(1~5)", "scale": "likert5",
                     "higher_is_better": True, "note": "취업자만 응답"},
    "근로시간만족": {"label": "근로시간 만족", "unit": "점(1~5)", "scale": "likert5",
                     "higher_is_better": True, "note": "취업자만 응답"},
}
DEFAULT_OUTCOMES = ["월소득_실질", "직무만족", "생활만족", "건강"]

# 결과변수를 바꿔도 그대로 남는 주의사항 + 결과변수 때문에 새로 생기는 주의사항.
# 만족·건강은 소득과 달리 '보고된 값' 이라, 같은 삶이어도 기준이 움직인다.
OUTCOME_CAVEATS = {
    "likert5": (
        "자기보고 5점 척도다. (1) 응답 기준 자체가 이동한다 — 이직 직후엔 같은 처지를 "
        "더 후하게 평가하는 쪽으로 기울 수 있다(response shift). (2) 등간 척도가 "
        "아니므로 '2→3' 과 '4→5' 를 같은 크기로 읽으면 안 된다. 점 단위보다 "
        "`ate_sd`(대조군 표준편차 대비)로 읽을 것. (3) 소득과 달리 상한(5점)이 있어 "
        "이미 만족도가 높은 층에서는 효과가 눌린다(천장효과)."
    ),
    "worker_only": (
        "취업자만 응답하는 문항이라, t+h 에 일하고 있지 않으면 결과가 관측되지 않는다. "
        "'쉬어가기' 처치에서는 복귀한 사람만 남으므로 소득 효과와 **같은 종류의** "
        "생존편의가 그대로 남는다."
    ),
}

# 처치 쪽 caveat 은 train_treatments.py 의 것을 그대로 쓴다(두 벌로 관리하지 않는다).
TREATMENT_CAVEATS = TT.CAVEATS


def _fit(d, w_cols: list[str], label: str, outcome: str, tag: str) -> dict | None:
    """주어진 W 집합으로 한 번 적합 → 요약 dict. 게이트·수렴 실패는 None."""
    n_t = int(d["T"].sum())
    if n_t < TT.MIN_TREATED:
        print(f"  [{label} × {outcome}]{tag} 처치 {n_t} < {TT.MIN_TREATED} → 생략")
        return None

    y = d["y"].to_numpy(dtype=float)
    t = d["T"].to_numpy()
    ctrl_sd = float(np.std(y[t == 0], ddof=1))
    naive = float(y[t == 1].mean() - y[t == 0].mean())

    try:
        _, ate, lo, hi = TT.fit_linear_dml(d, w_cols=w_cols)
    except Exception as exc:                      # 수렴 실패 등
        print(f"  [{label} × {outcome}]{tag} 적합 실패({type(exc).__name__}) → 생략")
        return None

    sig = "유의" if lo > 0 or hi < 0 else "비유의"
    print(f"  [{label} × {outcome:12s}]{tag} ATE {ate:+8.3f} "
          f"(CI {lo:+8.3f}~{hi:+8.3f}) {sig} | 표준화 {ate / ctrl_sd:+.3f}SD | "
          f"단순차 {naive:+.3f} | n={len(d):,} 처치 {n_t:,}")

    return {
        "ate": round(ate, 4),
        "ci": [round(lo, 4), round(hi, 4)],
        "significant": bool(lo > 0 or hi < 0),
        "ate_sd": round(ate / ctrl_sd, 4),         # 대조군 SD 대비 — 척도 간 비교용
        "control_sd": round(ctrl_sd, 4),
        "control_mean": round(float(y[t == 0].mean()), 4),
        "naive_diff": round(naive, 4),             # 혼재변수 미통제 단순 평균차
        "n": int(len(d)),
        "n_treated": n_t,
        "w_cols": list(w_cols),
    }


def measure(b, key: str, label: str, outcome: str, horizon: int) -> dict | None:
    """(처치 × 결과변수) 하나의 ATE.

    소득 외 Y 는 **직전 Y 통제본이 정본**이고, 통제 없는 추정치는 비교용으로
    `without_baseline_control` 에 붙인다(둘의 차이가 역인과·상태지속의 크기다).
    소득 Y 는 W 에 이미 `income_now` 가 있어 한 번만 적합한다.
    """
    d = TT.apply_treatment(TT.transition_frame(b, horizon, outcome=outcome), key)
    is_income = outcome == "월소득_실질"

    if is_income:
        return _fit(d, TT.W_COLS, label, outcome, "")

    plain = _fit(d, TT.W_COLS, label, outcome, " [통제전]")
    # 직전 문항에 응답한 사람만 남는다 — 표본이 줄어드는 건 설계상 정상이다.
    d_ctrl = d.dropna(subset=["outcome_now"])
    main = _fit(d_ctrl, [*TT.W_COLS, "outcome_now"], label, outcome, " [정본]  ")
    if main is None:
        return None
    main["without_baseline_control"] = plain
    main["baseline_controlled"] = True
    return main


def main() -> None:
    ap = argparse.ArgumentParser(description="소득 외 결과변수의 처치효과")
    ap.add_argument("--outcomes", default=",".join(DEFAULT_OUTCOMES))
    ap.add_argument("--horizon", type=int, default=1,
                    help="t+h 의 h. 기본 1 (전이 다음 해)")
    ap.add_argument("--treatments", default=",".join(k for k, _ in TT.TREATMENTS))
    args = ap.parse_args()

    outcomes = [o.strip() for o in args.outcomes.split(",") if o.strip()]
    if unknown := [o for o in outcomes if o not in OUTCOMES]:
        raise SystemExit(f"모르는 결과변수: {unknown} (가능: {list(OUTCOMES)})")
    want = {k.strip() for k in args.treatments.split(",") if k.strip()}

    b = TT.load_panel()
    if missing := [o for o in outcomes if o not in b.columns]:
        raise SystemExit(
            f"klips_base.pkl 에 {missing} 없음 — "
            "preprocess/preprocess_klips.py 를 다시 실행할 것(만족·건강 컬럼 추가본)."
        )

    report = {
        "built_at": datetime.now(timezone.utc).isoformat(),
        "source": TT.PANEL_LABEL,
        "horizon": args.horizon,
        "age_band": [TT.AGE_MIN, TT.AGE_MAX],
        "min_treated": TT.MIN_TREATED,
        "estimator": "LinearDML (RF nuisance, 분석적 95% CI)",
        "x_cols": TT.X_COLS, "w_cols": TT.W_COLS,
        "baseline_control": ("소득 외 Y 는 W 에 t 시점 같은 문항(outcome_now)을 더한 "
                             "것이 정본이다. 소득 모델의 income_now 와 같은 역할 — "
                             "직전 상태를 통제하지 않으면 '건강이 나빠서 쉰 것' 이 "
                             "'쉬어서 건강이 나빠진 것' 으로 잡힌다. 통제 없는 값은 "
                             "each effect 의 without_baseline_control 에 있다."),
        "note": ("처치·대조군 정의는 train_treatments.py 와 동일하다(Y 만 교체). "
                 "혼재변수에 t 시점 소득이 들어가므로 표본은 '전이 시점에 소득이 "
                 "관측된 사람' 으로 제한된다 — 소득 모델과 같은 모집단이다."),
        "outcomes": {o: OUTCOMES[o] for o in outcomes},
        "outcome_caveats": OUTCOME_CAVEATS,
        "effects": {},
    }

    for key, label in TT.TREATMENTS:
        if key not in want:
            continue
        print(f"\n=== {label}({key}) — 결과변수 {len(outcomes)}개, t+{args.horizon} ===")
        got = {}
        for outcome in outcomes:
            if (res := measure(b, key, label, outcome, args.horizon)) is not None:
                res["caveats"] = [c for c in (
                    TREATMENT_CAVEATS.get(key),
                    OUTCOME_CAVEATS["likert5"]
                    if OUTCOMES[outcome]["scale"] == "likert5" else None,
                    OUTCOME_CAVEATS["worker_only"]
                    if "취업자만" in OUTCOMES[outcome]["note"] else None,
                ) if c]
                got[outcome] = res
        if got:
            report["effects"][key] = {"label": label, "outcomes": got}
        else:
            report["effects"][key] = {"label": label, "outcomes": {},
                                      "reason": "표본 게이트 미만 — 추정하지 않음"}

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    print(f"\n[done] → {OUT_PATH}")


if __name__ == "__main__":
    main()
