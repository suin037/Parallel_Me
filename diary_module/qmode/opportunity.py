# -*- coding: utf-8 -*-
"""opportunity.py — 그 영역에서 '아직 안 가본 길'을 찾아 내민다.

이 서비스가 하는 일은 하나를 맞히는 게 아니라, 놓치고 있던 선택지를 여러 개
보이게 하는 것이다. 지금까지는 사용자가 이미 아는 두 선택지(A/B)를 직접 적어야만
시뮬레이션이 시작됐다. 그러면 시야가 넓어질 수가 없다.

여기서는 그 영역의 일기를 읽고, 사용자가 아직 저울에 올려본 적 없는 갈림길을
2~4개 만들어 준다. 각 기회는 그대로 시뮬레이션 입력(A/B)이 된다.

정직선: 이건 추천이지 처방이 아니다. 기록에 있는 흐름에서만 끌어오고, 근거를
반드시 함께 보여준다. 예측 수치(KLIPS)와는 무관하다.
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

_SYSTEM = (
    "너는 사용자의 일기를 읽고, 그 사람이 아직 저울에 올려본 적 없는 갈림길을 찾아 주는 사람이다.\n"
    "\n"
    "왜 필요한가\n"
    "사람은 자기가 아는 두 선택지(예: 이직 vs 버티기) 사이에서만 고민한다. 그 사이와 바깥에\n"
    "실제로는 더 많은 길이 있는데 보이지 않을 뿐이다. 네 일은 그걸 보이게 하는 것이다.\n"
    "\n"
    "무엇을 내놓는가 — 기회 3개(최소 2, 최대 4). 각각:\n"
    '- title  : 그 길의 이름. 12자 안팎, 구체적으로. ("직무만 바꿔 남기" 처럼)\n'
    "- why    : 왜 이 길이 이 사람 기록에서 나왔는지 2문장. 기록의 구체적 사실을 짚어라.\n"
    "- choiceA: 시뮬레이션에 올릴 선택지 A. 짧은 명사구.\n"
    "- choiceB: 그 반대편 선택지 B. 짧은 명사구.\n"
    '- effort : "지금 바로" | "몇 달 준비" | "길게 준비" 중 하나.\n'
    "- first  : 이번 주에 해볼 수 있는 가장 작은 한 걸음. 1문장.\n"
    "\n"
    "규칙\n"
    "1) 이미 비교해본 갈림길은 내놓지 마라(아래 [이미 비교한 것] 목록).\n"
    "2) 서로 다른 결의 길을 섞어라 — 크게 바꾸는 길, 지금 자리에서 바꾸는 길,\n"
    "   결정을 미루고 재료를 모으는 길이 한 번에 다 보여야 시야가 넓어진다.\n"
    "3) 기록에 근거가 없는 길은 만들지 마라(로또·이민 같은 뜬금없는 제안 금지).\n"
    "4) 훈계하지 마라. '~해야 한다'가 아니라 '이런 길도 있다'로 놓아라.\n"
    "5) 진단·병명·수치 예측 금지. 한국어로만.\n"
    "\n"
    'JSON만 출력: {"items": [{"title": "...", "why": "...", "choiceA": "...", '
    '"choiceB": "...", "effort": "...", "first": "..."}]}'
)


def _records_block(records):
    lines = []
    for r in (records or [])[:24]:
        text = (r.get("text") or "").strip()
        if not text:
            continue
        meta = " ".join(x for x in (
            f"기분{r.get('mood')}/5" if r.get("mood") else "",
            (r.get("emotion") or "").strip()) if x)
        lines.append(f"- {r.get('date') or '?'}: {text[:140]}" + (f" ({meta})" if meta else ""))
    return "\n".join(lines)


def _tried_block(sims):
    rows = []
    for s in (sims or [])[:10]:
        a, b = (s.get("choiceA") or "").strip(), (s.get("choiceB") or "").strip()
        if not a and not b:
            continue
        line = f"- {a} vs {b}"
        refl = (s.get("reflection") or "").strip()
        if refl:
            line += f" (회고: {refl[:100]})"
        rows.append(line)
    return "\n".join(rows)


_NO_KEY = "서버가 꺼져 있어 기회를 찾지 못했어요. 잠시 뒤 다시 시도해 주세요."


def scan(domain_label, records, analysis=None, sims=None, trips=None, speech="polite",
         model=None, max_tokens=1600):
    """그 영역의 '아직 안 가본 길' → {ok, items:[{title, why, choiceA, choiceB, effort, first}]}."""
    sp = "casual" if speech == "casual" else "polite"
    rec_block = _records_block(records)
    if not rec_block:
        return {"ok": False,
                "reason": "이 영역에 쌓인 일기가 아직 없어요. 며칠 기록이 모이면 길을 찾아볼 수 있어요."}
    client = _client()
    if client is None:
        return {"ok": False, "reason": _NO_KEY}

    parts = [f"[영역] {domain_label}"]
    if analysis:
        bits = []
        if analysis.get("n"):
            bits.append(f"기록 {analysis['n']}개")
        if analysis.get("moodAvg"):
            bits.append(f"평균 기분 {analysis['moodAvg']}/5")
        if analysis.get("topEmotions"):
            bits.append("자주 남긴 감정: " + ", ".join(analysis["topEmotions"][:4]))
        if bits:
            parts.append("[요약] " + " · ".join(bits))
    parts.append("[이 영역의 일기]\n" + rec_block)
    tried = _tried_block(sims)
    parts.append("[이미 비교한 것]\n" + tried if tried
                 else "[이미 비교한 것] 아직 없다. 그래서 첫 갈림길들을 넓게 벌려 보여줘라.")
    parts.append("위 기록을 읽고, 이 사람이 아직 저울에 올려본 적 없는 길을 찾아줘.")

    system = _SYSTEM + "\n\n" + _SPEECH[sp]
    model = model or "claude-sonnet-5"
    for attempt in range(2):
        try:
            resp = client.messages.create(
                model=model, max_tokens=max_tokens, system=system,
                thinking={"type": "disabled"},
                messages=[{"role": "user", "content": "\n\n".join(parts)}])
            raw = "".join(b.text for b in resp.content if b.type == "text").strip()
            i, j = raw.find("{"), raw.rfind("}")
            data = json.loads(raw[i:j + 1]) if i >= 0 and j > i else {}
            items = []
            for it in (data.get("items") or []):
                title = str(it.get("title") or "").strip()
                a, b = str(it.get("choiceA") or "").strip(), str(it.get("choiceB") or "").strip()
                if not (title and a and b):
                    continue      # 시뮬레이션에 꽂을 수 없는 항목은 버린다
                items.append({
                    "title": title,
                    "why": str(it.get("why") or "").strip(),
                    "choiceA": a,
                    "choiceB": b,
                    "effort": str(it.get("effort") or "").strip(),
                    "first": str(it.get("first") or "").strip(),
                })
            if not items:
                raise ValueError("no items")
            return {"ok": True, "items": items[:4]}
        except Exception as e:      # noqa: BLE001
            if attempt == 0 and any(s in str(e).lower() for s in
                                    ("529", "overload", "rate", "500", "timeout", "no items")):
                time.sleep(1.5)
                continue
            return {"ok": False, "reason": _NO_KEY}
    return {"ok": False, "reason": _NO_KEY}
