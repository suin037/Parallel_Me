# -*- coding: utf-8 -*-
"""card_map.py — 질문 ID → 이론카드 직결 매핑 (질문 경로 전용, ★핵심).

왜 벡터검색을 안 쓰나 (질문풀_설계.md §3)
    질문 답변은 '어떤 이론이 맞는지'를 질문 ID가 이미 알고 있다. 20장 남짓한 코퍼스에서
    코사인 유사도를 돌리면 이득 없이 오검색 위험만 생긴다. 그래서 질문 경로는
    ID→card_id 직접 조회로 카드를 확정한다.
      · 질문 답변  → 이 매핑으로 card_id 조회 → JSON 로드
      · 자유 일기칸 → psych_link.link_psych() (벡터검색) — 이 파일과 무관
    두 경로 모두 crisis.py + rag.safety 게이트를 통과해야 한다(게이트는 session.py).

카드 존재 검증
    validate() 가 매핑된 모든 card_id 가 실제 카드 JSON(기존 + cards_new)에 있는지
    확인한다. print_review() 는 근거가 확정되지 않은 PROVISIONAL 매핑을 사람이
    검토하도록 출력한다.

standalone:
    python diary_module/qmode/card_map.py      # 매핑 검증 + 검토 목록 출력
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent                      # repo 루트
EXISTING_CARDS = ROOT / "data" / "lanollab" / "심리학_이론카드"
NEW_CARDS = HERE / "cards_new"

# ── 확정 매핑 (질문풀_설계.md §3에서 지정) ─────────────────────────────
#    거리두기·자기자비·BPS 문항은 이론이 문항 설계 자체를 낳았으므로 직결이 확실하다.
CONFIRMED = {
    "C2": "self_distancing_reflection_002",    # '옆에서 지켜본 사람이라면' = 거리두기 성찰
    "R5": "self_distancing_reflection_002",    # '같은 상황의 친구를 본다면' = 거리두기 성찰
    "D5": "future_self_bps_001",               # '5년 뒤 잘 풀린 하루' = 최선의 미래 자기
    "D6": "self_compassion_kindness_001",      # '친구에게 말하듯' = 자기친절
}

# ── D4(부러움) — aggregate.classify_envy 판정으로 분기 ────────────────
#    선의=상승 동기(가치축), 악의=박탈감(위협). unclear 는 카드 미부여(축 반영 금지).
ENVY_SPLIT = {
    "benign": "envy_benign_001",
    "malicious": "envy_malicious_002",
    "unclear": None,
}

# ── 기준선 문항 — 카드 없음 (시계열 비교/축 추출 목적) ────────────────
BASELINE = {"C1", "T1", "D2"}

# ── 잠정 매핑 (PROVISIONAL) — 기존 카드에서 골랐고 사람 검토 필요 ──────
#    ⚠️ 임의로 지어내지 않았다. 아래는 실재하는 card_id 중 근거가 가장 가까운 것을
#       고른 것이며, 파일럿 전 검토 대상이다. (envy 외 신규 카드는 만들지 않음)
PROVISIONAL = {
    # T4: '시간이 녹는 활동 + 후 기분' = 몰입/흥미 → 확장-구축의 흥미 카드.
    #     단 risk_type=소진이라 '몰입 후 공허'면 방향이 반대일 수 있어 검토 필요.
    "T4": ("posemo_interest_002",
           "몰입/흥미(Interest) — 시간이 녹는 활동=탐색적 몰입. 소진 방향이면 재검토"),
    # R3: '잘 됐던 일 + 왜' = Three Good Things/음미 → 긍정적 의미찾기 카드.
    "R3": ("posemo_positive_meaning_008",
           "긍정적 의미찾기 — '왜 잘 됐나'는 좋은 일의 의미 부여. Seligman TGT 계열"),
    # R4: '나답지 않은 순간' = 자기불일치. 정확히 맞는 카드가 없어 인지평가로 근사.
    #     ⚠️ 매칭 약함 — 파일럿 후 전용 카드(자기개념/가치일치) 신설 고려.
    "R4": ("coping_appraisal_001",
           "인지적 재평가로 근사(매칭 약함) — 자기불일치 전용 카드 부재, 신설 검토"),
    # D1: '망설인 선택 + 마음에 걸린 것' = 1·2차 인지평가(위협/도전·자원).
    "D1": ("coping_appraisal_001",
           "인지적 평가(1·2차) — 의사결정 갈림길·자원 가늠에 직결(decision_types 일치)"),
    # D3: '1년 전 나 vs 지금' = 시간적 자기거리두기. 신규 거리두기 카드로 근사.
    "D3": ("self_distancing_reflection_002",
           "시간적 거리두기 — 과거 자기를 대상화. 거리두기 성찰 카드로 근사"),
}


def card_ids_for(qid, envy_verdict=None):
    """질문 ID → 부여할 card_id 리스트(없으면 빈 리스트).

    qid          : 질문 ID('C2', 'D4' 등)
    envy_verdict : D4 전용 — 'benign'|'malicious'|'unclear'
                   (aggregate.classify_envy 결과). D4는 이 값으로 카드가 갈린다.
    """
    if qid == "D4":
        cid = ENVY_SPLIT.get(envy_verdict or "unclear")
        return [cid] if cid else []
    if qid in BASELINE:
        return []
    if qid in CONFIRMED:
        return [CONFIRMED[qid]]
    if qid in PROVISIONAL:
        return [PROVISIONAL[qid][0]]
    return []


# ── 카드 로더 (직결 조회용) ──────────────────────────────────────────
_CARD_CACHE = None


def _all_cards():
    """기존 카드 + cards_new 를 {card_id: card_dict} 로 로드(캐시)."""
    global _CARD_CACHE
    if _CARD_CACHE is None:
        cache = {}
        dirs = [d for d in (EXISTING_CARDS, NEW_CARDS) if d.exists()]
        for d in dirs:
            for f in sorted(d.glob("cards_*_v1.json")):
                data = json.loads(f.read_text(encoding="utf-8"))
                for c in data.get("cards", []):
                    cache[c["card_id"]] = c
        _CARD_CACHE = cache
    return _CARD_CACHE


def load_card(card_id):
    """card_id → 카드 dict(없으면 None). 질문 경로는 이걸로 카드를 직접 가져온다."""
    return _all_cards().get(card_id)


def load_cards_for(qid, envy_verdict=None):
    """질문 ID → 카드 dict 리스트(존재하는 것만)."""
    return [c for c in (load_card(i) for i in card_ids_for(qid, envy_verdict)) if c]


# ── 검증 ────────────────────────────────────────────────────────────
def _mapped_ids():
    ids = set(CONFIRMED.values())
    ids |= {v for v in ENVY_SPLIT.values() if v}
    ids |= {v[0] for v in PROVISIONAL.values()}
    return ids


def validate():
    """매핑된 모든 card_id 가 실제 카드에 존재하는가. (missing_ids, 전체 카드 수)."""
    have = set(_all_cards())
    missing = sorted(_mapped_ids() - have)
    return missing, len(have)


def print_review():
    missing, n_cards = validate()
    print(f"[카드 로드] 총 {n_cards}장 "
          f"(기존: {EXISTING_CARDS.name}, 신규: {NEW_CARDS.name})")
    print()
    print("── 확정 매핑 (CONFIRMED) ──────────────────────────────")
    for q, c in CONFIRMED.items():
        print(f"  {q:3s} → {c}")
    print(f"  D4  → benign:{ENVY_SPLIT['benign']} / "
          f"malicious:{ENVY_SPLIT['malicious']} / unclear:없음")
    print(f"  기준선(카드 없음): {', '.join(sorted(BASELINE))}")
    print()
    print("── 잠정 매핑 (PROVISIONAL) — ⚠️ 사람 검토 필요 ─────────")
    for q, (c, why) in PROVISIONAL.items():
        print(f"  {q:3s} → {c}")
        print(f"       근거: {why}")
    print()
    if missing:
        print(f"❌ 실제 카드에 없는 card_id: {missing}")
        print("   → cards_new 작성 누락 또는 오타. 벡터DB 빌드 전에 반드시 해결.")
    else:
        print("✅ 매핑된 모든 card_id 가 실제 카드에 존재합니다.")


if __name__ == "__main__":
    print_review()
