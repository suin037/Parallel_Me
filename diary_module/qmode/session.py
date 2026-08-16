# -*- coding: utf-8 -*-
"""session.py — 질문형 일기 하루치 세션 분석 (두 경로 + 안전 게이트).

기존 diary_module 코드는 한 줄도 수정하지 않는다. import 해서 감싸기만 한다.
    infer.DiaryAnalyzer / hybrid.analyze_hybrid / metrics.analyze_text / crisis.detect
    backend/rag.safety

두 경로 (질문풀_설계.md §3)
    ① 질문 답변  → card_map 직결로 card_id 확정 → JSON 로드   (★ 벡터검색 안 씀)
    ② 자유 일기칸 → analyze_hybrid → psych_link.link_psych()   (벡터검색)
    두 경로 모두 crisis.detect + rag.safety 게이트를 통과한다. 위기면 카드 대신
    지원 안내로 하드 분기한다.

자유 일기 모드(기존)와의 차이
    기존 : 하루 = 텍스트 1덩어리 → analyze_hybrid(az, text)
    질문형: 하루 = {질문, 답변} N개 → 답변마다 감정분석, 카드는 질문 ID로 직결

질문 텍스트는 감정 모델·언어지표에 절대 넣지 않는다 (aggregate.py 상단 주석 참조).
답변만 넣고, 질문 라벨은 리포트·서사 프롬프트 단계에서만 합류시킨다.

사용:
    from infer import DiaryAnalyzer
    from qmode.session import analyze_session
    az = DiaryAnalyzer(ckpt="../model_v3_e6.pt")
    r = analyze_session(az, date="2026-07-26", answers=[
        {"question_id": "C1", "text": "요즘은 '버티는 중'. 출근길 지하철에서 제일 짙다."},
        {"question_id": "C2", "text": "..."},
    ], free_text="덧붙이자면 ...")
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DIARY = HERE.parent
ROOT = DIARY.parent
BACKEND = ROOT / "backend"
for p in (str(DIARY), str(BACKEND)):
    if p not in sys.path:
        sys.path.insert(0, p)

import metrics                                              # noqa: E402
from qmode import card_map                                 # noqa: E402
from qmode.aggregate import accumulate, entry_weight, classify_envy  # noqa: E402
from qmode.scheduler import Scheduler                       # noqa: E402

try:
    import crisis
    HAS_CRISIS = True
except ImportError:                                         # pragma: no cover
    HAS_CRISIS = False

try:
    from rag import safety
    HAS_SAFETY = True
except ImportError:                                         # pragma: no cover
    HAS_SAFETY = False

_SCH = Scheduler()


def _gate(text):
    """답변 1건의 안전 게이트 → (blocked, safety_level, hits).

    crisis.py(정규식, 재현율 우선) + rag.safety(감정/텍스트 키워드) 이중 확인.
    blocked=True 면 카드 대신 지원 안내로 분기한다.
    """
    level, hits = "normal", []
    block = False
    if HAS_CRISIS:
        cr = crisis.detect(text)
        if cr.block_report:               # L3 — 즉시개입
            block = True
        if cr.level >= 2:
            level, hits = "high_distress", list(cr.matched)
    if HAS_SAFETY:
        s_level, s_hits = safety.assess_safety(text=text)
        if s_level == "crisis":
            block, level = True, "crisis"
            hits = hits + s_hits
        elif s_level == "high_distress" and level == "normal":
            level, hits = "high_distress", s_hits
    if block:
        level = "crisis"
    return block, level, hits


def _norm_card(card):
    """원본 카드 dict → 프롬프트 블록용 정규화(자유칸 retriever 카드와 키 통일)."""
    src = card.get("source", {})
    return {
        "card_id": card["card_id"],
        "theory_ko": card.get("theory_ko", ""),
        "concept_ko": card.get("concept_ko", ""),
        "summary": card.get("summary", ""),
        "interventions": card.get("interventions", []),
        "narrative_guidance": card.get("narrative_guidance", ""),
        "source": src.get("citation", "") if isinstance(src, dict) else src,
    }


def analyze_session(analyzer, date, answers, *, free_text=None,
                    allow_api=True, k=3):
    """하루치 질문형 세션 분석.

    analyzer : DiaryAnalyzer (None 이면 감정모델·자유칸 벡터 경로를 건너뜀 — 글루 점검용)
    answers  : [{"question_id": "C1", "text": "..."}, ...]
    반환: {date, mode, question_ids, items[], free, session_crisis, crisis_message}
    """
    items = []
    for a in answers:
        qid = a.get("question_id")
        text = (a.get("text") or "").strip()
        q = _SCH.by_id.get(qid, {})
        if not text:
            items.append({"question_id": qid, "question_text": q.get("text"),
                          "skipped": True, "reason": "빈 답변"})
            continue

        # 답변만 지표에 넣는다(질문 텍스트 오염 방지).
        m = metrics.analyze_text(text)
        w, keys = entry_weight(m, source="question")

        # 감정(모델) — 질문 경로는 여기서 psych/벡터를 부르지 않는다.
        final_coarse = None
        if analyzer is not None:
            d = analyzer.analyze(text)
            final_coarse = (d.get("dominant") or {}).get("coarse")

        # 안전 게이트
        blocked, s_level, s_hits = _gate(text)

        # D4 는 부러움 판정으로 카드가 갈린다.
        verdict = classify_envy(text) if qid == "D4" else None

        # 카드 — 질문 ID 직결(★ 벡터검색 없음). 위기면 카드 대신 지원 안내.
        if blocked:
            cards, crisis_msg = [], (safety.crisis_message() if HAS_SAFETY else None)
        else:
            cards = [_norm_card(c) for c in card_map.load_cards_for(qid, verdict)]
            crisis_msg = None

        item = {
            "question_id": qid,
            "question_text": q.get("text"),
            "question_risk": q.get("risk"),
            "question_risk_type": q.get("risk_type"),
            "question_evidence": q.get("evidence"),
            "distancing": q.get("distancing", False),
            "answer": text,
            "metrics": m,
            "weight": w,
            "accepted_keys": list(keys),
            "final_coarse": final_coarse,
            "safety_level": s_level,
            "safety_hits": s_hits,
            "card_ids": [c["card_id"] for c in cards],
            "cards": cards,
            "card_provisional": qid in card_map.PROVISIONAL,
            "crisis_message": crisis_msg,
        }
        if qid == "D4":
            item["envy"] = verdict
        items.append(item)

    # 자유 일기칸 — 벡터 경로(link_psych). 모델 없으면 건너뛴다.
    free = None
    if free_text and free_text.strip() and analyzer is not None:
        from hybrid import analyze_hybrid          # 지연 import (torch 로드 회피)
        t = free_text.strip()
        blocked, s_level, s_hits = _gate(t)
        d = analyze_hybrid(analyzer, t, allow_api=allow_api, k=k)
        fm = metrics.analyze_text(t)
        fw, fkeys = entry_weight(fm, source="free")
        free = {
            "question_id": None, "source": "free", "answer": t,
            "metrics": fm, "weight": fw, "accepted_keys": list(fkeys),
            "final_coarse": d.get("final_coarse"),
            "safety_level": s_level,
            "psych_cards": [c.get("card_id") for c in
                            (d.get("psych") or {}).get("cards", [])],
            "crisis_message": (safety.crisis_message()
                               if blocked and HAS_SAFETY else None),
        }

    # 세션 전체 위기 판정 — 답변 중 하나라도 걸리면 세션 단위로 올린다.
    session_crisis = 0
    if HAS_CRISIS:
        joined = "\n".join([a.get("text", "") for a in answers] +
                           ([free_text] if free_text else []))
        if joined.strip():
            session_crisis = crisis.detect(joined).level

    return {
        "date": date,
        "mode": "question",
        "question_ids": [a.get("question_id") for a in answers],
        "items": items,
        "free": free,
        "session_crisis": session_crisis,
        "crisis_message": (crisis.support_message(session_crisis)
                           if HAS_CRISIS and session_crisis >= 2 else None),
    }


def to_answer_rows(sessions):
    """세션 목록 → aggregate.accumulate() 입력 형식으로 평탄화."""
    rows = []
    for s in sessions:
        for it in s.get("items", []):
            if it.get("skipped"):
                continue
            rows.append({"date": s["date"], "question_id": it["question_id"],
                         "source": "question", "text": it["answer"],
                         "metrics": it["metrics"]})
        if s.get("free"):
            f = s["free"]
            rows.append({"date": s["date"], "question_id": None, "source": "free",
                         "text": f["answer"], "metrics": f["metrics"]})
    return rows


def build_diary_metrics(sessions):
    """세션 목록 → backend PredictRequest.diary_metrics (없으면 None)."""
    return accumulate(to_answer_rows(sessions))


def to_prompt_block(sessions, agg=None):
    """서사 프롬프트에 붙일 질문-답변 블록.

    질문 라벨이 붙어야 '무엇에 대한 답인지'가 살아난다.
    (답만 넘기면 "'망설인 선택'을 물었을 때 리스크 회피 언어가 반복됐다" 같은
     서술이 불가능해진다.)
    """
    agg = agg or build_diary_metrics(sessions)
    lines = ["[질문형 일기 요약 — 서술 방식 참고용, 예측 수치와 무관]"]
    pq = agg.get("per_question", {})
    for qid, v in sorted(pq.items()):
        q = _SCH.by_id.get(qid, {})
        bits = []
        if "emotion_valence" in v:
            bits.append(f"정서극성 {v['emotion_valence']:+.2f}")
        if "coping_balance" in v:
            bits.append(f"대처균형 {v['coping_balance']:+.2f}")
        if "insight_ratio" in v:
            bits.append(f"통찰 {v['insight_ratio']:.3f}")
        label = (q.get("text") or qid)[:28]
        lines.append(f"- 「{label}…」({v['n']}회): " + " · ".join(bits))
    e = agg.get("envy")
    if e:
        note = ("가치축 신호로 사용" if e["use_for_axes"]
                else "박탈감/위협 신호 — 가치축에 반영하지 말 것")
        lines.append(f"- 부러움 유형: {e['label']} → {note}")
    if agg.get("gate_note"):
        lines.append(f"- ⚠ {agg['gate_note']}")
    return "\n".join(lines)


if __name__ == "__main__":
    # 모델 없이 글루 로직만 점검 (analyzer=None → 감정모델·벡터 경로 스킵)
    fake_sessions = [{
        "date": "2026-07-2%d" % i, "mode": "question",
        "items": [
            {"question_id": "C2", "answer": "그냥 참았다. 옆에서 봤으면 지쳐 보였을 것 같다.",
             "metrics": {"n_tokens": 24, "coping_balance": -0.4,
                         "emotion_valence": -0.3, "insight_ratio": 0.02,
                         "absolutist_ratio": 0.01, "first_person_ratio": 0.05,
                         "emotion_density": 0.07}},
            {"question_id": "R3", "answer": "발표가 잘 끝났다. 미리 준비한 덕분이라고 생각한다.",
             "metrics": {"n_tokens": 44, "coping_balance": 0.6,
                         "emotion_valence": 0.7, "insight_ratio": 0.06,
                         "absolutist_ratio": 0.0, "first_person_ratio": 0.04,
                         "emotion_density": 0.05}},
        ], "free": None} for i in range(1, 4)]

    agg = build_diary_metrics(fake_sessions)
    print(json.dumps({"n_answers": agg["n_answers"],
                      "diary_metrics": agg["diary_metrics"]},
                     ensure_ascii=False, indent=2))
    print()
    print(to_prompt_block(fake_sessions, agg))

    # 카드 직결 경로 점검 (analyzer 없이 card_map 만)
    print("\n--- 카드 직결(질문 경로) 점검 ---")
    for qid, verdict in [("C2", None), ("D5", None), ("D6", None),
                         ("D4", "benign"), ("D4", "malicious"), ("D4", "unclear"),
                         ("C1", None), ("D1", None)]:
        ids = card_map.card_ids_for(qid, verdict)
        tag = f"({verdict})" if verdict else ""
        print(f"  {qid}{tag:11s} → {ids or '카드 없음'}")
