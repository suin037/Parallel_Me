"""Claude API: 엔진 수치 + RAG 근거 → 사람이 읽을 '평행우주' 서사로 변환.

경계 원칙: 숫자는 엔진(L1~L5)이 만들고, RAG가 통계/이론 근거를 붙이며,
Claude 는 '지어내지 않고' 그 수치·근거를 이야기로 풀어 설명하는 역할만 한다.

지연 설계(측정 근거는 아래 수치 주석 참조):
  서사 호출 지연은 입력 처리가 아니라 **출력 토큰 생성**이 전부다. 한 번에
  A·B·비교·이미지장면을 다 뽑으면 출력이 ~1,270토큰이고 Haiku 는 ~100tok/s 라
  12초가 그대로 사용자 대기시간이 된다. 그래서 서로 의존하지 않는 세 덩이
  (A 서사 / B 서사 / 비교+이미지장면)를 **동시에** 호출해 벽시계 시간을
  '합'에서 '최댓값'으로 바꾼다. 세 콜 모두 A·B 수치를 함께 받으므로 비교 서사도
  같은 근거 위에서 쓰인다(프로젝트 원칙: 숫자는 엔진이 만든다).
"""

from __future__ import annotations

import asyncio
import json
import logging

from anthropic import Anthropic, AsyncAnthropic

from config import settings
from schemas import PredictRequest

log = logging.getLogger(__name__)

_client: Anthropic | None = None
_aclient: AsyncAnthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic(api_key=settings.anthropic_api_key)
    return _client


def _get_async_client() -> AsyncAnthropic:
    global _aclient
    if _aclient is None:
        _aclient = AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _aclient


# ────────────────────────────────────────────────────────────────
# 수치 요약: CompareResponse 의 한 ScenarioView(dict) → 프롬프트용 압축 텍스트
# ────────────────────────────────────────────────────────────────
def summarize_scenario(sv: dict) -> str:
    lines: list[str] = []
    lines.append(f"선택: {sv.get('choice','?')} — {sv.get('coverage','')}")

    ss = sv.get("satisfaction_summary") or {}
    if ss:
        lines.append(
            f"만족도(1~5): {ss.get('start')}→{ss.get('latest')} ({ss.get('direction','')}, "
            f"{ss.get('span_years','?')}년, n={ss.get('sample_n','?')})"
        )

    inc = [p for p in (sv.get("income") or []) if p.get("available")]
    if inc:
        parts = [f"{p['year']}년 {p.get('value')}만원({p.get('p25')}~{p.get('p75')})" for p in inc]
        lines.append("소득 궤적: " + " · ".join(parts))

    rs = sv.get("regret_summary") or {}
    if rs:
        lines.append(
            f"후회리스크: {rs.get('worst_year','?')}년 {rs.get('label','')} "
            f"{rs.get('worst_value','?')}{rs.get('unit','')}"
        )

    cc = [c for c in (sv.get("choice_context") or []) if isinstance(c, dict)]
    if cc:
        ctx = "; ".join(f"{c.get('label','')} {c.get('value','')}{c.get('unit','')}" for c in cc[:4])
        if ctx.strip():
            lines.append("선택맥락: " + ctx)

    conf = sv.get("confidence") or {}
    ci = conf.get("survival_c_index") or {}
    ce = conf.get("causal_effect") or {}
    if ci:
        lines.append(f"신뢰(생존모델 C-index): {ci.get('c_index_test')}")
    if ce:
        lines.append(f"신뢰(인과효과): {json.dumps(ce, ensure_ascii=False)[:160]}")
    return "\n".join(lines)


def _fmt_evidence(evidence: list[dict]) -> str:
    if not evidence:
        return "(근거 없음)"
    out = []
    # 검색 결과 전체 대신 실제 서사에 인용할 상위 근거만 전달해 지연을 줄인다.
    for e in evidence[:2]:
        out.append(
            f"- ({e.get('indicator','')}) {e.get('text','')[:160]}  [출처: {e.get('source','')[:50]}]"
        )
    return "\n".join(out)


