# -*- coding: utf-8 -*-
"""health_input.py — 개인 건강 자기보고 패널 (리포트 '병치' 전용, 범위 A).

왜 이걸 따로 받나 (설계 대화 §건강지표)
    rulebase._src_health 는 '또래(성별×연령대)의 유병률'만 준다(수면장애 %, 우울장애
    유병률 %, 스트레스인지율 % …). 개인 값이 아니다. 그래서 개인이 같은 축으로
    자기 상태를 입력하면, 리포트에서 "또래 4명 중 1명이 수면 문제 — 그리고 너도
    최근 수면이 나빴다"처럼 나란히(병치) 보여줄 수 있다. '나만 그런가'를
    '또래도 그렇다'로 정상화하는 효과.

범위 (사용자 결정)
    A. 리포트/서사 병치 + RAG·안전게이트 연결만. ★ 예측 모델은 건드리지 않는다.
       (소득·이직 ML 은 학습 피처가 고정 → 새 자기보고를 피처로 못 꽂음. backend 관할.)

핵심 원칙
    · 각 항목은 rulebase 지표명과 1:1(baseline_indicator)로 맞춘다 → 병치가 공짜.
    · backend 는 수정하지 않는다. pair_with_baseline() 이 PredictResponse.life_indicators
      (이미 돌려주는 값)를 받아 개인값과 짝지을 뿐이다.
    · 우울·불안은 '적당한 수준'만 — 단문 빈도 1개씩, 진단 라벨 금지. 높으면 crisis/
      safety 게이트로 라우팅하고 병치보다 지지 메시지를 우선한다.

standalone:
    python diary_module/qmode/health_input.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# rag.safety 는 순수 파이썬(모델 불필요). 없으면 게이트를 건너뛴다.
_BACKEND = Path(__file__).resolve().parent.parent.parent / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))
try:
    from rag import safety
    HAS_SAFETY = True
except ImportError:                                         # pragma: no cover
    HAS_SAFETY = False


# ── 패널 정의 ────────────────────────────────────────────────────────
# scale 종류
#   good5 : 1~5, 높을수록 좋음 (낮으면 우려)
#   bad5  : 1~5, 높을수록 나쁨 (높으면 우려)
#   freq4 : 0~3 (전혀없음/며칠/절반이상/거의매일), 높으면 우려 — 임상 민감
#   days8 : 0~7 (지난 한 주), 참고 지표
PANEL = [
    {"id": "sleep", "dim": "신체건강", "scale": "good5",
     "label": "최근 2주, 밤잠은 어땠나요?",
     "baseline_indicator": "수면장애", "clinical": False, "youth_only": False},
    {"id": "subjective_health", "dim": "신체건강", "scale": "good5",
     "label": "요즘 몸 컨디션은 어떤가요?",
     "baseline_indicator": None, "clinical": False, "youth_only": False},
    {"id": "exercise_days", "dim": "신체건강", "scale": "days8",
     "label": "지난 한 주, 몸을 움직인(운동·산책 등) 날은 며칠인가요?",
     "baseline_indicator": None, "clinical": False, "youth_only": False},
    {"id": "stress", "dim": "정신건강", "scale": "bad5",
     "label": "요즘 스트레스를 얼마나 느끼나요?",
     "baseline_indicator": "스트레스인지율", "clinical": False, "youth_only": False},
    # ── 임상 민감(우울·불안) — 단문 빈도 1개씩. 진단 아님, 선 넘지 않게. ──
    {"id": "low_mood", "dim": "정신건강", "scale": "freq4",
     "label": "최근 2주, 기분이 가라앉거나 무기력했던 날은 며칠쯤이었나요?",
     "baseline_indicator": "우울장애유병률", "clinical": True, "youth_only": False},
    {"id": "anxious", "dim": "정신건강", "scale": "freq4",
     "label": "최근 2주, 불안하거나 초조했던 날은 며칠쯤이었나요?",
     "baseline_indicator": "불안감유병", "clinical": True, "youth_only": False},
    # ── 청년(≤34) 전용 — rulebase _src_youth 와 축 일치 ──
    {"id": "burnout", "dim": "삶의질", "scale": "bad5",
     "label": "요즘 번아웃(소진)된 느낌이 있나요?",
     "baseline_indicator": "번아웃 경험률", "clinical": False, "youth_only": True},
    {"id": "loneliness", "dim": "삶의질", "scale": "bad5",
     "label": "요즘 외로움을 느끼나요?",
     "baseline_indicator": "외로움 경험률", "clinical": False, "youth_only": True},
]
_BY_ID = {p["id"]: p for p in PANEL}

# scale → (허용범위, 우려 방향, 수준 라벨)
#   concern_dir: 'low' = 값이 낮을수록 우려, 'high' = 높을수록 우려
_SCALE = {
    "good5": {"min": 1, "max": 5, "concern_dir": "low",
              "words": {1: "매우 나쁨", 2: "나쁨", 3: "보통", 4: "좋음", 5: "매우 좋음"}},
    "bad5":  {"min": 1, "max": 5, "concern_dir": "high",
              "words": {1: "거의 없음", 2: "약간", 3: "보통", 4: "심함", 5: "매우 심함"}},
    "freq4": {"min": 0, "max": 3, "concern_dir": "high",
              "words": {0: "전혀 없음", 1: "며칠", 2: "절반 이상", 3: "거의 매일"}},
    "days8": {"min": 0, "max": 7, "concern_dir": "low",
              "words": {}},   # 숫자 그대로
}


def _clamp(scale, v):
    s = _SCALE[scale]
    try:
        v = int(round(float(v)))
    except (TypeError, ValueError):
        return None
    return max(s["min"], min(s["max"], v))


def _level_word(scale, v):
    w = _SCALE[scale]["words"]
    return w.get(v, f"{v}일" if scale == "days8" else str(v))


def _is_concern(scale, v):
    """이 값이 '우려' 쪽인가 (병치·서사에서 강조할지 판단)."""
    s = _SCALE[scale]
    if s["concern_dir"] == "low":
        return v <= s["min"] + 1          # good5 → 1~2, days8 → 0~1
    return v >= s["max"] - 1              # bad5 → 4~5, freq4 → 2~3


def process_health(inputs, *, is_youth=True, note=""):
    """자기보고 dict → 구조화 패널 결과.

    inputs : {"sleep": 2, "stress": 4, "low_mood": 3, ...}  (부분 입력 허용)
    is_youth : 청년(≤34) 여부. False 면 youth_only 항목은 무시.
    note   : 자유 덧붙임(선택) — crisis 재확인용.

    반환:
      {
        "items": [{id,label,dim,value,level,concern,clinical,baseline_indicator}, ...],
        "clinical_elevated": [...],        # 우울·불안이 '거의 매일' 수준
        "safety": {"level","recommended","message"},
        "prompt_block": "...",             # 서사 프롬프트용(또래 병치 지시 포함)
      }
    """
    items = []
    clinical_elevated = []
    for pid, raw in (inputs or {}).items():
        p = _BY_ID.get(pid)
        if not p:
            continue
        if p["youth_only"] and not is_youth:
            continue
        v = _clamp(p["scale"], raw)
        if v is None:
            continue
        concern = _is_concern(p["scale"], v)
        it = {
            "id": pid, "label": p["label"], "dim": p["dim"],
            "value": v, "level": _level_word(p["scale"], v),
            "concern": concern, "clinical": p["clinical"],
            "baseline_indicator": p["baseline_indicator"],
        }
        items.append(it)
        # 임상 항목이 최고 빈도(거의 매일)면 격상
        if p["clinical"] and v >= _SCALE[p["scale"]]["max"]:
            clinical_elevated.append(pid)

    # ── 안전 게이트 ── 임상 격상 or note 위기어 → 지지 메시지 우선.
    s_level, recommended, message = "normal", False, None
    if HAS_SAFETY:
        lv, _ = safety.assess_safety(text=note or "")
        if lv == "crisis":
            s_level, recommended = "crisis", True
            message = safety.crisis_message()
    if clinical_elevated and s_level != "crisis":
        s_level, recommended = "high_distress", True
        message = ("최근 자주 힘든 날이 이어진 것 같아요. 혼자 견디지 않으셔도 됩니다. "
                   "필요하면 정신건강 위기상담 1577-0199 에서 이야기 나눌 수 있어요.")

    return {
        "items": items,
        "clinical_elevated": clinical_elevated,
        "safety": {"level": s_level, "recommended": recommended, "message": message},
        "prompt_block": _prompt_block(items, clinical_elevated),
    }


def pair_with_baseline(result, life_indicators):
    """개인 항목 ↔ 또래 통계 병치. backend 를 수정하지 않고,
    PredictResponse.life_indicators(이미 반환되는 값)를 받아 짝짓는다.

    life_indicators : [{"indicator": "수면장애", "value": 23.1, "unit": "%",
                        "group": "여성 25-29", "source": ...}, ...]
    반환: result["items"] 각 원소에 "peers" 키를 붙인 새 리스트.
    """
    by_ind = {li.get("indicator"): li for li in (life_indicators or [])}
    paired = []
    for it in result.get("items", []):
        bi = it.get("baseline_indicator")
        peer = by_ind.get(bi) if bi else None
        paired.append({**it, "peers": (
            None if not peer else
            {"value": peer.get("value"), "unit": peer.get("unit"),
             "group": peer.get("group"), "source": peer.get("source")})})
    return paired


def _prompt_block(items, clinical_elevated):
    """서사 프롬프트에 붙일 건강 자기보고 블록(또래 병치 지시 포함).

    최종 문장이 아니라 '재료'. 진단 라벨을 쓰지 말라는 가드도 함께 넣는다.
    """
    if not items:
        return ""
    lines = [
        "[개인 건강 자기보고 — 또래 통계와 '병치'해 서술하되, 진단 라벨은 쓰지 말 것]",
        "(각 항목의 또래 유병률/평균은 life_indicators 에서 같은 indicator 로 찾아 나란히 언급.",
        " '~장애입니다' 같은 단정 금지. 빈도·정도로만 서술.)",
        "",
    ]
    for it in items:
        tag = " ⚠우려" if it["concern"] else ""
        base = f" · 또래비교지표={it['baseline_indicator']}" if it["baseline_indicator"] else ""
        lines.append(f"- [{it['dim']}] {it['label']} → {it['level']}{tag}{base}")
    if clinical_elevated:
        lines.append("")
        lines.append("⚠ 임상 민감 항목이 '거의 매일' 수준입니다. 이 항목은 또래 병치보다 "
                     "지지·연결(상담자원) 톤을 우선하고, 감정을 더 파고드는 질문은 피할 것.")
    return "\n".join(lines)


if __name__ == "__main__":
    import json

    # 예시 입력 — 수면 나쁨·스트레스 심함·우울 거의매일(격상)·번아웃
    sample = {"sleep": 2, "subjective_health": 3, "exercise_days": 1,
              "stress": 4, "low_mood": 3, "anxious": 1, "burnout": 4, "loneliness": 3}
    r = process_health(sample, is_youth=True, note="")
    print("=== 패널 결과 ===")
    print(json.dumps(r, ensure_ascii=False, indent=2))

    # 또래 통계 병치 (backend life_indicators 를 흉내낸 값)
    fake_life = [
        {"indicator": "수면장애", "value": 23.1, "unit": "%", "group": "여성 25-29",
         "source": "KNHANES"},
        {"indicator": "스트레스인지율", "value": 31.4, "unit": "%", "group": "여성 25-29",
         "source": "KNHANES"},
        {"indicator": "우울장애유병률", "value": 7.2, "unit": "%", "group": "여성 25-29",
         "source": "CHS"},
        {"indicator": "번아웃 경험률", "value": 41.0, "unit": "%", "group": "청년 25-29",
         "source": "청년삶실태"},
    ]
    print("\n=== 병치(개인 vs 또래) ===")
    for it in pair_with_baseline(r, fake_life):
        me = f"{it['level']}"
        pe = ("또래 없음" if not it["peers"]
              else f"또래 {it['peers']['value']}{it['peers']['unit']} ({it['peers']['group']})")
        print(f"  {it['id']:17s}: 나={me:8s} | {pe}")

    print("\n=== 안전 ===")
    print(f"  level={r['safety']['level']} recommended={r['safety']['recommended']}")
    if r["safety"]["message"]:
        print(f"  message: {r['safety']['message']}")

    print("\n=== 위기 note 라우팅 검증 ===")
    r2 = process_health({"sleep": 3}, note="다 끝내고 싶다")
    print(f"  crisis note → level={r2['safety']['level']}, "
          f"recommended={r2['safety']['recommended']}")
