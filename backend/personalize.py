"""personalize.py — 성향 개인화 레이어 (Option A: 강조·초점·확신도만).

위치: backend/personalize.py

무엇을 하는가
    지윤 qmode(value_ranking.axis_weights, disposition)가 만든 '성향 재료'를
    예측 파이프라인(compare/simulate)에서 소비하는 글루.
    → 어느 지표·서사를 앞세울지(강조), 어떤 심리카드를 뽑을지(초점),
      성향을 얼마나 믿을지(확신도)를 정한다.

원칙 (jy-model/diary_module/qmode/PREDICTION_HANDOFF.md 합의)
    1) 성향을 예측 '모델(KNN/EconML/lifelines) 피처'로 넣지 않는다. 매칭 불변.
    2) 선택지(A/B) '적합도 단일 점수'를 만들지 않는다 — 우열 단정 금지(=Option A).
       대신 지표별 질적 비교('네 1순위 축은 A가 높다')만 제공.
    3) 성향은 온보딩 초기값 → 일기 쌓일수록 갱신(recency). 데이터 적으면 단정 금지.

입력 계약
    value_weights : 온보딩 가치순위 → 5축 가중치(합≈1).
        예) {"경제":0.30,"관계":0.20,"성장":0.25,"자기실현":0.15,"안정":0.10}
        (지윤 value_ranking.axis_weights(ranked_card_ids) 산출물)
    diary_weights : 일기 언어지표에서 갱신된 5축 가중치(선택, 같은 스키마).
    n_answers     : 누적 일기 답변 수(확신도/recency 판단).
    disposition_block : 지윤 disposition.build_disposition_block() 텍스트(서사 프롬프트용).
"""

from __future__ import annotations

# ── 가치축 → 3지표 계약 (지윤 value_ranking.AXIS_TO_INDICATOR 정본과 동일) ──
# qmode 가 사이패스에 있으면 그걸 정본으로 쓰고, 없으면 이 사본으로 폴백.
_FALLBACK_AXIS_TO_INDICATOR = {
    "경제": "경제적안정도", "성장": "성장가능성",
    "관계": "삶의질", "자기실현": "삶의질", "안정": "삶의질",
}
try:  # 지윤 모듈이 병합돼 있으면 정본을 import (계약 드리프트 방지)
    from qmode.value_ranking import AXIS_TO_INDICATOR as _AXIS_TO_INDICATOR  # type: ignore
except Exception:
    _AXIS_TO_INDICATOR = _FALLBACK_AXIS_TO_INDICATOR

INDICATORS = ["경제적안정도", "성장가능성", "삶의질"]


# ── 가중치 변환 ──────────────────────────────────────────────────────
def indicator_weights(value_weights: dict | None) -> dict | None:
    """5축 가중치 → 3지표 가중치(합=1).

    [집계 = 평균(mean)]  ★2026-07-30 변경: 기존 '합산(sum)' → '평균(mean)'.
      각 지표 가중치 = 그 지표로 매핑되는 축들의 '평균'.
        · 경제적안정도 = mean(경제)            = 경제
        · 성장가능성   = mean(성장)            = 성장
        · 삶의질       = mean(관계, 자기실현, 안정)   ← 3축을 흡수하지만 평균이라 과대대표 X
      마지막에 세 지표 합이 1이 되도록 정규화.

    왜 sum → mean 인가 (상세: docs/DECISION_lifequality_mean_2026-07-30.md):
      AXIS_TO_INDICATOR 가 5축 중 3축(관계·자기실현·안정)을 삶의질로 접는다.
      '합산'이면 삶의질이 축 개수 때문에 구조적으로 과대대표되어,
      사용자가 성장을 1순위로 꼽아도 삶의질이 서술 우선순위 맨 앞에 오는 문제가 있었다.
      '평균'은 지표별 '평균 중요도'라 사용자의 실제 우선순위를 더 정직하게 반영한다.
      (지윤 value_ranking.AXIS_TO_INDICATOR 매핑 자체는 손대지 않음 — 우리 쪽 집계만 변경.)
    """
    if not value_weights:
        return None
    # 각 지표로 매핑되는 축 가중치들을 모아 '평균' 낸다.
    buckets = {k: [] for k in INDICATORS}
    for ax, wt in value_weights.items():
        ind = _AXIS_TO_INDICATOR.get(ax)
        if ind in buckets:
            buckets[ind].append(float(wt or 0))
    w = {k: (sum(v) / len(v) if v else 0.0) for k, v in buckets.items()}
    tot = sum(w.values()) or 1.0
    return {k: round(v / tot, 4) for k, v in w.items()}

    # ── [이전 코드: 합산(sum) 방식] 2026-07-30 이전. 삶의질 과대대표 이슈로 mean 으로 교체. ──
    # w = {k: 0.0 for k in INDICATORS}
    # for ax, wt in value_weights.items():
    #     ind = _AXIS_TO_INDICATOR.get(ax)
    #     if ind in w:
    #         w[ind] += float(wt or 0)          # ← 합산: 삶의질이 3축을 다 더해 과대대표됨
    # tot = sum(w.values()) or 1.0
    # return {k: round(v / tot, 4) for k, v in w.items()}


