"""자유입력 선택지 분류의 **낮은 확신도 구간만** LLM으로 보완한다.

## 왜 전부 LLM으로 하지 않나

`choice_classifier.classify()` 의 확신도는 정답 여부와 거의 완벽하게 갈린다.
실측 22문장에서 확신도 0.4 이상은 13개 전부 정답이었고, 틀린 4개는 전부 0.00 이었다.
즉 키워드가 확신할 때는 이미 옳으므로, 그 구간을 LLM 에 다시 물으면 정확도는
그대로인 채 **모든 비교에 1초와 호출 비용**만 얹힌다.

낮은 확신도 구간만 넘기면 세 가지가 동시에 지켜진다.
  · 지연  — 대다수 비교는 예전처럼 0ms 로 끝난다
  · 가용성 — API 가 죽어도 키워드 결과가 그대로 답이 된다(폴백이 아니라 기본값)
  · 테스트 — 확신하는 구간은 결정적이라 회귀 테스트가 계속 유효하다

## 호출 지점

`/choices/classify-pair` 는 프론트가 비교 버튼을 누를 때 이미 한 번 부르는
엔드포인트다. 여기 얹으면 사용자가 기다리는 왕복이 늘지 않는다. A와 B를 한
요청에 같이 물어 호출은 비교당 최대 1회다.
"""

from __future__ import annotations

import json
import logging

from config import settings

log = logging.getLogger(__name__)

# 분류 가능한 유형. main.CHOICE_TAXONOMY 의 키 + '기타'.
# 여기 없는 값이 오면 쓰지 않는다 — 모르는 유형이 모델 라우팅에 흘러들면
# 없는 artifact 를 찾다가 조용히 빈 결과가 된다.
KINDS = ["이직", "유지", "진학", "창업", "휴식", "결혼", "주택", "이사", "기타"]

# domain_router.DOMAIN_LABELS 와 같은 9개.
DOMAINS = ["career", "education", "business", "finance", "health",
           "housing", "relationship", "lifestyle", "long_term_values"]

_SIDE = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": KINDS},
        "domain": {"type": "string", "enum": DOMAINS},
    },
    "required": ["kind", "domain"],
    "additionalProperties": False,
}
_SCHEMA = {
    "type": "object",
    "properties": {"A": _SIDE, "B": _SIDE},
    "required": ["A", "B"],
    "additionalProperties": False,
}

# 기본값은 '기타'다. 유형 8개는 각각 학습된 예측 모델이 붙어 있는 **특정 사건**이라,
# 문장이 그 사건을 말하지 않는데 붙이면 엉뚱한 모델이 돌아 틀린 숫자가 나온다.
# (첫 버전은 유형 목록을 먼저 보여주고 "억지로 끼워맞추지 말라"를 한 줄 덧붙였는데,
#  '빚 갚기'가 유지, '공무원 시험 준비'가 진학으로 분류돼 키워드보다 나빠졌다.
#  그래서 순서를 뒤집어 기타를 먼저 놓고, 8개 유형에 증거를 요구한다.)
_SYSTEM = f"""너는 한국어 인생 선택지를 정해진 분류 체계로 옮기는 분류기다.

**기본값은 '기타'다.** 아래 8개 유형은 각각 전용 예측 모델이 붙어 있는 특정
사건이라, 문장이 그 사건을 실제로 말할 때만 붙인다. 조금이라도 애매하면 기타다.
잘못 붙이면 엉뚱한 모델이 돌아 틀린 숫자가 사용자에게 나간다 — 기타로 두면
공통 지표로만 답하므로 훨씬 안전하다.

유형(kind):
  이직   **다른 일자리로 옮긴다**고 말할 때. 전직·재택 이직·팀 이동 요청 포함
  유지   **지금 상태를 그대로 둔다**고 말할 때. '지금처럼', '이대로', '남기'
  진학   **학위 과정**을 시작한다고 말할 때 (대학원·유학·편입)
  창업   **사업·자영·프리랜서**를 시작한다고 말할 때
  휴식   **일에서 물러난다**고 말할 때 (휴직·번아웃·갈 곳 없는 퇴사)
  결혼   혼인
  주택   집을 **사거나** 소유 형태를 바꿈
  이사   **사는 곳을 옮김**
  기타   위에 해당하지 않는 모든 것

기타로 두어야 하는 예 — 삶의 중요한 결정이지만 위 8개가 아니다:
  빚부터 갚기            → 기타 / finance
  야근 줄이고 저녁 확보    → 기타 / lifestyle
  공무원 시험 준비        → 기타 / career   (학위가 아니라 시험)
  부모님과 합가          → 기타 / relationship
  연인과 솔직하게 대화하기 → 기타 / relationship
  운동으로 건강 챙기기     → 기타 / health

영역(domain) — {", ".join(DOMAINS)} 중 하나. 유형이 '기타'여도 반드시 고른다.
유형을 못 정해도 영역은 대개 분명하니, 영역을 정확히 고르는 데 집중한다.

부정·대조는 읽어낸다: "박사 안 가고 취업" → 이직, "이직 말고 창업" → 창업.
완곡어법도 읽어낸다: "연봉 더 주는 곳으로" → 이직, "지금처럼 살기" → 유지."""


def classify_pair(text_a: str, text_b: str) -> dict | None:
    """A·B를 한 번에 분류한다. 실패하면 None — 호출부는 키워드 결과를 그대로 쓴다.

    예외를 밖으로 내보내지 않는다. 이 보완이 실패했다고 비교 자체가 막히면
    안 되기 때문이다(키워드 분류만으로도 화면은 정상 동작한다).
    """
    if not settings.anthropic_api_key:
        return None
    try:
        from utils.claude_api import _get_client

        resp = _get_client().messages.create(
            model=settings.claude_model,
            max_tokens=200,
            system=_SYSTEM,
            output_config={"format": {"type": "json_schema", "schema": _SCHEMA}},
            messages=[{"role": "user", "content":
                       f"A: {text_a}\nB: {text_b}"}],
        )
        text = resp.content[0].text if resp.content else ""
        parsed = json.loads(text)
    except Exception as exc:
        log.warning("선택 분류 LLM 보완 실패(키워드 결과 사용): %s: %s",
                    type(exc).__name__, exc)
        return None

    # 스키마가 enum 을 강제하지만 한 번 더 거른다 — 여기서 새는 값은
    # 모델 라우팅까지 흘러가므로 조용히 틀리는 것보다 안 쓰는 편이 낫다.
    out = {}
    for side in ("A", "B"):
        item = parsed.get(side) or {}
        kind, domain = item.get("kind"), item.get("domain")
        if kind in KINDS and domain in DOMAINS:
            out[side] = {"kind": kind, "domain": domain}
    return out or None
