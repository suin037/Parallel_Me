# metrics.py — L2 언어지표 (Kiwi 형태소 + 부정어 처리)
from kiwipiepy import Kiwi
kiwi = Kiwi()

FIRST_SINGULAR = {"나", "내", "제", "저", "날"}

ABSOLUTIST = {
    "항상", "언제나", "늘", "맨날", "매번", "항시", "절대", "결코", "전혀",
    "무조건", "반드시", "꼭", "전부", "모두", "모든", "전체", "완전", "죄다",
    "아무", "하나", "영원", "평생", "최악", "제일",
}
INSIGHT = {"왜냐", "때문", "그래서", "그러니까", "깨닫", "생각", "돌이키", "결국", "사실"}
APPROACH = {"시도", "찾", "계획", "준비", "노력", "극복", "해결", "도전", "묻", "버티"}
AVOIDANT = {"피하", "미루", "포기", "도망", "외면", "그만두", "나중", "싫"}

# 정서어를 긍/부정으로 분리 (방향 있는 정서밀도)
EMOTION_POS = {"행복", "기쁘", "즐겁", "설레", "뿌듯", "벅차", "편안", "감사", "만족", "좋"}
EMOTION_NEG = {"슬프", "화나", "불안", "무섭", "외롭", "속상", "서운", "우울", "짜증",
               "답답", "괴롭", "힘들", "지치", "억울", "후회", "실패", "귀찮", "싫", "밉"}

# 부정 표현 (앞 형태소를 뒤집음)
NEGATION = {"안", "못", "없", "말", "아니"}


def analyze_text(text):
    tokens = kiwi.tokenize(text)
    total = len(tokens)
    if total == 0:
        return {}

    forms = [t.form for t in tokens]
    tags = [t.tag for t in tokens]

    def near_negation(i, back=1, fwd=2):
        """i번째 형태소 앞뒤로 부정어가 있는지"""
        # 앞: '안', '못' (MAG 부사 부정)
        for j in range(max(0, i - back), i):
            if forms[j] in ("안", "못") and tags[j].startswith("MAG"):
                return True
        # 뒤: '없', '않', '말', '아니' (보조용언·형용사)
        for j in range(i + 1, min(i + 1 + fwd, total)):
            if forms[j] in ("없", "않", "말", "아니", "못"):
                return True
        return False

    first = sum(1 for t in tokens if t.tag == "NP" and t.form in FIRST_SINGULAR)
    absol = sum(1 for i, t in enumerate(tokens)
                if t.tag.startswith(("MAG", "MM", "NN")) and t.form in ABSOLUTIST)

    # 통찰: 부정 결합 시 제외 ("생각 안 났다" 등)
    insight = sum(1 for i, t in enumerate(tokens)
                  if t.tag.startswith(("V", "NN", "MAG")) and t.form in INSIGHT
                  and not near_negation(i))

    approach = sum(1 for i, t in enumerate(tokens)
                   if t.tag.startswith(("V", "NN")) and t.form in APPROACH
                   and not near_negation(i))
    avoid = sum(1 for i, t in enumerate(tokens)
                if t.tag.startswith(("V", "NN", "MAG")) and t.form in AVOIDANT)

    # 정서: 긍/부정 분리 + 부정어 뒤집기
    pos = neg = 0
    for i, t in enumerate(tokens):
        if not t.tag.startswith(("VA", "VV", "NN")):
            continue
        flip = near_negation(i)
        if t.form in EMOTION_POS:
            neg += 1 if flip else 0
            pos += 0 if flip else 1
        elif t.form in EMOTION_NEG:
            pos += 1 if flip else 0   # "안 슬프다" → 긍정 쪽
            neg += 0 if flip else 1

    emo_total = pos + neg
    past = sum(1 for t in tokens if t.tag == "EP")
    ef = max(sum(1 for t in tokens if t.tag == "EF"), 1)

    return {
        "n_tokens": total,
        "first_person_ratio": round(first / total, 4),
        "absolutist_ratio": round(absol / total, 4),
        "insight_ratio": round(insight / total, 4),
        "approach_count": approach,
        "avoidant_count": avoid,
        "coping_balance": round((approach - avoid) / max(approach + avoid, 1), 3),
        "emotion_density": round(emo_total / total, 4),
        "emotion_valence": round((pos - neg) / max(emo_total, 1), 3),  # -1~+1
        "past_ratio": round(past / ef, 3),
    }


