# -*- coding: utf-8 -*-
"""aggregate.py — 질문 답변 누적 → diary_metrics (backend 전달용).

핵심 규칙 (질문풀_설계.md §6)
    1. 길이 게이트 — 짧은 답변은 비율 지표를 심하게 튀게 하므로 가중치를 깎거나 제외
    2. 자유 일기칸 텍스트는 가중치 0.5 (문체 편차 보정) + 세그먼트 분리
    3. 답변 5개 미만이면 diary_metrics 를 backend 에 넘기지 않는다
    4. D4(부러움)는 선의/악의를 갈라서, 선의일 때만 가치축 신호로 쓴다

주의 — 질문 텍스트는 절대 지표 계산에 넣지 않는다.
    metrics.py 의 INSIGHT 집합에 '생각','때문'이, ABSOLUTIST 에 '가장','제일'이 들어 있고
    질문 문구가 바로 그 단어를 쓴다("왜 잘 됐다고 생각하나요", "가장 마음이 걸린").
    질문+답변을 합쳐 넣으면 insight_ratio·absolutist_ratio 가 질문 때문에 부풀고,
    답변이 짧을수록 오염이 커진다. 질문은 메타데이터로만 들고 다니다가
    리포트·서사 프롬프트 단계에서 합류시킨다.
"""

from __future__ import annotations

# 길이 게이트 (n_tokens 기준)
GATE_MIN = 15          # 미만 → 비율 지표 제외, 극성만 채택
GATE_FULL = 40         # 이상 → 가중치 1.0
W_SHORT = 0.6          # 15~40
W_FREE = 0.5           # 자유 일기칸 배수
MIN_ANSWERS = 5        # 이 미만이면 backend 전달 안 함

# 길이에 민감한(분모가 전체 형태소 수인) 지표 — 짧은 답변에서 제외
RATIO_KEYS = ("first_person_ratio", "absolutist_ratio", "insight_ratio",
              "emotion_density", "coping_balance")
# 길이 정규화가 아닌 지표 — 짧아도 채택
ROBUST_KEYS = ("emotion_valence",)
ALL_KEYS = RATIO_KEYS + ROBUST_KEYS

# 부러움 분기 (D4) — 선의/악의 판정 키워드
ENVY_BENIGN = ("되고 싶", "닮고 싶", "나도 저렇게", "배우고 싶", "따라가고 싶",
               "나도 그렇게", "본받", "자극이 됐", "동기부여")
ENVY_MALICIOUS = ("왜 나는", "나만", "불공평", "억울", "짜증", "꼴보기",
                  "안 됐으면", "밉", "박탈")


def entry_weight(m, *, source="question"):
    """지표 dict → (가중치, 채택할 키 목록)."""
    n = (m or {}).get("n_tokens", 0)
    if n <= 0:
        return 0.0, ()
    base = W_FREE if source == "free" else 1.0
    if n < GATE_MIN:
        return base * 1.0, ROBUST_KEYS          # 극성만
    if n < GATE_FULL:
        return base * W_SHORT, ALL_KEYS
    return base * 1.0, ALL_KEYS


def classify_envy(text):
    """D4 답변 → 'benign' | 'malicious' | 'unclear'.

    Van de Ven, Zeelenberg & Pieters (2009): 선의의 부러움은 자기 상승 동기로,
    악의적 부러움은 상대 하강 동기로 이어진다. 선의일 때만 '부러움의 대상'이
    그 사람의 가치축 신호가 된다. 악의는 박탈감·위협 신호이므로 축에 넣지 않는다.
    """
    t = (text or "").replace(" ", "")
    b = sum(1 for k in ENVY_BENIGN if k.replace(" ", "") in t)
    mal = sum(1 for k in ENVY_MALICIOUS if k.replace(" ", "") in t)
    if b > mal:
        return "benign"
    if mal > b:
        return "malicious"
    return "unclear"