def priority_order(value_weights: dict | None) -> list[str]:
    """가치 기반 서술 우선순위(높은 지표부터). 동점/미지정은 INDICATORS 고정순."""
    iw = indicator_weights(value_weights) or {}
    return sorted(INDICATORS, key=lambda k: (-iw.get(k, 0.0), INDICATORS.index(k)))


# ── 확신도 / recency (지윤 handoff §4 — 예측 쪽에 넘긴 미구현분) ──────────
def confidence(n_answers: int | None) -> dict:
    """누적 일기 답변 수 → 성향 확신도 + 톤 + (온보딩 vs 일기신호) 혼합 무게.

    n 적을수록 온보딩 순위 위주·단정 금지, 많을수록 일기 갱신신호 위주.
    """
    n = int(n_answers or 0)
    if n < 5:
        return {"level": "낮음", "diary_weight": 0.0, "onboarding_weight": 1.0,
                "n_answers": n, "tone": "성향 데이터 거의 없음 — 단정 말 것, 온보딩 순위만 참고."}
    if n < 10:
        return {"level": "낮음", "diary_weight": 0.25, "onboarding_weight": 0.75,
                "n_answers": n, "tone": "아직 단정 어렵지만 — 톤으로만 약하게 반영."}
    if n < 25:
        return {"level": "중간", "diary_weight": 0.5, "onboarding_weight": 0.5,
                "n_answers": n, "tone": "성향 경향이 보임 — 초점 축을 강조해도 됨."}
    return {"level": "높음", "diary_weight": 0.75, "onboarding_weight": 0.25,
            "n_answers": n, "tone": "성향 신호 충분 — 일기 갱신신호를 우선."}


def blend_weights(onboarding_w: dict | None, diary_w: dict | None, conf: dict) -> dict | None:
    """온보딩 가치가중치 ⊕ 일기유래 가중치 → 확신도 기반 혼합(합=1).

    diary_w 없거나 확신도 낮으면 온보딩 그대로.
    """
    if not onboarding_w:
        return diary_w
    if not diary_w or conf["diary_weight"] <= 0:
        return dict(onboarding_w)
    a, b = conf["onboarding_weight"], conf["diary_weight"]
    axes = set(onboarding_w) | set(diary_w)
    mixed = {ax: a * float(onboarding_w.get(ax, 0)) + b * float(diary_w.get(ax, 0)) for ax in axes}
    tot = sum(mixed.values()) or 1.0
    return {ax: round(v / tot, 4) for ax, v in mixed.items()}


# ── 심리카드 초점 선택 (deficit vs value 화해) ─────────────────────────
def psych_focus(indicator_scores: dict | None, value_weights: dict | None = None,
                mode: str = "need_x_value") -> tuple[str | None, float | None]:
    """어떤 지표를 심리카드 검색 초점으로 삼을지.

    기존 psych_narrative.select_focus 는 '가장 낮은 지표(개입 필요)'만 봤다.
    Option A 는 '사용자가 중요시하는 축'도 반영해야 한다. 셋 중 선택:
      · "deficit"      : 가장 낮은 지표 (기존 동작 — value_weights 없을 때 폴백)
      · "value"        : 가치 가중치 최상위 지표
      · "need_x_value" : 중요하면서(가중치↑) 동시에 낮은(점수↓) 지표
                         = argmax( weight · (1 - score) ). 기본값(추천).
    반환: (지표명, 점수) — 점수는 버킷팅용 원 지표점수.
    """
    if not indicator_scores:
        return None, None
    scores = {k: float(v) for k, v in indicator_scores.items() if k in INDICATORS}
    if not scores:
        return None, None

    if mode == "deficit" or not value_weights:
        focus = min(scores, key=scores.get)
        return focus, scores[focus]

    iw = indicator_weights(value_weights) or {}
    if mode == "value":
        focus = max(scores, key=lambda k: iw.get(k, 0.0))
        return focus, scores[focus]

    # need_x_value (기본): 중요하고 동시에 위태로운 축
    def need_score(k):
        return iw.get(k, 0.0) * (1.0 - scores[k])
    focus = max(scores, key=need_score)
    return focus, scores[focus]


