# -*- coding: utf-8 -*-
"""relationship.py — 관계 도메인 서사 (카톡 스크린샷 × 성향 → 선택지형 분기 서사).

왜 이 모듈인가
    이직 서사는 개인단위 인과 데이터(임금·생존)가 있어 '수치 평행우주'가 성립한다.
    관계엔 그런 데이터가 없다. 그래서 관계의 평행우주는 '경제 반사실'이 아니라
    '행동 분기(behavioral branches)'로 번역한다 — "이렇게 반응하면 → 이런 흐름".
    숫자를 붙이면 그게 곧 잘못된 정보(건강·주식에서 피하려던 것)라 절대 붙이지 않는다.

두 재료의 곱
    · 내 성향(disposition, 일기 기반)  ×  실제 관계 행동(카톡에서 읽은 신호)
    이 곱이 일반론(별자리 운세)과 갈리는 지점이다. 한쪽만으론 개인화가 안 된다.

톤·안전 (relationship-narrative-design 메모리 준수)
    · 선택지형(B): 분기 A/B로 흐름·트레이드오프 제시, 명령 아님.
    · 담백·직설. "우주" 비유·감성 수식 금지. 라벨은 행동 명사구.
    · 상대방 성격 진단·라벨 금지(나르시시스트 등). 관찰된 '행동'만.
    · 이별·관계정리 직접 지시 금지 — 선택지로만.
    · 위기 신호 → crisis.py 로 분기(서사 대신 지원 안내).

입력
    · images: [{"media_type","data"(base64)}]  — 카톡 스크린샷(Claude 비전이 직접 읽음).
    · transcript: 텍스트 대화(이미지 없이도 테스트·입력 가능).

키 없으면 (None, 사유) 반환 — 오프라인에서도 import·구조·조립은 검증 가능.
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

_ATTACH = ("secure", "anxious", "avoidant", "mixed")

# ── 안전 (crisis.py 재활용) ────────────────────────────────────────────
def safety_check(text: str) -> dict:
    """대화 텍스트에서 위기 신호 탐지. block=True 면 서사 대신 지원 안내."""
    try:
        import crisis
    except Exception:
        return {"level": 0, "block": False, "support": ""}
    r = crisis.detect(text or "")
    return {"level": r.level, "block": r.block_report,
            "attach": r.attach_support,
            "support": crisis.support_message(r.level) if r.attach_support else ""}


def signals_text(signals) -> str:
    """추출된 신호에서 위기 탐지에 걸 텍스트만 모은다.

    스크린샷만 올라온 경우 transcript 가 비어 있어 1차 게이트가 아무것도 못 본다.
    비전이 읽어낸 대사 인용·정서 톤을 여기 모아 2차 게이트에 다시 건다.
    """
    if not isinstance(signals, dict):
        return ""
    parts = [signals.get("interaction_pattern", ""), signals.get("emotional_tone", "")]
    for key in ("my_behavior", "other_behavior", "recurring_themes", "evidence"):
        v = signals.get(key)
        if isinstance(v, list):
            parts.extend(str(x) for x in v)
    return "\n".join(p for p in parts if p)


def safety_check_signals(signals) -> dict:
    """이미지 경로용 2차 안전 게이트 — 추출된 신호 텍스트에 crisis 규칙을 적용."""
    return safety_check(signals_text(signals))


# ── LLM 호출 (disposition_llm 과 동일 패턴: 재시도·백오프) ───────────────
def _client():
    try:
        import report_one as R1
        R1._load_dotenv()
    except Exception:
        pass
    if not os.getenv("ANTHROPIC_API_KEY"):
        return None, "ANTHROPIC_API_KEY 미설정(.env 확인)"
    try:
        from anthropic import Anthropic
    except ImportError:
        return None, "anthropic 미설치"
    return Anthropic(), None


def _call(system, content, *, model=None, max_tokens=1200):
    """content(문자열 또는 블록리스트) → LLM 텍스트. (txt, None) 또는 (None, 사유)."""
    client, err = _client()
    if client is None:
        return None, err
    model = model or "claude-sonnet-5"
    msg_content = content if isinstance(content, list) else [{"type": "text", "text": content}]
    last = None
    for attempt in range(3):
        try:
            resp = client.messages.create(
                model=model, max_tokens=max_tokens, system=system,
                thinking={"type": "disabled"},
                messages=[{"role": "user", "content": msg_content}],
            )
            return "".join(b.text for b in resp.content if b.type == "text").strip(), None
        except Exception as e:      # noqa: BLE001
            last = e
            m = str(e).lower()
            transient = any(s in m for s in ("529", "overload", "rate", "500", "502", "503", "timeout"))
            if transient and attempt < 2:
                time.sleep(1.5 * (attempt + 1))
                continue
            return None, f"LLM 오류: {e}"
    return None, f"LLM 오류: {last}"


def _parse_json(txt):
    """코드펜스 방어 후 JSON 파싱.

    화질이 낮거나 애매한 이미지에서는 모델이 JSON 앞뒤로 안내문을 덧붙인다
    (예: "해상도가 낮아..." 다음에 ```json{...}``` 다음에 "더 선명한 이미지를..").
    앞부분만 코드펜스인지 보던 예전 방식은 이 경우를 못 잡아 전체 텍스트를
    json.loads 에 넘겨 파싱이 통째로 실패했다. 위치와 무관하게 첫 '{'~마지막 '}' 를
    잘라내 파싱한다.
    """
    start, end = txt.find("{"), txt.rfind("}")
    if start != -1 and end != -1 and end > start:
        txt = txt[start:end + 1]
    return json.loads(txt)


# ── 1) 카톡 → 관계 신호 추출 ────────────────────────────────────────────
_EXTRACT_SYSTEM = (
    "너는 대화 기록(카톡 스크린샷 또는 텍스트)을 읽고 관계의 '상호작용 신호'를 "
    "구조화해 뽑는 분석기다. 상대방의 성격을 진단·라벨링하지 않는다(나르시시스트 등 금지). "
    "오직 대화에서 '관찰된 행동'과 사용자 쪽 경향만 근거와 함께 추출한다. "
    "아래 JSON 스키마에 정확히 맞는 데이터만 출력한다(설명·코드펜스 금지)."
)

_EXTRACT_SCHEMA = """반드시 이 JSON 형식으로만 답하라:
{
  "interaction_pattern": "반복 관찰되는 상호작용 흐름 한 줄 (예: 내가 먼저 사과 → 상대 회피 → 반복)",
  "my_behavior": ["사용자(나) 쪽에서 관찰된 행동 1~3개"],
  "other_behavior": ["상대 쪽에서 '관찰된 행동'만 1~3개. 성격 진단 금지, 행동 묘사만"],
  "attachment_lean_self": "secure | anxious | avoidant | mixed (사용자 쪽 경향, 근거 약하면 mixed)",
  "recurring_themes": ["반복되는 갈등 주제 (연락빈도/시간/신뢰 등)"],
  "emotional_tone": "대화의 정서 톤 한 줄",
  "confidence": 0.0,
  "evidence": ["판단 근거가 된 실제 대사 인용 1~3개"]
}
근거가 약하면 confidence 를 낮춰라(억지로 높이지 말 것)."""


def _validate_signals(obj):
    if not isinstance(obj, dict):
        raise ValueError("최상위가 dict 아님")
    if not obj.get("interaction_pattern"):
        raise ValueError("interaction_pattern 누락")
    if obj.get("attachment_lean_self") not in _ATTACH:
        obj["attachment_lean_self"] = "mixed"   # 관대 보정(추출은 흔들릴 수 있음)
    obj.setdefault("my_behavior", [])
    obj.setdefault("other_behavior", [])
    obj.setdefault("recurring_themes", [])
    obj.setdefault("evidence", [])
    return obj


def extract_signals(images=None, transcript=None, *, relation_tag=None, model=None):
    """카톡 스크린샷/텍스트 → 관계 신호 dict. (dict, None) 또는 (None, 사유)."""
    if not images and not (transcript or "").strip():
        return None, "입력 없음(images 또는 transcript 필요)"
    header = f"[관계 대화 분석 — 상대 태그: {relation_tag or '미지정'}]"
    blocks = []
    for im in (images or []):
        blocks.append({"type": "image", "source": {
            "type": "base64",
            "media_type": im.get("media_type", "image/png"),
            "data": im["data"]}})
    text_parts = [header]
    if transcript:
        text_parts.append("대화 텍스트:\n" + transcript)
    elif images:
        text_parts.append("위 스크린샷의 대화를 읽어라. 말풍선 좌/우로 누가 말했는지 구분하라.")
    text_parts.append("\n" + _EXTRACT_SCHEMA)
    blocks.append({"type": "text", "text": "\n".join(text_parts)})

    txt, err = _call(_EXTRACT_SYSTEM, blocks, model=model, max_tokens=1000)
    if txt is None:
        return None, err
    try:
        return _validate_signals(_parse_json(txt)), None
    except Exception as e:      # noqa: BLE001
        return None, f"신호 파싱 실패: {e}"


# ── 심리 논문 근거 (한국인 타당화 우선) ────────────────────────────────
# rag_local/심리학_논문 의 모든 청크 파일을 합쳐 읽는다.
#   · rag_wellbeing_papers_chunks_v2.json — 웰빙(Ryff·김명소2001), sohyun 논문RAG 복사본
#   · rag_papers_relationship_v1.json     — 관계 전용(indicator="관계"), 한국관계심리 Tier1
#   이 디렉터리가 없으면 근거 없이(프레임워크 이름만) 서사가 나간다.
#   그 경우 generate_narrative 가 paper_grounded=False 로 표시한다.
_PAPERS_DIR = HERE / "rag_local" / "심리학_논문"
# 관계 서사에 직결되는 토픽(웰빙 코퍼스 쪽). 관계 전용 청크는 indicator로 가중.
_REL_TOPICS = ("긍정적대인관계", "문화적맥락", "한국타당화", "자율성",
               "시나리오적용함의", "서비스적용근거")


def _load_papers():
    out = []
    try:
        for f in sorted(_PAPERS_DIR.glob("*.json")):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
                if isinstance(d, list):
                    out.extend(d)
            except Exception:
                continue
    except Exception:
        return []
    return out


# 신호 → 관련 토픽 매핑 (시나리오에 맞는 논문을 우선 주입하기 위함).
_LEAN_TOPICS = {
    "anxious": {"attachment_anxiety", "rejection_sensitivity", "attachment_type"},
    "avoidant": {"attachment_type", "demand_withdraw"},
    "secure": {"attachment_type"},
    "mixed": {"attachment_type"},
}
_KEYWORD_TOPICS = [
    (("갈등", "싸움", "다툼", "화", "비난", "경멸"), {"gottman", "demand_withdraw", "conflict_resolution"}),
    (("연락", "답장", "읽씹", "무시", "사과", "회피", "철회"), {"demand_withdraw", "rejection_sensitivity", "conflict_resolution"}),
    (("이별", "헤어", "정리", "그만", "끝"), {"jeong_application", "jeong_narrative"}),
    (("눈치", "맞춤", "배려", "참"), {"nunchi"}),
    (("정", "우리", "가족", "오래"), {"jeong_weness", "jeong_narrative"}),
]


def _signal_hints(signals):
    """신호 dict → 관련 토픽 집합(주입 우선순위용)."""
    if not signals:
        return set()
    hints = set(_LEAN_TOPICS.get(signals.get("attachment_lean_self"), set()))
    q = " ".join([signals.get("interaction_pattern", ""), signals.get("emotional_tone", "")]
                 + list(signals.get("recurring_themes", []))
                 + list(signals.get("my_behavior", [])) + list(signals.get("other_behavior", [])))
    for words, topics in _KEYWORD_TOPICS:
        if any(w in q for w in words):
            hints |= topics
    return hints


def paper_evidence(signals=None, k=4):
    """관계 서사용 논문 근거 청크. 관계 전용·한국 논문 우선 + 시나리오 신호에 맞는 토픽 가중.

    임베딩 없이 토픽 필터(소규모 코퍼스). 반환: [{source, document}] 최대 k개.
    signals 주면 그 시나리오(애착경향·갈등주제)에 맞는 논문을 우선 주입한다.
    """
    papers = _load_papers()
    if not papers:
        return []
    _TOP = {"긍정적대인관계": 3, "문화적맥락": 3}
    hints = _signal_hints(signals)
    def score(c):
        m = c.get("metadata", {})
        s = _TOP.get(m.get("topic"), 2 if m.get("topic") in _REL_TOPICS else 0)
        if m.get("indicator") == "관계":     # 관계 전용 청크 — 관계 서사에 최우선
            s += 4
        if m.get("topic") in hints:          # 이 시나리오에 직결되는 토픽
            s += 3
        if any(ord(ch) > 0x3130 for ch in m.get("source", "")[:10]):  # 저자 한글=한국 논문
            s += 3
        return s
    ranked = sorted(papers, key=score, reverse=True)
    out, per_src = [], {}
    for c in ranked:
        if score(c) <= 0:
            break
        src = c.get("metadata", {}).get("source", "")
        if per_src.get(src, 0) >= 2:      # 한 논문에서 최대 2청크 — 출처 다양성 확보
            continue
        per_src[src] = per_src.get(src, 0) + 1
        out.append({"source": src, "document": c.get("document", "")})
        if len(out) >= k:
            break
    return out


def papers_available() -> bool:
    """관계 논문 코퍼스가 실제로 로드되는지. False 면 서사는 근거 없이 생성된다."""
    return bool(_load_papers())


def _paper_block(ev):
    if not ev:
        return ""
    lines = ["\n[심리학 논문 근거 — 한국인 정서 맥락 우선. 관련되면 이 출처를 branches.basis 에 인용하라]"]
    for e in ev:
        lines.append(f"  · 출처: {e['source']}")
        lines.append(f"    요지: {e['document'][:220]}")
    return "\n".join(lines)


# ── 2) 신호 × 성향 → 선택지형 분기 서사 ─────────────────────────────────
_NARR_SYSTEM = (
    "너는 관계 코치가 아니라 '성찰 재료'를 제공하는 분석기다. 사용자의 성향과 "
    "대화에서 읽은 신호를 근거로, 앞으로의 '행동 분기'를 선택지로 제시한다.\n"
    "엄격한 규칙:\n"
    "· 담백하고 직설적으로 쓴다. '우주' 비유, 감성 수식어, 이모지 금지.\n"
    "· 분기 라벨은 행동 명사구로 (예: '먼저 다가가기', '한 박자 멈추고 표현하기').\n"
    "· 상대방 성격을 진단·라벨링하지 않는다.\n"
    "· '헤어져라/정리해라' 같은 직접 지시 금지. 선택지와 트레이드오프만 제시.\n"
    "· 근거는 제공된 '심리학 논문 근거'가 있으면 그 출처를 우선 인용하고(한국인 정서 "
    "맥락 우선), 없으면 널리 알려진 프레임워크 이름만(애착이론·비폭력대화·Gottman 등). "
    "제공되지 않은 특정 논문·페이지를 지어내지 말 것.\n"
    "· 수치·확률을 지어내지 말 것(관계엔 인과 데이터가 없다).\n"
    "아래 JSON 스키마에 정확히 맞는 데이터만 출력한다(설명·코드펜스 금지)."
)

_NARR_SCHEMA = """반드시 이 JSON 형식으로만 답하라:
{
  "reading": "지금 관계에서 읽히는 패턴 한두 줄 (담백, 단정 아닌 관찰)",
  "branches": [
    {"label": "행동 명사구", "outcome": "이 선택의 예상 흐름·트레이드오프 (담백, 성향과 연결)", "basis": "근거 심리 프레임워크 이름 (없으면 빈 문자열)"}
  ],
  "next_step": "오늘 해볼 수 있는 구체적 한 걸음 (성향에 맞는 선택지 제안, 명령 아님)",
  "change_note": "이전 스냅샷 대비 달라진 점 (히스토리 있을 때만, 없으면 빈 문자열)"
}
branches 는 2~3개."""


def _disposition_block(disp):
    if not disp:
        return "성향: (정보 없음 — 일반적 성향 가정 금지, 신호만으로 신중히)"
    keys = [("coping", "대처"), ("risk_tolerance", "변화감수"),
            ("decision_style", "결정방식"), ("value_order", "가치순위"),
            ("summary", "요약")]
    parts = []
    for k, ko in keys:
        v = disp.get(k)
        if v not in (None, "", []):
            parts.append(f"{ko}={v}")
    return "성향(일기 기반): " + " · ".join(parts) if parts else "성향: (정보 부족)"


def _history_block(history):
    if not history:
        return ""
    lines = ["\n[이전 관계 스냅샷 — 변화 추적용]"]
    for h in history[-4:]:
        lbl = h.get("label") or h.get("snapshot_time", "")
        pat = (h.get("signals") or {}).get("interaction_pattern", "")
        lines.append(f"  · {lbl}: {pat}")
    lines.append("→ change_note 에 이전 대비 달라진 점을 담백하게 적어라.")
    return "\n".join(lines)


def generate_narrative(signals, disposition=None, history=None, *, model=None):
    """관계 신호 × 성향 (+히스토리) → 선택지형 분기 서사 dict. (dict, None)|(None, 사유)."""
    if not signals:
        return None, "signals 없음"
    ev = paper_evidence(signals=signals)
    prompt = "\n".join([
        _disposition_block(disposition),
        "",
        "[대화에서 읽은 신호]",
        json.dumps(signals, ensure_ascii=False, indent=2),
        _history_block(history),
        _paper_block(ev),
        "",
        _NARR_SCHEMA,
    ])
    txt, err = _call(_NARR_SYSTEM, prompt, model=model, max_tokens=1200)
    if txt is None:
        return None, err
    try:
        obj = _parse_json(txt)
    except Exception as e:      # noqa: BLE001
        return None, f"서사 파싱 실패: {e}"
    obj.setdefault("branches", [])
    obj.setdefault("change_note", "")
    # 코퍼스가 없으면 프롬프트가 '프레임워크 이름만' 폴백으로 돌아간다.
    # 조용히 넘어가면 근거 없는 서사를 '논문 기반'으로 오인하게 되므로 응답에 남긴다.
    obj["paper_grounded"] = bool(ev)
    obj["paper_sources"] = [e["source"] for e in ev]
    obj["text"] = render_text(obj)
    return obj, None


def render_text(narr):
    """서사 dict → 담백한 표시용 텍스트."""
    lines = []
    if narr.get("reading"):
        lines.append(f"[읽은 패턴] {narr['reading']}")
        lines.append("")
    for i, b in enumerate(narr.get("branches", [])):
        tag = chr(ord("A") + i)
        line = f"{tag}. {b.get('label','')}"
        lines.append(line)
        if b.get("outcome"):
            lines.append(f"   {b['outcome']}")
        if b.get("basis"):
            lines.append(f"   근거: {b['basis']}")
        lines.append("")
    if narr.get("next_step"):
        lines.append(f"다음 한 걸음: {narr['next_step']}")
    if narr.get("change_note"):
        lines.append("")
        lines.append(f"지난번과 비교: {narr['change_note']}")
    return "\n".join(lines).rstrip()


# ── 오프라인 검증 (키 없이 조립·렌더 확인) ──────────────────────────────
if __name__ == "__main__":
    print("=== 안전 게이트 ===")
    for t in ["요즘 걔랑 자주 싸운다", "이러다 죽고 싶다는 생각까지 들어"]:
        s = safety_check(t)
        print(f"  L{s['level']} block={s['block']} :: {t}")

    fake_signals = {
        "interaction_pattern": "내가 먼저 사과 → 상대 회피 → 반복",
        "my_behavior": ["갈등 나면 내가 먼저 연락", "상대 기분 먼저 살핌"],
        "other_behavior": ["답장이 느려짐", "주제를 돌림"],
        "attachment_lean_self": "anxious",
        "recurring_themes": ["연락 빈도", "서운함 표현"],
        "emotional_tone": "지친 채로 눈치 보는 톤",
        "confidence": 0.6,
        "evidence": ["내가 미안하다고 했는데 읽씹함"],
    }
    fake_disp = {"coping": "avoidant", "risk_tolerance": 0.3,
                 "decision_style": "intuitive", "summary": "안정·관계 중심, 회피 경향"}

    print("\n=== 렌더 검증(가짜 서사) ===")
    demo = {"reading": "너는 갈등을 먼저 봉합하는 쪽, 상대는 물러서는 쪽.",
            "branches": [
                {"label": "먼저 다가가기", "outcome": "단기 평화, 회피 성향상 감정 쌓임", "basis": "애착이론"},
                {"label": "한 박자 멈추고 표현하기", "outcome": "초반 불편, 관계 재협상 여지", "basis": "비폭력대화"}],
            "next_step": "오늘은 사과 대신 '나는 이때 서운했어' 한 문장부터.",
            "change_note": ""}
    print(render_text(demo))

    # 키 있으면 실제 텍스트 대화로 end-to-end
    _c, _e = _client()
    if _c is not None:
        print("\n=== 실제 호출(텍스트 대화) ===")
        transcript = ("나: 어제 왜 답장 안 했어?\n상대: 바빴어\n나: 요즘 계속 이래..\n"
                      "상대: 또 그 얘기야?\n나: 미안, 내가 예민한가봐")
        sig, se = extract_signals(transcript=transcript, relation_tag="연인")
        print("신호:", se or json.dumps(sig, ensure_ascii=False)[:300])
        if sig:
            narr, ne = generate_narrative(sig, fake_disp)
            print("\n서사:\n", ne or narr["text"])
    else:
        print(f"\n(실제 호출 생략: {_e})")