def accumulate(answers):
    """답변 목록 → 누적 지표.

    answers: [{
        "date": "2026-07-26",
        "question_id": "C2" | None,          # None = 자유 일기칸
        "source": "question" | "free",
        "text": "답변 원문",
        "metrics": {...},                     # metrics.analyze_text 결과
    }, ...]

    반환:
        {
          "n_answers": int,          # 게이트 통과 답변 수
          "n_submitted": int,        # 제출된 전체 수
          "diary_metrics": {...} | None,   # MIN_ANSWERS 미만이면 None
          "per_question": {qid: {키: 값}},
          "envy": {"label":..., "n":...},
          "excluded": [...],
        }
    """
    acc = {k: 0.0 for k in ALL_KEYS}
    wsum = {k: 0.0 for k in ALL_KEYS}
    per_q = {}
    excluded = []
    envy_votes = []
    n_ok = 0

    for a in answers:
        m = a.get("metrics") or {}
        src = a.get("source", "question")
        w, keys = entry_weight(m, source=src)

        if w <= 0 or not keys:
            excluded.append({"date": a.get("date"), "question_id": a.get("question_id"),
                             "reason": "빈 입력 또는 형태소 0"})
            continue
        if m.get("n_tokens", 0) < GATE_MIN:
            excluded.append({"date": a.get("date"), "question_id": a.get("question_id"),
                             "reason": f"형태소 {m.get('n_tokens')}개 < {GATE_MIN} "
                                       f"— 비율 지표 제외, 극성만 채택"})

        n_ok += 1
        for k in keys:
            if k in m:
                acc[k] += m[k] * w
                wsum[k] += w

        qid = a.get("question_id")
        if qid:
            slot = per_q.setdefault(qid, {"n": 0, "sum": {}, "w": {}})
            slot["n"] += 1
            for k in keys:
                if k in m:
                    slot["sum"][k] = slot["sum"].get(k, 0.0) + m[k] * w
                    slot["w"][k] = slot["w"].get(k, 0.0) + w
            if qid == "D4":
                envy_votes.append(classify_envy(a.get("text", "")))

    dm = {k: round(acc[k] / wsum[k], 4) for k in ALL_KEYS if wsum[k] > 0}
    per_question = {
        qid: {**{k: round(s["sum"][k] / s["w"][k], 4)
                 for k in s["sum"] if s["w"].get(k, 0) > 0},
              "n": s["n"]}
        for qid, s in per_q.items()
    }

    envy = None
    if envy_votes:
        counts = {v: envy_votes.count(v) for v in set(envy_votes)}
        top = max(counts.values())
        winners = [v for v, c in counts.items() if c == top]
        # 동점이면 보수적으로 unclear — 축 신호로 쓰지 않는다
        label = winners[0] if len(winners) == 1 else "unclear"
        envy = {"label": label, "n": len(envy_votes), "votes": envy_votes,
                "use_for_axes": label == "benign"}

    return {
        "n_answers": n_ok,
        "n_submitted": len(answers),
        "diary_metrics": dm if n_ok >= MIN_ANSWERS else None,
        "gate_note": (None if n_ok >= MIN_ANSWERS
                      else f"답변 {n_ok}개 < {MIN_ANSWERS}개 — backend 전달 보류"),
        "per_question": per_question,
        "envy": envy,
        "excluded": excluded,
    }


if __name__ == "__main__":
    # metrics.analyze_text 결과를 흉내낸 가짜 입력 (kiwi 없이 로직만 검증)
    def fake(n, **kw):
        base = {"n_tokens": n, "first_person_ratio": 0.05, "absolutist_ratio": 0.01,
                "insight_ratio": 0.02, "coping_balance": 0.0,
                "emotion_density": 0.06, "emotion_valence": 0.0}
        base.update(kw)
        return base

    answers = [
        # 짧은 답변 — 비율 지표가 튀는 상황을 재현
        {"date": "2026-07-20", "question_id": "C1", "source": "question",
         "text": "피곤", "metrics": fake(4, absolutist_ratio=0.25, emotion_valence=-0.8)},
        {"date": "2026-07-21", "question_id": "C2", "source": "question",
         "text": "그냥 참았다 옆에서 보면 지쳐 보였을 듯",
         "metrics": fake(22, coping_balance=-0.4, emotion_valence=-0.3)},
        {"date": "2026-07-22", "question_id": "R3", "source": "question",
         "text": "발표가 잘 끝났다. 미리 준비해둔 덕분이라고 생각한다. 그래서 덜 떨렸다.",
         "metrics": fake(48, insight_ratio=0.06, coping_balance=0.6,
                         emotion_valence=0.7)},
        {"date": "2026-07-23", "question_id": "D4", "source": "question",
         "text": "친구가 이직한 게 부러웠다. 나도 저렇게 옮겨보고 싶다는 생각이 들었다.",
         "metrics": fake(45, emotion_valence=-0.1)},
        {"date": "2026-07-24", "question_id": None, "source": "free",
         "text": "오늘은 그냥 길게 썼다 " * 8,
         "metrics": fake(60, first_person_ratio=0.12, emotion_valence=-0.5)},
    ]

    import json
    r = accumulate(answers)
    print(json.dumps(r, ensure_ascii=False, indent=2))

    print("\n--- 게이트 효과 검증 ---")
    print("짧은 답변(4형태소)의 absolutist_ratio=0.25 가 누적 평균에 반영됐는가?")
    print(f"  누적 absolutist_ratio = {r['diary_metrics']['absolutist_ratio']}")
    print("  → 0.01 근처면 정상(제외됨), 0.05 이상이면 게이트 실패")

    print("\n--- 5개 미만 보류 검증 ---")
    r2 = accumulate(answers[:3])
    print(f"  n_answers={r2['n_answers']}, diary_metrics={r2['diary_metrics']}")
    print(f"  {r2['gate_note']}")

    print("\n--- 부러움 분기 검증 ---")
    mal = dict(answers[3], text="친구가 이직한 게 부러웠다. 왜 나는 안 될까 싶고 억울했다.")
    print(f"  benign  → {accumulate([mal] + answers[:4])['envy']}")
