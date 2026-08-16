# -*- coding: utf-8 -*-
"""disposition_llm.py — 구조화 LLM 성향 추출 (사전 지표 대체/보강).

왜 이걸 만드나
    metrics.py 사전 지표는 자연어 블로그체에서 대처·성향을 못 잡는다(회피형이 -0.02로
    뭉개짐 — dataset/build.py 실측). LLM은 이걸 잘 읽는다. 다만 '자유서술 성향'은
    검증 불가라 차별점을 해친다. 그래서 **구조화 출력**만 받는다:
      · 대처 방향(approach/avoidant/mixed) + confidence + 근거인용
      · 5축(경제·관계·성장·자기실현·안정) 각각의 '중심성' lean + confidence
      · 전달 스타일 플래그
    수치가 아니라 '구조'를 강제 → 감사·검증 가능, "AI가 지어낸 성향" 방지.

설계 원칙 (PREDICTION_HANDOFF · 성향기반_인수인계 준수)
    · 주간 배치. 매 답변이 아니라 그 주(또는 한 달) 답변을 통째로 1회 읽힌다(비용·프라이버시).
    · 감정모델·안전게이트는 이 밖의 결정적 코드가 담당. LLM은 성향 '재료'만.
    · 온보딩 가치순위(prior) + LLM 추출(evidence) → confidence·데이터량으로 블렌딩.
      = 인수인계 §4의 미구현 '갱신'을 실제 계산으로. (데이터 적으면 prior 우세.)
    · 예측 모델(KNN/EconML) 피처엔 절대 안 들어감. 서사·톤에만.

키 없으면 (None, 사유) 반환 — 오프라인에서도 import·구조는 검증 가능.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DIARY = HERE.parent
ROOT = DIARY.parent
for p in (str(DIARY), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

AXES = ["경제", "관계", "성장", "자기실현", "안정"]
AXIS_DESC = {
    "경제": "돈·재정 안정·물질적 여유·소득에 대한 관심과 불안",
    "관계": "가족·친구·소속·사람과의 유대",
    "성장": "배움·실력 향상·성취·커리어 발전",
    "자기실현": "자율·의미·나다움·스스로 결정하는 삶",
    "안정": "건강·삶의 안정·예측가능성·리스크 회피",
}

SYSTEM = (
    "너는 질문형 일기 답변을 읽고 사용자의 성향을 '구조화된 근거'로 추출하는 분석기다. "
    "자유서술 감상문이 아니라 아래 JSON 스키마에 정확히 맞는 데이터만 출력한다. "
    "모든 판단에는 답변에서 실제로 인용한 근거를 붙인다. 근거가 약하면 confidence를 낮춘다. "
    "진단 라벨(우울장애 등)·치료 판단은 하지 않는다. 오직 성향 '재료'만."
)

SCHEMA_HINT = """반드시 이 JSON 형식으로만 답하라(주석·설명·코드펜스 금지):
{
  "coping": {
    "direction": "approach | avoidant | mixed",
    "confidence": 0.0~1.0,
    "evidence": ["답변에서 실제 인용 1~3개"]
  },
  "value_axes": {
    "경제":   {"lean": 0.0~1.0, "confidence": 0.0~1.0},
    "관계":   {"lean": 0.0~1.0, "confidence": 0.0~1.0},
    "성장":   {"lean": 0.0~1.0, "confidence": 0.0~1.0},
    "자기실현": {"lean": 0.0~1.0, "confidence": 0.0~1.0},
    "안정":   {"lean": 0.0~1.0, "confidence": 0.0~1.0}
  },
  "delivery_flags": ["회피경향|행동지향|분석·성찰형|감정우선|정서부하 높음|흑백사고|자기초점 강함 중 해당되는 것"],
  "job_change": {
    "risk_tolerance": 0.0~1.0,
    "decision_style": "intuitive | analytic | mixed",
    "protect_most": "이직 같은 갈림길에서 이 사람이 '가장 지키려는 것' 한 마디",
    "confidence": 0.0~1.0
  },
  "summary": "한 줄 요약(단정 말고 경향)"
}

