# -*- coding: utf-8 -*-
"""domain_tag.py — 일기/기록을 인생 영역(행성)으로 자동 분류.

왜 별도 ML 모델이 아니라 LLM인가
    영역 분류는 학습 데이터·검증 부담이 큰 반면, 파이프라인엔 이미 Claude API가 있다.
    LLM에 짧은 분류 프롬프트 1회 → 다중 라벨 도메인. 학습 0, 유지비 0.
    키 없거나 실패하면 키워드 휴리스틱으로 폴백(오프라인에서도 동작).

도메인(행성) — 앱 PLANETS key와 1:1(result.js). 필요시 여기만 고치면 전 파이프라인 반영.
    relation(관계) / career(진로·일·돈) / health(건강) / growth(성장) / life(삶의 만족·일상)
    · 다중 라벨 허용(한 일기가 relation+health일 수 있다).
    · primary = 대표 1개(행성 렌즈 기본 귀속). 프론트는 checkin.domains 로 필터.

쓰임: 일기 저장 시 tag() 호출 → 체크인에 domains 저장 → 행성 렌즈가 필터.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
DIARY = HERE.parent
ROOT = DIARY.parent
for p in (str(DIARY), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

DOMAINS = ["relation", "career", "health", "growth", "life"]  # PLANETS key와 일치
_LABEL = {"relation": "관계", "career": "진로·일·돈", "health": "건강",
          "growth": "성장", "life": "삶의 만족·일상"}

# 폴백용 키워드(대략). LLM 없을 때만 쓰는 러프한 신호.
_KW = {
    "relation": ["친구", "연인", "남친", "여친", "여자친구", "남자친구", "가족", "엄마", "아빠",
                 "부모", "동료", "상사", "관계", "싸웠", "싸움", "다퉜", "연락", "데이트", "이별",
                 "헤어", "사랑", "서운", "질투", "카톡", "만났"],
    "career": ["돈", "월급", "연봉", "이직", "취업", "면접", "투자", "주식", "코인", "저축",
               "빚", "대출", "생활비", "월세", "지출", "진로", "일자리", "직장", "부업", "커리어"],
    "health": ["잠", "수면", "운동", "아프", "아팠", "피곤", "지침", "병원", "건강", "다이어트",
               "컨디션", "스트레스", "불안", "우울", "무기력", "두통", "체력", "걸음"],
    "growth": ["공부", "시험", "자격증", "배웠", "배움", "성장", "프로젝트", "실력",
               "목표", "합격", "강의", "독서", "스터디", "자기계발"],
}

_SYSTEM = (
    "너는 짧은 일기/기록을 읽고 어떤 인생 영역에 관한 내용인지 분류하는 태거다. "
    "아래 도메인 중 해당되는 것만 고른다(다중 가능). 진단·평가는 하지 않는다. "
    "JSON만 출력한다."
)


def _schema():
    defs = " / ".join(f"{k}={_LABEL[k]}" for k in DOMAINS)
    return ('반드시 이 JSON만 출력(도메인은 영문 key로):\n{"primary":"' + "|".join(DOMAINS) +
            '","domains":["해당 key 1~3개"]}\n도메인 정의: ' + defs +
            ". career=진로·돈·일자리, health=몸·수면·정신건강·운동, life=그 외 소소한 하루.")


def _keyword_tag(text):
    t = str(text or "")
    hits = []
    for dom, kws in _KW.items():
        if any(k in t for k in kws):
            hits.append(dom)
    if not hits:
        hits = ["life"]
    return {"primary": hits[0], "domains": hits, "method": "keyword"}


def tag(text, *, model=None, max_tokens=120):
    """일기 텍스트 → {"primary","domains","method"}. 키 없으면 키워드 폴백."""
    if not (text or "").strip():
        return {"primary": "life", "domains": ["life"], "method": "empty"}
    try:
        import report_one as R1
        R1._load_dotenv()
    except Exception:
        pass
    if not os.getenv("ANTHROPIC_API_KEY"):
        return _keyword_tag(text)
    try:
        from anthropic import Anthropic
    except ImportError:
        return _keyword_tag(text)
    prompt = "[일기]\n" + str(text)[:1500] + "\n\n" + _schema()
    client = Anthropic()
    model = model or "claude-sonnet-5"
    for attempt in range(2):
        try:
            resp = client.messages.create(
                model=model, max_tokens=max_tokens, system=_SYSTEM,
                thinking={"type": "disabled"},
                messages=[{"role": "user", "content": prompt}],
            )
            txt = "".join(b.text for b in resp.content if b.type == "text").strip()
            if txt.startswith("```"):
                txt = txt.strip("`"); txt = txt[txt.find("{"):txt.rfind("}") + 1]
            obj = json.loads(txt)
            doms = [d for d in obj.get("domains", []) if d in DOMAINS] or ["일상"]
            prim = obj.get("primary") if obj.get("primary") in DOMAINS else doms[0]
            return {"primary": prim, "domains": doms, "method": "llm"}
        except Exception as e:      # noqa: BLE001
            if attempt == 0 and any(s in str(e).lower() for s in ("529", "overload", "rate", "500", "timeout")):
                time.sleep(1.5); continue
            return _keyword_tag(text)   # 실패 시에도 결과는 준다
    return _keyword_tag(text)


if __name__ == "__main__":
    samples = [
        "남친이랑 연락 문제로 또 싸웠다. 그래서 잠도 잘 못 잤다.",
        "이직 면접 결과를 기다리는 중. 돈 생각에 불안하다.",
        "오늘은 그냥 산책하고 커피 마셨다.",
        "자격증 시험 공부를 3시간 했다. 실력이 느는 느낌.",
    ]
    for s in samples:
        r = tag(s)
        print(f"[{r['method']:7s}] primary={r['primary']:4s} domains={r['domains']}  ::  {s[:32]}")
