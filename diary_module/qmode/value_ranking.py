# -*- coding: utf-8 -*-
"""value_ranking.py — 온보딩 가치관 강제순위 → 비교축 가중치.

왜 순위인가 (설계 대화 §성향)
    자유서술로 "무엇이 중요한가"를 물으면 사회적 바람직성 편향으로 "다 중요해요"에
    수렴한다. 강제순위(둘 중 뭐가 더?)는 트레이드오프를 강제해 진짜 우선순위를 드러낸다.
    Schwartz 기본가치·Schein 커리어앵커 계열의 검증된 접근을 단순화한 것.

역할 분담
    · 가치관(무엇을 원하는가) → 이 순위질문 (온보딩 1회, 초기값)
    · 사고·대처 스타일(어떻게 처리하는가) → 일기 언어지표(metrics) = disposition.delivery_style
    순위는 고정값이 아니라 '초기값'이다. 일기가 쌓이면 언어지표로 갱신한다.

출력
    5개 비교축 가중치(합 1) + 서술 우선순위. 예측 시나리오에서 '어느 축부터 서술할지'.
    backend 매핑: 경제→경제적안정도, 성장→성장가능성, 관계·자기실현·안정→삶의질 프록시.

카드 수가 축마다 달라도 편향되지 않게, 축 점수는 '카드 평균'으로 계산한다.

standalone(모델 불필요):
    python diary_module/qmode/value_ranking.py
"""

from __future__ import annotations

# 8개 가치 카드 → 5개 비교축. (단어·구성은 조정 가능)
CARDS = [
    {"id": "money",     "label": "경제적 여유",   "desc": "돈 걱정 없이 사는 것",           "axis": "경제"},
    {"id": "status",    "label": "인정·지위",     "desc": "일에서 인정받고 자리를 갖는 것", "axis": "경제"},
    {"id": "family",    "label": "가족·사랑",     "desc": "가까운 사람과의 깊은 유대",       "axis": "관계"},
    {"id": "friends",   "label": "친구·소속",     "desc": "사람들과 어울리고 소속되는 것",   "axis": "관계"},
    {"id": "growth",    "label": "배움·성취",     "desc": "실력이 늘고 목표를 이루는 것",     "axis": "성장"},
    {"id": "freedom",   "label": "자유·자율",     "desc": "내 방식대로 결정하며 사는 것",     "axis": "자기실현"},
    {"id": "meaning",   "label": "의미·나다움",   "desc": "의미 있고 나다운 삶",             "axis": "자기실현"},
    {"id": "stability", "label": "건강·안정",     "desc": "몸과 삶이 안정적인 것",           "axis": "안정"},
]
AXES = ["경제", "관계", "성장", "자기실현", "안정"]

# 예측 비교축 → backend 지표(서술 연결용).
#
# 예전엔 backend 지표가 3개(경제적안정도·성장가능성·삶의질)뿐이라 관계·자기실현·안정
# 세 축이 전부 '삶의질' 하나로 접혔다. 온보딩에서 '가족·사랑' 을 1순위로 골라도
# '자유·자율' 을 골라도 같은 지표로 매핑돼, 사용자가 정렬한 답이 결과에 남지 않았다.
# backend 가 5축으로 바뀌면서(indicators.INDICATOR_KEYS) 이제 **항등 매핑**이다.
AXIS_TO_INDICATOR = {ax: ax for ax in AXES}
_BY_ID = {c["id"]: c for c in CARDS}
_LABEL_TO_ID = {c["label"]: c["id"] for c in CARDS}

# 최초 로그인 시 '제일 처음' 1회 게이트 — 일기 로테이션과 별도(드래그 정렬 UI).
# 특정 '날'이 아니라 '성향 프로파일이 아직 없을 때' 성향 파악용으로 맨 앞에 낸다.
ONBOARDING = {
    "id": "V0",
    "type": "ranking",                 # 서술이 아니라 드래그 순위 입력
    "gate": "first_login",            # 첫 로그인 1회, 일기 시작 전 '제일 처음'
    "prompt": "시작하기 전에 — 지금 내 삶에서 중요한 순서대로 정렬해 주세요.",
    "sub": "정답은 없어요. 둘 중 뭐가 더 중요한지 고르다 보면 우선순위가 드러납니다.",
    "cards": CARDS,
    "note": "성향 파악용 최초 1회. 이후 일기 언어지표로 갱신됨(고정 성향 아님).",
}


