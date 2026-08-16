# -*- coding: utf-8 -*-
"""api.py — 프론트 ↔ 내 성향모델 연결용 가벼운 로컬 API.

통합본 backend(KNN/EconML/lifelines/RAG)는 무거워 로컬 기동이 부담이라,
여기선 '내 몫'(성향 파악 + 주간 리포트)만 노출한다. 프론트가 일기/체크인을 보내면
DispositionModel + report.py 를 실제로 태워 결과를 돌려준다.

실행:
    uvicorn qmode.api:app --port 8000        (diary_module 을 cwd/PYTHONPATH 로)
  또는
    python diary_module/qmode/api.py

프론트(vite:5173)에서 POST http://localhost:8000/analyze
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
DIARY = HERE.parent
ROOT = DIARY.parent
for p in (str(DIARY), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from fastapi import FastAPI, File, UploadFile            # noqa: E402
from fastapi.middleware.cors import CORSMiddleware       # noqa: E402
from pydantic import BaseModel                           # noqa: E402

import metrics                                           # noqa: E402
from qmode.disposition_model import DispositionModel     # noqa: E402
from qmode import report as RPT, interests, card_map     # noqa: E402
from qmode.session import build_diary_metrics            # noqa: E402
from qmode.aggregate import classify_envy                # noqa: E402
from qmode import crypto_at_rest as CR                   # noqa: E402
import report_one as R1                                  # noqa: E402

app = FastAPI(title="qmode disposition API")

# 배포하면 이 서버가 우리 ANTHROPIC 키로 대신 호출해 준다. 아무나 부르면 그대로
# 비용이 나가므로, 배포 환경에선 ALLOWED_ORIGINS 로 우리 프론트 주소만 허용한다.
# (로컬 개발은 지정 안 하면 예전처럼 전부 허용.)
_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ORIGINS or ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
_MODEL = DispositionModel()


class Entry(BaseModel):
    date: Optional[str] = None
    text: Optional[str] = ""
    answers: Optional[dict] = None          # {qid: 답변}
    mood: Optional[int] = None
    energy: Optional[int] = None
    competency: Optional[str] = None
    emotion: Optional[str] = None


class AnalyzeReq(BaseModel):
    ranked_cards: Optional[list] = None      # 온보딩 가치순위(id 또는 label)
    mbti: Optional[str] = None
    entries: list[Entry] = []
    uid: Optional[str] = None                # 있으면 결과를 주별로 DB 저장
    week_key: Optional[str] = None           # 주 식별자(예: 그 주 월요일 날짜)


def _entries_to_sessions(entries):
    """프론트 일기 entries → qmode sessions(질문답변+자유칸, metrics 포함)."""
    sessions = []
    for e in entries:
        items = []
        for qid, ans in (e.answers or {}).items():
            if not (ans or "").strip():
                continue
            verdict = classify_envy(ans) if qid == "D4" else None
            item = {"question_id": qid, "answer": ans,
                    "metrics": metrics.analyze_text(ans),
                    "cards": card_map.load_cards_for(qid, verdict)}  # 질문 직결 이론카드
            if qid == "D4":
                item["envy"] = verdict
            items.append(item)
        free = None
        if (e.text or "").strip():
            free = {"question_id": None, "source": "free", "answer": e.text,
                    "metrics": metrics.analyze_text(e.text)}
        # 체크인은 세션 메타로 (리포트 기분흐름·컨텍스트용)
        sessions.append({"date": e.date, "items": items, "free": free,
                         "checkin": {"mood": e.mood, "energy": e.energy,
                                     "competency": e.competency, "emotion": e.emotion}})
    return sessions


def _psych_block(entries):
    """체크인 감정/기분 → 심리 이론카드 근거 블록(minjub RAG, 모델 없이).
    report 프롬프트에 주입되면 리포트가 그 이론 관점으로 써진다(출처는 NARR_SYSTEM이 숨김)."""
    try:
        import sys as _sys
        _sys.path.insert(0, str(DIARY))
        from psych_link import link_psych          # noqa: E402
    except Exception:
        return None
    from collections import Counter
    emos = [e.emotion for e in entries if e.emotion]
    moods = [e.mood for e in entries if e.mood]
    avg = (sum(moods) / len(moods)) if moods else 3
    NEG = {"지침": "불안", "답답함": "분노"}
    POS = {"성취감": "기쁨", "설렘": "기쁨"}
    if emos:
        top = Counter(emos).most_common(1)[0][0]
        coarse = NEG.get(top) or POS.get(top) or ("불안" if avg < 3 else "기쁨")
    else:
        coarse = "불안" if avg < 3 else ("슬픔" if avg < 3.5 else "기쁨")
    text = " ".join((e.text or "") for e in entries[-5:])
    diary = {"coarse": coarse, "display": coarse,
             "dominant": {"coarse": coarse}, "coarse_dist": {coarse: 0.8}}
    try:
        return link_psych(diary, text).get("prompt_block")
    except Exception:
        return None


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/analyze")
def analyze(req: AnalyzeReq):
    sessions = _entries_to_sessions(req.entries)

    # 성향 (온보딩+MBTI prior + 일기 LLM 갱신)
    prof = _MODEL.analyze(req.ranked_cards, sessions, mbti=req.mbti,
                          span_label="(웹 요청)")

    # 주간 리포트 서사 (report.py)
    narrative, nerr = None, None
    try:
        R1._load_dotenv()
        agg = build_diary_metrics(sessions)
        iblock = interests.build_block(interests.collect(sessions))
        prompt = RPT.build_narrative_prompt(sessions, agg, None,
                                            prof.get("jobchange_material"), iblock)
        pblock = _psych_block(req.entries)   # minjub 심리 RAG 근거(출처는 본문에 안 씀)
        if pblock:
            prompt += "\n\n" + pblock
        narrative, nerr = RPT.generate_narrative(prompt)
    except Exception as e:      # noqa: BLE001
        nerr = str(e)

    disposition = {
        "value_order": prof.get("value_order"),
        "coping": prof.get("coping"),
        "risk_tolerance": prof.get("risk_tolerance"),
        "decision_style": prof.get("decision_style"),
        "protect_most": prof.get("protect_most"),
        "summary": prof.get("summary"),
        "mbti": prof.get("mbti"),
        "confidence": prof.get("confidence"),
        "n_answers": prof.get("n_answers"),
    }
    report = narrative or f"(서사 생략: {nerr})"

    # 내일 할 거리 — 이번 주 답변에 매칭된 심리 이론카드의 행동 제안(intervention).
    # 성향 수치가 아니라 '해볼 것' 이라 사용자 화면에 바로 보여줄 수 있다.
    actions = []
    try:
        seen = set()
        for _, c in RPT._collect_cards(sessions):
            for iv in (c.get("interventions") or []):
                iv = (iv or "").strip()
                if iv and iv not in seen:
                    seen.add(iv)
                    actions.append(iv)
    except Exception:      # noqa: BLE001
        actions = []
    actions = actions[:3]

    # 주별 저장 — 지난 주는 이 저장본을 조회(GET /report). 이번 주만 실시간 재분석.
    if req.uid and req.week_key:
        con = _db()
        con.execute(
            "INSERT OR REPLACE INTO week_reports"
            "(uid, week_key, report, disposition, actions, updated_at)"
            " VALUES(?,?,?,?,?,?)",
            (req.uid, req.week_key, CR.enc_field(report), CR.enc_json(disposition),
             CR.enc_json(actions), _now()),  # 민감 컬럼 암호화 저장(at rest)
        )
        con.commit(); con.close()

    return {"disposition": disposition, "persona_block": prof.get("jobchange_material"),
            "report": report, "actions": actions, "report_error": nerr,
            "saved": bool(req.uid and req.week_key)}


# ── SQLite 영속화 (내장, 파일 하나 — 비용·설치 0) ────────────────────
DB_PATH = HERE / "qmode_store.db"


def _db():
    con = sqlite3.connect(str(DB_PATH))
    con.execute(
        "CREATE TABLE IF NOT EXISTS users("
        "uid TEXT PRIMARY KEY, profile TEXT, entries TEXT, "
        "persona_block TEXT, disposition TEXT, updated_at TEXT)"
    )
    con.execute(
        "CREATE TABLE IF NOT EXISTS week_reports("
        "uid TEXT, week_key TEXT, report TEXT, disposition TEXT, updated_at TEXT, "
        "PRIMARY KEY(uid, week_key))"
    )
    # 내일 할 거리(actions)는 나중에 추가된 컬럼 — 기존 DB 호환 위해 마이그레이션.
    try:
        con.execute("ALTER TABLE week_reports ADD COLUMN actions TEXT")
    except sqlite3.OperationalError:
        pass  # 이미 있음
    # 관계 스냅샷 — (uid, relation_tag) 로 스레딩, snapshot_time 으로 시계열.
    # 같은 태그로 2개+ 쌓이면 변화 추적((나) 모드)이 자동 활성화된다.
    con.execute(
        "CREATE TABLE IF NOT EXISTS relationship_snapshots("
        "uid TEXT, relation_tag TEXT, snapshot_time TEXT, label TEXT, "
        "signals TEXT, narrative TEXT, created_at TEXT, "
        "PRIMARY KEY(uid, relation_tag, snapshot_time))"
    )
    return con


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class SaveReq(BaseModel):
    uid: str
    ranked_cards: Optional[list] = None
    mbti: Optional[str] = None
    profile: Optional[dict] = None       # age/occupation/income 등(선택)
    entries: list[Entry] = []


@app.post("/save")
def save(req: SaveReq):
    """온보딩+일기 저장 + persona_block 계산해 함께 저장(예측에 넘길 재료)."""
    sessions = _entries_to_sessions(req.entries)
    prof = _MODEL.analyze(req.ranked_cards, sessions, mbti=req.mbti, span_label="(저장)")
    persona_block = prof.get("jobchange_material")
    # 일기 신호(직무불만·이직고민 등)를 서버에서 계산해 persona_block에 얹는다
    # → /scenario 이직 서사가 신호를 반영(새 LLM 호출 없음, 수치 불변).
    try:
        from qmode import diary_signals as DS
        _sig = DS.compute_signals([e.model_dump() for e in req.entries])
        _blk = DS.signal_block(_sig)
        if _blk:
            persona_block = (persona_block + "\n\n" + _blk) if persona_block else _blk
    except Exception:
        pass
    disposition = {
        "coping": prof.get("coping"), "risk_tolerance": prof.get("risk_tolerance"),
        "decision_style": prof.get("decision_style"), "value_order": prof.get("value_order"),
        "summary": prof.get("summary"), "confidence": prof.get("confidence"),
        "n_answers": prof.get("n_answers"), "mbti": prof.get("mbti"),
    }
    profile = {"ranked_cards": req.ranked_cards, "mbti": req.mbti, **(req.profile or {})}
    con = _db()
    con.execute(
        "INSERT OR REPLACE INTO users(uid, profile, entries, persona_block, disposition, updated_at)"
        " VALUES(?,?,?,?,?,?)",
        # 원문 최소화: 일기 entries는 저장하지 않는다(None). 파생물만 남기고 암호화(at rest).
        (req.uid, CR.enc_json(profile), None,
         CR.enc_field(persona_block), CR.enc_json(disposition), _now()),
    )
    con.commit(); con.close()
    return {"ok": True, "uid": req.uid, "persona_block": persona_block, "disposition": disposition}


@app.get("/persona/{uid}")
def get_persona(uid: str):
    """저장된 persona_block(예측 서사에 넘길 재료) 꺼내기."""
    con = _db()
    row = con.execute(
        "SELECT persona_block, disposition, updated_at FROM users WHERE uid=?", (uid,)
    ).fetchone()
    con.close()
    if not row:
        return {"found": False}
    return {"found": True, "persona_block": CR.dec_field(row[0]),
            "disposition": CR.dec_json(row[1]) if row[1] else None, "updated_at": row[2]}


@app.get("/users/{uid}")
def get_user(uid: str):
    con = _db()
    row = con.execute(
        "SELECT profile, entries, persona_block, disposition, updated_at FROM users WHERE uid=?",
        (uid,),
    ).fetchone()
    con.close()
    if not row:
        return {"found": False}
    return {"found": True, "profile": CR.dec_json(row[0]) if row[0] else None,
            "entries": CR.dec_json(row[1]) if row[1] else [],  # 원문 미저장 → 보통 []
            "persona_block": CR.dec_field(row[2]), "disposition": CR.dec_json(row[3]) if row[3] else None,
            "updated_at": row[4]}


@app.get("/report/{uid}/{week_key}")
def get_week_report(uid: str, week_key: str):
    """저장된 주간 리포트 조회 — 지난 주는 실시간 재분석 대신 이 저장본을 본다."""
    con = _db()
    row = con.execute(
        "SELECT report, disposition, updated_at, actions FROM week_reports"
        " WHERE uid=? AND week_key=?",
        (uid, week_key),
    ).fetchone()
    con.close()
    if not row:
        return {"found": False}
    return {"found": True, "report": CR.dec_field(row[0]),
            "disposition": CR.dec_json(row[1]) if row[1] else None,
            "updated_at": row[2],
            "actions": CR.dec_json(row[3]) if row[3] else []}


@app.delete("/reports/{uid}")
def clear_week_reports(uid: str):
    """저장된 주간 리포트 전체 삭제(uid 기준). 데모 재시드 시 옛 리포트가 남지 않게."""
    con = _db()
    n = con.execute("DELETE FROM week_reports WHERE uid=?", (uid,)).rowcount
    con.commit()
    con.close()
    return {"deleted": n}


# ── 예측 시나리오 서사 (persona_block 반영) ──────────────────────────
class ScenarioReq(BaseModel):
    uid: Optional[str] = None            # 저장된 persona 사용
    persona_block: Optional[str] = None  # 직접 전달도 가능(우선)
    choice: str = "이직"
    expected_wage: float = 0
    causal_effect: float = 0
    survival_months: float = 0
    age: Optional[int] = None
    major: Optional[str] = None


def _fetch_persona(uid):
    con = _db()
    row = con.execute("SELECT persona_block FROM users WHERE uid=?", (uid,)).fetchone()
    con.close()
    return CR.dec_field(row[0]) if row else None


@app.post("/scenario")
def scenario(req: ScenarioReq):
    """예측 수치 + persona_block → 성향 반영된 이직 서사. (suin generate_narrative 로컬판)"""
    import os
    pb = req.persona_block or (_fetch_persona(req.uid) if req.uid else None)
    prompt = (
        f"한 사용자가 '{req.choice}'라는 진로를 택한 평행우주를 상상합니다.\n"
        # 프론트는 이 자리에 화면 헤더와 같은 값(직종)을 보낸다. '전공'으로만 적어두면
        # 모델이 학력 배경으로 오해해 "○○ 전공이라…" 같은 문장을 만든다.
        f"- 나이: {req.age or '-'}, 전공·직군: {req.major or '-'}\n"
        f"- 예상 월급: {req.expected_wage:,.0f}만원\n"
        f"- 그 선택의 순수효과: {req.causal_effect:+,.1f}만원\n"
        f"- 예상 재직기간: {req.survival_months:.0f}개월\n\n"
        "이 데이터를 따뜻하면서도 현실적인 3~4문장으로 풀어 설명해줘."
    )
    if pb:
        prompt += (
            f"\n\n{pb}\n지시: 위 '지표 강조 순서'가 높은 것부터 서술하고, '리스크 프레임'과 "
            "'전달 스타일'에 맞춰 톤을 잡아라. 수치는 절대 바꾸지 말고, 불리한 축도 "
            "숨기지 마라(순서·톤만 조정)."
        )
    R1._load_dotenv()
    if not os.getenv("ANTHROPIC_API_KEY"):
        return {"narrative": "(ANTHROPIC_API_KEY 미설정)", "persona_used": bool(pb)}
    try:
        from anthropic import Anthropic
        resp = Anthropic().messages.create(
            model="claude-sonnet-5", max_tokens=700, thinking={"type": "disabled"},
            messages=[{"role": "user", "content": prompt}],
        )
        narr = "".join(b.text for b in resp.content if b.type == "text").strip()
        return {"narrative": narr, "persona_used": bool(pb)}
    except Exception as e:      # noqa: BLE001
        return {"narrative": f"(서사 생성 오류: {e})", "persona_used": bool(pb)}


# ── 제3의 제안 — A/B 외에 성향·일기신호에 근거한 '생각 못한 제3의 길' ──────
class ThirdPathReq(BaseModel):
    choice_a: str = "이직"
    choice_b: str = "유지"
    persona_block: Optional[str] = None
    uid: Optional[str] = None
    signal_block: Optional[str] = None   # 프론트가 넘긴 신호 블록(있으면 우선)
    entries: list[Entry] = []            # 없으면 이걸로 서버가 신호 계산
    age: Optional[int] = None
    major: Optional[str] = None


@app.post("/third-path")
def third_path(req: ThirdPathReq):
    """A/B 두 선택 외의 제3의 길을 성향·일기신호에 근거해 1개 제안. 재구성 제안(수치 예측 아님)."""
    import os
    pb = req.persona_block or (_fetch_persona(req.uid) if req.uid else None)
    sig_block = req.signal_block
    if not sig_block and req.entries:
        from qmode import diary_signals as DS
        sig_block = DS.signal_block(DS.compute_signals([e.model_dump() for e in req.entries]))
    prompt = (
        f"사용자가 두 갈림길을 두고 고민 중입니다: A) {req.choice_a}  vs  B) {req.choice_b}.\n"
        f"- 나이 {req.age or '-'} / 전공·직군 {req.major or '-'}\n"
        + (f"\n{pb}\n" if pb else "")
        + (f"\n{sig_block}\n" if sig_block else "")
        + "\nA·B는 사용자가 '이미' 떠올린 프레임이야. 네 역할은 그 프레임 자체를 의심해서, "
        "사용자가 미처 못 본 지점을 찔러주는 거야.\n"
        "규칙:\n"
        "1. 위 성향·기록 신호에서 사용자가 스스로 못 봤을 '숨은 전제'나 '진짜 고민'을 하나 짚어라 "
        "(예: 'A/B 둘 다 사실은 같은 두려움에서 나온 선택'처럼 관점을 뒤집기).\n"
        "2. 그 전제를 흔드는, A도 B도 아닌 제3의 길을 구체적으로 제안하라.\n"
        "3. 뻔한 절충(둘 다 조금씩·천천히)은 금지. 관점을 바꾸는 제안이어야 한다.\n"
        "4. 수치·통계·확률 지어내지 말 것. 오글거리는 미사여구·비유 금지, 담백하게.\n"
        "형식: 첫 줄 = 예상 못한 지점을 찌르는 통찰 한 문장(제목, 기호 없이). "
        "다음 줄부터 = 제3의 길 제안 + 근거 2~3문장."
    )
    R1._load_dotenv()
    if not os.getenv("ANTHROPIC_API_KEY"):
        return {"ok": False, "reason": "no_api_key", "persona_used": bool(pb), "signal_used": bool(sig_block)}
    try:
        from anthropic import Anthropic
        resp = Anthropic().messages.create(
            model="claude-sonnet-5", max_tokens=500, thinking={"type": "disabled"},
            messages=[{"role": "user", "content": prompt}],
        )
        txt = "".join(b.text for b in resp.content if b.type == "text").strip()
        lines = [ln.strip() for ln in txt.split("\n") if ln.strip()]
        title = lines[0] if lines else txt
        rationale = " ".join(lines[1:]).strip() if len(lines) > 1 else ""
        return {"ok": True, "title": title, "rationale": rationale,
                "persona_used": bool(pb), "signal_used": bool(sig_block)}
    except Exception as e:      # noqa: BLE001
        return {"ok": False, "reason": str(e)}


# ── 기업 분석 — OpenDART 공시·재무 + AI 요약 ───────────────────────────
# 공고 분석이 뽑은 회사명으로 바로 이어붙는다. 예측 수치가 '비슷한 사람들'을 말한다면
# 이건 '내가 가려는 그 회사'의 사실(공시·재무)을 말한다. 숫자는 지어내지 않는다.
class CompanyAnalyzeReq(BaseModel):
    name: str = ""                       # 회사명(공고에서 뽑힌 것)
    corp_code: Optional[str] = None      # 이미 알고 있으면 바로 사용
    persona_block: Optional[str] = None
    uid: Optional[str] = None


@app.get("/company/search")
def company_search(name: str = ""):
    """기업명 → DART 고유번호 후보. 상장사를 앞에 둔다."""
    from qmode import dart
    if not dart.api_key():
        return {"ok": False, "reason": "no_dart_key"}
    try:
        return {"ok": True, "items": dart.find_company(name)}
    except Exception as e:      # noqa: BLE001
        return {"ok": False, "reason": str(e)}


@app.get("/company/summary")
def company_summary(name: str = "", corp_code: str = ""):
    """재무 5개년 + 최근 공시 — 근거 자료 그대로."""
    from qmode import dart
    if not dart.api_key():
        return {"ok": False, "reason": "no_dart_key"}
    try:
        code, matched = corp_code, name
        if not code:
            hits = dart.find_company(name)
            if not hits:
                return {"ok": False, "reason": "not_found", "name": name}
            code, matched = hits[0]["corp_code"], hits[0]["name"]
        return {"ok": True, "name": matched, "corp_code": code,
                "financials": dart.financials(code),
                "disclosures": dart.disclosures(code)}
    except Exception as e:      # noqa: BLE001
        return {"ok": False, "reason": str(e)}


def _norm_corp(name):
    """회사명 비교용 정규화 — 공백·괄호·'주식회사'를 떼고 소문자로."""
    import re
    s = re.sub(r"주식회사|\(주\)|㈜", "", str(name or ""))
    return re.sub(r"[\s\(\)（）·.,'\"-]", "", s).lower()


@app.post("/company/analyze")
def company_analyze(req: CompanyAnalyzeReq):
    """재무 추이 + 공시 제목 → 지원자 관점 요약(사업 흐름·최근 집중·지원동기 포인트)."""
    import os
    from qmode import dart
    if not dart.api_key():
        return {"ok": False, "reason": "no_dart_key"}
    try:
        code, matched = req.corp_code, req.name
        if not code:
            hits = dart.find_company(req.name)
            if not hits:
                return {"ok": False, "reason": "not_found", "name": req.name}
            # 이름이 정확히 맞을 때만 자동 선택한다. find_company 는 부분일치라
            # '토스' → '비스토스' 처럼 전혀 다른 회사가 1순위로 잡힌다. 그걸 그대로
            # 분석하면 사용자가 물은 회사의 공시인 척하는 거짓말이 된다.
            exact = [h for h in hits if _norm_corp(h["name"]) == _norm_corp(req.name)]
            if exact:
                code, matched = exact[0]["corp_code"], exact[0]["name"]
            else:
                return {"ok": False, "reason": "ambiguous", "name": req.name,
                        "candidates": [{"name": h["name"], "corp_code": h["corp_code"]}
                                       for h in hits[:6]]}
        fin = dart.financials(code)
        disc = dart.disclosures(code)
    except Exception as e:      # noqa: BLE001
        return {"ok": False, "reason": str(e)}

    # 재무도 공시도 없으면 쓸 근거가 없다. 그래도 LLM 을 태우면 회사 이름만 보고
    # 그럴듯한 말을 만들 여지가 생긴다 — 아예 부르지 않는다(비상장·신설 법인이 여기 해당).
    if not fin and not disc:
        return {"ok": False, "reason": "no_data", "name": matched, "corp_code": code}

    R1._load_dotenv()
    if not os.getenv("ANTHROPIC_API_KEY"):
        return {"ok": True, "name": matched, "corp_code": code,
                "financials": fin, "disclosures": disc, "report": None}

    def _won(v):
        if v is None:
            return "—"
        if abs(v) >= 1_0000_0000_0000:
            return f"{v / 1_0000_0000_0000:.1f}조원"
        return f"{v / 1_0000_0000:.0f}억원"

    fin_lines = "\n".join(
        f"- {r['year']}년: 매출 {_won(r.get('revenue'))} / 영업이익 {_won(r.get('operating'))} / 순이익 {_won(r.get('net'))}"
        for r in fin) or "(재무 데이터 없음)"
    disc_lines = "\n".join(f"- {d['date']} {d['title']}" for d in disc[:8]) or "(최근 공시 없음)"
    pb = req.persona_block or (_fetch_persona(req.uid) if req.uid else None)

    prompt = (
        f"[기업] {matched}\n[공시 재무(OpenDART)]\n{fin_lines}\n\n[최근 공시]\n{disc_lines}\n\n"
        + (f"{pb}\n\n" if pb else "")
        + "취업·이직을 준비하는 사람이 이 회사를 이해하도록 정리하라.\n"
          "규칙: 위에 준 수치·공시 제목 밖의 사실(경쟁사 점유율, 조직문화, 합격률 등)은 "
          "절대 지어내지 마라. 모르면 모른다고 하라. 주가·투자 판단은 하지 마라.\n\n"
          '반드시 이 JSON만:\n'
          '{"trend":"재무 흐름 2~3문장(무엇이 늘고 줄었는지, 준 숫자만 근거로)",'
          '"focus":"최근 공시에서 읽히는 회사의 관심사 1~2문장(공시 제목 범위 안에서)",'
          '"talking_points":["지원동기·면접에서 쓸 수 있는 관점 3개"]}\n'
          "한국어만, 한자·설명·인사말 없이 JSON 하나만."
    )
    try:
        from anthropic import Anthropic
        resp = Anthropic().messages.create(
            model="claude-sonnet-5", max_tokens=900, thinking={"type": "disabled"},
            messages=[{"role": "user", "content": prompt}])
        txt = "".join(b.text for b in resp.content if b.type == "text").strip()
        s, e = txt.find("{"), txt.rfind("}")
        report = json.loads(txt[s:e + 1]) if s >= 0 and e > s else None
    except Exception:      # noqa: BLE001
        report = None

    return {"ok": True, "name": matched, "corp_code": code,
            "financials": fin, "disclosures": disc, "report": report}


# ── 커리어넷 직업가치관검사 — 성향을 '검증된 척도'로 한 겹 더 ──────────
# 우리 온보딩 8카드는 자체 제작이라 타당성 근거가 약하다. 커리어넷(한국직업능력연구원)
# 직업가치관검사(대학/일반, seq 6)는 28문항 = 8개 가치의 모든 쌍(8C2=28) 완전비교라
# 응답만 세면 순위가 떨어진다. 진로 질문을 한 직후에 '세부 질문'으로 권한다.
CAREERNET_TEST_SEQ = "6"
_CN_QUESTIONS = "https://www.career.go.kr/inspct/openapi/test/questions"
_CN_REPORT = "https://www.career.go.kr/inspct/openapi/test/report"


def _careernet_key():
    R1._load_dotenv()
    import os
    return os.getenv("CAREERNET_API_KEY")


def _cn_get(url, params):
    import urllib.parse, urllib.request
    with urllib.request.urlopen(url + "?" + urllib.parse.urlencode(params), timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


@app.get("/career/value-test")
def career_value_test():
    """직업가치관검사 28문항 — 각 문항은 가치 두 개 중 하나 고르기."""
    key = _careernet_key()
    if not key:
        return {"ok": False, "reason": "no_careernet_key"}
    try:
        data = _cn_get(_CN_QUESTIONS, {"apikey": key, "q": CAREERNET_TEST_SEQ})
        items = [
            {"no": q["qitemNo"],
             "a": {"name": q["answer01"], "desc": q["answer03"], "score": q["answerScore01"]},
             "b": {"name": q["answer02"], "desc": q["answer04"], "score": q["answerScore02"]}}
            for q in data.get("RESULT", [])
        ]
        return {"ok": True, "items": items, "n": len(items)}
    except Exception as e:      # noqa: BLE001
        return {"ok": False, "reason": str(e)}


class ValueAnswerReq(BaseModel):
    answers: dict = {}          # {문항번호(str|int): "1" | "2"}
    uid: Optional[str] = None


@app.post("/career/value-report")
def career_value_report(req: ValueAnswerReq):
    """응답 → 8개 가치 순위(승수 집계) + 커리어넷 공식 리포트 링크.

    28문항이 모든 쌍을 한 번씩 비교하므로, 고른 횟수가 곧 그 가치의 순위다.
    점수는 우리가 직접 세고(즉시·오프라인), 공식 리포트는 근거 링크로 함께 준다.
    """
    key = _careernet_key()
    if not key:
        return {"ok": False, "reason": "no_careernet_key"}
    try:
        qs = _cn_get(_CN_QUESTIONS, {"apikey": key, "q": CAREERNET_TEST_SEQ}).get("RESULT", [])
    except Exception as e:      # noqa: BLE001
        return {"ok": False, "reason": str(e)}

    wins, desc = {}, {}
    for q in qs:
        for name, d in ((q["answer01"], q["answer03"]), (q["answer02"], q["answer04"])):
            wins.setdefault(name, 0)
            desc.setdefault(name, d)
        picked = str(req.answers.get(str(q["qitemNo"])) or req.answers.get(q["qitemNo"]) or "")
        if picked == "1":
            wins[q["answer01"]] += 1
        elif picked == "2":
            wins[q["answer02"]] += 1

    ranking = [{"name": k, "wins": v, "desc": desc.get(k, "")}
               for k, v in sorted(wins.items(), key=lambda kv: -kv[1])]
    answered = sum(1 for q in qs
                   if str(req.answers.get(str(q["qitemNo"])) or req.answers.get(q["qitemNo"]) or ""))

    # 공식 리포트 링크 — 우리 집계가 아니라 커리어넷이 만든 결과를 근거로 함께 제공.
    report_url = None
    try:
        import urllib.request
        body = json.dumps({
            "apikey": key, "qestrnSeq": CAREERNET_TEST_SEQ, "trgetSe": "100",
            "gender": "100", "grade": "4", "startDtm": "1700000000000",
            "answers": " ".join(f"{q['qitemNo']}={req.answers.get(str(q['qitemNo'])) or req.answers.get(q['qitemNo']) or 1}"
                                for q in qs),
        }).encode("utf-8")
        rq = urllib.request.Request(_CN_REPORT, data=body,
                                    headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(rq, timeout=20) as r:
            report_url = (json.loads(r.read().decode("utf-8")).get("RESULT") or {}).get("url")
    except Exception:      # noqa: BLE001
        report_url = None

    return {"ok": True, "ranking": ranking, "answered": answered,
            "total": len(qs), "report_url": report_url}


# ── 관계 도메인 서사 (카톡 × 성향 → 선택지형 분기) ─────────────────────
class RelAnalyzeReq(BaseModel):
    uid: Optional[str] = None            # 있으면 관계 스냅샷 저장·시계열 추적
    relation_tag: Optional[str] = None   # 관계 상대 태그(연인/엄마/친구A) — 시계열 스레드 키
    label: Optional[str] = None          # 사람이 붙인 시간 라벨("오늘 카톡", "지난주 카톡")
    transcript: Optional[str] = None     # 텍스트 대화(이미지 없이도 가능)
    images: Optional[list] = None        # [{"media_type","data"(base64)}] 카톡 스크린샷
    snapshot_time: Optional[str] = None  # 시계열 정렬용(없으면 서버 시각)


def _load_disposition(uid):
    """저장된 성향(일기 기반) 로드 — 관계 서사 개인화 재료."""
    if not uid:
        return None
    con = _db()
    row = con.execute("SELECT disposition FROM users WHERE uid=?", (uid,)).fetchone()
    con.close()
    return CR.dec_json(row[0]) if row and row[0] else None


def _rel_history(uid, relation_tag):
    """같은 상대의 과거 스냅샷(시간순) — 있으면 (나) 변화추적 모드."""
    con = _db()
    rows = con.execute(
        "SELECT snapshot_time, label, signals FROM relationship_snapshots"
        " WHERE uid=? AND relation_tag=? ORDER BY snapshot_time",
        (uid, relation_tag),
    ).fetchall()
    con.close()
    return [{"snapshot_time": r[0], "label": r[1],
             "signals": CR.dec_json(r[2]) if r[2] else {}} for r in rows]


@app.post("/relationship/analyze")
def relationship_analyze(req: RelAnalyzeReq):
    """카톡 스크린샷/텍스트 → 관계 신호 추출 → 성향과 결합해 선택지형 서사.

    (가)/(나) 자동 판별: uid+relation_tag 로 과거 스냅샷이 있으면 변화추적(나),
    없으면 일회성(가). 저장은 uid+relation_tag 가 있을 때만.
    """
    from qmode import relationship as REL

    # 1) 안전 게이트 — 위기 신호면 서사 대신 지원 안내
    safe = REL.safety_check(req.transcript or "")
    if safe["block"]:
        return {"blocked": True, "support": safe["support"], "level": safe["level"]}

    # 2) 관계 신호 추출(비전/텍스트)
    signals, serr = REL.extract_signals(
        images=req.images, transcript=req.transcript, relation_tag=req.relation_tag)
    if signals is None:
        return {"error": serr}

    # 3) 성향 + 히스토리 결합
    disposition = _load_disposition(req.uid)
    history = _rel_history(req.uid, req.relation_tag) if (req.uid and req.relation_tag) else []
    mode = "track" if history else "single"      # 과거 스냅샷 있으면 (나) 추적

    # 4) 선택지형 분기 서사
    narr, nerr = REL.generate_narrative(signals, disposition, history=history)

    # 5) 저장 — uid+relation_tag 있을 때만 시계열로 적립
    saved = False
    if req.uid and req.relation_tag:
        st = req.snapshot_time or _now()
        con = _db()
        con.execute(
            "INSERT OR REPLACE INTO relationship_snapshots"
            "(uid, relation_tag, snapshot_time, label, signals, narrative, created_at)"
            " VALUES(?,?,?,?,?,?,?)",
            (req.uid, req.relation_tag, st, req.label,
             CR.enc_json(signals),                       # 대화 신호는 민감정보 — 암호화 저장
             CR.enc_json(narr) if narr else None, _now()),
        )
        con.commit(); con.close()
        saved = True

    return {"mode": mode, "signals": signals, "narrative": narr,
            "error": nerr, "saved": saved,
            "support": safe.get("support") or None,
            "history_count": len(history)}


@app.get("/relationship/{uid}/{relation_tag}")
def relationship_timeline(uid: str, relation_tag: str):
    """한 상대의 관계 스냅샷 시계열 — 변화 추적 화면용."""
    hist = _rel_history(uid, relation_tag)
    if not hist:
        return {"found": False, "count": 0, "snapshots": []}
    con = _db()
    rows = con.execute(
        "SELECT snapshot_time, label, signals, narrative FROM relationship_snapshots"
        " WHERE uid=? AND relation_tag=? ORDER BY snapshot_time",
        (uid, relation_tag),
    ).fetchall()
    con.close()
    snaps = [{"snapshot_time": r[0], "label": r[1],
              "signals": CR.dec_json(r[2]) if r[2] else {},
              "narrative": CR.dec_json(r[3]) if r[3] else None} for r in rows]
    return {"found": True, "count": len(snaps), "snapshots": snaps}


@app.delete("/relationship/{uid}/{relation_tag}")
def clear_relationship(uid: str, relation_tag: str):
    """한 상대의 관계 스냅샷 전체 삭제(데모 재시드·프라이버시)."""
    con = _db()
    n = con.execute(
        "DELETE FROM relationship_snapshots WHERE uid=? AND relation_tag=?",
        (uid, relation_tag),
    ).rowcount
    con.commit(); con.close()
    return {"deleted": n}



# ── 직무 분석 — 채용 공고 × 내 성향 ────────────────────────────────────
# 공고에서 요구역량을 뽑는 건 누구나 한다. 우리가 더할 수 있는 건 '이 사람'의
# 성향·가치순위와 대조해 맞는 지점과 부딪힐 지점을 짚는 것. 그래서 입력에
# persona_block(일기에서 만든 성향 재료)을 함께 넣는다.
class JobAnalyzeReq(BaseModel):
    posting: str = ""                    # 공고 원문(붙여넣기)
    uid: Optional[str] = None            # 저장된 성향 사용
    persona_block: Optional[str] = None  # 직접 전달(우선)
    choice: Optional[str] = None         # 이 공고가 걸린 선택지(예: "이직")


_JOB_SCHEMA = (
    '반드시 이 JSON만 출력:\n'
    '{"role":"직무명(공고에서)","company":"회사명(없으면 빈 문자열)",'
    '"requirements":["핵심 요구역량 3~5개, 공고 표현을 우리말로 정리"],'
    '"fit":[{"point":"성향과 맞는 지점","why":"근거 한 문장"}],'
    '"friction":[{"point":"부딪힐 수 있는 지점","why":"근거 한 문장"}],'
    '"prep":["지원 전 준비할 것 3개, 구체적 행동으로"],'
    '"questions":[{"q":"예상 면접 질문","angle":"이 사람 성향으로 답할 각도"}]}\n'
    "fit·friction 은 각 2~3개. 공고에 없는 회사 사정을 지어내지 말고, 성향 재료가 "
    "없으면 friction 을 비워라. 단정·진단 금지, 담백하게. 한국어만 쓰고 한자는 쓰지 마라. "
    "설명·인사말 없이 JSON 하나만 출력한다."
)


# 공고를 붙여넣기 말고 URL·PDF 로도 받는다. 다만 채용 사이트 상당수가 JS 렌더링이라
# URL 만으로는 제목·회사 정도만 건지는 경우가 많다 — 그럴 땐 부족하다고 알려준다.
class JobExtractReq(BaseModel):
    url: str = ""


_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}


def _strip_html(html):
    import re
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", t).strip()


@app.post("/job/extract-url")
def job_extract_url(req: JobExtractReq):
    """공고 URL → 텍스트. JSON-LD(JobPosting)를 먼저 보고, 없으면 본문 텍스트."""
    import re, urllib.request
    url = (req.url or "").strip()
    if not url.startswith("http"):
        return {"ok": False, "reason": "bad_url"}
    try:
        rq = urllib.request.Request(url, headers=_UA)
        with urllib.request.urlopen(rq, timeout=15) as r:
            html = r.read().decode("utf-8", "ignore")
    except Exception as e:      # noqa: BLE001
        return {"ok": False, "reason": f"fetch_failed: {type(e).__name__}"}

    title = company = ""
    parts = []
    for m in re.finditer(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, re.S):
        try:
            d = json.loads(m.group(1))
        except Exception:      # noqa: BLE001
            continue
        items = d if isinstance(d, list) else [d]
        for it in items:
            if isinstance(it, dict) and it.get("@type") == "JobPosting":
                title = it.get("title") or title
                company = ((it.get("hiringOrganization") or {}).get("name")) or company
                body = _strip_html(it.get("description") or "")
                if body:
                    parts.append(body)
                for k in ("responsibilities", "qualifications", "skills", "experienceRequirements"):
                    v = it.get(k)
                    if isinstance(v, str) and v.strip():
                        parts.append(_strip_html(v))
    if not title:
        m = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)', html)
        title = m.group(1) if m else ""

    text = "\n".join(parts).strip()
    if len(text) < 200:      # JS 렌더링이라 본문을 못 건진 경우 — 페이지 텍스트로 보완
        page = _strip_html(html)
        if len(page) > len(text):
            text = page[:6000]
    head = " ".join(x for x in (company, title) if x)
    full = (head + "\n" + text).strip()
    # 본문이 얇으면(내비게이션만 긁힌 경우) 사용자에게 붙여넣기를 권한다.
    thin = len(text) < 300
    return {"ok": True, "title": title, "company": company, "text": full[:6000],
            "thin": thin, "chars": len(full)}


@app.post("/job/extract-pdf")
async def job_extract_pdf(file: UploadFile = File(...)):
    """공고 PDF → 텍스트. 채용 페이지를 PDF로 저장해 오는 경우가 많다."""
    try:
        raw = await file.read()
        import io as _io
        from pypdf import PdfReader
        reader = PdfReader(_io.BytesIO(raw))
        pages = [(p.extract_text() or "") for p in reader.pages[:10]]
        text = "\n".join(pages).strip()
        text = " ".join(text.split())
        if len(text) < 100:
            return {"ok": False, "reason": "no_text",
                    "hint": "이미지로 스캔된 PDF 같아요. 본문을 붙여넣어 주세요."}
        return {"ok": True, "text": text[:6000], "chars": len(text),
                "pages": len(reader.pages)}
    except Exception as e:      # noqa: BLE001
        return {"ok": False, "reason": str(e)}


@app.post("/job/analyze")
def job_analyze(req: JobAnalyzeReq):
    """채용 공고 + 내 성향 → 요구역량·맞는 지점·부딪힐 지점·준비·예상질문."""
    import os
    text = (req.posting or "").strip()
    if len(text) < 30:
        return {"ok": False, "reason": "too_short"}
    pb = req.persona_block or (_fetch_persona(req.uid) if req.uid else None)
    R1._load_dotenv()
    if not os.getenv("ANTHROPIC_API_KEY"):
        return {"ok": False, "reason": "no_api_key"}
    # 과부하(529)·순간 오류는 사용자 잘못이 아니다 — 짧게 한 번 더 시도한다.
    def _ask(client, prompt, max_tokens):
        import time as _t
        for attempt in range(3):
            try:
                resp = client.messages.create(
                    model="claude-sonnet-5", max_tokens=max_tokens,
                    thinking={"type": "disabled"},
                    messages=[{"role": "user", "content": prompt}])
                return "".join(b.text for b in resp.content if b.type == "text").strip()
            except Exception as e:      # noqa: BLE001
                transient = any(s in str(e).lower() for s in ("529", "overload", "rate", "500", "timeout"))
                if attempt == 2 or not transient:
                    raise
                _t.sleep(1.5 * (attempt + 1))
        return ""

    prompt = (
        "[채용 공고]\n" + text[:6000] + "\n\n"
        + (f"{pb}\n\n" if pb else "")
        + (f"[맥락] 사용자는 지금 '{req.choice}' 선택을 저울질하는 중이다.\n\n" if req.choice else "")
        + "위 공고를 지원자 관점에서 분석하라. 성향 재료가 있으면 그 사람과 이 일이 "
          "만나는 지점과 부딪히는 지점을 반드시 구체적으로 짚어라.\n\n" + _JOB_SCHEMA
    )
    try:
        from anthropic import Anthropic
        txt = _ask(Anthropic(), prompt, 1200)
        # 코드펜스든 설명이 앞에 붙든, 첫 '{' ~ 마지막 '}' 만 취한다.
        s, e = txt.find("{"), txt.rfind("}")
        if s < 0 or e <= s:
            return {"ok": False, "reason": "no_json", "raw": txt[:200]}
        data = json.loads(txt[s:e + 1])
        data["ok"] = True
        data["persona_used"] = bool(pb)
        return data
    except Exception as e:      # noqa: BLE001
        return {"ok": False, "reason": str(e)}


# ── 일기 신호 (직무불만·이직고민 등) — 예측 서사 재료 & 검증용 ──────────
class SignalsReq(BaseModel):
    entries: list[Entry] = []
    window_days: int = 28


@app.post("/signals")
def diary_signals_endpoint(req: SignalsReq):
    """entries → 이직 관련 신호(서버 계산). /save 가 persona_block에 얹는 것과 동일 로직."""
    from qmode import diary_signals as DS
    sig = DS.compute_signals([e.model_dump() for e in req.entries], window_days=req.window_days)
    return {**sig, "block": DS.signal_block(sig)}


# ── 도메인(행성) 자동 태깅 — 일기 저장 시 영역 분류 ────────────────────
class TagReq(BaseModel):
    text: str


@app.post("/tag")
def tag_domain(req: TagReq):
    """일기 텍스트 → 인생 영역(관계/경제/건강/성장/일상). 행성 렌즈가 이 태그로 필터."""
    from qmode import domain_tag as DT
    return DT.tag(req.text)


# ── 마스코트 대화형 일기 ────────────────────────────────────────────────
class ChatMsg(BaseModel):
    role: str            # "user" | "bot"
    text: str


class ChatReq(BaseModel):
    messages: list[ChatMsg] = []
    persona: Optional[str] = "lumi"   # lumi(공감)/cosmo(분석)/nova(재미)
    uid: Optional[str] = None         # 있으면 서버 DB(SQLite)에서 지난 일기·성향을 꺼낸다
    context: Optional[dict] = None    # 프론트가 보낸 기억 — {recent:[{date,emotion,text}], hardStreak}
                                      # 로컬 우선 설계라 PII 마스킹된 이 경로가 기본이다.
    role: Optional[str] = None        # 이 대화의 역할(일상 되묻기 / 마음 살피기 / 건강 체크)
    speech: Optional[str] = None      # 말투 — "polite"(기본) | "casual". 사용자가 켜고 끈다.


@app.post("/chat")
def chat_turn(req: ChatReq):
    """대화 한 턴 → 마스코트 답변 + 진행 단계(stage/suggest_compose)."""
    from qmode import chatbot as CB
    msgs = [m.model_dump() for m in req.messages]
    reply = CB.chat(msgs, persona=req.persona or "lumi", uid=req.uid,
                    context=req.context, role=req.role, speech=req.speech)
    return {"reply": reply, **CB.stage_info(msgs)}


class FutureReq(BaseModel):
    """행성(삶의 영역) 하나의 'N년 뒤'. 일기 + 시뮬레이션 + 회고를 한 번에 읽는다."""
    domain: Optional[str] = None
    label: str = "이 영역"
    years: int = 5
    records: list[dict] = []          # [{date, text, mood, emotion}]
    analysis: Optional[dict] = None   # {n, moodAvg, topEmotions, trend}
    sims: list[dict] = []             # [{savedAt, choiceA, choiceB, headline, decision, reflection, doneActions}]
    trips: list[dict] = []            # 다녀온 작은 탐험 [{title, step, note, doneAt}]
    persona: Optional[str] = None     # 프론트가 만든 성향 블록(가치 순서·MBTI·기록 신호)
    speech: Optional[str] = None


@app.post("/future/scenario")
def future_scenario(req: FutureReq):
    """그 영역이 N년 뒤 어디에 가 있을지 — 기록에서만 끌어온 서사(예측 수치 아님)."""
    from qmode import future as FU
    years = max(1, min(30, int(req.years or 5)))
    return FU.scenario(req.label or "이 영역", years, req.records,
                       analysis=req.analysis, sims=req.sims, trips=req.trips,
                       persona=req.persona, speech=req.speech)


class MediaReq(BaseModel):
    records: list[dict] = []
    speech: Optional[str] = None
    limit: int = 3


@app.post("/media/tracks")
def media_tracks(req: MediaReq):
    """일기 → 실재하는 추천곡. 곡 정보는 Deezer(키 불필요)에서 오고 LLM 은 고르기만 한다."""
    from qmode import media as MD
    return MD.tracks(req.records, speech=req.speech, limit=max(1, min(5, req.limit or 3)))


class SoftCompareReq(BaseModel):
    """수치가 없는 영역(관계·건강·일상)의 두 길 비교. KLIPS 예측이 안 맞는 자리다."""
    choiceA: str = ""
    choiceB: str = ""
    domain: Optional[str] = None
    label: str = ""
    records: list[dict] = []
    persona: Optional[str] = None
    speech: Optional[str] = None


@app.post("/compare/soft")
def compare_soft(req: SoftCompareReq):
    """두 길을 장면으로 비교한다 — 숫자를 만들지 않고 기록에서만 끌어온다."""
    from qmode import compare_soft as CS
    return CS.compare(req.choiceA, req.choiceB, domain=req.domain,
                      domain_label=req.label, records=req.records,
                      persona=req.persona, speech=req.speech)


class SuggestReq(BaseModel):
    """오늘 해볼 만한 것. 기회(인생 갈림길)와 달리 오늘 크기의 제안이다."""
    records: list[dict] = []          # [{date, text, mood, emotion}] 최근 것부터
    moodAvg: Optional[float] = None
    speech: Optional[str] = None


@app.post("/suggest/daily")
def suggest_daily(req: SuggestReq):
    """최근 기록 → 오늘 해볼 만한 것 3개. 기록이 무거운 날엔 권하지 않고 care 로 답한다."""
    from qmode import suggest as SG
    return SG.suggest(req.records, mood_avg=req.moodAvg, speech=req.speech)


class OpportunityReq(BaseModel):
    """그 영역에서 아직 안 가본 길. 이미 비교한 갈림길(sims)은 빼고 찾는다."""
    domain: Optional[str] = None
    label: str = "이 영역"
    records: list[dict] = []
    analysis: Optional[dict] = None
    sims: list[dict] = []
    trips: list[dict] = []            # 다녀온 작은 탐험 — 같은 길을 또 권하지 않게 넘긴다
    persona: Optional[str] = None
    speech: Optional[str] = None


@app.post("/opportunity/scan")
def opportunity_scan(req: OpportunityReq):
    """일기를 읽고 아직 저울에 올려본 적 없는 갈림길 2~4개 — 그대로 시뮬레이션 입력이 된다."""
    from qmode import opportunity as OP
    return OP.scan(req.label or "이 영역", req.records,
                   analysis=req.analysis, sims=req.sims, trips=req.trips,
                   speech=req.speech)


class ComfortReq(BaseModel):
    entries: list[dict] = []          # 그 주 기록 [{date, text, mood, emotion}]
    persona: Optional[str] = "lumi"
    speech: Optional[str] = None


@app.post("/chat/comfort")
def chat_comfort(req: ComfortReq):
    """한 주치 기록 → 위로 한마디(주 1회). 분석·할 거리는 /report 몫이고 여기는 위로만."""
    from qmode import chatbot as CB
    return {"text": CB.comfort(req.entries, persona=req.persona or "lumi",
                               speech=req.speech)}


@app.post("/diary/compose")
def diary_compose(req: ChatReq):
    """대화 전체 → 1인칭 일기 + 기분 + 감정 + 영역(domains). 체크인 저장용."""
    from qmode import chatbot as CB
    msgs = [m.model_dump() for m in req.messages]
    return CB.compose(msgs)


@app.get("/chat/opener")
def chat_opener(persona: str = "lumi", uid: Optional[str] = None,
                speech: Optional[str] = None):
    """첫 인사 — uid 주면 지난 일기를 잇는 기억 오프너(서버 DB 경로)."""
    from qmode import chatbot as CB
    return {"opener": CB.opener(persona, uid=uid, speech=speech), "persona": persona}


@app.post("/chat/opener")
def chat_opener_ctx(req: ChatReq):
    """첫 인사 — 프론트 기억(context)으로 지난 일기를 잇는다(로컬 우선 기본 경로)."""
    from qmode import chatbot as CB
    return {"opener": CB.opener(req.persona or "lumi", uid=req.uid,
                                context=req.context, speech=req.speech),
            "persona": req.persona or "lumi"}


# ── 감정 모델(로컬 파인튜닝 klue/roberta) — 감정 미선택 시 일기에서 추론 ──
_EMO = None
_MOOD_BY_EMO = {"기쁨": 5, "당황": 3, "분노": 2, "불안": 2, "슬픔": 2, "상처": 2}


def _emotion_analyzer():
    global _EMO
    if _EMO is None:
        try:
            import infer  # diary_module/infer.py (sys.path 우선)
            _EMO = infer.DiaryAnalyzer(
                ckpt=str(ROOT / "model_v3_e6.pt"),
                taxonomy=str(DIARY / "emotion_taxonomy.json"))
        except Exception:
            _EMO = False   # 체크포인트/deps 없음 → 폴백 신호
    return _EMO or None


class EmotionReq(BaseModel):
    text: str


@app.post("/emotion")
def emotion_infer(req: EmotionReq):
    """일기 텍스트 → 감정모델 추론(감정·기분·위기). 감정 미선택 시 폴백용.
    체크포인트/deps 없으면 {ok:False} → 프론트가 LLM 폴백으로 강등."""
    an = _emotion_analyzer()
    if an is None or not (req.text or "").strip():
        return {"ok": False}
    try:
        r = an.analyze(req.text)
        dom = r.get("dominant") or {}
        return {"ok": True, "emotion": dom.get("display") or dom.get("coarse"),
                "fine": dom.get("fine"),
                "mood": _MOOD_BY_EMO.get(dom.get("coarse"), 3),
                "crisis_level": r.get("crisis_level", 0),
                "block": bool(r.get("block_report"))}
    except Exception:
        return {"ok": False}


if __name__ == "__main__":
    import os
    import uvicorn
    # 배포 환경(Render/Railway 등)은 PORT 를 주고 0.0.0.0 바인딩을 요구한다.
    # 로컬에서는 예전처럼 127.0.0.1:8000 으로 뜬다.
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0" if os.getenv("PORT") else "127.0.0.1")
    uvicorn.run(app, host=host, port=port)