def _extract_json(text: str) -> dict | None:
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t[:4].lower() == "json":
            t = t[4:]
    a, b = t.find("{"), t.rfind("}")
    if a != -1 and b != -1 and b > a:
        try:
            return json.loads(t[a : b + 1])
        except Exception:
            return None
    return None


# ────────────────────────────────────────────────────────────────
# 프롬프트 조각 — 정적 규칙은 system 으로 분리해 요청마다 재조립하지 않는다.
# ────────────────────────────────────────────────────────────────
_RULES_COMMON = """너는 '평행우주 인생 시뮬레이터'의 서사 작가다. 입력은 실제 한국 패널 데이터로 계산한 두 진로 선택의 수치와, RAG로 검색한 통계·심리 근거다.

규칙(엄수):
- 숫자를 새로 지어내지 마라. 제공된 수치·근거 안에서만 말하라.
- "너와 비슷한 사람들이 그 길을 갔을 때"의 관점으로 서술하라(단정 예측 금지).
- 따뜻하되 현실적으로 쓰고, 단정적 미래 예측 대신 가능성을 표현하라.
- 이론명·저자명·출판연도·논문명을 서사에 직접 인용하지 마라. 근거는 자연스러운 설명으로만 반영하라.
- A/B를 억지로 정답/오답 또는 긍정/부정으로 나누지 마라."""

_RULES_STORY = """
- 모든 필드는 한국어로 쓴다. detail 의 세 필드는 summary 를 반복하지 않는다.
- 글자수는 권장이 아니라 지켜야 하는 상한이다. 넘기면 화면에서 잘려 실패한다.
  각 필드를 쓰고 나서 세어 보고, 넘었으면 문장을 쪼개지 말고 덜 중요한 수식어를 지워라.
    title 20자 · summary 90자 · detail.present/transition/future 각 70자 · gain 35자 · cost 35자
- 길이 감각 예시(내용은 무시하고 분량만 참고):
    title: "안정을 택한 3년"  (8자)
    summary: "소득은 천천히 늘지만 성장 체감은 줄어드는 길—지금의 편안함과 5년 뒤 선택폭을 맞바꾼다."  (48자)
    detail.transition: "첫 1~2년은 익숙함이 버팀목이 되지만 배움의 속도는 느려집니다."  (34자)
    gain: "예측 가능한 소득과 낮은 적응 비용"  (17자)"""

_RULES_COMPARISON = """
- comparison.summary 는 두 길의 trade-off 를 한 문장(90자 이내)으로, question 은 사용자가 스스로 답할 질문 한 문장으로 쓴다. 둘 다 한국어.
- visual_a / visual_b 는 간결한 영어로 쓴 이미지 장면 지시문이다. scene 은 배경·행동·감정·핵심 사물·카메라 앵글을 담은 35 English words 이내의 생생한 한 문장이다.
- A와 B의 장면은 구도가 서로 달라야 한다. 이야기에 맞는 장소·행동·자세·소품·앵글·조명·색감을 골라라. 둘 다 노트북 앞에 앉은 사람으로 기본값을 두지 마라.
- 장면은 주어진 이야기를 극적으로 표현할 수 있으나 사실관계를 새로 만들면 안 된다. 등장인물은 정확히 한 명이며 동료·군중·실루엣·반사상·초상·배경 인물을 넣지 마라. 사회적 맥락은 환경과 사물로 표현하라. 읽을 수 있는 글자를 넣지 마라."""

