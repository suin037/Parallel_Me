"""자유입력 선택지 → 예측 가능한 유형(kind) 분류 + 확신도 + 커버리지 계측.

유형(kind) 위에 **창업 맥락**(업종·규모)도 같은 방식으로 뽑는다
(`extract_startup_context`). 기업생멸 생존율 테이블은 업종 19개 × 규모 5개를
갖고 있는데 그 축을 안 열면 "카페 창업" 과 "IT 창업" 이 같은 숫자를 받는다.

## 왜 바꿨나
기존 `core.choice_kind()` 는 한국어 키워드 `in` 검사였다. 두 가지가 깨졌다.

1. **부정·대조를 못 읽는다.** "박사 안 가고 취업할래" 가 '박사' 하나로 진학이 됐다.
   "이직 말고 창업" 은 '이직' 이 먼저 매칭돼 창업을 놓쳤다.
2. **틀렸는지 알 수 없다.** 어디에도 안 걸리면 조용히 `기타` → 개인단위 레이어
   (L2/L3/L4)가 통째로 꺼지는데, 그게 얼마나 자주 일어나는지 아무도 몰랐다.

그래서 (a) 부정/대조 마커를 반영한 **점수 기반** 분류로 바꾸고, (b) `confidence` 를
함께 돌려주며, (c) 분류 결과를 집계해 **`기타` 비율(=커버리지 손실)을 측정**한다.
임베딩/LLM 분류로 가기 전에 '지금 얼마나 새고 있는지' 부터 숫자로 잡는 게 순서다.

분류는 결정적(deterministic)이라 테스트가 가능하고 지연·비용이 0 이다.
"""

from __future__ import annotations

import re
import threading
from collections import Counter
from dataclasses import dataclass, field

