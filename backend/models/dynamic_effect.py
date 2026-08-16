"""L3 인과효과의 **시간 프로파일** (동적 처치효과) + 불확실성 밴드.

## 왜 필요한가
기존 `core.py` 는 L3 점추정 `effect` 하나를 10년 궤적의 p25·p50·p75 **전부에 같은
값으로** 더했다. 두 가지가 틀렸다.

1. **효과가 시간에 따라 변한다.** KLIPS 로 상대시간별 ATE 를 따로 추정하면
   이직은 t+1 +6.6만(95% CI 가 0을 포함) → t+4 +16.7만으로 **커진다**.
   상수로 더하면 1년차는 과대, 4년차는 과소 추정이 된다.
2. **불확실성이 밴드에 안 실렸다.** p25 와 p75 에 같은 값을 더하니 분포 폭이 그대로
   였다. 인과추정의 95% CI 는 계산해 놓고 표시만 했지 궤적엔 반영되지 않았다.

이 모듈은 `train_treatments.py` 가 만든 `dynamic_effects.json` 을 읽어 연차별
`(효과, CI 하한offset, CI 상한offset)` 을 돌려준다.

## 개인 이질효과와 합치는 방식 — 곱이 아니라 합
개인별 효과 `e`(CausalForest, t+1 기준)에 시간 형태를 입힐 때 비율(ate_h/ate_1)을
쓰면 ate_1 이 0 근처일 때 폭발한다(이직 ate_1=6.55 → t+4 배율 2.6배).
그래서 **가산 방식** `e + (ate_h − ate_1)` 을 쓴다. 개인 이질성은 상수 오프셋으로
보존하고, 데이터가 실제로 말하는 건 시간에 따른 **변화량**뿐이라고 보는 셈이다.

## 관측 밖 연차
프로파일은 표본이 버티는 h 까지만 있다(이직·창업 모두 t+4~5). 그 뒤 연차는 마지막
관측값을 그대로 끌고 가되 `extrapolated=True` 로 표시한다. 값을 늘리거나 CI 를
좁히지 않는다 — 모르는 구간을 아는 척하지 않기 위해서.
"""

from __future__ import annotations

import json
from functools import lru_cache

from config import settings

PROFILE_PATH_NAME = "dynamic_effects.json"


@lru_cache(maxsize=1)
def _profiles() -> dict:
    p = settings.artifacts_abspath / PROFILE_PATH_NAME
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def has_profile(treatment: str) -> bool:
    return bool(_profiles().get(treatment, {}).get("horizons"))


def profile_meta(treatment: str) -> dict | None:
    """연차별 ATE 프로파일 요약 — 응답에 근거로 실어 보내기 위한 것."""
    prof = _profiles().get(treatment)
    if not prof or not prof.get("horizons"):
        return None
    hz = prof["horizons"]
    years = sorted(int(h) for h in hz)
    return {
        "treatment": treatment,
        "label": prof.get("label"),
        "source": prof.get("source"),
        "caveat": prof.get("caveat"),
        "max_observed_year": years[-1],
        "by_year": {int(h): {"ate": hz[h]["ate"], "ci_low": hz[h]["ci_low"],
                             "ci_high": hz[h]["ci_high"], "n_treated": hz[h]["n_treated"]}
                    for h in hz},
        "method": "LinearDML, 상대시간 h 별 개별 적합 (95% analytic CI)",
        "note": ("프로파일(효과의 시간 형태)은 KLIPS 전연령 종단에서 추정한다. "
                 "개인별 점추정(causal_effect)은 연령대에 맞는 모델(청년=YP)에서 오므로, "
                 "궤적은 '수준=연령대 모델 / 변화 형태=KLIPS' 조합이다."),
    }


def effect_at(treatment: str, year: int) -> dict | None:
    """연차 `year` 의 {ate, ci_low, ci_high, extrapolated}. 프로파일 없으면 None."""
    hz = _profiles().get(treatment, {}).get("horizons") or {}
    if not hz or year < 1:
        return None
    years = sorted(int(h) for h in hz)
    h = year if year in years else years[-1]      # 관측 밖 → 마지막 관측값 유지
    e = hz[str(h)]
    return {"ate": float(e["ate"]), "ci_low": float(e["ci_low"]),
            "ci_high": float(e["ci_high"]), "n_treated": e.get("n_treated"),
            "basis_year": h, "extrapolated": h != year}


def shift_at(treatment: str, year: int, base_effect: float) -> dict | None:
    """연차 `year` 에 궤적을 얼마나 밀고, 밴드를 얼마나 벌릴지.

    반환 {shift, band_low, band_high, extrapolated, basis_year}
      · shift      = p50 에 더할 값 (개인효과 + 시간에 따른 변화량)
      · band_low   = p25 에 **추가로** 더할 음수 오프셋 (CI 하한 − ATE)
      · band_high  = p75 에 **추가로** 더할 양수 오프셋 (CI 상한 − ATE)

    base_effect 는 t+1 기준 개인별 효과(L3 점추정). 프로파일이 없으면 None 을
    돌려주고, 호출부는 기존처럼 상수 오프셋으로 폴백한다.
    """
    e1 = effect_at(treatment, 1)
    eh = effect_at(treatment, year)
    if e1 is None or eh is None:
        return None
    return {
        "shift": round(base_effect + (eh["ate"] - e1["ate"]), 1),
        "band_low": round(eh["ci_low"] - eh["ate"], 1),
        "band_high": round(eh["ci_high"] - eh["ate"], 1),
        "ate": eh["ate"],
        "basis_year": eh["basis_year"],
        "extrapolated": eh["extrapolated"],
    }
