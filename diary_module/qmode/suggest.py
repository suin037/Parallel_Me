# -*- coding: utf-8 -*-
"""suggest.py — 오늘의 기록을 보고 지금 해볼 만한 걸 건넨다.

기회(opportunity.py)가 인생 갈림길 크기라면, 여기는 오늘 크기다.
"기분이 가라앉아 보이면 몸을 움직이는 쪽", "좋다고 적은 노래가 있으면 그 결의 다른 것",
"요즘 심심하다고 쓰면 해볼 만한 것" — 기록에 근거해 작게 권한다.

한계(중요): 음악·취미는 붙어 있는 데이터 소스가 없어 모델 지식에만 기댄다.
그래서 (1) '요즘 유행'이라고 단정하지 않고, (2) 확실하지 않은 고유명사는 검색어로
돌려 사용자가 직접 확인하게 한다. 화면에도 그렇게 밝힌다.

안전선: 기록이 많이 무거운 날엔 아무것도 권하지 않는다. 그날 필요한 건 할 일이 아니다.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
DIARY = HERE.parent
ROOT = DIARY.parent
for p in (str(DIARY), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)


def _client():
    try:
        import report_one as R1
        R1._load_dotenv()
    except Exception:      # noqa: BLE001
        pass
    if not os.getenv("ANTHROPIC_API_KEY"):
        return None
    try:
        from anthropic import Anthropic
        return Anthropic()
    except ImportError:
        return None


_SPEECH = {
    "polite": "존댓말('~요/~예요')로 쓴다.",
    "casual": "친근한 반말로 쓴다. '~요/~예요' 를 쓰지 마라.",
}

# 이런 말이 최근 기록에 있으면 권하지 않는다 — 그날 필요한 건 할 일이 아니다.
_HEAVY = ("죽고 싶", "사라지고 싶", "살기 싫", "자해", "못 버티", "무너지",
          "숨이 막", "아무 의미 없")

# 음악은 여기서 다루지 않는다 — media.py 가 Deezer 로 실재 확인한 곡을 따로 내놓는다.
# 한 카드에서 검증된 노래와 검증 안 된 음악 조언이 같이 뜨면 어느 쪽을 믿을지 알 수 없다.
_KINDS = {
    "move": "몸",
    "try": "해보기",
    "rest": "쉬기",
    "meet": "사람",
}

_SYSTEM = (
    "너는 사용자의 최근 기록을 읽고, 오늘 해볼 만한 작은 것 3개를 건네는 사람이다.\n"
    "\n"
    "각 제안:\n"
    '- kind : "move"(몸 움직이기) | "try"(해보기) | "rest"(쉬기) | "meet"(사람)\n'
    "- title: 12자 안팎. 무엇을 하는지 바로 알게.\n"
    "- why  : 왜 이걸 골랐는지 1~2문장. 기록의 구체적 사실을 짚어라.\n"
    "- how  : 지금 당장 할 수 있는 형태 1문장. 문턱을 낮춰라.\n"
    '- search: 사용자가 더 찾아볼 검색어 1개(없으면 "").\n'
    "\n"
    "규칙\n"
    "1) 기분이 낮은 날엔 큰 걸 권하지 마라. '헬스 등록' 말고 '집 앞 열 걸음'이다.\n"
    "   기운이 있는 날엔 조금 더 벌려도 된다. 기록의 온도에 맞춰라.\n"
    "2) 세 개의 결을 다르게 섞어라(몸 하나, 해보거나 쉬는 것 하나, 나머지 하나).\n"
    "3) 노래·음악·플레이리스트는 어떤 kind 로도 제안하지 마라(제목에도, how 에도,\n"
    "   search 에도). 곡 추천은 다른 화면이 실제 곡 정보로 따로 내놓는다 —\n"
    "   여기서 또 말하면 검증된 추천과 아닌 것이 한 카드에 섞인다.\n"
    "4) 취미는 '요즘 유행'이라고 단정하지 마라. 네가 아는 시점이 지났을 수 있다.\n"
    "   '해볼 만한 것'으로 놓고, 확실치 않은 고유명사는 search 로 돌려라.\n"
    "5) 진단·치료·영양제·병원 권유 금지. 훈계하지 마라.\n"
    "6) 기록에 없는 사실을 지어내지 마라. 한국어로만.\n"
    "\n"
    'JSON만 출력: {"items": [{"kind": "...", "title": "...", "why": "...", '
    '"how": "...", "search": "..."}]}'
)

_CARE = {
    "polite": "오늘은 뭘 더 하지 않아도 괜찮아요. 기록을 남긴 것만으로 충분해요.",
    "casual": "오늘은 뭘 더 안 해도 괜찮아. 기록 남긴 것만으로 충분해.",
}


def _records_block(records):
    lines = []
    for r in (records or [])[:14]:
        text = (r.get("text") or "").strip()
        if not text:
            continue
        meta = " ".join(x for x in (
            f"기분{r.get('mood')}/5" if r.get("mood") else "",
            (r.get("emotion") or "").strip()) if x)
        lines.append(f"- {r.get('date') or '?'}: {text[:140]}" + (f" ({meta})" if meta else ""))
    return "\n".join(lines)


_MUSIC_WORDS = ("노래", "음악", "플레이리스트", "플리", "앨범", "디스코그래피",
                "가수", "밴드", "음원", "playlist")


def _mentions_music(item):
    blob = " ".join(str(item.get(k) or "") for k in ("title", "how", "search", "why"))
    return any(w in blob for w in _MUSIC_WORDS)


def _too_heavy(records):
    joined = " ".join((r.get("text") or "") for r in (records or [])[:5])
    return any(w in joined for w in _HEAVY)


def suggest(records, mood_avg=None, speech="polite", model=None, max_tokens=1200):
    """최근 기록 → {ok, items:[{kind, kindLabel, title, why, how, search}]}."""
    sp = "casual" if speech == "casual" else "polite"
    if _too_heavy(records):
        # 무거운 날엔 할 일을 권하지 않는다. 이건 실패가 아니라 의도된 응답이다.
        return {"ok": False, "care": True, "reason": _CARE[sp]}
    block = _records_block(records)
    if not block:
        return {"ok": False, "reason": "며칠 기록이 모이면 오늘 해볼 만한 걸 골라볼게요."}
    client = _client()
    if client is None:
        return {"ok": False, "reason": "서버가 꺼져 있어 제안을 만들지 못했어요."}

    parts = ["[최근 기록]\n" + block]
    if mood_avg:
        parts.append(f"[최근 평균 기분] {mood_avg}/5")
    parts.append("위 기록을 보고 오늘 해볼 만한 걸 3개 골라줘.")

    for attempt in range(2):
        try:
            resp = client.messages.create(
                model=model or "claude-sonnet-5", max_tokens=max_tokens,
                system=_SYSTEM + "\n\n" + _SPEECH[sp],
                thinking={"type": "disabled"},
                messages=[{"role": "user", "content": "\n\n".join(parts)}])
            raw = "".join(b.text for b in resp.content if b.type == "text").strip()
            i, j = raw.find("{"), raw.rfind("}")
            data = json.loads(raw[i:j + 1]) if i >= 0 and j > i else {}
            items = []
            for it in (data.get("items") or []):
                title = str(it.get("title") or "").strip()
                if not title:
                    continue
                kind = str(it.get("kind") or "try").strip()
                items.append({
                    "kind": kind if kind in _KINDS else "try",
                    "kindLabel": _KINDS.get(kind, "해보기"),
                    "title": title,
                    "why": str(it.get("why") or "").strip(),
                    "how": str(it.get("how") or "").strip(),
                    "search": str(it.get("search") or "").strip(),
                })
            # 음악은 프롬프트로만 막으면 새어 나온다(kind 를 '해보기'로 바꿔 곡을
            # 권하는 식으로). 검증된 곡 추천과 섞이지 않게 여기서 확실히 걸러낸다.
            items = [it for it in items if not _mentions_music(it)]
            if not items:
                raise ValueError("no items")
            return {"ok": True, "items": items[:3]}
        except Exception as e:      # noqa: BLE001
            if attempt == 0 and any(s in str(e).lower() for s in
                                    ("529", "overload", "rate", "500", "timeout", "no items")):
                time.sleep(1.5)
                continue
            return {"ok": False, "reason": "제안을 만들지 못했어요. 잠시 뒤 다시 시도해 주세요."}
    return {"ok": False, "reason": "제안을 만들지 못했어요."}
