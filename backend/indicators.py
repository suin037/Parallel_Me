"""3지표 산출기 (엔진 L1~L5 출력 → 경제적안정도·성장가능성·삶의질, 0~1).

- 입력: /compare 의 ScenarioView(dict) — 소득 궤적·만족도·후회·성장% 등.
- 출력: {"경제적안정도":0~1, "성장가능성":0~1, "삶의질":0~1} (무언더스코어 = 계약 정본).
- 이 점수를 rag/psych_narrative.get_psych_evidence() 에 그대로 넘겨 심리카드를 검색한다.
- '지표 산출'은 KNN(레이어2)과 별개 단계다. (용어 충돌 방지: L2=유사인물 매칭, 지표=여기)

## v2 — 매직넘버에서 백분위 순위로
예전 공식은 이랬다.

    econ = 0.35 + (income-250)/300*0.40 + max(change,0)*0.8 - regret/100*0.15
    grow = 0.25 + growth5/40*0.9 + max(change,0)*0.4

전부 손튜닝 상수였고 두 가지가 깨져 있었다.

1. **의미가 없다.** 0.62 가 좋은 건지 말할 수 없고 캘리브레이션할 기준도 없다.
2. **지표 간 비교가 깨진다.** `psych_narrative.select_focus()` 는 세 지표 중 가장
   낮은 걸 골라 심리카드를 검색하는데, 세 공식의 절편·기울기가 제각각이라
   '어떤 지표가 가장 낮은가' 를 사용자 상태가 아니라 공식 상수가 결정했다.
   → **어떤 이론카드가 뽑히는지가 매직넘버에 좌우됐다.**

이제 각 구성요소를 실제 분포의 **백분위 순위**로 바꾼다(기준 분포는
`scripts/build_indicator_reference.py` 가 만든 indicator_reference.json).
  · 0.62 = "같은 나이대에서 상위 38%" 라는 해석이 생긴다
  · 세 지표가 같은 척도에 놓여 '가장 낮은 지표' 비교가 성립한다
  · 분포가 바뀌면 스크립트만 다시 돌려 재캘리브레이션한다

합성 가중치(아래 WEIGHTS)는 여전히 사람이 정한 값이지만, **합이 1인 배분 비율**이고
각 항이 이미 공통 척도(백분위)라 남은 자유도가 훨씬 작다. 무엇보다 근거를
`components` 로 함께 내보내 어떤 항이 점수를 끌어내렸는지 확인할 수 있다.

기준 분포 파일이 없으면 예전 공식으로 폴백하고 `method` 에 그 사실을 적는다.
"""

from __future__ import annotations

import json
from functools import lru_cache

from config import settings

# 계약 정본 키(언더스코어 없음). 언더스코어 별칭은 psych 계층이 정규화한다.
INDICATOR_KEYS = ["경제적안정도", "성장가능성", "삶의질"]

# 합성 배분(각 지표별 합=1). 항은 전부 0~1 백분위라 서로 더할 수 있다.
WEIGHTS = {
    "경제적안정도": {"income_level": 0.65, "income_growth": 0.20, "low_exit_risk": 0.15},
    "성장가능성":   {"income_growth": 1.00},
    "삶의질":       {"satisfaction": 0.75, "low_exit_risk": 0.25},
}


