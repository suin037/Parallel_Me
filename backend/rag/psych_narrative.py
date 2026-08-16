"""
재료 제공형 심리 RAG — 검색된 이론카드 → '심리 해석 + 근거' 재료로 가공.

이 모듈은 최종 문장을 만들지 않는다(재료 제공형). 레이어2의 3지표 점수 + 감정
키워드로 관련 이론카드를 retrieve하고, 레이어3 메인 내러티브 생성기가 프롬프트에
그대로 주입할 수 있는 '근거 블록' + '행동 제안 후보'로 정리해 반환한다.
최종 서사는 utils/claude_api.py::generate_narrative 가 통합해서 낸다.

LLM을 호출하지 않는다(순수 검색 + 텍스트 가공). 비용·지연 없음.
"""

from rag.psych_retriever import retrieve, bucket

# 낮을수록 개입이 필요한 지표. 가장 낮은 지표를 심리검색 초점으로 삼는다.
_INDICATOR_ORDER = ["경제적안정도", "성장가능성", "삶의질"]
_NORMALIZE = {"경제적_안정도": "경제적안정도", "성장_가능성": "성장가능성", "삶의_질": "삶의질"}


def select_focus(indicator_scores, eligible_indicators=None):
    """3지표 점수 dict → (초점지표, 점수). 가장 낮은(=가장 개입 필요한) 지표 선택.

    indicator_scores 예: {"경제적안정도": 0.6, "성장가능성": 0.3, "삶의질": 0.18}
    언더스코어 표기 키도 허용.
    """
    if not indicator_scores:
        return None, None
    allowed = set(eligible_indicators) if eligible_indicators is not None else None
    norm = {_NORMALIZE.get(k, k): v for k, v in indicator_scores.items()
            if allowed is None or _NORMALIZE.get(k, k) in allowed}
    if not norm:
        return None, None
    focus = min(norm, key=norm.get)
    return focus, norm[focus]


def get_psych_evidence(indicator_scores, emotions=None, decision_type=None, k=3,
                       focus_override=None, eligible_indicators=None, basis="model"):
    """레이어2 신호 → 관련 이론카드 top-k(재료). 카드가 없으면 빈 리스트.

    focus_override: 초점 지표를 강제 지정(성향 개인화 레이어가 '중요하며 위태로운' 축을
        고른 경우). None 이면 기존 동작(가장 낮은 지표 = 개입 필요)으로 폴백.
    """
    allowed = set(eligible_indicators) if eligible_indicators is not None else None
    if focus_override and (allowed is None or focus_override in allowed):
        focus = focus_override
        score = (indicator_scores or {}).get(focus)
        if score is None:  # override 지표에 점수가 없으면 안전하게 폴백
            focus, score = select_focus(indicator_scores, eligible_indicators)
    else:
        focus, score = select_focus(indicator_scores, eligible_indicators)
    if focus is None or score is None:
        return {"focus_indicator": None, "level": None, "cards": [], "basis": basis,
                "reason": "심리 RAG에 사용할 수 있는 검증된 상태 점수가 없음"}
    level = bucket(score, focus)
    cards = retrieve(indicator=focus, score=score, emotions=emotions,
                     decision_type=decision_type, k=k)
    return {"focus_indicator": focus, "score": score, "level": level, "cards": cards,
            "basis": basis}


def build_psych_prompt_block(evidence):
    """근거 카드 → 레이어3 프롬프트에 주입할 한국어 텍스트 블록.

    최종 문장이 아니라 '재료'다. 메인 생성기가 이 블록을 근거로 서사를 통합한다.
    출처는 내부 근거 확인용으로만 포함하고 사용자 문장에는 노출하지 않는다.
    """
    cards = evidence.get("cards", [])
    if not cards:
        return ""

    focus = evidence.get("focus_indicator")
    level = evidence.get("level")
    lines = [
        "[심리학 근거 카드]",
        f"(초점 지표: {focus}={level}. 아래 이론을 근거로 심리 상태를 해석하고, "
        "행동 제안 1개를 고르되 이론명·저자·연도·논문명은 사용자 문장에 쓰지 마라.)",
        "",
    ]
    for i, c in enumerate(cards, 1):
        actions = c.get("interventions", [])
        lines.append(f"{i}) 이론: {c['theory_ko']} — {c['concept_ko']}")
        lines.append(f"   해석근거: {c.get('summary', '')}")
        if actions:
            lines.append("   행동제안 후보: " + " / ".join(actions))
        if c.get("narrative_guidance"):
            lines.append(f"   톤 가이드: {c['narrative_guidance']}")
        lines.append(f"   출처: {c.get('source', '')}")
        lines.append("")
    return "\n".join(lines).rstrip()


if __name__ == "__main__":
    # 데모: 삶의 질이 가장 낮은 사용자 + 후회 감정 + 이직 고민
    ev = get_psych_evidence(
        indicator_scores={"경제적안정도": 0.62, "성장가능성": 0.40, "삶의질": 0.18},
        emotions=["후회", "자책"],
        decision_type="이직",
        k=3,
    )
    print(f"초점 지표: {ev['focus_indicator']} = {ev['score']} ({ev['level']})")
    print(f"검색된 카드: {[c['card_id'] for c in ev['cards']]}\n")
    print("=" * 60)
    print("레이어3 프롬프트에 주입될 근거 블록:")
    print("=" * 60)
    print(build_psych_prompt_block(ev))
