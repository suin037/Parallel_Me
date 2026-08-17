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
#
# ## v3 — 3지표에서 5축으로
# 예전 키는 ["경제적안정도", "성장가능성", "삶의질"] 이었고 세 가지가 깨져 있었다.
#
# 1. **중복 투입.** `income_growth` 가 경제적안정도(0.20)와 성장가능성(1.00)에,
#    `low_exit_risk` 가 경제적안정도(0.15)와 삶의질(0.25)에 각각 두 번 들어갔다.
#    성장가능성은 구성요소가 `income_growth` 하나뿐이라 경제적안정도의 부분집합이었다
#    — 축이 하나 는 게 아니라 같은 축을 두 번 보여준 것이다.
# 2. **이름과 내용 불일치.** '성장가능성' 이 재던 건 소득 상승률 100% 였고,
#    '경제적안정도' 는 상승률이 클수록 점수가 올라 급등하는 사람이 안정적으로 잡혔다.
# 3. **가치축과 5:3으로 안 맞음.** `value_ranking.AXES` 는 5개인데 지표가 3개라
#    관계·자기실현·안정 세 축이 전부 '삶의질' 하나로 접혔다. 온보딩에서 '가족·사랑' 을
#    골라도 '자유·자율' 을 골라도 같은 지표로 매핑돼 답이 결과에 안 남았다.
#
# 이제 지표 키를 가치축과 **같게** 둔다(AXIS_TO_INDICATOR 가 항등이 된다).
# 각 구성요소는 **정확히 한 축에만** 들어간다 — 중복 투입이 구조적으로 불가능하다.
INDICATOR_KEYS = ["경제", "성장", "관계", "자기실현", "안정"]

# 구지표(3) → 신축(5). 심리카드 태그·기존 응답 호환에 쓴다.
# '삶의질' 은 세 축으로 갈라졌으므로 역방향은 1:N 이다.
AXIS_TO_LEGACY = {
    "경제": "경제적안정도", "성장": "성장가능성",
    "관계": "삶의질", "자기실현": "삶의질", "안정": "삶의질",
}
LEGACY_TO_AXES = {
    "경제적안정도": ["경제"], "성장가능성": ["성장"],
    "삶의질": ["관계", "자기실현", "안정"],
}

# 합성 배분(각 축별 합=1).
#
# ⚠ 척도 주의: `career_growth` 만 백분위가 아니라 **관측 비율**(0~1)이다. 나머지는
#   기준 분포의 백분위 순위다. 비율과 백분위를 한 축 안에서 더하는 건 근사이며,
#   축 간 min() 비교(psych 초점 선택)에 쓰이므로 method 에 함께 적어 내보낸다.
# ⚠ YP facet 5개는 전부 1~5 일자리만족 문항이라 공통 `satisfaction` 격자에 댄다
#   (facet 별 기준 분포는 아직 없음 — build_indicator_reference.py 확장 대상).
# ⚠ 관계·안정은 선택 유형에 따라 서로 다른 항이 채워진다(KOWEPS 수준값 vs KLIPS
#   관측 변화). 없는 항은 배분에서 빠지고 남은 항끼리 재정규화되므로, 같은 가중치를
#   준 두 항은 '둘 중 있는 쪽' 또는 '둘 다 있으면 평균' 으로 동작한다.
WEIGHTS = {
    "경제":     {"income_level": 0.60, "satis_income": 0.25, "satis_stability": 0.15},
    "성장":     {"career_growth": 0.50, "satis_growth": 0.30, "satis_future": 0.20},
    "관계":     {"relation_level": 1.00, "relation_observed": 1.00},
    "자기실현":  {"autonomy_observed": 1.00},
    "안정":     {"low_exit_risk": 0.40, "health_level": 0.30, "health_observed": 0.30},
}