def evidence_statuses(kind: str, validated_prediction: dict | None = None,
                      provided_scores: dict | None = None,
                      scenario: dict | None = None) -> dict:
    """3지표 숫자와 근거 수준을 분리한 계약.

    legacy 0~1 점수는 화면 호환용일 뿐 검증된 예측으로 승격하지 않는다.
    명시적으로 제공된 점수만 사용자 상태 신호로 심리 RAG에 사용할 수 있다.
    """
    if provided_scores:
        return {
            key: {
                "status": "user_provided_state",
                "score": provided_scores.get(key),
                "eligible_for_psych_rag": provided_scores.get(key) is not None,
                "reason": "사용자가 제공한 현재 상태 점수이며 미래 예측값이 아님",
            }
            for key in INDICATOR_KEYS
        }

    if kind == "이직":
        vp = validated_prediction or {}
        observed_domains = ((vp.get("observed_outcomes") or {}).get("domains") or {})
        has_growth = any(item.get("available") for item in observed_domains.get("growth", []))
        has_life = any(item.get("available") for item in observed_domains.get("quality_of_life", []))
        pop = vp.get("population_evidence") or {}
        effect = pop.get("effect")
        financial_status = "directional_evidence" if effect is not None else "insufficient_evidence"
        return {
            "경제적안정도": {
                "status": financial_status,
                "score": None,
                "direction": "positive" if effect is not None and effect > 0 else "uncertain",
                "effect": effect,
                "unit": pop.get("unit"),
                "ci95": pop.get("ci95"),
                "eligible_for_psych_rag": False,
                "reason": "집단 임금효과의 방향 근거이며 개인의 현재 심리 상태 점수가 아님",
            },
            "성장가능성": {
                "status": "matched_observation" if has_growth else "insufficient_evidence", "score": None,
                "eligible_for_psych_rag": False,
                "reason": "유사 집단의 실제 경력상태 전환 관측값" if has_growth else "최근 연도 검증에서 성장 효과가 재현되지 않음",
            },
            "삶의질": {
                "status": "matched_observation" if has_life else "insufficient_evidence", "score": None,
                "eligible_for_psych_rag": False,
                "reason": "유사 집단의 만족·행복·건강·웰빙 변화 관측값" if has_life else "반복 검증에서 삶의 질 효과가 안정적이지 않음",
            },
        }

    if kind == "창업":
        scen = scenario or {}
        raw = scen.get("raw") or {}
        conf = scen.get("confidence") or {}
        causal = conf.get("causal_effect_ci") or {}
        effect = raw.get("causal_effect")
        has_survival = raw.get("survival_months") is not None
        return {
            "경제적안정도": {
                "status": "directional_evidence" if effect is not None else "insufficient_evidence",
                "score": None, "effect": effect,
                "unit": causal.get("unit"),
                "ci95": ([causal.get("ci95_low"), causal.get("ci95_high")]
                         if causal.get("ci95_low") is not None else None),
                "eligible_for_psych_rag": False,
                "reason": ("KLIPS 임금근로→자영 전환의 신고소득 방향 근거. "
                           "임금과 사업소득의 개념 차이·생존편의를 포함해 개인 수익 예측으로 해석할 수 없음"),
            },
            "성장가능성": {
                "status": "proxy_observation" if has_survival else "insufficient_evidence",
                "score": None, "eligible_for_psych_rag": False,
                "reason": ("KLIPS 자영 상태 지속·이탈 모델은 사업 지속가능성의 부분 대리지표이며 "
                           "역량·직업성장을 직접 측정하지 않음" if has_survival else
                           "창업 후 역량·직업성장을 직접 측정한 검증 결과가 없음"),
            },
            "삶의질": {
                "status": "insufficient_evidence", "score": None,
                "eligible_for_psych_rag": False,
                "reason": "창업 표본의 선택별 만족도·건강·웰빙 경로가 표본 부족으로 검증되지 않음",
            },
        }

    vp = validated_prediction or {}
    observed = vp.get("observed_outcomes") or {}
    if kind == "유지" and observed.get("status") == "available":
        return {
            "경제적안정도": {"status": "matched_observation", "score": None, "eligible_for_psych_rag": False, "reason": "유사 유지 집단의 관측 결과"},
            "성장가능성": {"status": "matched_observation", "score": None, "eligible_for_psych_rag": False, "reason": "유지 집단의 실제 경력상태 전환 관측값"},
            "삶의질": {"status": "matched_observation", "score": None, "eligible_for_psych_rag": False, "reason": "유지 집단의 만족·행복·건강·웰빙 변화 관측값"},
        }

    reason = "해당 선택의 검증된 개인 예측모델이 없어 집단통계·관측값만 제공"
    return {
        key: {"status": "reference_only", "score": None,
              "eligible_for_psych_rag": False, "reason": reason}
        for key in INDICATOR_KEYS
    }