# 유형별 단서. 앞쪽일수록 강한 단서(가중치가 높다).
KEYWORDS: dict[str, list[tuple[str, float]]] = {
    # '차리' 만으로는 "차릴래·차려서" 를 못 잡는다(한국어 음절 블록이 달라
    # 부분문자열이 아니다). 활용형을 따로 넣는다.
    # '본업으로' 는 부업·사이드를 본업으로 돌리는 결정이라 창업 쪽 단서다.
    # ("회사 나와서 브랜드 본업으로" 가 기타로 새던 자리 — '회사 나와서' 자체는
    #  휴식·이직과도 겹쳐 단서로 쓰지 않는다.)
    "창업": [("창업", 1.0), ("사업", 0.8), ("자영", 1.0), ("개업", 1.0),
             ("장사", 0.8), ("프리랜", 0.6), ("startup", 1.0), ("법인", 0.6),
             ("차리", 0.7), ("차릴", 0.7), ("차려", 0.7), ("개원", 1.0),
             ("가게", 0.6), ("공방", 0.6), ("1인 기업", 0.9),
             ("본업으로", 0.6), ("본업 삼", 0.7), ("내 브랜드", 0.7)],
    "진학": [("진학", 1.0), ("대학원", 1.0), ("유학", 1.0), ("석사", 1.0),
             ("박사", 1.0), ("학업", 0.8), ("편입", 0.9), ("로스쿨", 1.0),
             ("전문대학원", 1.0), ("공부", 0.4)],
    "이직": [("이직", 1.0), ("전직", 1.0), ("옮기", 0.9), ("옮길", 0.9),
             ("옮겨", 0.9), ("다른 회사", 0.9), ("다른 데", 0.7),
             ("갈아타", 0.8), ("갈아탈", 0.8), ("스카웃", 0.8), ("스카우트", 0.8),
             ("연봉 높", 0.5), ("취업", 0.5), ("입사", 0.6), ("구직", 0.5),
             ("경력직", 0.7)],
    # '퇴사' 는 예전에 이직 단서(0.7)였다. 그래서 "퇴사하고 좀 쉬고 싶다" 가
    # 이직으로 분류돼 **다른 회사로 옮겼을 때의 소득효과**를 답했다. 쉬는 것과
    # 옮기는 것은 다른 결정이라 유형을 갈랐다.
    #   · 퇴사 + 갈 곳이 있다 → '이직' (옮기·전직·입사 단서가 같이 잡힌다)
    #   · 퇴사 + 갈 곳이 없다 → '휴식'
    # 단독 '퇴사' 는 후자로 본다 — 갈 곳이 정해졌으면 보통 그걸 같이 쓴다.
    "휴식": [("휴직", 1.0), ("쉬어가", 1.0), ("쉬고 싶", 1.0), ("쉬려", 0.9),
             ("쉴까", 0.9), ("쉬는 게", 0.8), ("쉬면서", 0.8),
             ("퇴사", 0.7), ("그만두", 0.8), ("그만둘", 0.8), ("번아웃", 0.9),
             ("소진", 0.6), ("공백기", 0.8), ("갭이어", 1.0), ("안식년", 1.0),
             ("재충전", 0.9), ("잠시 쉬", 1.0), ("좀 쉬", 0.9)],
    # A/B 비교에서 B쪽은 대개 '계속 다닐까' 라 활용형이 특히 자주 나온다.
    # '계속 다니' 만 있던 탓에 "지금 회사 계속 다닐까" 가 통째로 기타로 샜다.
    "유지": [("유지", 0.9), ("현상 유지", 1.0), ("현직", 0.9), ("잔류", 1.0),
             ("그대로", 0.8),
             ("계속 다니", 1.0), ("계속 다닐", 1.0), ("계속 다녀", 1.0),
             ("다닐까", 0.9), ("다니는 게", 0.9), ("계속 일하", 0.9),
             ("계속 할", 0.7), ("계속할", 0.7), ("계속 갈", 0.7),
             ("남기", 0.7), ("남는", 0.7), ("남을", 0.7), ("남아", 0.7),
             ("버티", 0.7), ("버틸", 0.7), ("버텨", 0.7), ("존버", 0.7)],
    # ── 커리어 밖 생활사건 (KOWEPS 종단 근거) ──────────────────────────────
    # 시연 입력을 재보니 기타로 새는 것의 대부분이 커리어가 아닌 인생 선택이었다.
    # KOWEPS 에 표본이 있어(결혼 1,063 · 자가 2,219 · 이사 6,854, 20~39세 전이쌍)
    # 처치효과를 낼 수 있는 것만 유형으로 연다 — 근거 없는 유형은 만들지 않는다.
    "결혼": [("결혼", 1.0), ("혼인", 0.9), ("식 올리", 0.8), ("웨딩", 0.8),
             ("프러포즈", 0.7), ("상견례", 0.8), ("혼자 살", 0.5), ("비혼", 0.9)],
    # 집을 '사는' 결정. 이사(거처 이동)와는 다른 질문이라 유형을 가른다.
    "주택": [("집을 사", 1.0), ("집 사", 0.9), ("집을 산", 1.0),
             ("집을 살", 1.0), ("집 살", 0.9), ("집을 매수", 1.0),
             ("집을 팔", 1.0), ("집을 판", 1.0), ("집을 매도", 1.0),
             ("아파트를 사", 1.0), ("아파트를 산", 1.0),
             ("아파트를 팔", 1.0), ("아파트를 판", 1.0), ("매매", 0.9),
             ("자가", 1.0), ("내 집", 0.9), ("분양", 0.9), ("청약", 0.9),
             ("주담대", 0.8), ("전세로 살", 0.6), ("전세 유지", 0.7),
             ("월세 계속", 0.6)],
    "이사": [("이사", 1.0), ("이사갈", 1.0), ("이사할", 1.0), ("이주", 0.7),
             ("옮겨 살", 0.8), ("내려갈", 0.5), ("올라갈", 0.4),
             ("독립할", 0.6), ("나가 살", 0.7), ("분가", 0.9)],
}

