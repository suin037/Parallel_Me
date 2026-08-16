# -*- coding: utf-8 -*-
"""chatbot.py — 마스코트 대화형 일기.

세 페르소나(마스코트)와 대화하며 하루를 남긴다. 대화 끝에 compose()가 그 대화를
1인칭 일기로 정리하고 기분·감정을 추론한다. 영역 분류는 domain_tag 재사용.
LLM 하나가 (1)대화 (2)일기작성 (3)감정을 하고, 영역은 /tag.

'생명체 느낌'의 세 축:
  · 기억 — uid 주면 SQLite(qmode_store.db)의 지난 일기·성향을 읽어 대화에 잇는다.
    첫 인사부터 "지난번 그 일 그 뒤로 어때?" 가 가능해진다.
  · 단계 — 대화를 열기(open)→구체화(deepen)→정리(wrap)로 끌고 가며, 중반엔
    장면·감정·이유를 파고드는 세부 질문을 유형을 바꿔가며 던진다.
  · 반응 — 사용자의 단어를 되받고, 무거운 말엔 질문을 멈추고 곁에 있는다.

키 없으면 폴백(단계별 캔드 응답 / 사용자 발화 이어붙이기)으로 오프라인 흐름 검증 가능.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
DIARY = HERE.parent
ROOT = DIARY.parent
for p in (str(DIARY), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

# 마스코트 페르소나 — 캐릭터 시트 기반.
PERSONAS = {
    "lumi": {
        "label": "루미",
        "system": (
            "너는 '루미', 다정하고 공감적인 별빛 가이드다. 사용자의 하루를 따뜻하게 물어보고 "
            "짧게 공감하며 대화를 이어간다. 판단·진단·조언 강요를 하지 않는다. "
            "힘든 얘기엔 먼저 마음을 알아준다."),
        "opener": "오늘 하루 어땠어? 좋았던 일이든 힘들었던 일이든, 편하게 말해줘.",
        "opener_polite": "오늘 하루 어떠셨어요? 좋았던 일이든 힘들었던 일이든, 편하게 말씀해 주세요.",
    },
    "cosmo": {
        "label": "코스모",
        "system": (
            "너는 '코스모', 차분하고 분석적인 행성 탐험가다. 사용자가 오늘 한 선택과 그 이유를 "
            "정리하도록 돕는다. 사실→감정→선택 순으로 짧게 되짚어 묻는다. "
            "단정·진단은 피하고 '이렇게 볼 수도 있어' 식으로 관점을 준다."),
        "opener": "오늘 있었던 일을 같이 정리해볼까? 무슨 일이 있었는지 편하게 적어줘.",
        "opener_polite": "오늘 있었던 일을 같이 정리해볼까요? 무슨 일이 있었는지 편하게 적어 주세요.",
    },
    "nova": {
        "label": "노바",
        "system": (
            "너는 '노바', 재미있고 활력 넘치는 유성 가이드다. 사용자의 하루를 가볍고 즐겁게 "
            "끌어낸다. 호기심 가득한 반응 + 이어지는 질문. 과장은 하되 "
            "무례하지 않게. 힘든 얘기엔 톤을 낮춰 곁에 있어준다."),
        "opener": "오~ 오늘 무슨 일 있었어?! 아무거나 툭 던져봐.",
        "opener_polite": "오~ 오늘 무슨 일 있으셨어요?! 아무거나 툭 던져 주세요.",
    },
}

# 말투 — 사용자가 켜고 끄는 값. 기본은 존댓말(처음 만나는 사이의 기본 거리).
SPEECH_DEFAULT = "polite"
_SPEECH = {
    "polite": "말투는 처음부터 끝까지 존댓말('~요/~예요')로 고정한다. 딱딱한 '~습니다'체는 쓰지 마라.",
    "casual": "말투는 처음부터 끝까지 친근한 반말로 고정한다. '~요/~예요/~네요' 를 쓰지 마라.",
}


def _speech(v):
    return "casual" if v == "casual" else "polite"


def persona_opener(persona="lumi", speech=None):
    """말투에 맞는 기본 첫 인사."""
    p = PERSONAS.get(persona, PERSONAS["lumi"])
    return p["opener"] if _speech(speech) == "casual" else p.get("opener_polite", p["opener"])


def _client():
    try:
        import report_one as R1
        R1._load_dotenv()
    except Exception:
        pass
    if not os.getenv("ANTHROPIC_API_KEY"):
        return None
    try:
        from anthropic import Anthropic
        return Anthropic()
    except ImportError:
        return None


def _to_anthropic(messages):
    """[{role,text}] → anthropic messages. 선두 assistant(오프너) 제거, user부터 시작."""
    out = []
    for m in messages or []:
        t = (m.get("text") or "").strip()
        if not t:
            continue
        role = "assistant" if m.get("role") in ("bot", "assistant") else "user"
        out.append({"role": role, "content": t})
    while out and out[0]["role"] != "user":   # anthropic 은 user 로 시작해야 함
        out.pop(0)
    return out


# ── 기억 — SQLite(users)의 지난 일기·성향을 대화에 잇는다 ──────────────
DB_PATH = HERE / "qmode_store.db"


def load_memory(uid, db_path=None):
    """qmode_store.db users 행 → {entries, disposition}. 없으면 None."""
    if not uid:
        return None
    path = Path(db_path) if db_path else DB_PATH
    if not path.exists():
        return None
    try:
        con = sqlite3.connect(str(path))
        row = con.execute(
            "SELECT entries, disposition FROM users WHERE uid=?", (uid,)).fetchone()
        con.close()
        if not row:
            return None
        entries = json.loads(row[0]) if row[0] else []
        disposition = json.loads(row[1]) if row[1] else None
    except Exception:      # noqa: BLE001
        return None
    if not entries and not disposition:
        return None
    return {"entries": entries, "disposition": disposition}


def _recent_entries(mem, n=5):
    ent = [e for e in (mem or {}).get("entries") or [] if (e.get("text") or "").strip()]
    return ent[-n:]


def context_to_memory(context):
    """프론트가 보낸 기억(PII 마스킹 완료) → 내부 mem 형식.

    앱은 로컬 우선이라 기록이 브라우저(localStorage)에 있다. 그래서 서버 DB 대신
    이 경로가 기본이다. {recent:[{date,emotion,text}], hardStreak} 를 받는다.
    """
    if not context:
        return None
    entries = []
    for r in (context.get("recent") or []):
        text = (r.get("text") or "").strip()
        if not text:
            continue
        entries.append({"date": r.get("date"), "text": text,
                        "emotion": (r.get("emotion") or "").strip()})
    entries.reverse()      # 최신순으로 왔으니 옛것부터 나열되게
    if not entries:
        return None
    return {"entries": entries, "disposition": None,
            "hard_streak": int(context.get("hardStreak") or 0)}


def _memory_block(mem):
    """기억 → 시스템 프롬프트 블록. 최근 일기 몇 개 + 성향 한 줄 + 힘든 연속."""
    if not mem:
        return ""
    lines = []
    for e in _recent_entries(mem):
        meta = " ".join(x for x in (
            f"기분{e['mood']}/5" if e.get("mood") else "",
            (e.get("emotion") or "").strip()) if x)
        lines.append(f"- {e.get('date') or '?'}: {e['text'][:60]}"
                     + (f" ({meta})" if meta else ""))
    block = ""
    if lines:
        block += "[지난 일기 — 이 사용자가 최근 남긴 기록]\n" + "\n".join(lines) + "\n"
    summary = (mem.get("disposition") or {}).get("summary")
    if summary:
        block += f"[성향 메모] {summary}\n"
    streak = mem.get("hard_streak") or 0
    if streak >= 3:
        block += (f"[상태] 힘든 기록이 {streak}일 연속이다. 오늘은 캐묻지 말고 먼저 알아주고, "
                  "잘 버텨온 걸 짚어줘라. 해결책·조언은 사용자가 원할 때만.\n")
    if block:
        block += ("규칙: 위 기억은 네가 이 사용자를 계속 알아온 근거다. 이야기와 닿을 때만 "
                  "자연스럽게 한 번 슬쩍 잇는다(예: 지난번 그 일은 그 뒤로 어때?). "
                  "기억을 나열하거나 다 알고 있다는 듯 굴지 않는다.")
    return block


# ── 대화 단계 — 열기 → 구체화 → 정리 ──────────────────────────────────
def _n_user(messages):
    return sum(1 for m in (messages or [])
               if m.get("role") not in ("bot", "assistant") and (m.get("text") or "").strip())


def stage_info(messages):
    """진행 단계 + '일기로 정리' 제안 여부 — 프론트가 버튼 노출 판단에 쓴다."""
    n = _n_user(messages)
    stage = "open" if n <= 1 else ("deepen" if n <= 4 else "wrap")
    return {"stage": stage, "n_user": n, "suggest_compose": n >= 5}


_CRAFT = (
    "대화 원칙:\n"
    "1) 매 턴 = 반응 먼저(1문장) + 질문은 최대 1개. 전체 1~3문장.\n"
    "2) 사용자가 쓴 구체적인 단어를 하나 골라 자연스럽게 되받아라(그대로 복붙 말고).\n"
    "3) 질문 유형을 돌려 써라 — ①장면 구체화(언제·어디서·누가 뭐라고 했는지) "
    "②감정에 이름 붙이기(서운함인지 억울함인지 허탈함인지) ③그게 마음에 남은 이유 "
    "④지난 기억과 잇기. 직전 턴과 같은 유형을 연속으로 쓰지 마라.\n"
    "4) 답이 짧거나 피하는 기색이면 캐묻지 말고 화제를 살짝 옮기거나 가볍게 받아라.\n"
    "5) 무겁고 힘든 얘기엔 질문을 멈추고 먼저 마음을 알아줘라. 해결책·조언을 서두르지 마라.\n"
    "6) 같은 말버릇('그랬구나' 등) 반복 금지. 반응 길이도 턴마다 조금씩 다르게.\n"
    "7) {speech} 대화 중간에 말투가 바뀌면 다른 사람이 된 것처럼 튄다.\n"
    "8) 한국어로만 답한다. 다른 언어 단어를 섞지 마라.\n\n")

_STAGE_HINT = {
    "open": "지금은 대화 초반이다. 가볍게 문을 여는 반응과 부담 없는 질문 하나.",
    "deepen": ("지금은 대화 중반이다. 오늘 이야기에서 한 장면을 골라 조금 더 깊이 "
               "들어가라(위 질문 유형 활용)."),
    "wrap": ("지금은 대화 후반이다. 새 화제를 벌리지 말고, 오늘 이야기를 한 줄로 "
             "짚어준 뒤 오늘 얘기를 일기로 정리해줄지 부드럽게 제안하라"
             "(제안 문장도 위에서 정한 말투로 쓴다)."),
}

# 마지막 사용자 발화가 무거우면 이번 턴은 질문 없이 곁에 있는다.
_HEAVY = ("죽고 싶", "사라지고 싶", "너무 힘들", "못 버티", "포기하고 싶",
          "울었", "숨이 막", "무너지", "지쳤")


def _last_user_text(messages):
    return next((m.get("text") or "" for m in reversed(messages or [])
                 if m.get("role") not in ("bot", "assistant")), "")


def _is_heavy(messages):
    return any(k in _last_user_text(messages) for k in _HEAVY)


# 키 없을 때 — 단계별 캔드 응답 회전(오프라인에서도 되물음 흐름 유지). 말투별로 둔다.
_FALLBACK = {
    "casual": {
        "open": ["그런 하루였구나. 그 얘기 조금만 더 들려줄래?",
                 "오, 시작부터 궁금한데. 무슨 일이 있었던 거야?"],
        "deepen": ["그때 상황이 어땠는지 궁금해. 누가 뭐라고 했어?",
                   "그 순간 기분은 어땠어? 한 단어로 하면?",
                   "그게 유독 마음에 남은 이유가 있을까?"],
        "wrap": ["오늘 얘기 잘 들었어. 내가 일기로 정리해줄까?",
                 "이야기 충분히 모인 것 같아. 오늘 하루, 일기로 남겨볼까?"],
    },
    "polite": {
        "open": ["그런 하루였군요. 그 얘기 조금만 더 들려주실래요?",
                 "오, 시작부터 궁금한데요. 무슨 일이 있었던 거예요?"],
        "deepen": ["그때 상황이 어땠는지 궁금해요. 누가 뭐라고 했어요?",
                   "그 순간 기분은 어땠어요? 한 단어로 하면요?",
                   "그게 유독 마음에 남은 이유가 있을까요?"],
        "wrap": ["오늘 얘기 잘 들었어요. 제가 일기로 정리해드릴까요?",
                 "이야기 충분히 모인 것 같아요. 오늘 하루, 일기로 남겨볼까요?"],
    },
}


def _fallback_reply(info, speech=None):
    pool = _FALLBACK[_speech(speech)][info["stage"]]
    return pool[info["n_user"] % len(pool)]


def opener(persona="lumi", uid=None, context=None, speech=None):
    """첫 인사. 기억(context 또는 uid)이 있으면 지난 일기를 잇는 인사."""
    p = PERSONAS.get(persona, PERSONAS["lumi"])
    sp = _speech(speech)
    base = persona_opener(persona, sp)
    mem = context_to_memory(context) or load_memory(uid)
    last = (_recent_entries(mem, 1) or [None])[-1]
    if not last:
        return base
    client = _client()
    if client is None:
        snippet = last["text"][:24]
        return (f"어서 와! 지난번에 '{snippet}' 얘기했었잖아. 그 뒤로 어때? 오늘 하루도 들려줘."
                if sp == "casual" else
                f"어서 오세요! 지난번에 '{snippet}' 얘기하셨잖아요. 그 뒤로 어떠세요? 오늘 하루도 들려주세요.")
    tone = "친근한 반말로" if sp == "casual" else "'~요'로 끝나는 존댓말로"
    try:
        resp = client.messages.create(
            model="claude-sonnet-5", max_tokens=120, system=p["system"],
            thinking={"type": "disabled"},
            messages=[{"role": "user", "content":
                       f"[지난 일기] {last.get('date')}: {last['text'][:80]}\n"
                       "위 기억을 자연스럽게 잇는 첫 인사를 1~2문장으로 해줘. "
                       f"{tone}, 오늘 하루를 묻는 질문으로 끝내라. 인사말만 출력."}])
        txt = "".join(b.text for b in resp.content if b.type == "text").strip()
        return txt or base
    except Exception:      # noqa: BLE001
        return base


def chat(messages, persona="lumi", model=None, max_tokens=250, uid=None, context=None,
         role=None, speech=None):
    """대화 한 턴 → 마스코트 답변 텍스트.

    기억은 두 경로: context(프론트가 보낸 최근 기록 — 로컬 우선 기본 경로) 또는
    uid(서버 SQLite). 둘 다 없으면 기억 없이 단계 전략만으로 대화한다.
    role 을 주면 그 대화의 역할(앱의 영역: 일상 되묻기 / 마음 살피기 / 건강 체크)을 얹는다.
    speech 는 사용자가 고른 말투("polite" 기본 / "casual").
    """
    p = PERSONAS.get(persona, PERSONAS["lumi"])
    sp = _speech(speech)
    amsgs = _to_anthropic(messages)
    if not amsgs:
        return opener(persona, uid, context=context, speech=sp)
    info = stage_info(messages)
    client = _client()
    if client is None:      # 폴백 — 단계별 캔드 응답
        return _fallback_reply(info, sp)

    system = (p["system"] + "\n\n" + _CRAFT.replace("{speech}", _SPEECH[sp])
              + _STAGE_HINT[info["stage"]])
    if role:
        system += "\n\n[이번 대화의 역할] " + role
    mb = _memory_block(context_to_memory(context) or load_memory(uid))
    if mb:
        system += "\n\n" + mb
    if _is_heavy(messages):
        system += ("\n\n[지금] 사용자의 마지막 말이 무겁다. 이번 턴은 질문 없이 "
                   "곁에 있어주는 말만 해라. 짧아도 된다.")

    model = model or "claude-sonnet-5"
    for attempt in range(2):
        try:
            resp = client.messages.create(
                model=model, max_tokens=max_tokens, system=system,
                thinking={"type": "disabled"}, messages=amsgs)
            return "".join(b.text for b in resp.content if b.type == "text").strip()
        except Exception as e:      # noqa: BLE001
            if attempt == 0 and any(s in str(e).lower() for s in ("529", "overload", "rate", "500", "timeout")):
                time.sleep(1.5); continue
            return ("그랬구나. 오늘 얘기 잘 들었어." if sp == "casual"
                    else "그러셨군요. 오늘 얘기 잘 들었어요.")
    return "그랬구나." if sp == "casual" else "그러셨군요."


# ── 주간 위로 — 한 주치 기록을 읽고 건네는 말 한마디 ──────────────────
# 리포트(분석·수치·할 거리)가 아니다. 그건 report.py 몫이고, 여기는 위로만 한다.
_COMFORT_SYSTEM = (
    "너는 사용자의 지난 한 주 기록을 읽고 위로의 말을 건네는 마스코트다.\n"
    "규칙:\n"
    "1) 3~4문장. 분석·통계·조언·할 거리 제안 금지 — 그건 다른 화면이 한다.\n"
    "2) 그 주에 실제로 있었던 일 한두 개를 구체적으로 짚어라(기록에 있는 말로).\n"
    "3) 잘 버틴 지점을 알아주고, 좋았던 날이 있었으면 같이 기뻐해라.\n"
    "4) '힘내'처럼 뭉뚱그린 응원 대신, 그 사람이 지나온 걸 본 사람만 할 수 있는 말을 해라.\n"
    "5) 진단·라벨 금지. 한국어로만. 인사말만 출력하고 제목·머리말은 붙이지 마라."
)

_COMFORT_FALLBACK = {
    "polite": "이번 주도 하루하루 남겨주셨네요. 그것만으로도 충분히 잘 지나오신 거예요.",
    "casual": "이번 주도 하루하루 남겼네. 그것만으로도 충분히 잘 지나온 거야.",
}


def comfort(entries, persona="lumi", speech=None, model=None, max_tokens=300):
    """한 주치 기록 → 위로 한마디. entries=[{date, text, mood, emotion}] (그 주 것만)."""
    sp = _speech(speech)
    rows = [e for e in (entries or []) if (e.get("text") or "").strip()]
    if not rows:
        return _COMFORT_FALLBACK[sp]
    client = _client()
    if client is None:
        return _COMFORT_FALLBACK[sp]
    lines = []
    for e in rows[:7]:
        meta = " ".join(x for x in (
            f"기분{e['mood']}/5" if e.get("mood") else "",
            (e.get("emotion") or "").strip()) if x)
        lines.append(f"- {e.get('date') or '?'}: {(e.get('text') or '')[:120]}"
                     + (f" ({meta})" if meta else ""))
    system = _COMFORT_SYSTEM + "\n\n" + _SPEECH[sp]
    p = PERSONAS.get(persona, PERSONAS["lumi"])
    system = p["system"] + "\n\n" + system
    try:
        resp = client.messages.create(
            model=model or "claude-sonnet-5", max_tokens=max_tokens, system=system,
            thinking={"type": "disabled"},
            messages=[{"role": "user", "content":
                       "[지난 한 주 기록]\n" + "\n".join(lines)
                       + "\n\n위 한 주를 지나온 사람에게 건넬 말을 해줘."}])
        txt = "".join(b.text for b in resp.content if b.type == "text").strip()
        return txt or _COMFORT_FALLBACK[sp]
    except Exception:      # noqa: BLE001
        return _COMFORT_FALLBACK[sp]


_COMPOSE_SYSTEM = (
    "너는 사용자와의 대화를 읽고 그 하루를 사용자 시점(1인칭)의 짧은 일기로 정리하는 도우미다. "
    "지어내지 말고 대화에 있는 내용만. 진단 라벨 금지. JSON만 출력한다."
)


def _clean_insights(value):
    """Keep only grounded, non-diagnostic signals that can be safely reused."""
    value = value if isinstance(value, dict) else {}

    def clean_text(item, limit=160):
        return str(item or "").strip()[:limit]

    def clean_list(key, limit=5):
        items = value.get(key) if isinstance(value.get(key), list) else []
        return [clean_text(item) for item in items if clean_text(item)][:limit]

    signals = []
    raw_signals = value.get("preference_signals", [])
    for item in raw_signals if isinstance(raw_signals, list) else []:
        if not isinstance(item, dict):
            continue
        label = clean_text(item.get("label"), 80)
        evidence = clean_text(item.get("evidence"), 160)
        if not label or not evidence:
            continue
        try:
            confidence = max(0.0, min(1.0, float(item.get("confidence", 0.5))))
        except (TypeError, ValueError):
            confidence = 0.5
        signals.append({"label": label, "evidence": evidence, "confidence": confidence})

    future_options = []
    raw_options = value.get("future_options", [])
    for item in raw_options if isinstance(raw_options, list) else []:
        if not isinstance(item, dict):
            continue
        label = clean_text(item.get("label"), 100)
        detail = clean_text(item.get("detail"), 240)
        if label:
            future_options.append({"label": label, "detail": detail or label})

    return {
        "decision_topic": clean_text(value.get("decision_topic")),
        "goals": clean_list("goals"),
        "priorities": clean_list("priorities"),
        "constraints": clean_list("constraints"),
        "concerns": clean_list("concerns"),
        "preference_signals": signals[:5],
        "future_options": future_options[:2],
    }


def compose(messages, model=None, max_tokens=700):
    """대화 → {text(1인칭 일기), mood(1~5), emotion(한 단어), domains, primary}."""
    user_text = " ".join(
        (m.get("text") or "") for m in (messages or []) if m.get("role") not in ("bot", "assistant")
    ).strip()
    from qmode import domain_tag as DT

    client = _client()
    if client is None:      # 폴백 — 사용자 발화 이어붙이기 + 키워드 태깅
        dom = DT.tag(user_text)
        return {"text": user_text or "(내용 없음)", "mood": 3, "emotion": "",
                "domains": dom["domains"], "primary": dom["primary"], "method": "fallback"}

    convo = "\n".join(
        ("나: " if m.get("role") not in ("bot", "assistant") else "가이드: ") + (m.get("text") or "")
        for m in (messages or []) if (m.get("text") or "").strip()
    )
    schema = ('반드시 이 JSON만:\n{"text":"1인칭 일기 2~3문장","mood":1~5(오늘 기분,높을수록 좋음),'
              '"emotion":"오늘을 한 단어로"}\n대화에 없는 내용은 넣지 말 것.')
    schema += '''\nAlso include this object in the same JSON:
"insights":{"decision_topic":"","goals":[],"priorities":[],"constraints":[],
"concerns":[],"preference_signals":[{"label":"","evidence":"","confidence":0.0}],
"future_options":[]}
If and only if the user explicitly describes two alternative futures, also include
two items in insights.future_options: [{"label":"short option A","detail":"grounded detail"},{"label":"short option B","detail":"grounded detail"}].
Only extract information explicitly grounded in the user's words. Do not diagnose or infer personality,
mental health, or other sensitive traits. Use empty values when there is no evidence.'''
    model = model or "claude-sonnet-5"
    text, mood, emotion, insights = user_text, 3, "", _clean_insights({})
    try:
        resp = client.messages.create(
            model=model, max_tokens=max_tokens, system=_COMPOSE_SYSTEM,
            thinking={"type": "disabled"},
            messages=[{"role": "user", "content": "[대화]\n" + convo + "\n\n" + schema}])
        txt = "".join(b.text for b in resp.content if b.type == "text").strip()
        if txt.startswith("```"):
            txt = txt.strip("`"); txt = txt[txt.find("{"):txt.rfind("}") + 1]
        obj = json.loads(txt)
        text = obj.get("text") or user_text
        mood = int(obj.get("mood") or 3)
        mood = max(1, min(5, mood))
        emotion = (obj.get("emotion") or "").strip()
        insights = _clean_insights(obj.get("insights"))
    except Exception:      # noqa: BLE001
        pass
    dom = DT.tag(text)
    return {"text": text, "mood": mood, "emotion": emotion,
            "domains": dom["domains"], "primary": dom["primary"], "method": "llm",
            "insights": insights}


if __name__ == "__main__":
    convo = [
        {"role": "bot", "text": opener("lumi", uid="me")},
        {"role": "user", "text": "오늘 남친이랑 연락 문제로 좀 싸웠어. 서운했어."},
        {"role": "bot", "text": "그랬구나… 많이 속상했겠다."},
        {"role": "user", "text": "응. 내가 먼저 사과했는데 답이 늦더라."},
    ]
    print("=== 기억 오프너 (uid=me) ===")
    print(convo[0]["text"])
    print("\n=== chat 한 턴 (기억+단계) ===")
    print("루미:", chat(convo, "lumi", uid="me"))
    print("단계:", stage_info(convo))
    print("\n=== compose ===")
    print(json.dumps(compose(convo), ensure_ascii=False, indent=2))