def psych_eligible_scores(statuses: dict) -> dict:
    """미래 예측값을 심리 상태처럼 사용하는 것을 차단한다."""
    return {
        key: item["score"] for key, item in (statuses or {}).items()
        if item.get("eligible_for_psych_rag") and item.get("score") is not None
    }


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _avail(arr):
    return [p for p in (arr or []) if p.get("available")]


def _last(arr):
    a = _avail(arr)
    return a[-1] if a else None


@lru_cache(maxsize=1)
def _reference() -> dict | None:
    p = settings.artifacts_abspath / "indicator_reference.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _band(ref: dict, age: float | None) -> str:
    """나이 → 기준 분포 나이대 키. 범위 밖이거나 나이가 없으면 전체 분포."""
    if age is None:
        return "all"
    for lo, hi in ref.get("age_bands", []):
        if lo <= age <= hi:
            return f"{lo}-{hi}"
    return "all"


def _pct(grid: list | None, x: float | None) -> float | None:
    """분위점 격자에서 값 x 의 백분위 순위(0~1). 격자 밖은 0/1 로 잘린다."""
    if not grid or x is None:
        return None
    n = len(grid)
    if x <= grid[0]:
        return 0.0
    if x >= grid[-1]:
        return 1.0
    for i in range(1, n):
        if x <= grid[i]:
            lo, hi = grid[i - 1], grid[i]
            frac = 0.0 if hi == lo else (x - lo) / (hi - lo)
            return (i - 1 + frac) / (n - 1)
    return 1.0


def _risk_grid(ref: dict, year: int | None, source_hint: str | None) -> list | None:
    """연차별 이탈확률 기준 격자. 후회 값이 몇 년차 것인지에 맞춰 고른다.

    10년 확률을 5년 분포에 대보면 누구나 '위험 상위' 가 된다 → 연차를 맞춘다.
    """
    d = (ref.get("dists", {}).get("exit_risk") or {}).get(str(year))
    if not d:
        return None
    if source_hint:
        for key in d:
            if key in source_hint.lower():
                return d[key]
    return next(iter(d.values()))