# 축별로 '무엇을 재는가' — 화면·서사에서 축 이름만으로는 알 수 없어 함께 내보낸다.
AXIS_MEANING = {
    "경제":     "소득 수준과 그 소득에 대한 만족·고용안정",
    "성장":     "직종·고용형태·조직규모·임금구간의 실제 이동과 자기발전·장래성 만족",
    "관계":     "가족·사회관계 만족의 변화",
    "자기실현":  "자율성과 의미 — 현재 측정 근거 없음",
    "안정":     "이탈위험과 신체·정신건강",
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

    if kind in ("이직", "유지"):
        return _observed_statuses(kind, validated_prediction)

    if kind == "창업":
        scen = scenario or {}
        raw = scen.get("raw") or {}
        conf = scen.get("confidence") or {}
        causal = conf.get("causal_effect_ci") or {}
        effect = raw.get("causal_effect")
        has_survival = raw.get("survival_months") is not None
        return {
            "경제": {
                "status": "directional_evidence" if effect is not None else "insufficient_evidence",
                "score": None, "effect": effect,
                "unit": causal.get("unit"),
                "ci95": ([causal.get("ci95_low"), causal.get("ci95_high")]
                         if causal.get("ci95_low") is not None else None),
                "eligible_for_psych_rag": False,
                "reason": ("KLIPS 임금근로→자영 전환의 신고소득 방향 근거. "
                           "임금과 사업소득의 개념 차이·생존편의를 포함해 개인 수익 예측으로 해석할 수 없음"),
            },
            "성장": {
                "status": "proxy_observation" if has_survival else "insufficient_evidence",
                "score": None, "eligible_for_psych_rag": False,
                "reason": ("KLIPS 자영 상태 지속·이탈 모델은 사업 지속가능성의 부분 대리지표이며 "
                           "역량·직업성장을 직접 측정하지 않음" if has_survival else
                           "창업 후 역량·직업성장을 직접 측정한 검증 결과가 없음"),
            },
            "관계": _insufficient("창업 표본의 선택별 가족·사회관계 만족 경로가 검증되지 않음"),
            "자기실현": _unmeasured_autonomy(),
            "안정": _insufficient("창업 표본의 선택별 건강·정신건강 경로가 표본 부족으로 검증되지 않음"),
        }

    if kind == "휴식":
        return _break_statuses()

    if kind in _LIFE_TREATMENT:
        return _life_statuses(kind)

    reason = ("해당 선택의 검증된 개인 예측모델이 없어 집단통계·관측값만 제공"
              if kind != "진학" else
              "실제 입학 사건 컬럼이 없어 학력코드 상승을 대리사건으로 썼고, 처치군 178건이 "
              "운영 게이트(200건)에 미달해 선택별 효과를 학습·서빙하지 않음 "
              "(enroll_treatment_audit.json: blocked_pending_true_enrollment_event)")
    return {
        key: {"status": "reference_only", "score": None,
              "eligible_for_psych_rag": False, "reason": reason}
        for key in INDICATOR_KEYS
    }


# ══ 축별 근거 조립 ═══════════════════════════════════════════════════════════

def _insufficient(reason: str) -> dict:
    return {"status": "insufficient_evidence", "score": None,
            "eligible_for_psych_rag": False, "reason": reason}


def _unmeasured_autonomy() -> dict:
    """자기실현 축은 어느 선택에서도 측정 근거가 없다 — 그 사실을 그대로 내보낸다.

    '자유·자율' 과 '의미·나다움' 을 직접 측정한 패널 문항이 없다. 여가만족·근로시간이
    자율성의 부분 대리 후보지만 선택별 분기가 검증되지 않았다. 숫자를 지어내는 대신
    빈 칸으로 두고 이유를 적는다.
    """
    return {"status": "unmeasured", "score": None, "eligible_for_psych_rag": False,
            "reason": "자율성·의미를 직접 측정한 검증 결과가 없어 이 축은 비워둠"}


# 관측 결과(job_change_observed_outcomes.json) 의 지표를 축으로 나눈다.
# 한 지표가 두 축에 들어가지 않도록 배타 분할한다.
_OBSERVED_AXIS: dict[str, tuple[str, tuple[str, ...] | None]] = {
    "성장": ("growth", None),                       # 도메인 전체
    "관계": ("quality_of_life", ("satisfaction_family_relationship_change",
                                "satisfaction_kin_relationship_change",
                                "satisfaction_social_relationship_change")),
    "자기실현": ("quality_of_life", ("satisfaction_leisure_change",)),
    "안정": ("quality_of_life", ("health_score_change", "health_peer_improvement",
                                "happiness_change", "wellbeing_index_change",
                                "future_optimism_change", "work_limitation_t1",
                                "other_limitation_t1")),
}


def _observed_axis_hit(domains: dict, axis: str) -> bool:
    """그 축에 배정된 관측지표 중 available 한 게 하나라도 있는가."""
    spec = _OBSERVED_AXIS.get(axis)
    if not spec:
        return False
    domain, cols = spec
    items = domains.get(domain) or []
    return any(it.get("available") and (cols is None or it.get("key") in cols)
               for it in items)


def _observed_statuses(kind: str, validated_prediction: dict | None) -> dict:
    """이직·유지 — KLIPS 관측 결과를 축별로 배분한다."""
    vp = validated_prediction or {}
    domains = ((vp.get("observed_outcomes") or {}).get("domains") or {})
    pop = vp.get("population_evidence") or {}
    effect = pop.get("effect")
    who = "이직" if kind == "이직" else "유지"

    out = {
        "경제": {
            "status": "directional_evidence" if effect is not None else "insufficient_evidence",
            "score": None,
            "direction": "positive" if effect is not None and effect > 0 else "uncertain",
            "effect": effect, "unit": pop.get("unit"), "ci95": pop.get("ci95"),
            "eligible_for_psych_rag": False,
            "reason": "집단 임금효과의 방향 근거이며 개인의 현재 심리 상태 점수가 아님",
        },
    }
    reasons = {
        "성장": (f"{who} 집단의 직종전환·고용형태개선·조직규모·임금구간 실제 관측값",
                "최근 연도 검증에서 성장 효과가 재현되지 않음"),
        "관계": (f"{who} 집단의 가족·친인척·사회관계 만족 변화 관측값",
                "관계 만족 변화가 표본 부족으로 관측되지 않음"),
        "안정": (f"{who} 집단의 건강·행복·웰빙 변화 관측값",
                "건강·웰빙 변화가 표본 부족으로 관측되지 않음"),
    }
    for axis, (ok, no) in reasons.items():
        hit = _observed_axis_hit(domains, axis)
        out[axis] = {"status": "matched_observation" if hit else "insufficient_evidence",
                     "score": None, "eligible_for_psych_rag": False,
                     "reason": ok if hit else no}

    # 자기실현은 여가만족 변화만 걸리므로 '대리 관측' 이 최대치다.
    if _observed_axis_hit(domains, "자기실현"):
        out["자기실현"] = {
            "status": "proxy_observation", "score": None, "eligible_for_psych_rag": False,
            "reason": (f"{who} 집단의 여가생활 만족 변화 관측값 — 자율성의 부분 대리이며 "
                       "의미·나다움은 측정하지 않음"),
        }
    else:
        out["자기실현"] = _unmeasured_autonomy()
    return out


def _break_statuses() -> dict:
    """휴식 — KLIPS `break` 처치(쉬어가기)가 학습돼 있는데 분기가 없어 비어 있었다."""
    tr = ((_treatment_report() or {}).get("treatments") or {}).get("break") or {}
    if not tr.get("trained"):
        return {k: {"status": "reference_only", "score": None,
                    "eligible_for_psych_rag": False,
                    "reason": "쉬어가기 처치 모델이 학습되지 않음"} for k in INDICATOR_KEYS}
    ate, n = tr.get("ate"), tr.get("n_treated")
    return {
        "경제": {"status": "directional_evidence", "score": None, "effect": ate,
                "unit": "만원", "eligible_for_psych_rag": False,
                "reason": (f"KLIPS 쉬어가기 전이의 소득 방향 근거(처치군 {n}건). "
                           "쉬는 동안의 소득 공백이 아니라 복귀 후 관측 소득의 차이다")},
        "성장": _insufficient("쉬어가기 후 직종·고용형태 이동을 직접 관측한 검증 결과가 없음"),
        "관계": _insufficient("쉬어가기 표본의 관계 만족 경로가 검증되지 않음"),
        "자기실현": _unmeasured_autonomy(),
        "안정": _insufficient("쉬어가기 표본의 건강·정신건강 경로가 검증되지 않음"),
    }


# 선택 유형 → KOWEPS 생활효과 처치 키.
_LIFE_TREATMENT = {"결혼": "결혼", "주택": "자가", "이사": "이사"}

# KOWEPS 결과변수를 축으로 배타 분할한다.
_LIFE_AXIS_OUTCOMES: dict[str, tuple[str, ...]] = {
    "경제": ("가처분소득",),
    "관계": ("가족만족", "사회관계만족"),
    "안정": ("정신건강", "건강", "전반만족"),
    "성장": (),
    "자기실현": (),
}


def _life_statuses(kind: str) -> dict:
    """결혼·주택·이사 — KOWEPS 생활효과(LinearDML, 95% CI, 직전상태 통제)."""
    band = _life_band(kind)
    if band is None:
        return {k: {"status": "reference_only", "score": None,
                    "eligible_for_psych_rag": False,
                    "reason": "KOWEPS 생활효과 산출물이 없음"} for k in INDICATOR_KEYS}

    caveat = ((_life_effects() or {}).get("treatments", {})
              .get(_LIFE_TREATMENT[kind], {}).get("caveat"))
    out = {}
    for axis in INDICATOR_KEYS:
        if axis == "자기실현":
            out[axis] = _unmeasured_autonomy()
            continue
        cols = [c for c in _LIFE_AXIS_OUTCOMES.get(axis, ()) if band.get(c)]
        sig = [c for c in cols if band[c].get("significant")]
        if not sig:
            out[axis] = _insufficient(
                f"'{kind}' 처치의 {axis} 축 결과가 유의하지 않거나 측정되지 않음")
            continue
        top = max(sig, key=lambda c: abs(band[c]["ate"]))
        e = band[top]
        out[axis] = {
            "status": "causal_estimate", "score": None,
            "effect": e["ate"], "ci95": e.get("ci"), "unit": "점(1~5)" if axis != "경제" else "만원",
            "outcomes": sig, "n_treated": e.get("n_treated"),
            "eligible_for_psych_rag": False,
            "reason": (f"KOWEPS {kind} 처치의 {'·'.join(sig)} 인과효과"
                       f"(LinearDML, 직전상태 통제, 처치군 {e.get('n_treated')}건)"
                       + (f". {caveat}" if caveat and axis == "경제" else "")),
        }
    return out


@lru_cache(maxsize=1)
def _life_effects() -> dict | None:
    p = settings.artifacts_abspath / "koweps_life_effects.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


@lru_cache(maxsize=1)
def _treatment_report() -> dict | None:
    p = settings.artifacts_abspath / "treatment_report.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _life_band(kind: str, band_key: str = "20-45") -> dict | None:
    """그 선택의 KOWEPS 효과 묶음(연령밴드 하나)을 꺼낸다."""
    d = _life_effects()
    key = _LIFE_TREATMENT.get(kind)
    if not d or not key:
        return None
    bands = ((d.get("treatments") or {}).get(key) or {}).get("bands") or {}
    return bands.get(band_key) or (next(iter(bands.values())) if bands else None)


def life_levels(kind: str) -> dict | None:
    """관계·안정 축의 **수준값**(1~5) — compute_indicators 가 점수를 만들 때 쓴다.

    KOWEPS 는 효과(ATE)만 주는데 축 점수는 수준이 필요하다. 대조군 평균에 효과를
    더해 '이 선택을 했을 때의 수준' 을 만든다 — A/B 가 서로 다른 값을 받는다
    (선택을 안 한 쪽은 control_mean 그대로).
    """
    band = _life_band(kind)
    if not band:
        return None
    out = {}
    for axis, name in (("relation", "관계"), ("health", "안정")):
        vals = [band[c]["control_mean"] + band[c]["ate"]
                for c in _LIFE_AXIS_OUTCOMES[name]
                if band.get(c) and band[c].get("significant")
                and band[c].get("control_mean") is not None]
        if vals:
            out[axis] = sum(vals) / len(vals)
    return out or None


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


def _facet_latest(scen: dict, key: str) -> float | None:
    """satisfaction_facets 에서 facet 하나의 최신값(1~5). 없으면 None.

    facet 은 '이 선택을 한 유사인' 하위집단에서 계산되므로 A/B 가 서로 다른 값을
    받는다 — 집단 기준값과 달리 선택별로 갈리는 항이라 축 점수에 쓸 수 있다.
    """
    for f in scen.get("satisfaction_facets") or []:
        if f.get("key") == key:
            v = f.get("latest")
            return None if v is None else float(v)
    return None


def _observed_change_ratio(validated_prediction: dict | None, axis: str) -> float | None:
    """관측 '변화' 지표 → 개선:악화 비율(0~1). 0.5 면 개선과 악화가 같은 수.

    quality_of_life 지표는 수준이 아니라 **변화 분포**라 그대로는 축 점수가 안 된다.
    improved_rate / (improved_rate + worsened_rate) 로 방향을 요약한다 — 변화 없음
    (unchanged_rate)은 리커트 정수 단위의 측정 한계가 대부분이라 분모에서 뺀다.

    표본 n 으로 가중해 얇은 지표가 축을 흔들지 않게 한다.
    """
    spec = _OBSERVED_AXIS.get(axis)
    if not spec:
        return None
    domain, cols = spec
    domains = ((validated_prediction or {}).get("observed_outcomes") or {}).get("domains") or {}
    num = den = 0.0
    for it in domains.get(domain) or []:
        if not it.get("available") or (cols is not None and it.get("key") not in cols):
            continue
        up, down, n = it.get("improved_rate"), it.get("worsened_rate"), it.get("n")
        if up is None or down is None or not n:
            continue
        moved = float(up) + float(down)
        if moved <= 0:
            continue
        num += (float(up) / moved) * float(n)
        den += float(n)
    return None if den <= 0 else num / den


def _career_growth_rate(validated_prediction: dict | None) -> float | None:
    """관측 성장지표(직종전환·고용형태개선·조직규모↑·임금구간↑)의 표본가중 평균.

    단순평균이면 고용형태 개선율(n≈292)이 직종 전환율(n≈1,366)과 같은 무게를 갖는다.
    표본이 얇은 지표가 축 점수를 흔들지 않도록 n 으로 가중한다.

    반환은 백분위가 아니라 **관측 비율**(0~1)이다 — WEIGHTS 주석의 척도 주의 참고.
    """
    domains = ((validated_prediction or {}).get("observed_outcomes") or {}).get("domains") or {}
    num = den = 0.0
    for item in domains.get("growth") or []:
        if not item.get("available"):
            continue
        rate, n = item.get("rate"), item.get("n")
        if rate is None or not n:
            continue
        num += float(rate) * float(n)
        den += float(n)
    return None if den <= 0 else num / den


def compute_indicators_detail(scen: dict, baseline: float | None = None,
                              age: float | None = None,
                              validated_prediction: dict | None = None,
                              life_levels: dict | None = None) -> dict:
    """5축 + 근거(각 구성요소의 백분위). {scores, components, unmeasured, method}.

    life_levels : 관계·안정 축의 수준값 {'relation': 1~5, 'health': 1~5} — KOWEPS
        생활효과(control_mean + ate)에서 호출측이 만들어 넘긴다. 없으면 두 축은
        unmeasured 로 비운다(사용자 선택: 근거 없는 축은 '측정 근거 없음' 으로 표시).
    """
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
        return {"scores": _legacy(scen, baseline), "components": {},
                "unmeasured": ["관계", "자기실현"],
                "axis_meaning": AXIS_MEANING,
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

    # YP facet 5개는 전부 1~5 일자리만족 문항이라 공통 satisfaction 격자를 공유한다.
    sat_grid = grid("satisfaction")
    lv = life_levels or {}

    comp = {
        # ── 경제 ────────────────────────────────────────────────────────────
        "income_level": _pct(grid("income_level", income_band),
                             last if last is not None else baseline),
        "satis_income": _pct(sat_grid, _facet_latest(scen, "satis_income")),
        "satis_stability": _pct(sat_grid, _facet_latest(scen, "satis_stability")),
        # ── 성장 ────────────────────────────────────────────────────────────
        "career_growth": _career_growth_rate(validated_prediction),
        "satis_growth": _pct(sat_grid, _facet_latest(scen, "satis_growth")),
        "satis_future": _pct(sat_grid, _facet_latest(scen, "satis_future")),
        # ── 관계 · 안정 ─────────────────────────────────────────────────────
        # 두 갈래에서 온다. KOWEPS 생활효과는 **수준값**(결혼·주택·이사), KLIPS 관측은
        # **변화 방향**(이직·유지). 선택 유형에 따라 한쪽만 채워지고, 둘 다 있으면
        # 재정규화로 평균된다 — 근거 계약(evidence_statuses)과 축이 어긋나지 않는다.
        "relation_level": _pct(sat_grid, lv.get("relation")),
        "relation_observed": _observed_change_ratio(validated_prediction, "관계"),
        "health_level": _pct(sat_grid, lv.get("health")),
        "health_observed": _observed_change_ratio(validated_prediction, "안정"),
        # ── 자기실현 ────────────────────────────────────────────────────────
        # 자유·자율 / 의미·나다움 을 직접 측정한 문항이 없다. 이직·유지에서만 여가만족
        # 변화가 자율성의 **부분 대리**로 잡히고, 그 외 선택에서는 비어 있다.
        # (의미·나다움 쪽은 어떤 선택에서도 측정되지 않는다.)
        "autonomy_observed": _observed_change_ratio(validated_prediction, "자기실현"),
    }
    rp = _pct(_risk_grid(ref, regret_year, risk_src),
              regret / 100.0 if regret is not None else None)
    comp["low_exit_risk"] = None if rp is None else 1.0 - rp

    # 예전 3지표 공식이 쓰던 항 — 더는 어떤 축에도 안 들어가지만 근거 표시용으로 남긴다.
    # (income_growth 는 경제·성장 두 축에 중복 투입되던 항이라 v3 에서 배분에서 뺐다.)
    comp["income_growth"] = _pct(grid("income_growth"), growth5)
    comp["satisfaction"] = _pct(sat_grid, satis)

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
        "method": "percentile-rank (기준 분포: indicator_reference.json). "
                  "단 career_growth 는 백분위가 아니라 KLIPS 관측 비율(0~1)이다.",
        "axis_meaning": AXIS_MEANING,
        "note": "각 점수는 같은 나이대 분포에서의 백분위. 0.62 = 상위 38%. "
                "근거가 없는 구성요소는 배분에서 빠지며, 전부 없으면 0.5(중립)+unmeasured. "
                "⚠소득 백분위는 '계속 관측된 임금근로자' 궤적을 단면 분포에 대는 것이라 "
                "탈락자가 빠진 만큼 다소 높게 나온다(구성 차이). "
                "⚠자기실현 축은 측정 근거가 없어 항상 unmeasured 다.",
    }


def compute_indicators(scen: dict, baseline: float | None = None,
                       age: float | None = None,
                       validated_prediction: dict | None = None,
                       life_levels: dict | None = None) -> dict:
    """ScenarioView(dict) → 5축 점수(0~1).

    반환은 **INDICATOR_KEYS 5개 키의 float 만** — `psych_narrative.select_focus()` 가
    min() 으로 최저 축을 고르므로 다른 타입의 키가 섞이면 비교가 터진다.
    근거까지 필요하면 `compute_indicators_detail()` 을 쓴다.
    """
    return compute_indicators_detail(scen, baseline, age,
                                     validated_prediction, life_levels)["scores"]


def to_legacy_scores(scores: dict) -> dict:
    """5축 → 구지표 3개. 삶의질은 관계·자기실현·안정의 평균이다.

    측정된 축만 평균한다 — 자기실현이 항상 unmeasured 라 0.5 가 섞이면
    삶의질이 중립 쪽으로 끌려간다.
    """
    out: dict = {}
    for legacy, axes in LEGACY_TO_AXES.items():
        vals = [scores[a] for a in axes if scores.get(a) is not None]
        out[legacy] = round(sum(vals) / len(vals), 3) if vals else None
    return out


def _legacy(scen: dict, baseline: float | None) -> dict:
    """기준 분포 파일이 없을 때의 폴백 — 예전 손튜닝 공식을 5축에 매핑한다.

    폴백은 소득·만족·후회밖에 못 쓰므로 관계·자기실현 축은 채울 수 없다.
    호출측이 unmeasured 로 처리하도록 None 이 아니라 중립값+표시로 넘긴다.
    """
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
    econ = 0.35 + (income_level - 250) / 300 * 0.40 - regret / 100 * 0.15
    grow = 0.25 + growth5 / 40 * 0.9 + max(change, 0) * 0.4
    stab = satis / 5.0 - regret / 100 * 0.20
    return {"경제": round(_clamp01(econ), 3),
            "성장": round(_clamp01(grow), 3),
            "관계": 0.5,
            "자기실현": 0.5,
            "안정": round(_clamp01(stab), 3)}