def onboarding_question():
    """최초 로그인 시 제일 처음 낼 가치순위 질문 descriptor."""
    return ONBOARDING


def _resolve(ranked):
    """id 또는 label 리스트 → id 리스트(유효한 것만, 순서 유지)."""
    out = []
    for r in ranked or []:
        cid = r if r in _BY_ID else _LABEL_TO_ID.get(r)
        if cid and cid not in out:
            out.append(cid)
    return out


def axis_weights(ranked):
    """순위(위→아래) → {축: 가중치(합 1)}.

    ranked : 카드 id(또는 label)를 중요한 순으로 정렬한 리스트. 부분 순위 허용
             (빠진 카드는 최하위로 처리).
    점수: 위에서부터 N, N-1, …, 1점. 빠진 카드는 0점.
    축 점수 = 그 축 카드들의 '평균 점수'(카드 수 불균형 보정) → 합이 1이 되게 정규화.
    """
    ids = _resolve(ranked)
    n = len(CARDS)
    pts = {c["id"]: 0 for c in CARDS}
    for pos, cid in enumerate(ids):
        pts[cid] = n - pos                      # 1등 = n점
    # 축별 평균 점수
    axis_raw = {}
    for ax in AXES:
        cards = [c["id"] for c in CARDS if c["axis"] == ax]
        axis_raw[ax] = sum(pts[c] for c in cards) / len(cards)
    total = sum(axis_raw.values()) or 1.0
    return {ax: round(axis_raw[ax] / total, 4) for ax in AXES}


def narrate_order(weights):
    """가중치 → 서술 우선순위(높은 축부터). 동점은 AXES 고정 순서로 안정 정렬."""
    return sorted(AXES, key=lambda a: (-weights.get(a, 0), AXES.index(a)))


def profile(ranked):
    """순위 → 성향 프로파일 dict(예측 스크립트 주입용)."""
    w = axis_weights(ranked)
    order = narrate_order(w)
    return {
        "weights": w,
        "narrate_order": order,
        "primary": order[:2],
        "block": build_block(w, order),
    }


def build_block(weights, order=None):
    """예측 서사 프롬프트에 붙일 '내용 강조 순서' 블록.

    온보딩 초기값임을 명시 — 일기 언어지표로 갱신됨(고정 성향으로 단정 금지).
    """
    order = order or narrate_order(weights)
    lines = [
        "[가치 우선순위 — 온보딩 초기값. 시나리오 '내용 강조 순서'의 가중치.",
        " 고정 성향 아님: 일기가 쌓이면 언어지표로 갱신됨. 단정적으로 규정하지 말 것.]",
        "· 서술 우선순위(높은 축부터):",
    ]
    for i, ax in enumerate(order, 1):
        ind = AXIS_TO_INDICATOR.get(ax, "")
        lines.append(f"   {i}) {ax} (가중치 {weights[ax]:.2f} · 예측지표 {ind})")
    lines.append(f"· 1순위: {order[0]} → 이 유저에겐 '{order[0]}' 관련 결과부터 서술.")
    return "\n".join(lines)


if __name__ == "__main__":
    import json

    print("=== 카드 8개 → 축 5개 ===")
    for c in CARDS:
        print(f"  {c['label']:10s} → {c['axis']}")

    # 시나리오 A — 관계·안정 우선(전형적 '안정 추구형')
    rankedA = ["family", "stability", "friends", "money", "meaning",
               "growth", "freedom", "status"]
    pA = profile(rankedA)
    print("\n=== A: 관계·안정 우선 ===")
    print("가중치:", json.dumps(pA["weights"], ensure_ascii=False))
    print("서술순서:", " → ".join(pA["narrate_order"]))
    print(pA["block"])

    # 시나리오 B — 성장·자기실현 우선('도전형')
    rankedB = ["growth", "freedom", "meaning", "money", "status",
               "family", "friends", "stability"]
    pB = profile(rankedB)
    print("\n=== B: 성장·자기실현 우선 ===")
    print("가중치:", json.dumps(pB["weights"], ensure_ascii=False))
    print("서술순서:", " → ".join(pB["narrate_order"]))
    print("1·2순위:", pB["primary"])

    # 부분 순위(상위 3개만 정렬) — 나머지 최하위 처리
    print("\n=== 부분 순위(상위 3만) ===")
    pP = profile(["money", "status", "growth"])
    print("가중치:", json.dumps(pP["weights"], ensure_ascii=False))
    print("서술순서:", " → ".join(pP["narrate_order"]))
