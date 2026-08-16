# -*- coding: utf-8 -*-
"""personas.py — 합성 데이터셋용 페르소나 4종.

레퍼런스 일기(공시생·런던석사·창업·이직)에서 뽑은 실제 인물 원형을, 가치순위가
뚜렷이 갈리도록 배치했다. 같은 예측 수치라도 이 4명의 '미래 서사'가 달라지는 것을
보여주는 게 데이터셋의 목적.

각 페르소나:
  ranked        : 온보딩 가치순위(value_ranking.CARDS id, 중요한 순). → 5축 가중치 초기값.
  coping        : 예상 대처 경향(회피/능동/혼합) — 답변 어휘로 드러낼 기준.
  voice         : 말투·소재 힌트(VOICE_GUIDE 위에 페르소나색 얹기).
  situation     : 30일간의 삶의 배경(문항 답변의 재료).
"""

PERSONAS = {
    "P1_stability": {
        "name": "수현",
        "label": "안정·관계형 (지방직 공시생)",
        "ranked": ["stability", "family", "friends", "money", "meaning",
                   "growth", "freedom", "status"],
        "coping": "회피~버티기 혼합 (미룸·유기 잦지만 엄마·루틴으로 버팀)",
        "voice": "공시생체. 정병·빵꾸·ㄱㅊ·유기, 학원강사(써니쌤)·모고점수·"
                 "스카·간장계란밥. 자책 뒤 '그래도 해야지'. 엄마 반찬으로 버팀.",
        "situation": "지방직 시험 D-30→시험→발표대기. 국어논리 약점, 행법 빵꾸, "
                     "혼자 스카 생활, 엄마와 동거, 합격=안정에 삶이 걸림.",
    },
    "P2_growth": {
        "name": "린",
        "label": "도전·성장·자율형 (런던 석사)",
        "ranked": ["growth", "freedom", "meaning", "friends", "status",
                   "money", "family", "stability"],
        "coping": "능동 (새 경험 찾아 나서고 실험·시도 언어 많음)",
        "voice": "런던 유학+알바체. 의식의 흐름, 자조 유머, 여행·마켓알바·"
                 "헬스장·에세이 점수. 돈 걱정하면서도 경험엔 지름. 영어 섞임.",
        "situation": "런던 석사 마무리, 카페·베이커리 알바 병행, 사르데냐·브라이튼 여행, "
                     "에세이 distinction↔fail 롤러코스터, 근로소득 없는 불안.",
    },
    "P3_meaning": {
        "name": "다운",
        "label": "관계·자기실현형 (직장인 + 사이드 브랜드, 전직 고민)",
        "ranked": ["meaning", "friends", "family", "freedom", "growth",
                   "status", "money", "stability"],
        "coping": "능동+정서 (몰입해서 밀어붙이되 감정을 크게 느끼고 함께 소화)",
        "voice": "지랄일기체. '.. .' 말줄임, 극락도락, 자기대상화, 동료 채연과 공동체, "
                 "회사·브랜드 병행 고됨. 힘들면 울고 또 버팀. 밥 못 챙기는 삶.",
        "situation": "낮엔 회사원, 밤·주말엔 동료 채연과 작은 브랜드 운영. 이 일에 의미·"
                     "공동체를 느껴 '회사를 나와 이걸 본업으로 할지(전직)' 고민. 둘 다 "
                     "하느라 번아웃·밥 못 챙김. 돈보다 의미·사람으로 감.",
    },
    "P5_balance": {
        "name": "은우",
        "label": "워라밸·균형형 (과로 직장인, 이직 고민)",
        "ranked": ["freedom", "stability", "meaning", "friends", "family",
                   "growth", "money", "status"],
        "coping": "혼합 (번아웃으로 미루다가도 삶을 바꾸려 조금씩 알아봄)",
        "voice": "과로 직장인 번아웃체. 야근·주말출근·현타, 저녁 있는 삶 갈망, "
                 "소소한 취미(운동·넷플·등산)로 버팀. 자조 섞인 담담함.",
        "situation": "광고대행사 과로 3년차, 번아웃. 연봉 좀 줄어도 워라밸·저녁 있는 "
                     "삶 위해 이직 고민. 건강·취미·관계를 되찾고 싶음. 지원은 자꾸 미룸.",
    },
    # ── 확장 데모 (20~30대 밖) ──
    # 서비스 대상은 20~30대지만 구조는 연령·주제에 묶여 있지 않다는 걸 보여주는 페르소나.
    # 건강 축은 이미 qmode/health_input.py 가 또래(성별×연령대) 유병률 병치로 받고 있어,
    # 일기·가치순위·리포트 경로는 그대로 재사용된다.
    # ⚠ 단, 예측 모델(소득·이직 ML)은 학습 피처가 고정이라 이 페르소나엔 안 붙는다
    #    (health_input.py 범위 A). 리포트·서사 개인화까지가 확장 범위다.
    "H1_health": {
        "name": "명숙",
        "label": "건강·안정형 (52세, 수면·통증 관리 + 은퇴 준비)",
        "ranked": ["stability", "family", "meaning", "friends", "freedom",
                   "growth", "money", "status"],
        "coping": "회피→관리 전환 (참다가 기록·병원으로 옮겨감)",
        "voice": "담담한 중년체. 몸 신호·수면·통증·검진 수치, 가족 언급 잦음. "
                 "과장 없이 짧게 적고 '나이 탓'으로 넘기던 말이 뒤로 갈수록 줄어듦.",
        "situation": "새벽 각성·어깨 통증·경계 수치로 시작해 기록·걷기·물리치료로 "
                     "관리 체계를 만들어가는 1년. 은퇴 후 건강 비용도 계산 시작.",
    },
    "P4_economy": {
        "name": "지호",
        "label": "경제·성취형 (이직러)",
        "ranked": ["money", "status", "growth", "stability", "freedom",
                   "meaning", "family", "friends"],
        "coping": "능동·분석 (타임라인·전략으로 상황을 구조화)",
        "voice": "이직러체. 담백·정리형, 커리어 타임라인·연봉·상사·업무스킬, "
                 "비교와 성과 언어. 감정보다 계획. 슬랭 적고 문장 완결적.",
        "situation": "3번째 직장 6개월차 적응 완료, 좋은 상사로 물경력 탈출, "
                     "다음 이직·연봉·커리어 상승 저울질, 성과·인정에 민감.",
    },
}


def onboarding_weights(persona_key):
    """페르소나 → 온보딩 5축 가중치(value_ranking)."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from qmode import value_ranking
    return value_ranking.axis_weights(PERSONAS[persona_key]["ranked"])


if __name__ == "__main__":
    import json
    for k, p in PERSONAS.items():
        w = onboarding_weights(k)
        order = sorted(w, key=w.get, reverse=True)
        print(f"{k}  {p['label']}")
        print(f"   가중치: {json.dumps(w, ensure_ascii=False)}")
        print(f"   우선축: {' > '.join(order)}")
        print()