# 키워드 **뒤**에 붙어 그 선택지를 물리는 표현.
# 한국어는 서술어가 뒤에 오므로 부정·대조는 항상 대상 뒤에 붙는다
#   "박사 안 가고 취업"  → '안 가고' 가 무는 건 박사, 뒤의 취업이 아니다
#   "이직 말고 창업"     → '말고' 가 무는 건 이직, 뒤의 창업이 아니다
# 그래서 **앞쪽은 보지 않는다.** (앞을 보면 위 두 문장에서 취업·창업까지 같이 죽는다.)
#
# "안" 은 '안정' 같은 명사에 섞이므로 단독 음절로 쓰인 형태만 명시한다.
NEGATE_AFTER = (
    "안 ", "안가", "안감", "안갈", "안하", "안할", "안함", "안 가", "안 하",
    "않", "못 ", "못가", "못하",
    "말고", "대신", "보다는", "아니라", "포기", "그만두", "그만둘", "접고",
    "접을", "제외", "빼고",
)

_WINDOW_AFTER = 6      # 키워드 뒤 몇 글자까지 부정/대조를 볼지

MIN_CONFIDENCE = 0.34  # 이 아래면 유형을 단정하지 않는다(=기타로 넘김)


@dataclass
class ChoiceKind:
    """분류 결과. `kind` 만 쓰던 기존 코드와 호환되도록 문자열처럼도 동작한다."""

    kind: str
    confidence: float
    scores: dict[str, float] = field(default_factory=dict)
    matched: list[str] = field(default_factory=list)
    method: str = "rules"

    def __str__(self) -> str:          # noqa: D105
        return self.kind

    def __eq__(self, other) -> bool:   # noqa: D105 - kind == "이직" 비교 유지
        if isinstance(other, str):
            return self.kind == other
        return NotImplemented

    def __hash__(self) -> int:         # noqa: D105
        return hash(self.kind)


# ---------------------------------------------------------------- 계측
_lock = threading.Lock()
_STATS: Counter = Counter()
_LOW_CONF_SAMPLES: list[str] = []      # 기타/저확신 입력 표본(최근 것 일부만)
_MAX_SAMPLES = 30


def _record(text: str, res: ChoiceKind) -> None:
    with _lock:
        _STATS["total"] += 1
        _STATS[f"kind:{res.kind}"] += 1
        if res.kind == "기타" or res.confidence < MIN_CONFIDENCE + 0.1:
            _STATS["low_confidence"] += 1
            if len(_LOW_CONF_SAMPLES) < _MAX_SAMPLES:
                _LOW_CONF_SAMPLES.append(text[:80])


def classification_stats() -> dict:
    """분류 커버리지 — `기타` 비율이 곧 개인단위 레이어를 못 켠 비율이다.

    `/health` 로 노출한다. 이 값이 높으면 키워드 사전이나 분류 방식을 손봐야 한다는
    신호이며, 임베딩/LLM 분류 도입 여부를 감으로가 아니라 이 숫자로 판단한다.
    """
    with _lock:
        total = _STATS["total"]
        by_kind = {k.split(":", 1)[1]: v for k, v in _STATS.items()
                   if k.startswith("kind:")}
        other = by_kind.get("기타", 0)
        return {
            "total_classified": total,
            "by_kind": by_kind,
            "other_ratio": round(other / total, 4) if total else None,
            "low_confidence_ratio": (round(_STATS["low_confidence"] / total, 4)
                                     if total else None),
            "low_confidence_samples": list(_LOW_CONF_SAMPLES),
            "note": "other_ratio = 개인단위 레이어(L2/L3/L4)를 켜지 못한 요청 비율",
        }


def reset_stats() -> None:
    """테스트용."""
    with _lock:
        _STATS.clear()
        _LOW_CONF_SAMPLES.clear()


