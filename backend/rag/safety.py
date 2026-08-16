"""위기·고통 신호 안전 분기 — 심리 조언 생성 모듈의 필수 리스크 관리 장치.

감정 신호(및 일기 텍스트)에서 급성 위기/강한 고통을 감지해, 평소의 '행동 제안'식
서사 대신 톤을 낮추거나 전문 자원 안내로 분기한다. 두 단계 게이트:

  1) crisis (급성 위기)  : 일반 서사·행동제안을 내지 않고 자원 안내로 하드 분기.
  2) high_distress (강한 고통): 서사는 생성하되 행동제안을 강요하지 않고 톤을 낮춘다.
  3) normal              : 평소 흐름.

⚠️ 상담 번호는 안전 크리티컬이며 시기에 따라 바뀐다. 배포 전 반드시 최신 여부를
   확인할 것. (2024년 자살예방상담전화가 109로 통합됨.)
⚠️ 키워드 리스트는 초안이다. 실제 사용자 데이터로 오탐/누락을 보정해야 한다.
   특히 부정 어법("죽고 싶지 않아") 오탐은 후속 과제.
"""

# ── 급성 위기 신호: 감지 시 하드 분기(서사·행동제안 생략, 자원 안내) ──────────
CRISIS_SIGNALS = [
    "자살", "죽고 싶", "죽고싶", "자해", "사라지고 싶", "사라지고싶",
    "살고 싶지 않", "살기 싫", "끝내고 싶", "없어지고 싶", "다 끝내",
]

# ── 강한 고통 신호: 톤 완화 + 행동제안 비강요. (후회·자책 등 '작업 가능한' 감정은
#    제외 — 반사실·대처 카드가 정확히 다루는 정상 대상이라 여기서 억제하지 않는다.
#    팀 판단에 따라 조정 가능한 튜닝 지점.) ──────────────────────────────────
HIGH_DISTRESS_SIGNALS = [
    "무력감", "절망", "체념", "우울감", "소진", "번아웃", "공허", "압도감", "압도",
]

# 전문 상담 자원(안전 크리티컬 — 배포 전 최신 확인 필수).
CRISIS_RESOURCES = [
    "자살예방 상담전화 109 (24시간, 전화·문자)",
    "정신건강 위기상담 1577-0199",
    "청소년 상담 1388",
]


def assess_safety(emotions=None, text: str = ""):
    """감정 리스트 + (선택)일기 텍스트 → (level, matched_signals).

    level: 'crisis' | 'high_distress' | 'normal'
    """
    emotions = emotions or []
    haystack = " ".join(emotions) + " " + (text or "")

    crisis = [s for s in CRISIS_SIGNALS if s in haystack]
    if crisis:
        return "crisis", crisis

    distress = [s for s in emotions if s in HIGH_DISTRESS_SIGNALS]
    # 일기 텍스트에서도 고통 신호 탐지
    distress += [s for s in HIGH_DISTRESS_SIGNALS if s in (text or "") and s not in distress]
    if distress:
        return "high_distress", distress

    return "normal", []


def crisis_message() -> str:
    """급성 위기 시 서사 대신 반환할 지지 메시지 + 자원. 조언·행동제안을 하지 않는다."""
    lines = [
        "지금 많이 힘든 마음이 느껴져요. 그 마음을 혼자 감당하지 않으셔도 됩니다.",
        "지금 바로 이야기 나눌 수 있는 곳이 있어요:",
    ]
    lines += [f"· {r}" for r in CRISIS_RESOURCES]
    lines.append("당신의 이야기를 들어줄 사람이 늘 있습니다. 괜찮다면 오늘, 위 번호 중 한 곳에 닿아보세요.")
    return "\n".join(lines)
