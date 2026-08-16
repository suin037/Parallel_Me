# slang.py
# slang.py — 형태소 인식 슬랭 정규화
from kiwipiepy import Kiwi
kiwi = Kiwi()

# polarity: 정규화 실패해도 최소한 감정 극성은 보정
SLANG = {
    # 긍정
    "야르": ("분위기 좋다", "긍정"),
    "개찢": ("정말 잘했다", "긍정"), "찢었": ("정말 잘했다", "긍정"),
    "럭키비키": ("운이 좋다", "긍정"), "럭비": ("운이 좋다", "긍정"),
    "폼 미쳤": ("상태가 최고다", "긍정"), "폼미쳤": ("상태가 최고다", "긍정"),
    "갓생": ("성실한 삶", "긍정"), "갓벽": ("완벽하다", "긍정"),
    "존맛": ("정말 맛있다", "긍정"), "존잼": ("정말 재밌다", "긍정"),
    "꿀잼": ("재밌다", "긍정"), "개꿀": ("정말 좋다", "긍정"),
    "뽕차": ("벅차다", "긍정"), "지린다": ("대단하다", "긍정"),
    "쩐다": ("대단하다", "긍정"), "쩔어": ("대단하다", "긍정"),
    "갓띵작": ("명작이다", "긍정"), "폼미쳐": ("상태 최고다", "긍정"),
    "existed": (None, "긍정"),
    # 부정
    "킹받": ("짜증난다", "부정"), "빡친": ("화난다", "부정"),
    "빡쳐": ("화난다", "부정"), "빡침": ("화난다", "부정"),
    "극혐": ("정말 싫다", "부정"), "노잼": ("재미없다", "부정"),
    "노답": ("답이 없다", "부정"), "현타": ("허무하다", "부정"),
    "멘붕": ("혼란스럽다", "부정"), "현웃": (None, "긍정"),
    # 중립(정규화만)
    "오운완": ("오늘 운동 완료", "중립"),
    "손절": ("관계를 끊다", "부정"),
}

# 오탐 방지: 이 단어의 일부일 땐 치환 안 함
GUARD = {
    "지린": ["어지린", "어지러"],   # "어지러운"
    "손절": ["손절매"],             # 주식 용어
}

def normalize_slang(text):
    if not isinstance(text, str):
        return text, []
    hits = []
    result = text
    for k in sorted(SLANG, key=len, reverse=True):
        if k not in result:
            continue
        # 가드 체크
        blocked = any(g in text for g in GUARD.get(k, []))
        if blocked:
            continue
        norm, pol = SLANG[k]
        if norm:
            result = result.replace(k, norm)
        hits.append((k, pol))
    return result, hits


def slang_polarity(text):
    """일기에 섞인 슬랭의 긍/부정 카운트 (감정 모델 보조 신호)"""
    _, hits = normalize_slang(text)
    pos = sum(1 for _, p in hits if p == "긍정")
    neg = sum(1 for _, p in hits if p == "부정")
    return {"slang_pos": pos, "slang_neg": neg, "slang_hits": [h[0] for h in hits]}


if __name__ == "__main__":
    tests = [
        "그 카페 완전 야르였다", "발표 개찢었다", "킹받는데 참았음",
        "현타 오는 하루", "어지러운 하루였다",  # '지린' 오탐 테스트
        "주식 손절했다",                        # '손절매' 가드 테스트
        "fun한 하루 happy했다",                 # 영어 안 깨지는지
    ]
    for t in tests:
        norm, hits = normalize_slang(t)
        print(f"{t}\n  → {norm}   {hits}\n")