# ---------------------------------------------------------------- 분류
def _polarity(text: str, end: int) -> float:
    """키워드 1회 등장의 부호. 바로 뒤에 부정/대조가 붙어 있으면 -1, 아니면 +1."""
    after = text[end:end + _WINDOW_AFTER]
    return -1.0 if any(m in after for m in NEGATE_AFTER) else 1.0


def classify(choice: str, record: bool = True) -> ChoiceKind:
    """자유입력 → ChoiceKind. 근거 없는 유형은 만들지 않는다(없으면 '기타').

    `record=False` 는 커버리지 통계에 집계하지 않는다. 한 요청 안에서 유형을 다시
    확인해야 하는 하위 모듈(rulebase 등)이 쓴다 — 안 그러면 요청 1건이 2건으로
    잡혀 `/health` 의 other_ratio 가 틀어진다.
    """
    text = re.sub(r"\s+", " ", str(choice or "")).strip().lower()
    scores: dict[str, float] = {}
    matched: list[str] = []

    for kind, kws in KEYWORDS.items():
        s = 0.0
        for kw, w in kws:
            for m in re.finditer(re.escape(kw), text):
                pol = _polarity(text, m.end())
                s += w * pol
                matched.append(f"{kind}:{kw}{'(-)' if pol < 0 else ''}")
        if s:
            scores[kind] = round(s, 3)

    positive = {k: v for k, v in scores.items() if v > 0}
    if not positive:
        res = ChoiceKind("기타", 0.0, scores, matched)
        if record:
            _record(choice, res)
        return res

    ranked = sorted(positive.items(), key=lambda kv: -kv[1])
    best, best_s = ranked[0]
    second_s = ranked[1][1] if len(ranked) > 1 else 0.0
    # 1등이 2등을 얼마나 앞서는가 → 확신도. 단독 매칭이면 1.0.
    conf = round(best_s / (best_s + second_s), 3) if (best_s + second_s) else 0.0

    if conf < MIN_CONFIDENCE:
        res = ChoiceKind("기타", conf, scores, matched, method="rules(ambiguous)")
    else:
        res = ChoiceKind(best, conf, scores, matched)
    if record:
        _record(choice, res)
    return res


# ================================================================ 창업 맥락
# KSIC 10차 대분류 코드 → 기업생멸 lookup 의 `industry` 문자열.
# **CSV 값과 한 글자도 다르면 조회가 조용히 빈다** — 값을 바꿀 땐 반드시
# lookup_bizsurvival_survival_v1.csv 의 industry 컬럼과 대조할 것.
INDUSTRY_BY_SECTION: dict[str, str] = {
    "A": "농업, 임업 및 어업",
    "B": "광업",
    "C": "제조업",
    "D": "전기, 가스, 증기 및 공기조절 공급업",
    "E": "수도, 하수 및 폐기물처리, 원료재생업",
    "F": "건설업",
    "G": "도매 및 소매업",
    "H": "운수 및 창고업",
    "I": "숙박 및 음식점업",
    "J": "정보통신업",
    "K": "금융 및 보험업",
    "L": "부동산업",
    "M": "전문과학기술서비스업",
    "N": "사업시설관리, 사업지원 및 임대 서비스업",
    "P": "교육서비스업",
    "Q": "보건업 및 사회복지 서비스업",
    "R": "예술, 스포츠 및 여가관련 서비스업",
    "S": "협회 및 단체, 수리 및 기타 개인서비스업",
}