# ── 구조화 출력 스키마: 마크다운 펜스/서두 없이 유효한 JSON 을 보장한다.
#    (기존엔 "JSON만 출력하라" + 정규식 추출이라, 잘리면 조용히 raw 앞 600자가
#     서사 a 로 들어갔다.) 주의: json_schema 는 maxLength 를 지원하지 않아
#     글자수 제한은 위 규칙 프롬프트로만 건다.
_DETAIL_SCHEMA = {
    "type": "object",
    "properties": {
        "present": {"type": "string"},
        "transition": {"type": "string"},
        "future": {"type": "string"},
    },
    "required": ["present", "transition", "future"],
    "additionalProperties": False,
}
_STORY_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "summary": {"type": "string"},
        "detail": _DETAIL_SCHEMA,
        "gain": {"type": "string"},
        "cost": {"type": "string"},
    },
    "required": ["title", "summary", "detail", "gain", "cost"],
    "additionalProperties": False,
}
_VISUAL_SCHEMA = {
    "type": "object",
    "properties": {"scene": {"type": "string"}},
    "required": ["scene"],
    "additionalProperties": False,
}
_COMPARISON_SCHEMA = {
    "type": "object",
    "properties": {
        "comparison": {
            "type": "object",
            "properties": {"summary": {"type": "string"}, "question": {"type": "string"}},
            "required": ["summary", "question"],
            "additionalProperties": False,
        },
        "visual_a": _VISUAL_SCHEMA,
        "visual_b": _VISUAL_SCHEMA,
    },
    "required": ["comparison", "visual_a", "visual_b"],
    "additionalProperties": False,
}
_FULL_SCHEMA = {
    "type": "object",
    "properties": {
        "a": _STORY_SCHEMA,
        "b": _STORY_SCHEMA,
        "comparison": _COMPARISON_SCHEMA["properties"]["comparison"],
        "visual_a": _VISUAL_SCHEMA,
        "visual_b": _VISUAL_SCHEMA,
    },
    "required": ["a", "b", "comparison", "visual_a", "visual_b"],
    "additionalProperties": False,
}


def _facts_block(profile: dict, scen_a: dict, scen_b: dict,
                 evidence_a: list[dict], evidence_b: list[dict], note: str) -> str:
    """세 콜이 공유하는 '근거' 본문. 같은 수치를 보게 해 서사 간 모순을 막는다."""
    prof = ", ".join(f"{k}={v}" for k, v in profile.items() if v is not None)
    return f"""[사용자 프로필] {prof}
[주의사항] {note or '(없음)'}

===== 선택지 A =====
{summarize_scenario(scen_a)}
[A 근거]
{_fmt_evidence(evidence_a)}

===== 선택지 B =====
{summarize_scenario(scen_b)}
[B 근거]
{_fmt_evidence(evidence_b)}"""


# ────────────────────────────────────────────────────────────────
# A/B 시나리오 서사
# ────────────────────────────────────────────────────────────────
def _empty(msg: str) -> dict:
    return {"a": msg, "b": msg, "comparison": msg, "_skipped": True}


async def _one_call(model: str, system: str, user: str, schema: dict,
                    max_tokens: int) -> tuple[dict, dict | None]:
    """구조화 출력 1회. (파싱된 dict, usage) 반환."""
    resp = await _get_async_client().messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        output_config={"format": {"type": "json_schema", "schema": schema}},
        messages=[{"role": "user", "content": user}],
    )
    text = resp.content[0].text if resp.content else ""
    parsed = _extract_json(text) or {}
    usage = getattr(resp, "usage", None)
    u = (
        {"input_tokens": getattr(usage, "input_tokens", None),
         "output_tokens": getattr(usage, "output_tokens", None)}
        if usage else None
    )
    return parsed, u


def _sum_usage(parts: list[dict | None]) -> dict | None:
    got = [p for p in parts if p]
    if not got:
        return None
    return {
        "input_tokens": sum(p.get("input_tokens") or 0 for p in got),
        "output_tokens": sum(p.get("output_tokens") or 0 for p in got),
        "calls": len(got),
    }