job_change.risk_tolerance = 이직 같은 '변화'를 감수하는 성향(0=지금을 지키려 함/떠남을 꺼림,
  1=새 도전에 뛰어드는 편). decision_style = 결정을 직관으로 하나 분석으로 하나.
lean = 그 축을 이 사람이 얼마나 '중요하게 여기는가'(0=별로, 1=매우).
  ⚠ 화제 빈도 ≠ 가치. 일기에 자주 나오는 소재(예: 공부 얘기가 압도적으로 많다)를
    그 축(성장)이 중요하다는 뜻으로 착각하지 말 것. '무엇을 지키려 하고, 무엇을 위해
    다른 걸 포기·감수하는가'로 판단하라. 예: 시험공부에 매달려도 그건 '안정(합격)'을
    위한 수단일 수 있고 '성장' 자체를 중시하는 게 아닐 수 있다. 수단과 가치를 구분하라.
  근거가 약하거나 애매하면 confidence를 낮춰라(억지로 높이지 말 것)."""


def build_extract_prompt(sessions, *, span_label=""):
    """세션들 → LLM 추출용 프롬프트. 질문 라벨을 함께 준다(무엇에 대한 답인지 문맥)."""
    from qmode.scheduler import Scheduler
    sch = Scheduler()
    lines = [f"[질문형 일기 {span_label} — 답변에서 성향을 구조화 추출하라.]", ""]
    lines.append("축 정의:")
    for a in AXES:
        lines.append(f"  · {a}: {AXIS_DESC[a]}")
    lines.append("")
    lines.append("일기 (질문 → 답변):")
    for s in sessions:
        d = s.get("date", "")
        for it in s.get("items", []):
            if it.get("skipped"):
                continue
            q = sch.by_id.get(it.get("question_id"), {})
            qt = q.get("text") or it.get("question_id")
            lines.append(f"  [{d}] Q: {qt}")
            lines.append(f"        A: {it.get('answer','')}")
        if s.get("free") and s["free"].get("answer"):
            lines.append(f"  [{d}] (자유칸) {s['free']['answer']}")
    lines += ["", SCHEMA_HINT]
    return "\n".join(lines)


def _validate(obj):
    """구조 검증 — 스키마 어긋나면 ValueError."""
    if not isinstance(obj, dict):
        raise ValueError("최상위가 dict 아님")
    c = obj.get("coping", {})
    if c.get("direction") not in ("approach", "avoidant", "mixed"):
        raise ValueError(f"coping.direction 이상: {c.get('direction')}")
    va = obj.get("value_axes", {})
    for a in AXES:
        if a not in va or "lean" not in va[a]:
            raise ValueError(f"value_axes.{a} 누락")
    return obj


def extract(sessions, *, model=None, span_label="", max_tokens=1200):
    """세션들 → 구조화 성향 dict. (실패 시 (None, 사유))."""
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
    model = model or "claude-sonnet-5"
    prompt = build_extract_prompt(sessions, span_label=span_label)
    import time
    client = Anthropic()
    last = None
    for attempt in range(3):          # 전이적 오류(529 과부하·5xx·rate)엔 재시도
        try:
            resp = client.messages.create(
                model=model, max_tokens=max_tokens, system=SYSTEM,
                thinking={"type": "disabled"},
                messages=[{"role": "user", "content": prompt}],
            )
            txt = "".join(b.text for b in resp.content if b.type == "text").strip()
            if txt.startswith("```"):          # 코드펜스 방어
                txt = txt.strip("`")
                txt = txt[txt.find("{"):txt.rfind("}") + 1]
            return _validate(json.loads(txt)), None
        except Exception as e:      # noqa: BLE001
            last = e
            msg = str(e).lower()
            transient = any(s in msg for s in ("529", "overload", "rate", "500", "502", "503", "timeout"))
            if transient and attempt < 2:
                time.sleep(1.5 * (attempt + 1))     # 1.5s, 3s 백오프
                continue
            return None, f"추출 오류: {e}"
    return None, f"추출 오류: {last}"


# ── 온보딩(prior) + LLM(evidence) 블렌딩 = '갱신'의 실제 계산 ──────────
def _normalize(d):
    tot = sum(d.values()) or 1.0
    return {k: v / tot for k, v in d.items()}


def blend_weights(onboarding_weights, llm_extract, *, n_answers, alpha_cap=0.3):
    """온보딩 가중치(prior) + LLM lean(evidence) → 갱신 가중치(posterior).

    가치관은 온보딩 강제순위가 '주(主)'다 — 사회적 바람직성·화제빈도 편향을 막아주는
    검증된 신호. 일기는 '보정'으로만 살짝(α 상한 0.3) 얹는다. 이렇게 하지 않으면
    공부 얘기가 압도적인 일기가 '성장'을 1순위로 뒤집는 오독이 발생(P1 실측).

    · 대처·전달 스타일은 LLM이 담당(delivery_from_llm) — 여긴 가치 축 전용.
    · α = 데이터량 × 평균 confidence, 상한 alpha_cap. 데이터 적으면 온보딩 그대로.
    """
    prior = _normalize(dict(onboarding_weights))
    if not llm_extract:
        return {"weights": prior, "alpha": 0.0,
                "note": "LLM 추출 없음 — 온보딩 그대로"}
    va = llm_extract.get("value_axes", {})
    leans = {a: float(va.get(a, {}).get("lean", 0.0)) for a in AXES}
    confs = [float(va.get(a, {}).get("confidence", 0.0)) for a in AXES]
    mean_conf = sum(confs) / len(confs) if confs else 0.0
    evidence = _normalize({a: max(leans[a], 1e-6) for a in AXES})

    data_factor = min(1.0, n_answers / 60.0)          # ~한 달(≈60답변)이면 최대
    alpha = min(alpha_cap, data_factor * mean_conf)   # 가치는 온보딩이 주 — 상한 낮게
    post = {a: prior[a] * (1 - alpha) + evidence[a] * alpha for a in AXES}
    return {"weights": _normalize(post), "alpha": round(alpha, 3),
            "prior": prior, "evidence": evidence, "mean_conf": round(mean_conf, 3),
            "note": f"α={alpha:.2f} (가치는 온보딩 주도 · 일기 보정 상한 {alpha_cap})"}


# 재료 블록 조립(build_jobchange_material)·delivery_from_llm 은 disposition.py 로 이동.
# 이 모듈은 '추출 엔진'만 담당한다(extract/blend). value_ranking 중복 제거.


if __name__ == "__main__":
    # 오프라인 검증 — 프롬프트 조립 + 블렌딩 로직(가짜 추출로).
    fake = {
        "coping": {"direction": "avoidant", "confidence": 0.8, "evidence": ["걍 넘김", "유기"]},
        "value_axes": {"경제": {"lean": .3, "confidence": .5}, "관계": {"lean": .7, "confidence": .7},
                       "성장": {"lean": .3, "confidence": .5}, "자기실현": {"lean": .2, "confidence": .4},
                       "안정": {"lean": .9, "confidence": .8}},
        "delivery_flags": ["회피경향", "자기초점 강함"], "summary": "안정·관계 중심, 회피 경향",
    }
    prior = {"경제": 0.13, "관계": 0.28, "성장": 0.13, "자기실현": 0.13, "안정": 0.34}
    print("=== 블렌딩(갱신) 검증 ===")
    for n in (5, 20, 60):
        b = blend_weights(prior, fake, n_answers=n)
        w = ", ".join(f"{k} {v:.2f}" for k, v in b["weights"].items())
        print(f"  n={n:3d}: {b['note']}\n         → {w}")
    # 재료 조립은 disposition 로 이동 — 데모도 거기서 불러 쓴다.
    from qmode import disposition
    print("\n전달 스타일:", disposition.delivery_from_llm(fake))
    print("\n=== 이직 재료 블록 ===")
    print(disposition.build_jobchange_material(
        blend_weights(prior, fake, n_answers=60)["weights"], fake))