# 업종 단서. kind 분류와 같은 (키워드, 가중치) 구조라 부정·대조 처리를 그대로 쓴다
# ("카페 말고 학원" → 카페가 음수, 학원이 양수).
#
# 일상어를 KSIC 로 옮길 때 헷갈리는 것들만 근거를 적어둔다:
#   · 약국·꽃집은 제조/보건이 아니라 **소매(G)**
#   · 사진 스튜디오는 예술(R)이 아니라 **전문서비스(M)**
#   · 인테리어(실내건축)는 서비스가 아니라 **건설(F)**
#   · 미용실·네일·세탁·수리는 **개인서비스(S)**
# 'kind' 쪽 단서(창업·사업·자영…)는 업종 정보가 없으므로 여기 넣지 않는다.
KSIC_KEYWORDS: dict[str, list[tuple[str, float]]] = {
    "I": [("카페", 1.0), ("커피", 0.8), ("식당", 1.0), ("음식점", 1.0), ("요식", 1.0),
          ("술집", 1.0), ("주점", 1.0), ("호프", 0.8), ("포차", 0.9), ("펍", 0.7),
          ("베이커리", 1.0), ("빵집", 1.0), ("제과", 0.8), ("디저트", 0.8),
          ("브런치", 0.8), ("치킨", 0.9), ("분식", 1.0), ("맛집", 0.6),
          ("레스토랑", 1.0), ("바리스타", 0.8), ("숙박", 0.9), ("게스트하우스", 1.0),
          ("펜션", 1.0), ("호텔", 0.8), ("민박", 1.0)],
    "G": [("소매", 1.0), ("도매", 1.0), ("유통", 0.8), ("편의점", 1.0), ("마트", 0.9),
          ("쇼핑몰", 0.9), ("스마트스토어", 1.0), ("스토어", 0.6), ("셀러", 0.8),
          ("커머스", 0.9), ("리테일", 0.9), ("옷가게", 1.0), ("의류매장", 1.0),
          ("문구점", 1.0), ("서점", 1.0), ("꽃집", 1.0), ("화훼", 0.8),
          ("약국", 1.0), ("잡화", 0.7), ("판매점", 0.8)],
    "J": [("소프트웨어", 1.0), ("앱 ", 0.7), ("어플", 0.8), ("웹서비스", 1.0),
          ("플랫폼", 0.8), ("게임", 0.8), ("it ", 0.8), ("아이티", 0.7),
          ("개발사", 1.0), ("출판", 0.9), ("영상 제작", 0.9), ("유튜브", 0.7),
          ("미디어", 0.7), ("방송", 0.7), ("콘텐츠", 0.6), ("sass", 0.8),
          ("saas", 0.9), ("소프트웨어 개발", 1.0)],
    "M": [("컨설팅", 1.0), ("디자인", 0.8), ("광고", 0.8), ("마케팅", 0.7),
          ("법률", 0.9), ("법무", 0.9), ("회계", 0.9), ("세무", 1.0), ("노무", 0.9),
          ("특허", 0.9), ("변리", 1.0), ("건축사", 1.0), ("엔지니어링", 0.9),
          ("연구소", 0.8), ("사진관", 1.0), ("스튜디오", 0.6), ("번역", 0.8)],
    "P": [("학원", 1.0), ("과외", 1.0), ("교습", 1.0), ("공부방", 1.0),
          ("어학원", 1.0), ("입시", 0.8), ("교육사업", 1.0), ("교육서비스", 1.0),
          ("강사", 0.6), ("튜터", 0.8)],
    "Q": [("병원", 1.0), ("의원", 0.9), ("클리닉", 1.0), ("한의원", 1.0),
          ("치과", 1.0), ("요양", 0.9), ("어린이집", 1.0), ("산후조리", 1.0),
          ("심리상담", 0.9), ("복지시설", 0.9), ("동물병원", 1.0)],
    "R": [("헬스장", 1.0), ("피트니스", 1.0), ("필라테스", 1.0), ("요가", 0.9),
          ("체육관", 0.9), ("골프", 0.8), ("스크린", 0.6), ("노래방", 1.0),
          ("pc방", 1.0), ("공연", 0.8), ("갤러리", 0.9), ("전시", 0.6)],
    "S": [("미용실", 1.0), ("미용", 0.7), ("헤어", 0.8), ("네일", 1.0),
          ("피부관리", 1.0), ("에스테틱", 1.0), ("세탁", 0.9), ("수리점", 0.9),
          ("정비소", 1.0), ("마사지", 0.8), ("반려동물", 0.7), ("애견", 0.8)],
    "C": [("제조", 1.0), ("공장", 0.9), ("생산", 0.6), ("가공", 0.8),
          ("양조", 1.0), ("제작소", 0.9), ("제조업", 1.0)],
    "F": [("건설", 1.0), ("인테리어", 0.9), ("시공", 0.9), ("리모델링", 0.9),
          ("토목", 1.0), ("설비", 0.7)],
    "H": [("물류", 1.0), ("배송", 0.8), ("택배", 1.0), ("운송", 0.9),
          ("화물", 0.9), ("대리운전", 1.0), ("창고업", 1.0)],
    "L": [("부동산", 1.0), ("공인중개", 1.0), ("중개사", 0.9), ("임대업", 0.9)],
    "K": [("보험", 0.9), ("금융", 0.8), ("핀테크", 0.8), ("대부", 0.9)],
    "N": [("청소업", 1.0), ("경비업", 1.0), ("인력사무소", 1.0), ("렌탈", 0.9),
          ("여행사", 1.0), ("파견", 0.8)],
    "A": [("농사", 1.0), ("귀농", 1.0), ("농장", 0.9), ("스마트팜", 1.0),
          ("양식장", 1.0), ("축산", 1.0), ("과수원", 1.0), ("임업", 0.9)],
}

