# -*- coding: utf-8 -*-
"""future.py — 삶의 한 영역이 'N년 뒤' 어디로 가 있을지 쓴다.

나의 우주의 행성 하나 = 삶의 한 영역. 그 행성에는 세 가지가 쌓인다.
  (1) 그 영역으로 분류된 일기        — 지금까지 실제로 지나온 것
  (2) 그 영역에서 돌린 시뮬레이션    — 저울에 올려본 갈림길
  (3) 저장한 우주에 적은 회고        — 그 갈림길이 그 뒤 어떻게 됐는지

이 셋을 한 번에 읽고 "이대로 가면 N년 뒤"를 서사로 쓴다.

정직선(중요): 예측이 아니다. KLIPS 생존분석·인과효과 같은 수치와 무관하고,
사용자가 남긴 기록에서만 이야기를 끌어온다. 화면에도 그렇게 밝힌다.
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
    "polite": "존댓말('~요/~예요')로 쓴다. 딱딱한 '~습니다'체는 쓰지 마라.",
    "casual": "친근한 반말로 쓴다. '~요/~예요' 를 쓰지 마라.",
}

_SYSTEM = (
    "너는 사용자가 남긴 기록만 읽고, 삶의 한 영역이 N년 뒤 어디에 가 있을지 써 주는 사람이다.\n"
    "\n"
    "무엇을 쓰는가\n"
    "- now  : 그 영역이 지금 어디쯤인지. 2문장. 기록에 실제로 있는 말로.\n"
    "- future: 'N년 뒤' 장면. 4~5문장. 하루의 한 장면처럼 구체적으로 —\n"
    "          어디에 있고, 무엇을 하고 있고, 무엇이 달라져 있는지.\n"
    "- hinge : 그 미래를 가르는 갈림길 하나. 2문장. 지금 기록에서 이미 흔들리는 지점으로.\n"
    "- basis : 이 이야기를 어디서 끌어왔는지 3~4개. 각 항목은 한 줄, 기록의 구체적 사실.\n"
    "\n"
    "규칙\n"
    "1) 기록에 없는 사건(승진·이사·결혼 등)을 지어내지 마라. 기록에 있는 흐름을 늘려라.\n"
    "2) 점치지 마라. '~할 것이다' 대신 '이대로라면 ~쯤에 있을 것 같다'처럼 쓴다.\n"
    "3) 다녀온 탐험과 회고가 있으면 반드시 반영해라 — 실제로 해보고 알게 된 것이\n"
    "   가장 무거운 재료다. 상상한 갈림길보다 겪고 온 한 줄이 앞선다.\n"
    "4) **future 는 이 사람이 닿을 수 있는 자리를 그린다.** 힘든 기록을 지우거나\n"
    "   미화하지는 않되, 무게중심은 '이미 하고 있는 것이 쌓였을 때 도달하는 곳'에 둔다.\n"
    "   기록에 있는 작은 움직임(먼저 연락한 것, 다시 붙잡은 것, 선을 그은 것,\n"
    "   다녀온 탐험)이 몇 년 뒤 무엇이 되어 있을지를 보여줘라.\n"
    "   '여전히 그대로일 것'으로 끝내지 마라 — 지금 힘든 사람에게 그건 예언이 아니라\n"
    "   체념을 건네는 것이다. 힘듦은 지나온 자리로 두고, 도착점은 열어둬라.\n"
    "5) 아래 [성향]이 있으면 그 사람이 무엇을 지키려는 사람인지에 비춰 써라.\n"
    "   같은 흐름이라도 안정을 지키려는 사람과 성장을 좇는 사람의 5년 뒤는 다르다.\n"
    "   성향을 라벨로 부르지 말고(‘당신은 안정형이라…’ 금지) 장면 속에 녹여라.\n"
    "6) hinge 는 경고가 아니라 손잡이다. '안 하면 이렇게 된다'가 아니라\n"
    "   '여기를 잡으면 저쪽으로 간다'로 써라. 실제로 붙잡을 수 있는 지점이어야 한다.\n"
    "7) 성격 진단·병명·수치 예측 금지. 조언을 늘어놓지 말고 장면으로 보여줘라.\n"
    "8) 한국어로만 쓴다.\n"
    "\n"
    "JSON만 출력한다: "
    '{"now": "...", "future": "...", "hinge": "...", "basis": ["...", "..."]}'
)


def _records_block(records):
    lines = []
    for r in (records or [])[:24]:
        meta = " ".join(x for x in (
            f"기분{r.get('mood')}/5" if r.get("mood") else "",
            (r.get("emotion") or "").strip()) if x)
        text = (r.get("text") or "").strip()
        if not text:
            continue
        lines.append(f"- {r.get('date') or '?'}: {text[:140]}" + (f" ({meta})" if meta else ""))
    return "\n".join(lines)


def _sims_block(sims):
    """시뮬레이션 + 회고. 회고가 있는 것을 먼저 보여준다(가장 무거운 재료)."""
    rows = sorted((sims or []), key=lambda x: 0 if (x.get("reflection") or "").strip() else 1)
    out = []
    for s in rows[:8]:
        head = f"- {s.get('savedAt') or '?'} · {s.get('choiceA') or '?'} vs {s.get('choiceB') or '?'}"
        if s.get("headline"):
            head += f" — {str(s['headline'])[:80]}"
        pick = {"A": s.get("choiceA"), "B": s.get("choiceB")}.get(s.get("decision"))
        if pick:
            head += f"\n    고른 쪽: {pick}"
        elif s.get("decision") == "none":
            head += "\n    고른 쪽: 아직 보류"
        refl = (s.get("reflection") or "").strip()
        if refl:
            head += f"\n    회고: {refl[:160]}"
        done = [d for d in (s.get("doneActions") or []) if str(d).strip()][:3]
        if done:
            head += "\n    실제로 한 것: " + ", ".join(str(d)[:40] for d in done)
        out.append(head)
    return "\n".join(out)


def _trips_block(trips):
    """다녀온 작은 탐험. 상상이 아니라 실제로 겪고 온 것이라 가장 무거운 재료다."""
    out = []
    for t in (trips or [])[:8]:
        note = (t.get("note") or "").strip()
        if not note:
            continue
        line = f"- {t.get('doneAt') or '?'} · {t.get('title') or '탐험'}"
        if t.get("step"):
            line += f" (해본 것: {str(t['step'])[:60]})"
        line += f"\n    알게 된 것: {note[:180]}"
        out.append(line)
    return "\n".join(out)


def _analysis_block(a):
    if not a:
        return ""
    bits = []
    if a.get("n"):
        bits.append(f"기록 {a['n']}개")
    if a.get("moodAvg"):
        bits.append(f"평균 기분 {a['moodAvg']}/5")
    if a.get("topEmotions"):
        bits.append("자주 남긴 감정: " + ", ".join(a["topEmotions"][:4]))
    trend = a.get("trend")
    if trend is not None:
        try:
            t = float(trend)
            bits.append("뒤로 갈수록 나아지는 흐름" if t > 0.15
                        else ("뒤로 갈수록 무거워지는 흐름" if t < -0.15 else "기분은 대체로 평평함"))
        except (TypeError, ValueError):
            pass
    return " · ".join(bits)


_FALLBACK_NOTE = "서버가 꺼져 있어 이야기를 쓰지 못했어요. 잠시 뒤 다시 시도해 주세요."


def scenario(domain_label, years, records, analysis=None, sims=None, trips=None,
             persona=None, speech="polite", model=None, max_tokens=1400):
    """그 영역의 'N년 뒤' 서사 → {now, future, hinge, basis[]}."""
    sp = "casual" if speech == "casual" else "polite"
    rec_block = _records_block(records)
    if not rec_block:
        return {"ok": False,
                "reason": "이 영역에 쌓인 일기가 아직 없어요. 며칠 기록이 모이면 써볼 수 있어요."}
    client = _client()
    if client is None:
        return {"ok": False, "reason": _FALLBACK_NOTE}

    parts = [f"[영역] {domain_label}", f"[햇수] {years}년 뒤"]
    if (persona or "").strip():
        parts.append("[성향 — 이 사람이 무엇을 지키려는지. 라벨로 부르지 말고 장면에 녹여라]\n"
                     + str(persona).strip()[:1200])
    stat = _analysis_block(analysis)
    if stat:
        parts.append(f"[이 영역 요약] {stat}")
    parts.append("[이 영역의 일기]\n" + rec_block)
    trips_block = _trips_block(trips)
    if trips_block:
        parts.append("[실제로 다녀온 작은 탐험 — 겪고 온 것이라 가장 무겁게 다뤄라]\n" + trips_block)
    sims_block = _sims_block(sims)
    if sims_block:
        parts.append("[이 영역에서 돌린 시뮬레이션과 그 뒤 회고]\n" + sims_block)
    elif not trips_block:
        parts.append("[시뮬레이션] 아직 이 영역에서 돌린 갈림길이 없다. "
                     "일기의 흐름만으로 쓰되, hinge 는 기록에서 이미 흔들리는 지점으로 잡아라.")
    parts.append(f"위 기록을 읽고 {years}년 뒤의 이 영역을 써줘.")

    system = _SYSTEM + "\n\n" + _SPEECH[sp]
    model = model or "claude-sonnet-5"
    for attempt in range(2):
        try:
            resp = client.messages.create(
                model=model, max_tokens=max_tokens, system=system,
                thinking={"type": "disabled"},
                messages=[{"role": "user", "content": "\n\n".join(parts)}])
            raw = "".join(b.text for b in resp.content if b.type == "text").strip()
            # 모델이 앞뒤에 말을 붙여도 JSON 만 건져낸다.
            i, j = raw.find("{"), raw.rfind("}")
            data = json.loads(raw[i:j + 1]) if i >= 0 and j > i else {}
            if not data.get("future"):
                raise ValueError("no future")
            basis = [str(b).strip() for b in (data.get("basis") or []) if str(b).strip()]
            return {"ok": True, "years": years,
                    "now": str(data.get("now") or "").strip(),
                    "future": str(data["future"]).strip(),
                    "hinge": str(data.get("hinge") or "").strip(),
                    "basis": basis[:5],
                    "used": {"records": len(rec_block.splitlines()),
                             "sims": len(sims_block.splitlines()) if sims_block else 0}}
        except Exception as e:      # noqa: BLE001
            if attempt == 0 and any(s in str(e).lower() for s in
                                    ("529", "overload", "rate", "500", "timeout", "no future")):
                time.sleep(1.5)
                continue
            return {"ok": False, "reason": _FALLBACK_NOTE}
    return {"ok": False, "reason": _FALLBACK_NOTE}