async def agenerate_scenarios(
    profile: dict,
    scen_a: dict,
    scen_b: dict,
    evidence_a: list[dict],
    evidence_b: list[dict],
    note: str = "",
    model: str | None = None,
) -> dict:
    """A 서사·B 서사·비교+이미지장면을 동시 3콜로 생성.

    출력 토큰이 콜당 1/3 로 줄어 벽시계 시간이 '합'에서 '최댓값'이 된다.
    한 콜이 실패해도 나머지는 살린다(부분 실패 > 전체 실패).
    """
    used_model = model or settings.claude_model
    facts = _facts_block(profile, scen_a, scen_b, evidence_a, evidence_b, note)

    sys_story = _RULES_COMMON + _RULES_STORY
    sys_cmp = _RULES_COMMON + _RULES_COMPARISON

    tasks = [
        _one_call(used_model, sys_story,
                  facts + "\n\n위 근거로 **선택지 A** 의 서사만 작성하라.",
                  _STORY_SCHEMA, settings.narrative_max_tokens_story),
        _one_call(used_model, sys_story,
                  facts + "\n\n위 근거로 **선택지 B** 의 서사만 작성하라.",
                  _STORY_SCHEMA, settings.narrative_max_tokens_story),
        _one_call(used_model, sys_cmp,
                  facts + "\n\n위 근거로 comparison 과 visual_a·visual_b 만 작성하라.",
                  _COMPARISON_SCHEMA, settings.narrative_max_tokens_comparison),
    ]
    res = await asyncio.gather(*tasks, return_exceptions=True)

    parsed: list[dict] = []
    usages: list[dict | None] = []
    errors: list[str] = []
    for name, r in zip(("a", "b", "comparison"), res):
        if isinstance(r, BaseException):
            log.error("서사 콜 실패(%s): %s", name, r)
            errors.append(f"{name}:{type(r).__name__}")
            parsed.append({})
            usages.append(None)
        else:
            parsed.append(r[0])
            usages.append(r[1])

    a_obj, b_obj, cmp_obj = parsed
    out: dict = {
        "a": a_obj or "",
        "b": b_obj or "",
        "comparison": cmp_obj.get("comparison", ""),
        "visual_a": cmp_obj.get("visual_a", {}),
        "visual_b": cmp_obj.get("visual_b", {}),
        "_model": used_model,
        "_usage": _sum_usage(usages),
        "_mode": "parallel3",
    }
    if errors:
        out["_partial_error"] = ",".join(errors)
    return out


def _single_call_scenarios(
    profile: dict, scen_a: dict, scen_b: dict,
    evidence_a: list[dict], evidence_b: list[dict],
    note: str, used_model: str,
) -> dict:
    """예전 경로: 1회 호출로 전부 생성. 느리지만 A·B·비교가 한 컨텍스트에서 나온다.
    settings.narrative_parallel=False 로 되돌릴 수 있게 남겨둔다."""
    facts = _facts_block(profile, scen_a, scen_b, evidence_a, evidence_b, note)
    system = _RULES_COMMON + _RULES_STORY + _RULES_COMPARISON + """
- 최종 출력은 a, b, comparison, visual_a, visual_b 를 모두 담은 하나의 JSON 객체다."""
    resp = _get_client().messages.create(
        model=used_model,
        # 한국어 JSON은 토큰 효율이 낮아 너무 작게 제한하면 객체 끝이 잘린다.
        max_tokens=3000,
        system=system,
        output_config={"format": {"type": "json_schema", "schema": _FULL_SCHEMA}},
        messages=[{"role": "user", "content": facts + "\n\n위 근거로 전체 서사를 작성하라."}],
    )
    raw = resp.content[0].text if resp.content else ""
    parsed = _extract_json(raw) or {}
    usage = getattr(resp, "usage", None)
    return {
        "a": parsed.get("a", raw[:600]),
        "b": parsed.get("b", ""),
        "comparison": parsed.get("comparison", ""),
        "visual_a": parsed.get("visual_a", {}),
        "visual_b": parsed.get("visual_b", {}),
        "_model": used_model,
        "_usage": {
            "input_tokens": getattr(usage, "input_tokens", None),
            "output_tokens": getattr(usage, "output_tokens", None),
        }
        if usage
        else None,
        "_mode": "single",
    }