# 기업생멸 lookup 의 firm_size 값. 순서 = 작은 규모부터.
SCALE_BUCKETS = ("1인~4인", "5인~9인", "10인~19인", "20인 이상")
SCALE_ALL = "계"

# 텍스트에 규모 단서가 없을 때 쓰는 기본값.
#
# '계'(전 규모 평균)를 쓰면 20인 이상 법인까지 섞여 생존율이 낙관적으로 잡힌다
# (전체 업종 5년: 계 35.4% vs 1인~4인 33.4% vs 20인 이상 48.7%). 이 서비스가
# 시뮬레이션하는 창업은 개인 창업이므로 가장 작은 구간을 기본으로 둔다.
#
# ⚠ 그래도 낙관 편향이 남는다. 기업생멸통계는 **상용근로자 1인 이상 기업**만
#   집계해서 고용원 없는 순수 1인 자영업이 통째로 빠져 있다
#   (data/dgroup/README.md 함정 3번). 여기서 더 내릴 축이 없다.
DEFAULT_SCALE = "1인~4인"

_SCALE_KEYWORDS: list[tuple[str, str, float]] = [
    ("1인~4인", "혼자", 0.9), ("1인~4인", "나홀로", 1.0), ("1인~4인", "1인샵", 1.0),
    ("1인~4인", "1인 기업", 1.0), ("1인~4인", "직원 없이", 1.0),
    ("1인~4인", "무직원", 1.0), ("1인~4인", "소규모", 0.6),
    ("1인~4인", "소자본", 0.6), ("1인~4인", "프리랜", 0.8),
    ("20인 이상", "법인 설립", 0.5), ("20인 이상", "중견", 0.8),
]

# "직원 7명", "5명 규모", "10인 규모" 처럼 **사람 수**를 직접 적은 경우.
# 숫자 뒤 단위가 명/인 이어야 하고, 앞뒤에 규모 맥락어가 있어야 잡는다
# (그냥 "3년" "2000만원" 같은 숫자를 규모로 오인하지 않도록).
_HEADCOUNT_RE = re.compile(
    r"(?:직원|고용|인력|규모|식구|팀원)\s*(\d{1,3})\s*[명인]"
    r"|(\d{1,3})\s*[명인]\s*(?:규모|정도|짜리|직원|고용)"
)


def _bucket_for(n: int) -> str:
    if n < 5:
        return "1인~4인"
    if n < 10:
        return "5인~9인"
    if n < 20:
        return "10인~19인"
    return "20인 이상"


