# -*- coding: utf-8 -*-
"""report.py — 질문형 일기(+건강 패널) → 리포트 한 장.

기존 diary_module 파일은 수정하지 않는다. report_one.py 의 조각을 import 해서 쓴다.
    report_one._sparkline / _load_dotenv / NARR_MODEL / NARR_SYSTEM

엮는 재료
    1) qmode.session.analyze_session(...) 결과 세션들 (질문 답변 + 카드 직결 + 안전)
    2) qmode.aggregate 로 누적한 diary_metrics (길이게이트·부러움 분기)
    3) qmode.health_input 패널 + 또래 통계 병치 (선택)
안전 우선: 세션 위기(≥3)나 건강 위기면 리포트 대신 지지 메시지로 하드 분기한다.

구조 렌더(render_report)는 모델·API 없이 결정적으로 돈다 → 오프라인 검증 가능.
서사(Claude)는 선택 — ANTHROPIC_API_KEY 있을 때만 통합, 없으면 자동 생략.

실행(전체 e2e, 실모델):
    python diary_module/qmode/report.py            # 데모 세션 + 건강패널 렌더
    python diary_module/qmode/report.py --no-narrative   # 서사 없이(키 불필요)
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DIARY = HERE.parent
ROOT = DIARY.parent
for p in (str(DIARY), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from qmode import health_input, interests                      # noqa: E402
from qmode.session import build_diary_metrics, to_prompt_block  # noqa: E402
from qmode.scheduler import Scheduler                           # noqa: E402
import report_one as R1                                         # noqa: E402  (조각 재사용)

_SCH = Scheduler()


# 주간 리포트 서사 지침 — 위로가 아니라 '못 본 흐름' 짚기. AI 상투어 배제.
NARR_SYSTEM = (
    "너는 지난 일주일의 질문형 일기를 읽고, 사용자가 스스로 보지 못한 한 가지 흐름을 "
    "짚어주는 사람이다. 위로가 아니라 관찰이 목적이다.\n"
    "\n"
    "쓰는 법:\n"
    "- 그 주 기록에서만 근거를 찾아, 사용자가 놓쳤을 법한 구체적 패턴 하나를 중심에 둔다"
    "(요일·상황에 따라 갈리는 지점, 반복되는 대조 같은 것). 사용자가 쓴 말을 그대로 다시 "
    "들려주는 뻔한 미러링은 금지 — 그 위에서 한 걸음 나아간 관찰을 줘라.\n"
    "- 단정할 수 있는 건 단정한다. '~인 것 같아요 / ~처럼 보여요 / ~듯해요 / ~이지 않을까요' "
    "같은 추측성 말끝을 연달아 쓰지 말 것. 한 문단에 한 번이면 충분하다.\n"
    "- 위로 상투어 금지: '그만큼 애써왔다는 증거예요', '잘 알아차리고 있었어요', "
    "'그 자체로 의미 있어요' 류. 인정이 필요하면 감정을 반복하는 대신 사실로 대신한다.\n"
    "- 문장 길이를 섞는다. 짧은 단정문을 두려워하지 말 것. 모든 문단을 같은 리듬"
    "(길게 쓰고 대시로 인용하고 위로로 닫기)으로 찍어내지 말 것.\n"
    "- 조언은 억지로 넣지 않는다. 넣는다면 그 주 장면에서 자연스럽게 나온 것 하나만, "
    "실행 가능한 형태로. '관찰자 시점으로 써보세요' 같은 일반론이 아니라 이번 주 상황에 붙는 것.\n"
    "- 이모지·과한 존댓말 쿠션은 쓰지 않는다. 담백하고 존중하는 반존대.\n"
    "\n"
    "금지: 논문명·저자·연도·퍼센트·또래 통계·진단 라벨('~장애입니다')을 본문에 쓰지 않는다. "
    "특히 내부 분석 지표의 '이름'과 '숫자'를 본문에 노출하지 마라 — '대처균형', '정서극성', "
    "'통찰', '1인칭 비율', '+0.25', '-0.14' 같은 표현 절대 금지. 이런 지표로 패턴을 "
    "'찾는' 건 좋지만, 유저에게는 반드시 일상어로 옮겨 말한다. "
    "예: '대처균형이 +0.25로 올라간다' → '잘 됐던 일을 떠올릴 때만 뭘 해야 할지 또렷해진다'. "
    "심리학 관점은 출처 없이 자연스럽게만 녹인다. 건강은 '수면이 부족한 편'처럼 말로만. "
    "위기 신호가 있으면 낙관 톤을 접고 지지·연결을 먼저 둔다.\n"
    "분량: 3~4문단, 전체 짧게."
)

# 건강 자기보고(우려 항목) → 서사·리포트용 '말' (퍼센트 없이)
_HEALTH_WORDS = {
    "sleep": "수면이 부족한 편",
    "subjective_health": "몸 컨디션이 저조한 편",
    "exercise_days": "활동량이 적은 편",
    "stress": "스트레스가 높은 상태",
    "low_mood": "기분이 자주 가라앉음",
    "anxious": "불안·초조가 잦음",
    "burnout": "번아웃(소진) 느낌이 큼",
    "loneliness": "외로움을 느끼는 편",
}


def _health_words(health_result):
    """건강 자기보고 → 우려 항목을 퍼센트 없이 '말'로. (없으면 [])"""
    out = []
    for it in (health_result or {}).get("items", []):
        if it.get("concern") and it["id"] in _HEALTH_WORDS:
            out.append(_HEALTH_WORDS[it["id"]])
    return out


def _free_entries(sessions):
    """주간 자유 기록(선택칸) 모음 — 유저 본인 목소리. (최신순)"""
    out = []
    for s in sessions:
        f = s.get("free")
        if f and f.get("answer"):
            out.append({"date": s.get("date"), "text": f["answer"]})
    out.sort(key=lambda x: x.get("date") or "", reverse=True)
    return out


# 유저용 리포트 — 기분 흐름/하이라이트 (숫자·카드·축 숨김)
_MOOD_EMOJI = ["😞", "🙁", "😐", "🙂", "😄"]


def _mood_idx(avg):
    """평균 정서극성(-1~1) → 이모지 인덱스. 데드존을 좁혀(±0.08) 약한 신호도 움직이게.
    선형 매핑(round)은 반추형 일기의 valence가 0 근처에 몰려 전부 😐로 붕괴한다."""
    if avg <= -0.35:
        return 0
    if avg <= -0.08:
        return 1
    if avg < 0.08:
        return 2
    if avg < 0.35:
        return 3
    return 4


def _weekly_mood(sessions):
    """하루별 평균 정서극성 → 이모지 라인. (데일리 체크인 붙기 전 임시 — 답변서 추정)"""
    out = []
    for s in sessions:
        vals = [(it.get("metrics") or {}).get("emotion_valence")
                for it in s.get("items", []) if not it.get("skipped")]
        vals = [v for v in vals if v is not None]
        if not vals:
            continue
        avg = sum(vals) / len(vals)
        out.append((s.get("date"), _MOOD_EMOJI[_mood_idx(avg)]))
    return out


def _snippets(sessions, qids, n):
    """특정 질문들의 답변에서 짧은 조각(중복 제거, 최대 n개) — 유저용 '한눈에'."""
    out = []
    for s in sessions:
        for it in s.get("items", []):
            if it.get("skipped") or it.get("question_id") not in qids:
                continue
            a = (it.get("answer") or "").strip()
            if not a:
                continue
            short = a[:18] + ("…" if len(a) > 18 else "")
            if short not in out:
                out.append(short)
    return out[:n]


# ── 재료 수집 ────────────────────────────────────────────────────────
def _collect_cards(sessions):
    """세션들의 질문 답변에 직결된 카드를 (질문라벨, 카드) 로 모은다(중복 제거).

    위기 분기된 항목(카드 없음)은 건너뛴다.
    """
    seen, out = set(), []
    for s in sessions:
        for it in s.get("items", []):
            if it.get("skipped") or it.get("crisis_message"):
                continue
            for c in it.get("cards", []):
                if c["card_id"] in seen:          # card_id 기준 중복 제거(여러 질문이 같은 카드)
                    continue
                seen.add(c["card_id"])
                out.append((it.get("question_text") or it.get("question_id"), c))
    return out


def _valence_series(sessions):
    """세션 답변들의 emotion_valence 를 시간순으로 → 스파크라인용."""
    vals = []
    for s in sessions:
        for it in s.get("items", []):
            if it.get("skipped"):
                continue
            v = (it.get("metrics") or {}).get("emotion_valence")
            if v is not None:
                vals.append(v)
    return vals


def _session_crisis(sessions):
    return max((s.get("session_crisis", 0) for s in sessions), default=0)


# ── 서사(선택) ───────────────────────────────────────────────────────
def build_narrative_prompt(sessions, agg, health_result, disposition_block=None,
                           interests_block=None):
    dates = sorted({s.get("date") for s in sessions if s.get("date")})
    span = f"{dates[0]}~{dates[-1]} ({len(dates)}일)" if dates else ""
    lines = [
        f"[지난 일주일({span}) 질문형 일기다. 사용자가 스스로 놓쳤을 법한 흐름 하나를 중심에 "
        "두고, 짧은 3~4문단으로 담백하게 써라. 추측성 말끝을 반복하지 말고, 위로 상투어·"
        "논문명·저자·연도·퍼센트는 쓰지 말 것. 조언은 이번 주 장면에서 나온 것 하나만"
        "(억지로 넣지 말 것).]",
        "",
        "· 이번 주 문항별 신호:",
        to_prompt_block(sessions, agg),
    ]
    # 건강은 퍼센트 없이 '말'로만.
    hw = _health_words(health_result)
    if hw:
        lines += ["", "· 몸·마음 상태(말로만, 수치 언급 금지): " + ", ".join(hw)]
    # 자유 기록 — 유저 본인 목소리(고정 질문이 못 잡은 주제). 있으면 반영.
    free = _free_entries(sessions)
    if free:
        lines += ["", "· 자유롭게 남긴 말(본인 목소리 — 자연스럽게 반영):"]
        for f in free[:3]:
            lines.append(f"   - 「{f['text'][:60]}…」" if len(f['text']) > 60
                         else f"   - 「{f['text']}」")
    if disposition_block:
        lines += ["", disposition_block]
    if interests_block:
        lines += ["", interests_block]
    # 이론 카드는 '관점'만 준다(출처는 본문에 쓰지 말 것 — 리포트 근거 섹션에 이미 있음).
    cards = _collect_cards(sessions)
    if cards:
        lines += ["", "· 참고 심리 관점(출처는 본문에 인용하지 말 것, 관점만 녹이기):"]
        for label, c in cards[:3]:
            acts = c.get("interventions", [])
            tip = f" 예: {acts[0]}" if acts else ""
            lines.append(f"   - {c['concept_ko']} — {c.get('summary','')[:70]}…{tip}")
    return "\n".join(lines)


def generate_narrative(prompt, model=None):
    """Claude 서사 통합. 미설정/실패 시 (None, 사유)."""
    import os
    model = model or R1.NARR_MODEL
    if not os.getenv("ANTHROPIC_API_KEY"):
        return None, "ANTHROPIC_API_KEY 미설정(.env 확인)"
    try:
        from anthropic import Anthropic
    except ImportError:
        return None, "anthropic 미설치"
    try:
        client = Anthropic()
        resp = client.messages.create(
            model=model, max_tokens=1100, system=NARR_SYSTEM,
            thinking={"type": "disabled"},
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(b.text for b in resp.content if b.type == "text").strip(), None
    except Exception as e:      # noqa: BLE001
        return None, f"API 오류: {e}"


# ── 렌더(결정적) ─────────────────────────────────────────────────────
def render_report(sessions, *, agg=None, health_result=None,
                  life_indicators=None, narrative=None, source_label="",
                  disposition_block=None, interests_block=None):
    agg = agg or build_diary_metrics(sessions)
    L = []
    add = L.append
    add("=" * 62)
    add("　　　　질 문 형 일 기 · 주 간 리 포 트")
    add("=" * 62)
    if source_label:
        add(f"대상: {source_label}")
    dates = sorted({s.get("date") for s in sessions if s.get("date")})
    if dates:
        add(f"기간: {dates[0]} ~ {dates[-1]}  ({len(dates)}일치 기록)")
    add("")

    # ── 안전 하드 분기 ──
    scz = _session_crisis(sessions)
    h_safe = (health_result or {}).get("safety", {})
    if scz >= 3 or h_safe.get("level") == "crisis":
        add("⚠️  안전 안내")
        add("-" * 62)
        msg = next((s.get("crisis_message") for s in sessions if s.get("crisis_message")),
                   None) or h_safe.get("message") or ""
        add(msg)
        add("")
        add("오늘은 분석 대신 이걸 먼저 전하고 싶었어요. 혼자 견디지 않으셔도 됩니다.")
        return "\n".join(L)

    # ── 응답 요약 ──
    n_answers = agg.get("n_answers", 0)
    add("■ 응답 요약")
    add("-" * 62)
    add(f"  답변 문항 수 : {n_answers}개"
        + ("" if agg.get("diary_metrics") else f"  (⚠ {agg.get('gate_note')})"))
    add(f"  감정 궤적    : {R1._sparkline(_valence_series(sessions))}")
    dm = agg.get("diary_metrics")
    if dm:
        add(f"  누적 정서극성: {dm.get('emotion_valence')}   "
            f"대처균형: {dm.get('coping_balance')}   통찰: {dm.get('insight_ratio')}")
    add("")

    # ── 문항별 언어 신호 ──
    add("■ 문항별 신호  (답변만 반영 · 질문 텍스트 제외)")
    add("-" * 62)
    for line in to_prompt_block(sessions, agg).splitlines()[1:]:   # 헤더 1줄 제거
        add("  " + line)
    add("")

    # ── 심리 이론 근거(카드 직결) ──
    add("■ 심리 해석 근거  (질문 → 이론카드 직결)")
    add("-" * 62)
    cards = _collect_cards(sessions)
    if not cards:
        add("  (직결된 이론카드 없음)")
    for i, (label, c) in enumerate(cards, 1):
        prov = "  [잠정매핑]" if _is_provisional(label) else ""
        add(f"  {i}) {c['theory_ko']} — {c['concept_ko']}{prov}")
        add(f"     해석: {c.get('summary', '')[:90]}…")
        acts = c.get("interventions", [])
        if acts:
            add(f"     행동 제안: {acts[0]}")
        add(f"     출처: {c.get('source', '')}")
        add("")

    # ── 자유 기록(선택칸) — 유저 본인 목소리 ──
    free = _free_entries(sessions)
    if free:
        add("■ 자유 기록  (선택칸 · 본인이 자유롭게 남긴 말)")
        add("-" * 62)
        for f in free:
            add(f"  [{f['date']}] {f['text'][:70]}" + ("…" if len(f['text']) > 70 else ""))
        add("")

    # ── 건강 자기보고 (말로만 · 또래 통계 없이) ──
    if health_result and health_result.get("items"):
        add("■ 몸·마음 상태  (자기보고)")
        add("-" * 62)
        for it in health_result["items"]:
            flag = " ⚠" if it["concern"] else ""
            add(f"  · [{it['dim']}] {it['label'].split(',')[0]} → {it['level']}{flag}")
        words = _health_words(health_result)
        if words:
            add("  요약: " + ", ".join(words))
        if health_result.get("clinical_elevated") and h_safe.get("message"):
            add("")
            add("  ※ 자주 힘든 날이 이어진 항목이 있어, 지지·연결을 먼저 권합니다.")
            add(f"    {h_safe['message']}")
        add("")

    # ── 취향·관심사 메모(라포·개인화) ──
    if interests_block:
        add("■ 취향·관심사 메모  (라포·개인화 재료 · 예측 수치와 무관)")
        add("-" * 62)
        for line in interests_block.splitlines()[2:]:      # 가드 헤더 2줄 제외
            add("  " + line)
        add("")

    # ── 성향 프로파일(예측 서사 반영용) ──
    if disposition_block:
        add("■ 성향 프로파일  (시나리오 '내용 강조'·'전달 방식' 반영)")
        add("-" * 62)
        for line in disposition_block.splitlines():
            add("  " + line)
        add("")

    # ── 통합 서사 ──
    add("■ 통합 리포트" + ("  (Claude 서사)" if narrative else ""))
    add("-" * 62)
    if narrative:
        for para in narrative.split("\n"):
            add("  " + para)
    else:
        add("  (서사 생략 — 위 구조화 재료로 대체)")
    add("")
    add("=" * 62)
    return "\n".join(L)


def render_user_report(sessions, *, agg=None, health_result=None, narrative=None,
                       interests_profile=None, source_label=""):
    """유저 공개용 슬림 리포트 — 서사 중심. 지표·카드·축 등 내부 재료는 전부 숨긴다.

    보여줄 것: 기간 · 기분 흐름 · 이번 주 한눈에(좋음/걸림/몸마음) · 서사 · 취향 한 줄.
    위기 시엔 지지 메시지만.
    """
    agg = agg or build_diary_metrics(sessions)
    L = []
    add = L.append
    dates = sorted({s.get("date") for s in sessions if s.get("date")})
    period = f"{dates[0]} ~ {dates[-1]}" if dates else ""
    add(f"📅 이번 주 기록  ({period})")
    if source_label:
        add(f"   {source_label}")
    add("")

    # 안전 분기 — 위기면 지지 메시지만.
    scz = _session_crisis(sessions)
    h_safe = (health_result or {}).get("safety", {})
    if scz >= 3 or h_safe.get("level") == "crisis":
        msg = next((s.get("crisis_message") for s in sessions if s.get("crisis_message")),
                   None) or h_safe.get("message") or ""
        add(msg)
        return "\n".join(L)

    # 기분 흐름(명시적 체크인 붙기 전 임시 — 답변서 추정)
    mood = _weekly_mood(sessions)
    if mood:
        add("🗓  이번 주 기분 흐름")
        add("    " + "  ".join(e for _, e in mood))
        add("")

    # 이번 주 한눈에
    hi = _snippets(sessions, ("R3", "T1", "T4"), 3)
    lo = _snippets(sessions, ("C2", "R5", "D6"), 2)
    words = _health_words(health_result)
    add("✨ 이번 주 한눈에")
    if hi:
        add("    ☀ 좋았던 순간    " + "  ·  ".join(hi))
    if lo:
        add("    🌧 마음에 남은 것  " + "  ·  ".join(lo))
    if words:
        add("    💤 몸·마음        " + ", ".join(words))
    add("")

    # 서사(핵심)
    if narrative:
        add("─" * 46)
        for para in narrative.split("\n"):
            if para.strip():
                add(para.strip())
                add("")

    # 취향 한 줄
    kw = (interests_profile or {}).get("keywords", [])
    if kw:
        add("💛 요즘 관심: " + ", ".join(w for w, _ in kw[:5]))
    return "\n".join(L).rstrip()


def _is_provisional(label):
    """라벨(질문 텍스트)로 잠정매핑 여부 추정 — 표시용."""
    from qmode import card_map
    for qid in card_map.PROVISIONAL:
        q = _SCH.by_id.get(qid, {})
        if q.get("text") and q["text"] == label:
            return True
    return False


def build_report(sessions, *, health_result=None, life_indicators=None,
                 agg=None, source_label="", with_narrative=True, model=None,
                 disposition_block=None):
    """세션(+건강+성향) → 리포트 텍스트. with_narrative=True 이고 키가 있으면 서사 통합."""
    agg = agg or build_diary_metrics(sessions)
    scz = _session_crisis(sessions)
    h_crisis = (health_result or {}).get("safety", {}).get("level") == "crisis"

    interests_block = interests.build_block(interests.collect(sessions))

    narrative = None
    if with_narrative and scz < 3 and not h_crisis:
        R1._load_dotenv()
        prompt = build_narrative_prompt(sessions, agg, health_result,
                                        disposition_block, interests_block)
        narrative, _ = generate_narrative(prompt, model=model)

    return render_report(sessions, agg=agg, health_result=health_result,
                         life_indicators=life_indicators, narrative=narrative,
                         source_label=source_label, disposition_block=disposition_block,
                         interests_block=interests_block)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-narrative", action="store_true", help="Claude 서사 생략")
    ap.add_argument("--ckpt", default=str(ROOT / "model_v3_e6.pt"))
    args = ap.parse_args()

    from infer import DiaryAnalyzer                    # noqa: E402
    from qmode.session import analyze_session          # noqa: E402

    print("모델 로드 중…")
    az = DiaryAnalyzer(ckpt=args.ckpt,
                       taxonomy=str(DIARY / "emotion_taxonomy.json"))

    # 1주일치 데모 (평일 4문항 + 심층일 5문항, 자유칸 선택 입력)
    days = [
        ("2026-07-20", [  # 월
            {"question_id": "C1", "text": "출근길 라디오에서 좋아하는 노래가 나왔다."},
            {"question_id": "C2", "text": "회의에서 의견을 삼켰다. 옆에서 봤으면 눈치만 보는 사람 같았을 듯."},
            {"question_id": "T1", "text": "애니 '프리렌' 보는 중. 잔잔한 여운이 오래 남는다."},
            {"question_id": "R3", "text": "점심에 동료가 챙겨줘서 고마웠다. 덕분에 조금 풀렸다."}], None),
        ("2026-07-21", [  # 화
            {"question_id": "C1", "text": "저녁 하늘이 예뻐서 잠깐 멈춰 봤다."},
            {"question_id": "C2", "text": "할 일을 또 미뤘다. 스스로 한심하게 느껴졌다."},
            {"question_id": "T4", "text": "주말 클라이밍 생각하며 버텼다. 그거 할 때만 시간이 순삭이다."},
            {"question_id": "R4", "text": "평소 안 하던 야근을 자처했다. 좀 나답지 않았다."}],
         "요즘 뭘 위해 이렇게까지 하나 싶다."),
        ("2026-07-22", [  # 수(심층)
            {"question_id": "C1", "text": "혼자 카페에서 멍때린 시간."},
            {"question_id": "C2", "text": "메일 하나 붙잡고 한참 못 보냈다. 떨어져 보면 완벽하려 애쓴 것 같다."},
            {"question_id": "R3", "text": "오랜만에 친구랑 통화하고 웃었다."},
            {"question_id": "D1", "text": "이직을 계속 망설인다. 안정과 새 도전 사이가 마음에 걸린다."}], None),
        ("2026-07-23", [  # 목
            {"question_id": "C1", "text": "아침에 커피 향이 유난히 좋았다."},
            {"question_id": "C2", "text": "동기 승진 소식에 마음이 복잡했다. 옆에서 봤으면 씁쓸해 보였을 듯."},
            {"question_id": "T4", "text": "클라이밍 갔다. 끝나고 개운했지만 이내 피곤이 몰려왔다."},
            {"question_id": "R5", "text": "이번 주 나를 제일 지치게 한 건 끝없는 업무. 친구라면 좀 쉬라 했을 것."}], None),
        ("2026-07-24", [  # 금
            {"question_id": "C1", "text": "퇴근길 지하철에서 본 노을."},
            {"question_id": "C2", "text": "결국 하고 싶던 말을 못 했다. 나중에 후회됐다."},
            {"question_id": "T1", "text": "무라카미 소설을 다시 편다. 문장이 좋다."},
            {"question_id": "R3", "text": "저녁에 산책했다. 바람이 시원해서 좋았다."}], None),
        ("2026-07-25", [  # 토
            {"question_id": "C1", "text": "늦잠 자고 일어난 주말 아침."},
            {"question_id": "C2", "text": "밀린 집안일 앞에서 아무것도 못 하고 누워있었다."},
            {"question_id": "T4", "text": "클라이밍장에서 오래 있었다. 몰입하니 잡생각이 사라졌다."},
            {"question_id": "R4", "text": "혼자 있고 싶어 약속을 미뤘다. 나답진 않았다."}],
         "번아웃인가 싶다. 다 놓고 싶은 마음과 잘하고 싶은 마음이 같이 있다."),
        ("2026-07-26", [  # 일(심층)
            {"question_id": "C1", "text": "친구가 보낸 강아지 영상 보고 한참 웃었다."},
            {"question_id": "C2", "text": "친구에게 먼저 연락했다. 오랜만에 마음이 놓였다."},
            {"question_id": "R3", "text": "친구랑 저녁 먹으며 많이 웃었다."},
            {"question_id": "D6", "text": "실수한 나에게, 비슷한 친구였다면 괜찮다고 다독여줬을 것 같다."}], None),
    ]
    sessions = [analyze_session(az, d, a, free_text=fr, allow_api=False)
                for d, a, fr in days]

    # 건강 패널 + (backend 가 줄) 또래 통계 흉내
    health = health_input.process_health(
        {"sleep": 2, "stress": 4, "low_mood": 1, "exercise_days": 2,
         "burnout": 4, "loneliness": 3}, is_youth=True)
    life_indicators = [
        {"indicator": "수면장애", "value": 23.1, "unit": "%", "group": "여성 25-29"},
        {"indicator": "스트레스인지율", "value": 31.4, "unit": "%", "group": "여성 25-29"},
        {"indicator": "번아웃 경험률", "value": 41.0, "unit": "%", "group": "청년 25-29"},
    ]

    # 온보딩 가치순위(초기값) + 일기 언어지표 → 성향 프로파일
    from qmode import value_ranking, disposition          # noqa: E402
    ranked = ["family", "stability", "friends", "money", "meaning",
              "growth", "freedom", "status"]              # 관계·안정 우선 유저
    vw = value_ranking.axis_weights(ranked)
    agg = build_diary_metrics(sessions)
    disp = disposition.analyze_disposition(sessions, (agg or {}).get("diary_metrics"),
                                           value_weights=vw)
    interests_prof = interests.collect(sessions)
    interests_block = interests.build_block(interests_prof)

    # 서사 1회 생성 → 디버그/유저 리포트 양쪽에 재사용
    narrative = None
    if not args.no_narrative and _session_crisis(sessions) < 3 \
            and health["safety"]["level"] != "crisis":
        R1._load_dotenv()
        prompt = build_narrative_prompt(sessions, agg, health, disp["block"],
                                        interests_block)
        narrative, _ = generate_narrative(prompt)

    src = "(데모 1주일치 · 관계·안정 우선 유저)"
    debug = render_report(sessions, agg=agg, health_result=health, narrative=narrative,
                          disposition_block=disp["block"],
                          interests_block=interests_block, source_label=src)
    user = render_user_report(sessions, agg=agg, health_result=health,
                              narrative=narrative, interests_profile=interests_prof,
                              source_label=src)

    outdir = HERE / "samples"
    (outdir / "sample_report.txt").write_text(debug, encoding="utf-8")
    (outdir / "sample_user_report.txt").write_text(user, encoding="utf-8")
    print("=== [유저 공개용] ===\n")
    print(user)
    print(f"\n\n(디버그 풀뷰는 {outdir / 'sample_report.txt'} 에 저장됨)")
