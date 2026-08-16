"""일기 감정분석 → 심리 이론 RAG 브리지.

diary_module 의 DiaryAnalyzer.analyze() 출력을 backend/rag 의 심리 이론카드
검색기에 연결해, '감정 상태 → 이론 근거 + 행동제안 후보' 재료를 만든다.

설계 원칙
- 재료 제공형: 최종 서사(문장)는 만들지 않는다. backend/utils/claude_api.py 가
  이 근거 블록을 프롬프트에 주입해 통합한다. (LLM 호출 없음 → 비용·지연 0)
- 안전 우선: 급성 위기 신호는 카드 대신 상담자원 안내로 하드 분기한다.
- 감정 주도 검색: 시뮬레이션(지표 주도)과 달리 일기는 감정이 1차 신호이므로,
  대분류 감정 극성을 삶의질 프록시 점수로 환산해 검색 게이트를 통과시킨다.

현 카드셋(coping·positive_emotion)은 전부 direction='낮을수록_적용'(고통 개입용)이라,
부정 감정은 '낮음', 기쁨도 '중간'으로 두어 카드가 걸리게 한다('높음'은 두지 않는다).

사용:
    from infer import DiaryAnalyzer
    from psych_link import analyze_and_link
    az = DiaryAnalyzer(ckpt="../model_v3_e6.pt")
    r = analyze_and_link(az, "오늘 발표를 망쳤다...")
    print(r["psych"]["prompt_block"])
"""

import sys
from pathlib import Path

# backend/ 를 경로에 올려 rag 패키지(psych_retriever 등)를 임포트한다.
_ROOT = Path(__file__).resolve().parent.parent
_BACKEND = _ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from rag.psych_narrative import build_psych_prompt_block  # noqa: E402
from rag.psych_retriever import retrieve, bucket           # noqa: E402
from rag import safety                                      # noqa: E402

# 대분류 감정 → 삶의질 프록시 점수(0~1). 모두 낮음/중간에 떨어지도록 매핑.
_COARSE_QOL = {
    "분노": 0.20, "슬픔": 0.20, "불안": 0.20,
    "상처": 0.25, "당황": 0.40, "기쁨": 0.60,
}
_DEFAULT_QOL = 0.35


def _emotion_terms(diary):
    """diary 결과 → 의미검색용 감정어 리스트(중복 제거, 순서 유지)."""
    terms = []
    dom = diary.get("dominant", {})
    for key in ("coarse", "fine", "display"):
        v = dom.get(key)
        if v and v not in terms:
            terms.append(v)
    # 보조 감정: 대분류 분포 상위 중 확률이 유의미한 것만(반대 극성 노이즈 방지).
    dist = diary.get("coarse_dist", {})
    for name, prob in sorted(dist.items(), key=lambda x: -x[1])[:2]:
        if name and prob >= 0.15 and name not in terms:
            terms.append(name)
    return terms


def link_psych(diary, text="", k=3):
    """일기 분석 결과(dict) → 심리 RAG 재료(dict).

    diary : DiaryAnalyzer.analyze() 반환 dict
    text  : 원문(위기 재확인용, 선택)
    반환 : {
        safety_level, safety_hits, focus_indicator, level, score,
        emotions, cards, prompt_block[, crisis_message]
    }
    """
    emotions = _emotion_terms(diary)

    # 1) 안전 게이트 — 일기 자체 위기판정 + rag.safety 재확인.
    s_level, s_hits = safety.assess_safety(emotions=emotions, text=text)
    crisis_hard = (
        bool(diary.get("block_report"))
        or diary.get("crisis_level", 0) >= 2
        or s_level == "crisis"
    )
    if crisis_hard:
        return {
            "safety_level": "crisis",
            "safety_hits": s_hits,
            "focus_indicator": None,
            "level": None,
            "score": None,
            "emotions": emotions,
            "cards": [],
            "prompt_block": "",
            "crisis_message": safety.crisis_message(),
        }

    # 2) 대분류 감정 극성 → 삶의질 프록시 점수 → 버킷(낮음/중간/높음).
    dom_coarse = diary.get("dominant", {}).get("coarse")
    score = _COARSE_QOL.get(dom_coarse, _DEFAULT_QOL)
    level = bucket(score, "삶의질")

    # 3) 이론카드 검색 — 감정 주도(지표 불일치도 유사도로 허용).
    cards = retrieve(
        indicator="삶의질", score=score, emotions=emotions,
        allow_indicator_miss=True, k=k,
    )

    # 4) 레이어3 프롬프트용 근거 블록(최종 문장 아님, '재료').
    evidence = {"focus_indicator": "삶의질", "level": level, "score": score, "cards": cards}
    block = build_psych_prompt_block(evidence)

    return {
        "safety_level": s_level,          # normal | high_distress
        "safety_hits": s_hits,
        "focus_indicator": "삶의질",
        "level": level,
        "score": score,
        "emotions": emotions,
        "cards": cards,
        "prompt_block": block,
    }


def analyze_and_link(analyzer, text, k=3):
    """DiaryAnalyzer.analyze() + link_psych() 한 번에. diary 에 'psych' 키를 붙여 반환."""
    diary = analyzer.analyze(text)
    if "error" in diary:
        return diary
    diary["psych"] = link_psych(diary, text=text, k=k)
    return diary


if __name__ == "__main__":
    # 모델 없이 브리지만 검증하는 목(mock) 테스트.
    mock = {
        "crisis_level": 0,
        "block_report": False,
        "dominant": {"coarse": "슬픔", "fine": "후회되는", "display": "슬픔"},
        "coarse_dist": {"슬픔": 0.6, "불안": 0.3, "분노": 0.1},
    }
    r = link_psych(mock, text="그때 그 선택을 후회한다. 계속 자책하게 된다.")
    print("안전:", r["safety_level"], "| 초점:", r["focus_indicator"], r["level"],
          f"(score {r['score']})")
    print("감정 쿼리:", r["emotions"])
    print("검색 카드:", [c["card_id"] for c in r["cards"]])
    print("-" * 60)
    print(r["prompt_block"])