def generate_scenarios(
    profile: dict,
    scen_a: dict,
    scen_b: dict,
    evidence_a: list[dict],
    evidence_b: list[dict],
    note: str = "",
    model: str | None = None,
) -> dict:
    """엔진 수치 + RAG 근거 → 요약·상세 구조의 A/B 서사. 키 없으면 skip.

    동기 시그니처를 유지한다(/simulate 가 sync 엔드포인트라 threadpool 에서 돈다).
    이미 이벤트 루프 안이면 agenerate_scenarios 를 직접 await 하라.
    """
    if not settings.anthropic_api_key:
        return _empty("(ANTHROPIC_API_KEY 미설정 — 서사 생략)")

    used_model = model or settings.claude_model
    if not settings.narrative_parallel:
        return _single_call_scenarios(
            profile, scen_a, scen_b, evidence_a, evidence_b, note, used_model
        )

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass  # 루프 없음 = 정상 경로(동기 호출)
    else:
        raise RuntimeError(
            "generate_scenarios() 를 실행 중인 이벤트 루프에서 호출했다. "
            "async 문맥에서는 agenerate_scenarios() 를 await 하라."
        )

    return asyncio.run(
        agenerate_scenarios(
            profile, scen_a, scen_b, evidence_a, evidence_b, note=note, model=used_model
        )
    )


async def _awarm_schemas(model: str) -> None:
    """실제로 쓰는 스키마들을 동시에 한 번씩 태운다."""
    await asyncio.gather(
        _one_call(model, "Reply with the shortest possible valid object.",
                  "warmup", _STORY_SCHEMA, 96),
        _one_call(model, "Reply with the shortest possible valid object.",
                  "warmup", _COMPARISON_SCHEMA, 96),
        _one_call(model, "Reply with the shortest possible valid object.",
                  "warmup", _FULL_SCHEMA, 128),
        return_exceptions=True,
    )


def warm_narrative_schema(model: str | None = None) -> bool:
    """구조화 출력 스키마의 최초 컴파일 비용을 기동 시점으로 옮긴다.

    새 스키마는 처음 쓸 때 한 번 컴파일 비용을 낸다(이후 24시간 캐시). 실측에서
    이 비용은 첫 /simulate 를 12.4s(정상 6.3s)로 만들 만큼 컸다. **실제 서사에
    쓰는 스키마와 동일한 객체**를 태워야 캐시가 맞는다 — 더 작은 스키마로
    대신 태우면 컴파일 비용이 첫 사용자에게 그대로 남는다.
    """
    if not settings.anthropic_api_key:
        return False
    try:
        asyncio.run(_awarm_schemas(model or settings.claude_model))
        return True
    except Exception as exc:  # 워밍업 실패는 치명적이지 않다 — 지연 로딩으로 폴백
        log.warning("서사 스키마 워밍업 실패(무시): %s", exc)
        return False


# ── 하위호환: 단일 선택 내러티브(기존 시그니처 유지) ──
def generate_narrative(
    req: PredictRequest,
    expected_wage: float,
    causal_effect: float,
    survival_months: float,
    persona_block: str | None = None,
) -> str:
    """단일 선택 서사. persona_block은 수치가 아닌 서술 순서와 톤에만 반영한다."""
    if not settings.anthropic_api_key:
        return "(ANTHROPIC_API_KEY 미설정 — 내러티브 생략)"
    prompt = (
        f"한 사용자가 '{req.choice}'라는 진로를 택한 평행우주를 상상합니다.\n"
        # 전공은 사용자가 실제로 고른 경우에만 넣는다. 없는데 넣으면 모델이 그걸
        # 사실로 받아 "○○ 배경은 …" 같은 문장을 만든다.
        + (f"- 전공: {req.major}\n" if req.major else "")
        + f"- 나이: {req.age}\n"
        f"- 예상 월급: {expected_wage:,.0f}만원\n"
        f"- 그 선택의 인과효과: {causal_effect:,.0f}\n"
        f"- 예상 재직기간: {survival_months:.1f}개월\n\n"
        "이 데이터를 따뜻하면서도 현실적인 2~3문장으로, 숫자를 지어내지 말고 풀어 설명해줘."
    )
    if persona_block:
        prompt += (
            f"\n\n{persona_block}\n"
            "위 성향 재료의 지표 강조 순서, 리스크 프레임, 전달 스타일을 서사에 반영하되 "
            "예측 수치는 바꾸거나 불리한 내용은 숨기지 마라."
        )
    resp = _get_client().messages.create(
        model=settings.claude_model,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text