def compute_indicators_detail(scen: dict, baseline: float | None = None,
                              age: float | None = None) -> dict:
    """3지표 + 근거(각 구성요소의 백분위). {scores, components, method}."""
    ref = _reference()
    inc = _avail(scen.get("income"))
    first = inc[0]["value"] if inc else None
    last_pt = inc[-1] if inc else None
    last = last_pt["value"] if last_pt else None
    # 소득 백분위는 **그 소득이 실현되는 시점의 나이대** 분포에 대야 한다.
    # 26살의 10년 뒤 소득(=36살 소득)을 22~26세 분포에 대면 누구나 상위권이 된다.
    last_year = int(last_pt.get("year") or 0) if last_pt else 0

    gp = _last(scen.get("growth_potential"))
    growth5 = (gp or {}).get("value") if gp else None
    if growth5 is None and first and last:
        growth5 = (last - first) / first * 100.0

    satis = (scen.get("satisfaction_summary") or {}).get("latest")
    rs = scen.get("regret_summary") or {}
    regret = rs.get("worst_value")
    regret_year = rs.get("worst_year")

    if ref is None:
        return {"scores": _legacy(scen, baseline), "components": {}, "unmeasured": [],
                "method": "legacy-heuristic (indicator_reference.json 없음 — "
                          "scripts/build_indicator_reference.py 로 생성)"}

    band = _band(ref, age)                                    # 성장률·만족도 기준
    income_band = _band(ref, None if age is None else age + last_year)
    D = ref.get("dists", {})

    def grid(name: str, b: str = band):
        d = D.get(name) or {}
        return d.get(b) or d.get("all")

    # 이탈위험은 어떤 생존모델(KLIPS/YP)이 낸 값인지에 맞는 분포에 대야 한다.
    # regret_summary.source 엔 모델 정체가 없어 신뢰지표의 source 를 함께 본다.
    risk_src = ((scen.get("confidence") or {}).get("survival_c_index") or {}).get("source") \
        or rs.get("source") or ""

    comp = {
        "income_level": _pct(grid("income_level", income_band),
                             last if last is not None else baseline),
        "income_growth": _pct(grid("income_growth"), growth5),
        "satisfaction": _pct(grid("satisfaction"), satis),
    }
    rp = _pct(_risk_grid(ref, regret_year, risk_src),
              regret / 100.0 if regret is not None else None)
    comp["low_exit_risk"] = None if rp is None else 1.0 - rp

    scores, unmeasured = {}, []
    for key, mix in WEIGHTS.items():
        parts = {c: (comp[c], w) for c, w in mix.items() if comp.get(c) is not None}
        if not parts:
            # 근거 없음 → 중립값을 넣되 '측정 못 함'으로 표시한다. 0 으로 두면 '최악'
            # 으로 오독되고, 0.5 를 측정값처럼 두면 심리카드 초점 선택(최저 지표)이
            # 자리채우기에 좌우된다 → 호출측이 unmeasured 를 보고 빼도록 알린다.
            scores[key] = 0.5
            unmeasured.append(key)
            continue
        wsum = sum(w for _, w in parts.values())
        scores[key] = round(_clamp01(sum(v * w for v, w in parts.values()) / wsum), 3)

    return {
        "scores": scores,
        "unmeasured": unmeasured,
        "components": {k: (None if v is None else round(v, 3)) for k, v in comp.items()},
        "age_band": band,
        "income_age_band": income_band,
        "income_at_year": last_year,
        "risk_reference": {"year": regret_year, "model_hint": risk_src or None},
        "method": "percentile-rank (기준 분포: indicator_reference.json)",
        "note": "각 점수는 같은 나이대 분포에서의 백분위. 0.62 = 상위 38%. "
                "근거가 없는 구성요소는 배분에서 빠지며, 전부 없으면 0.5(중립). "
                "⚠소득 백분위는 '계속 관측된 임금근로자' 궤적을 단면 분포에 대는 것이라 "
                "탈락자가 빠진 만큼 다소 높게 나온다(구성 차이).",
    }


def compute_indicators(scen: dict, baseline: float | None = None,
                       age: float | None = None) -> dict:
    """ScenarioView(dict) → 3지표(0~1).

    반환은 **3개 키의 float 만** — `psych_narrative.select_focus()` 가 min() 으로
    최저 지표를 고르므로 다른 타입의 키가 섞이면 비교가 터진다.
    근거까지 필요하면 `compute_indicators_detail()` 을 쓴다.
    """
    return compute_indicators_detail(scen, baseline, age)["scores"]


def _legacy(scen: dict, baseline: float | None) -> dict:
    """기준 분포 파일이 없을 때의 폴백 — 예전 손튜닝 공식 그대로."""
    inc = _avail(scen.get("income"))
    first = inc[0]["value"] if inc else None
    last = inc[-1]["value"] if inc else None
    base = baseline or first or 300.0
    change = ((last - first) / first) if (first and last) else 0.0
    gp = _last(scen.get("growth_potential"))
    growth5 = (gp or {}).get("value", 0.0) or 0.0
    satis = (scen.get("satisfaction_summary") or {}).get("latest") or 3.5
    regret = (scen.get("regret_summary") or {}).get("worst_value") or 0.0

    income_level = (last or base)
    econ = 0.35 + (income_level - 250) / 300 * 0.40 + max(change, 0) * 0.8 - regret / 100 * 0.15
    grow = 0.25 + growth5 / 40 * 0.9 + max(change, 0) * 0.4
    life = satis / 5.0 - regret / 100 * 0.20
    return {"경제적안정도": round(_clamp01(econ), 3),
            "성장가능성": round(_clamp01(grow), 3),
            "삶의질": round(_clamp01(life), 3)}
