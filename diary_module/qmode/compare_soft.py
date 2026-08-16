# -*- coding: utf-8 -*-
"""compare_soft.py — 수치가 없는 영역(관계·건강·일상)의 두 길을 비교한다.

왜 따로 필요한가
  예측 엔진(KLIPS)은 진로·소득 데이터로 만들어졌다. '먼저 말 꺼내기 vs 지금처럼
  두기' 같은 관계 갈림길에 그 수치를 붙이면 맞지도 않고, 필터에 걸려 화면이
  통째로 비기도 한다(실제로 관계는 지표가 하나도 안 걸려 빈 화면이었다).

그래서 여기서는 숫자를 만들지 않는다. 그 사람이 그 영역에 남긴 기록만 읽고,
두 길이 각각 어떤 하루가 되는지 장면으로 보여준다.

정직선: 예측이 아니다. 확률·점수·통계 표현을 쓰지 않는다.
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

# 영역마다 무엇을 짚어야 하는지가 다르다. 관계에서 '비용'은 돈이 아니라 감정이다.
_DOMAIN_FOCUS = {
    "relation": ("관계에서는 '누가 먼저 움직이는가'와 '그 뒤에 무엇이 남는가'가 갈린다. "
                 "옳고 그름을 판정하지 말고, 두 길에서 관계가 어떻게 달라지는지를 보여줘라. "
                 "상대를 평가하거나 진단하지 마라."),
    "health": ("건강에서는 '지금 덜어내는 것'과 '나중에 치르는 것'이 갈린다. "
               "의학적 조언·진단·치료 권유는 절대 하지 마라. 몸이 보내는 신호와 "
               "생활에서 바뀌는 것만 말해라."),
    "life": ("일상에서는 '하루의 모양'이 갈린다. 시간이 어디로 가는지, 무엇이 늘고 "
             "무엇이 줄어드는지를 구체적인 하루 장면으로 보여줘라."),
    "growth": ("성장에서는 '지금 드는 품'과 '나중에 생기는 선택지'가 갈린다. "
               "성과를 약속하지 말고, 무엇을 배우게 되는지를 말해라."),
}

_SYSTEM = (
    "너는 사용자의 기록을 읽고, 두 갈래 길이 각각 어떤 하루가 되는지 보여주는 사람이다.\n"
    "\n"
    "무엇을 쓰는가 — A와 B 각각에 대해:\n"
    "- scene : 그 길을 골랐을 때의 하루 한 장면. 3문장. 기록에 있는 말과 상황으로.\n"
    "- gain  : 그 길에서 얻는 것. 1문장.\n"
    "- cost  : 그 길에서 치르는 것. 1문장. (없다고 하지 마라 — 모든 선택에는 대가가 있다)\n"
    "그리고 공통으로:\n"
    "- hinge : 두 길을 가르는 지점 하나. 2문장. 지금 기록에서 이미 흔들리는 자리로.\n"
    "- basis : 이 이야기를 어디서 끌어왔는지 2~3개. 각 항목 한 줄, 기록의 구체적 사실.\n"
    "\n"
    "규칙\n"
    "1) 숫자·확률·점수·퍼센트를 쓰지 마라. 여기는 통계로 답하는 자리가 아니다.\n"
    "2) 어느 쪽이 옳다고 하지 마라. 두 길을 나란히 놓고 사용자가 고르게 둔다.\n"
    "3) 기록에 없는 사건을 지어내지 마라. 기록이 적으면 적은 대로 조심스럽게 쓴다.\n"
    "4) 진단·병명·치료·상대에 대한 평가 금지. 한국어로만.\n"
    "\n"
    'JSON만 출력: {"a": {"scene": "...", "gain": "...", "cost": "..."}, '
    '"b": {"scene": "...", "gain": "...", "cost": "..."}, "hinge": "...", "basis": ["..."]}'
)

_NO_KEY = "서버가 꺼져 있어 비교를 쓰지 못했어요. 잠시 뒤 다시 시도해 주세요."


def _records_block(records):
    lines = []
    for r in (records or [])[:20]:
        text = (r.get("text") or "").strip()
        if not text:
            continue
        meta = f" (기분{r.get('mood')}/5)" if r.get("mood") else ""
        lines.append(f"- {r.get('date') or '?'}: {text[:140]}{meta}")
    return "\n".join(lines)


def compare(choice_a, choice_b, domain=None, domain_label="", records=None,
            persona=None, speech="polite", model=None, max_tokens=1500):
    """두 길 → {ok, a:{scene,gain,cost}, b:{...}, hinge, basis[]}."""
    sp = "casual" if speech == "casual" else "polite"
    client = _client()
    if client is None:
        return {"ok": False, "reason": _NO_KEY}

    parts = [f"[영역] {domain_label or domain or '삶'}",
             f"[두 갈래] A: {choice_a} / B: {choice_b}"]
    focus = _DOMAIN_FOCUS.get(domain)
    if focus:
        parts.append("[이 영역에서 짚을 것] " + focus)
    if (persona or "").strip():
        parts.append("[성향 — 라벨로 부르지 말고 장면에 녹여라]\n" + str(persona).strip()[:900])
    block = _records_block(records)
    parts.append("[이 영역의 기록]\n" + block if block
                 else "[기록] 이 영역에 쌓인 기록이 거의 없다. 단정하지 말고 조심스럽게 써라.")
    parts.append("두 길이 각각 어떤 하루가 되는지 써줘.")

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
            if not (data.get("a") or {}).get("scene"):
                raise ValueError("no scene")
            pick = lambda d: {k: str((d or {}).get(k) or "").strip()   # noqa: E731
                              for k in ("scene", "gain", "cost")}
            return {"ok": True, "a": pick(data.get("a")), "b": pick(data.get("b")),
                    "hinge": str(data.get("hinge") or "").strip(),
                    "basis": [str(x).strip() for x in (data.get("basis") or []) if str(x).strip()][:4]}
        except Exception as e:      # noqa: BLE001
            if attempt == 0 and any(s in str(e).lower() for s in
                                    ("529", "overload", "rate", "500", "timeout", "no scene")):
                time.sleep(1.5)
                continue
            return {"ok": False, "reason": _NO_KEY}
    return {"ok": False, "reason": _NO_KEY}