# ── 질적 A/B 강조 (Option A — 단일 점수 없음) ──────────────────────────
def emphasis_compare(ind_a: dict | None, ind_b: dict | None,
                     value_weights: dict | None, margin: float = 0.08) -> list[dict]:
    """A/B 3지표를 '사용자 우선순위대로' 질적 비교. 종합 우열 점수는 만들지 않는다.

    반환: [{indicator, weight, a, b, delta, verdict}] (우선순위 높은 지표부터)
      verdict ∈ {"A가 높음","B가 높음","비슷"}  (margin 이내면 '비슷')
    """
    if not ind_a or not ind_b:
        return []
    iw = indicator_weights(value_weights) or {k: 0.0 for k in INDICATORS}
    out = []
    for ind in priority_order(value_weights):
        a, b = ind_a.get(ind), ind_b.get(ind)
        if a is None or b is None:
            continue
        a, b = float(a), float(b)
        d = round(a - b, 3)
        verdict = "비슷" if abs(d) < margin else ("A가 높음" if d > 0 else "B가 높음")
        out.append({"indicator": ind, "weight": round(iw.get(ind, 0.0), 3),
                    "a": round(a, 3), "b": round(b, 3), "delta": d, "verdict": verdict})
    return out


# ── 서사 프롬프트 지시문 (지윤 handoff §2 주입) ────────────────────────
def narrative_directive(personalization: dict, choice_a: str = "A", choice_b: str = "B") -> str:
    """개인화 결과 → 서사 생성 프롬프트에 붙일 지시문 블록.

    '서술 우선순위' + '확신도 톤' + (있으면) 지윤 disposition 블록을 합친다.
    단정 금지·권유 금지 원칙을 명시(Option A / 제품 원칙).
    """
    order = personalization.get("narrate_order") or INDICATORS
    conf = personalization.get("confidence") or {}
    lines = [
        "[개인화 지시 — 사용자 가치 우선순위에 맞춰 '강조·순서'만 조정. "
        "선택지 우열을 단정하거나 특정 선택을 권유하지 말 것.]",
        f"· 서술 우선순위(중요도 높은 축부터): {' > '.join(order)}",
    ]
    if conf.get("tone"):
        lines.append(f"· 확신도({conf.get('level')}): {conf['tone']}")
    emp = personalization.get("emphasis") or []
    if emp:
        frag = ", ".join(f"{e['indicator']}={e['verdict']}" for e in emp)
        lines.append(f"· 지표별 비교(사실만, 종합 우열 금지): {frag} "
                     f"(A={choice_a} / B={choice_b})")
    block = personalization.get("disposition_block") or ""
    if block:
        lines += ["", block]
    return "\n".join(lines)


# ── 진입점 ───────────────────────────────────────────────────────────
def build_personalization(value_weights: dict | None = None,
                          diary_weights: dict | None = None,
                          n_answers: int | None = 0,
                          indicator_scores_a: dict | None = None,
                          indicator_scores_b: dict | None = None,
                          disposition_block: str = "",
                          focus_mode: str = "need_x_value") -> dict:
    """파이프라인이 부르는 단일 진입점.

    반환 dict:
      effective_weights : 온보딩⊕일기 혼합 5축 가중치
      indicator_weights : 3지표 가중치
      narrate_order     : 서술 우선순위(지표)
      confidence        : 확신도/톤/혼합무게
      focus_a / focus_b : (지표, 점수) — 심리카드 검색 초점 (지표점수 있을 때만)
      emphasis          : 질적 A/B 비교 리스트 (지표점수 A·B 둘 다 있을 때만)
      disposition_block : 서사 프롬프트용 원본 블록(있으면)
    """
    conf = confidence(n_answers)
    eff = blend_weights(value_weights, diary_weights, conf)
    result = {
        "value_weights": value_weights,
        "diary_weights": diary_weights,
        "effective_weights": eff,
        "indicator_weights": indicator_weights(eff),
        "narrate_order": priority_order(eff),
        "confidence": conf,
        "focus_a": None,
        "focus_b": None,
        "emphasis": [],
        "disposition_block": disposition_block or "",
    }
    if indicator_scores_a:
        result["focus_a"] = psych_focus(indicator_scores_a, eff, mode=focus_mode)
    if indicator_scores_b:
        result["focus_b"] = psych_focus(indicator_scores_b, eff, mode=focus_mode)
    if indicator_scores_a and indicator_scores_b:
        result["emphasis"] = emphasis_compare(indicator_scores_a, indicator_scores_b, eff)
    return result
