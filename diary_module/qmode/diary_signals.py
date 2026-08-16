# ─────────────────────────────────────────────────────────────
# 일기 신호(서버판) — 최근 2~4주 entries에서 '이직 고민' 관련 상태를 뽑는다.
# 프론트 frontend/src/data/diarySignals.js 와 대응(같은 사전·같은 축).
#
# 정직선: 예측 숫자를 바꾸지 않는다. 예측 서사의 '무엇을 짚을지·톤'에만 쓰는 재료.
# LLM 없음 — 키워드 규칙만. persona_block에 얹혀 /scenario 서사에 반영된다.
# ─────────────────────────────────────────────────────────────
from __future__ import annotations
from datetime import date, datetime

# key → (표시라벨, 키워드들, 가치축)
LEX = {
    "jobChange": ("이직 고민", ["이직", "퇴사", "그만두", "그만둘", "옮기", "이력서", "면접", "경력직", "다른 회사", "회사를 떠"], "성장"),
    "jobDissatisfaction": ("직무 불만", ["상사", "야근", "회의", "눈치", "압박", "실적", "불만", "지친", "지쳐", "버티", "꼰대", "갈굼", "혼났", "업무가 많", "일이 많"], "성장"),
    "growthStagnation": ("성장 정체", ["정체", "지루", "반복", "똑같", "그대로", "도태", "배울 게 없", "성장이 없", "권태", "매너리즘"], "성장"),
    "stabilityPreference": ("안정 선호", ["안정", "안전", "불안", "무섭", "무서워", "두렵", "리스크", "위험", "포기", "놓기", "겁", "확실"], "안정"),
    "burnout": ("번아웃·소진", ["번아웃", "소진", "방전", "무기력", "탈진", "의욕이 없", "쉬고 싶", "지쳤"], "안정"),
}


def _text_of(e: dict) -> str:
    parts = [e.get("text") or ""]
    ans = e.get("answers")
    if isinstance(ans, dict):
        parts += [str(v) for v in ans.values() if v]
    elif isinstance(ans, list):
        for qa in ans:
            if isinstance(qa, dict):
                parts.append(qa.get("a") or "")
    return " ".join(p for p in parts if p)


def _parse(d):
    if not d:
        return None
    try:
        return datetime.strptime(str(d)[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def compute_signals(entries: list[dict], window_days: int = 28) -> dict:
    """entries(dict: date/text/answers/mood) → 신호 요약. 날짜 있으면 최근 window_days만."""
    dated = [(_parse(e.get("date")), e) for e in entries]
    today = max((d for d, _ in dated if d), default=None) or date.today()
    recent = [e for d, e in dated if d is None or 0 <= (today - d).days <= window_days]
    if not recent:
        return {"ok": False, "window_days": window_days, "n": 0}

    hit_days = {k: set() for k in LEX}
    for i, e in enumerate(recent):
        t = _text_of(e)
        if not t:
            continue
        key = e.get("date") or f"#{i}"  # 날짜 없으면 인덱스로 '하루' 취급
        for k, (_, words, _ax) in LEX.items():
            if any(w in t for w in words):
                hit_days[k].add(key)

    signals = []
    axis_days: dict[str, int] = {}
    for k, (label, _w, ax) in LEX.items():
        days = len(hit_days[k])
        signals.append({"key": k, "label": label, "axis": ax, "days": days})
        axis_days[ax] = axis_days.get(ax, 0) + days
    signals.sort(key=lambda s: s["days"], reverse=True)

    moods = [e.get("mood") for e in recent if isinstance(e.get("mood"), (int, float))]
    mood_trend = None
    if len(moods) >= 4:
        mid = len(moods) // 2
        first, second = moods[:mid], moods[mid:]
        mood_trend = round(sum(second) / len(second) - sum(first) / len(first), 2)

    top_axis = max((a for a in axis_days if axis_days[a] > 0), key=lambda a: axis_days[a], default=None)

    return {
        "ok": True,
        "window_days": window_days,
        "n": len(recent),
        "signals": signals,
        "job_change_days": len(hit_days["jobChange"]),
        "mood_trend": mood_trend,
        "revealed_axis": top_axis,
    }


def signal_block(sig: dict) -> str | None:
    """신호 요약 → 예측 서사 프롬프트에 얹을 한국어 지시 블록. 없으면 None."""
    if not sig or not sig.get("ok"):
        return None
    strong = [s for s in sig["signals"] if s["days"] > 0][:3]
    if not strong and sig.get("mood_trend") is None:
        return None
    parts = [f"{s['label']} {s['days']}일" for s in strong]
    trend = sig.get("mood_trend")
    mood_txt = ""
    if trend is not None:
        mood_txt = " 기분은 " + ("회복세" if trend > 0.1 else "하강세" if trend < -0.1 else "비슷한 흐름") + "."
    body = f"최근 {sig['window_days']}일 일기에서 " + "·".join(parts) + "이(가) 드러남." + mood_txt
    return (
        "[최근 기록 신호]\n" + body + "\n"
        "지시: 위 신호를 서사가 이미 알고 있는 듯 자연스럽게 짚어라(반복된 고민·지친 지점 등). "
        "단, 통계 수치는 절대 바꾸지 말고 강조·톤에만 반영하라."
    )
