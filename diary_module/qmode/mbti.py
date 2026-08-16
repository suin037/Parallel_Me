# -*- coding: utf-8 -*-
"""mbti.py — MBTI → 스타일 성향 prior (초기 힌트, 일기가 갱신).

왜 prior로만 쓰나
    MBTI는 재검사 신뢰도·예측력이 약하다. 그래서 '확정 성향'이 아니라 스타일 차원
    (결정방식·위험감수·전달톤)의 **온보딩 초기값**으로만 쓴다. 일기가 쌓이면 LLM 추출이
    덮어쓴다(대처=LLM > MBTI). 가치축은 MBTI로 안 건드림(가치=강제순위).

    = 가치가 '온보딩 순위(prior) → 일기(갱신)'인 것과 같은 패턴을, 스타일엔 MBTI로.

매핑(약한 근거라 부드럽게)
    T/F → 결정방식(analytic/intuitive)
    J/P → 위험감수도(J=구조·안정 선호 낮음 / P=유연·개방 높음)
    E/I → 전달 톤(외향=함께 나눔·사회적 지지 / 내향=혼자 정리할 여백)
    S/N → 프레임(S=구체·현실 / N=의미·가능성)
"""

from __future__ import annotations

_VALID = set("EISNTFJP")


def parse(mbti):
    """'INTJ' 등 → 4글자 대문자 or None."""
    if not mbti:
        return None
    s = str(mbti).strip().upper()
    if len(s) != 4 or any(c not in _VALID for c in s):
        return None
    if not (s[0] in "EI" and s[1] in "SN" and s[2] in "TF" and s[3] in "JP"):
        return None
    return s


def prior(mbti):
    """MBTI → 스타일 prior dict (파싱 실패 시 None)."""
    s = parse(mbti)
    if not s:
        return None
    ei, sn, tf, jp = s

    decision_style = "analytic" if tf == "T" else "intuitive"
    risk_tolerance = 0.4 if jp == "J" else 0.6          # 중앙 0.5에서 약하게만

    flavor = []
    flavor.append("외향형: 함께 나누고 사회적 지지를 넛지" if ei == "E"
                  else "내향형: 혼자 정리할 여백을 먼저")
    flavor.append("직관형: 의미·가능성 프레임으로" if sn == "N"
                  else "감각형: 구체·현실적 근거로")

    return {
        "mbti": s,
        "decision_style": decision_style,
        "risk_tolerance": risk_tolerance,
        "delivery_flavor": flavor,
        "source": f"mbti:{s}",
        "note": "MBTI는 초기 힌트 — 일기가 쌓이면 갱신됨(신뢰도 보정, 확정 아님)",
    }


if __name__ == "__main__":
    for m in ["INTJ", "ENFP", "ISFJ", "estp", "XXXX", "", None]:
        p = prior(m)
        if p:
            print(f"{p['mbti']}: 결정={p['decision_style']} 위험={p['risk_tolerance']} "
                  f"톤={p['delivery_flavor']}")
        else:
            print(f"{m!r}: (무효 — 무시)")