def rag_triggers(m):
    t = []
    if m.get("first_person_ratio", 0) > 0.05:
        t.append("liwc_first_person_depression")
    if m.get("absolutist_ratio", 0) > 0.015:
        t.append("absolutist_thinking")
    if m.get("insight_ratio", 0) > 0.02:
        t.append("liwc_cognitive_reappraisal")
    if m.get("coping_balance", 0) < -0.2:
        t.append("avoidant_coping")
    if m.get("emotion_density", 0) > 0.10 and m.get("insight_ratio", 0) < 0.015:
        t.append("liwc_emotion_immersion_caveat")
    return t


def interpret(m):
    """지표 조합 → 상태 한 줄 요약 (리포트 보조). 위에서부터 우선순위."""
    if not m:
        return "분석 불가"
    fp = m["first_person_ratio"]
    ab = m["absolutist_ratio"]
    ins = m["insight_ratio"]
    cop = m["coping_balance"]
    ed = m.get("emotion_density", 0)
    ev = m.get("emotion_valence", 0)

    # 1) 반추: 자기초점 + 흑백사고 + 통찰 없음
    if fp > 0.08 and ab > 0.02 and ins < 0.02:
        return "반추 경향 — 자기초점·흑백사고 신호"

    # 2) 부정 정서 몰입: 부정 정서 강한데 통찰이 없어 소화 안 되는 상태
    if ed > 0.08 and ev < -0.5 and ins < 0.02:
        return "부정 정서 몰입 — 소화보다 반복 신호"

    # 3) 회복: 인과·통찰어 + 능동 대처
    if ins > 0.03 and cop > 0:
        return "인지적 재구성 — 회복 방향 신호"

    # 4) 회피
    if cop < -0.3:
        return "회피 대처 — 문제 미루기 신호"

    # 5) 능동
    if cop > 0.3:
        return "능동 대처 — 문제 접근 신호"

    # 6) 긍정 정서 우세 (신호는 약하지만 방향은 긍정)
    if ed > 0.06 and ev > 0.5:
        return "긍정 정서 우세 — 안정적 신호"

    return "뚜렷한 언어 패턴 없음"


if __name__ == "__main__":
    tests = [
        "나는 항상 실패해. 아무도 날 이해 못 해. 다 내 잘못인 것 같아.",
        "왜 이렇게 됐는지 생각해봤다. 돌이켜보니 조급했다. 다음엔 준비해보려 한다.",
        "그냥 다 귀찮다. 하기 싫어서 계속 미뤘다. 나중에 하지 뭐.",
        "오늘 발표를 준비했다. 떨렸지만 끝까지 노력해서 해냈다.",
        "생각이 안 났다. 하나도 기억이 안 나.",          # 부정 처리 테스트
        "이제 안 슬프다. 오히려 후련하다.",              # 정서 뒤집기 테스트
    ]
    for t in tests:
        m = analyze_text(t)
        print(f"\n{t}")
        print(f"  1인칭 {m['first_person_ratio']} | 절대어 {m['absolutist_ratio']} | "
              f"통찰 {m['insight_ratio']} | 대처 {m['coping_balance']} | "
              f"정서밀도 {m['emotion_density']} | 정서극성 {m['emotion_valence']} | "
              f"과거 {m['past_ratio']}")
        print(f"  판정: {interpret(m)}")
        print(f"  RAG: {rag_triggers(m)}")