@dataclass
class StartupContext:
    """창업 자유입력에서 뽑은 조회 축. 못 찾은 축은 None/기본값으로 남는다."""

    ksic_section: str | None = None      # 'I' 등. None 이면 업종 미상
    industry: str | None = None          # lookup 의 industry 문자열
    scale: str = DEFAULT_SCALE           # lookup 의 firm_size 값
    scale_inferred: bool = True          # True = 텍스트에 근거 없이 기본값을 쓴 것
    confidence: float = 0.0              # 업종 확신도 (1등/1등+2등)
    matched: list[str] = field(default_factory=list)

    @property
    def industry_or_all(self) -> str:
        """조회용 industry. 업종을 못 뽑았으면 '전체' 로 떨어진다."""
        return self.industry or "전체"

    def label(self) -> str:
        """지표 `group` 에 실을 사람이 읽는 기준 표기."""
        scale = f"상용 {self.scale}" + ("(가정)" if self.scale_inferred else "")
        return f"{self.industry_or_all}·{scale}"

    def as_dict(self) -> dict:
        return {"ksic_section": self.ksic_section, "industry": self.industry,
                "scale": self.scale, "scale_inferred": self.scale_inferred,
                "confidence": self.confidence, "matched": list(self.matched)}


def _extract_scale(text: str) -> tuple[str, bool]:
    """(firm_size 값, 기본값을 쓴 것인지). 사람 수 표기가 키워드보다 우선."""
    m = _HEADCOUNT_RE.search(text)
    if m:
        n = int(next(g for g in m.groups() if g))
        return _bucket_for(n), False

    best, best_w = None, 0.0
    for bucket, kw, w in _SCALE_KEYWORDS:
        for hit in re.finditer(re.escape(kw), text):
            if _polarity(text, hit.end()) > 0 and w > best_w:
                best, best_w = bucket, w
    if best:
        return best, False
    return DEFAULT_SCALE, True


def extract_startup_context(choice: str) -> StartupContext:
    """창업 자유입력 → (업종, 규모). `classify()` 와 같은 부정·대조 규칙을 쓴다.

    업종을 못 찾으면 `ksic_section=None` 으로 두고 조회 쪽이 '전체' 로 떨어지게
    한다. 근거 없이 업종을 찍지 않는 게 원칙 — 틀린 업종의 생존율은 전체 평균보다
    나쁘다(숙박·음식 26.1% vs 보건 67.4%, 5년 기준).
    """
    text = re.sub(r"\s+", " ", str(choice or "")).strip().lower()
    scale, inferred = _extract_scale(text)

    scores: dict[str, float] = {}
    matched: list[str] = []
    for section, kws in KSIC_KEYWORDS.items():
        s = 0.0
        for kw, w in kws:
            for hit in re.finditer(re.escape(kw), text):
                pol = _polarity(text, hit.end())
                s += w * pol
                matched.append(f"{section}:{kw.strip()}{'(-)' if pol < 0 else ''}")
        if s:
            scores[section] = round(s, 3)

    positive = {k: v for k, v in scores.items() if v > 0}
    if not positive:
        return StartupContext(scale=scale, scale_inferred=inferred, matched=matched)

    ranked = sorted(positive.items(), key=lambda kv: -kv[1])
    best, best_s = ranked[0]
    second_s = ranked[1][1] if len(ranked) > 1 else 0.0
    conf = round(best_s / (best_s + second_s), 3) if (best_s + second_s) else 0.0
    if conf < MIN_CONFIDENCE:
        # 업종 후보가 팽팽하면(예: "카페 겸 서점") 찍지 않고 전체로 간다.
        return StartupContext(scale=scale, scale_inferred=inferred,
                              confidence=conf, matched=matched)

    return StartupContext(ksic_section=best, industry=INDUSTRY_BY_SECTION[best],
                          scale=scale, scale_inferred=inferred,
                          confidence=conf, matched=matched)
