"""
crisis.py — 위기 신호 탐지
규칙 기반. 재현율(놓치지 않는 것)이 정밀도보다 중요.
오탐은 허용, 미탐은 허용하지 않는다.
걸리면 감정 리포트 대신 지원 안내로 분기한다.
"""
import re
from dataclasses import dataclass, field
from typing import List

# LEVEL 3 : 즉시 개입. 리포트 생성 중단
L3 = [
    r"죽고\s*싶", r"죽어야\s*(겠|할|만)", r"죽는\s*게\s*(낫|편)",
    r"자살", r"자해", r"목숨을?\s*끊",
    r"사라지고\s*싶", r"없어지고\s*싶", r"소멸하고\s*싶",
    r"(존재|살아|남아)\s*있?\s*(하)?고\s*싶지\s*않",
    r"세상에\s*(존재|남아|있)",  # '세상에 존재하고 싶지 않' 계열 포괄
    r"없어졌으면", r"사라졌으면", r"안\s*태어났으면",
    r"태어나지\s*(말|않았)", r"태어난\s*게\s*후회",
    r"살\s*이유가?\s*없", r"살아갈\s*이유가?\s*없",
    r"내일이?\s*안\s*(왔으면|오면)", r"눈을?\s*안\s*떴으면",
    r"잠들어서?\s*(깨지|안\s*깨)", r"영원히\s*잠",
    r"유서", r"마지막\s*(인사|편지|글)",
    r"다\s*정리하고\s*(싶|가)", r"끝내고\s*싶",
]

# LEVEL 2 : 주의. 리포트는 생성하되 톤 조정 + 지원 안내 첨부
L2 = [
    r"살기\s*싫", r"사는\s*게\s*(의미|무의미|지옥|고통|괴로)",
    r"버티기\s*(힘들|어렵|벅차)", r"더는?\s*못\s*(버티|하)",
    r"희망이?\s*없", r"미래가?\s*(없|안\s*보)",
    r"아무\s*의미\s*없", r"다\s*소용\s*없", r"의미가\s*없",
    r"혼자\s*(감당|견디|버티)", r"아무도\s*(없|모르|관심)",
    r"짐이?\s*(되|된)", r"민폐",
    r"무너질\s*것\s*같", r"한계(다|야|에\s*왔)",
    r"숨이\s*(막|안\s*쉬)", r"가슴이\s*(답답|조여)",
    r"우울증", r"공황", r"불면",
    r"하고\s*싶은\s*(게|것이)?\s*없", r"의욕이?\s*(없|안\s*생)",
    r"누워\s*(만)?\s*있고\s*싶", r"아무것도\s*하기\s*싫",
    r"무기력", r"공허", r"텅\s*빈\s*것\s*같",
]

# 오탐 억제 (관용구·창작물 언급)
NEG = [
    r"(웃겨|웃기|재밌|귀여워|배고파|졸려|더워|추워|힘들어|피곤해)\s*죽",
    r"죽\s*(을|겠|는)\s*(만큼|정도로)\s*(맛있|재밌|좋|예뻐)",
    r"영화|드라마|소설|웹툰|만화|게임|기사|가사|노래|다큐",
]


@dataclass
class CrisisResult:
    level: int = 0
    matched: List[str] = field(default_factory=list)

    @property
    def block_report(self) -> bool:
        return self.level >= 3

    @property
    def attach_support(self) -> bool:
        return self.level >= 2


def _find(pats, t):
    return [p for p in pats if re.search(p, t)]


def detect(text: str) -> CrisisResult:
    if not isinstance(text, str) or not text.strip():
        return CrisisResult()
    t = re.sub(r"\s+", " ", text)
    supp = _find(NEG, t)

    hit3 = _find(L3, t)
    if hit3:
        # '죽' 관용구 단독일 때만 억제, 그 외는 무조건 L3
        only_idiom = supp and len(hit3) == 1 and "죽" in hit3[0]
        if not only_idiom:
            return CrisisResult(3, hit3)

    hit2 = _find(L2, t)
    if hit2:
        return CrisisResult(2, hit2)
    return CrisisResult(0, [])


def support_message(level: int) -> str:
    """진단하지 않고, 판단하지 않고, 연결만 한다."""
    if level >= 3:
        return (
            "오늘 이야기 잘 담아뒀어요.\n"
            "지금 많이 힘든 시간을 보내고 계신 것 같아서, "
            "오늘은 분석 대신 이걸 먼저 전하고 싶어요.\n\n"
            "· 자살예방 상담전화 109 (24시간)\n"
            "· 정신건강 위기상담 1577-0199\n"
            "· 청소년 전화 1388\n\n"
            "혼자 견디지 않으셔도 됩니다."
        )
    if level >= 2:
        return (
            "요즘 많이 지치신 것 같아요. 이야기를 나눌 곳이 필요하다면 "
            "정신건강 위기상담 1577-0199 에서 도움을 받을 수 있어요."
        )
    return ""


if __name__ == "__main__":
    tests = [
        "오늘 발표 망쳐서 너무 창피했다.",
        "스트레스를 너무 많이 받아서 이 세상에 존재하고 싶지 않을 정도다.",
        "요즘 사는 게 무의미하게 느껴진다. 뭘 해도 재미가 없다.",
        "그 영화 진짜 웃겨 죽는 줄 알았어",
        "배고파 죽겠다 점심 뭐 먹지",
        "더는 못 버티겠어. 희망이 없어.",
        "친구랑 카페 갔다. 오랜만이라 즐거웠다.",
        "개인적인 일이 터져서 정신이 나갔다. 죽고 싶었다.",
    ]
    for t in tests:
        r = detect(t)
        tag = {0: "안전", 2: "주의", 3: "즉시개입"}[r.level]
        print(f"[L{r.level} {tag:5s}] {t[:40]}")
        if r.matched:
            print(f"          matched: {r.matched}")
