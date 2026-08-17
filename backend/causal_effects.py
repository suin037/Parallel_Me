"""선택 유형별 인과효과(ATE) 서빙 — 소득 외 결과변수.

## 왜 이 모듈인가
`econml_*.pkl` 이 서빙하는 인과효과의 Y 는 **소득 하나뿐**이다. 만족·건강·관계 효과는
`train_outcomes.py`(KLIPS)와 `train_koweps_life.py`(KOWEPS)가 이미 추정해 JSON 으로
떨어뜨리고 있었지만, **읽는 코드가 없어서 화면까지 가지 못했다.** 이 모듈이 그 두
아티팩트를 한 인터페이스로 묶는다.

    outcome_effects.json      KLIPS 12~27차   move · startup · break (· enroll: 차단)
    koweps_life_effects.json  KOWEPS 1~20차   결혼 · 자가 · 이사

## 무엇을 내보내고 무엇을 감추는가
- **정본(baseline_controlled)만 서빙한다.** 두 아티팩트 모두 t 시점 같은 문항을 W 에
  넣은 설계가 정본이고, 통제 전 추정치는 진단용이다. 통제 전 값은 `uncontrolled_ate`
  로 같이 실어 보내되 그 자체를 수치로 쓰지 않는다 — 둘의 간격이 곧 "직전 상태를
  안 잡았을 때 새는 양" 이라, 화면이 그걸 설명할 재료로만 쓴다.
- **`significant=False` 는 지우지 않고 그대로 내보낸다.** 비유의를 감추면 화면이
  '유의한 것만 있는 세계' 를 그리게 된다. 대신 플래그를 실어 보내 막대를 그리지
  않게 한다(기획안 4장: 견줄 데 없는 숫자에 길이를 주지 않는다).
- **진학(enroll)은 수치가 나와도 서빙하지 않는다.** 전체응답 문항(생활만족·건강·관계)
  은 표본 226건으로 게이트를 통과해 추정값이 존재하지만, 차단 사유가 표본이 아니라
  **처치 정의**다 — '학력코드 상승' 이 '진학 사건' 이 아니다(근거:
  artifacts/enroll_treatment_audit.json 의 `blocked_pending_true_enrollment_event`).
  게이트를 통과했다고 열면, 막아둔 이유를 표본 수로 오해한 채 여는 셈이 된다.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path

from config import settings

log = logging.getLogger(__name__)

KLIPS_FILE = "outcome_effects.json"
KOWEPS_FILE = "koweps_life_effects.json"

# 선택 유형 → (아티팩트, 처치키). core.py 의 kind 와 같은 문자열을 쓴다.
_ROUTES: dict[str, tuple[str, str]] = {
    "이직": ("klips", "move"),
    "창업": ("klips", "startup"),
    "휴식": ("klips", "break"),
    "결혼": ("koweps", "결혼"),
    "주택": ("koweps", "자가"),
    "이사": ("koweps", "이사"),
}

# 서빙하지 않는 유형과 그 이유. 화면이 "왜 비었는지" 를 말할 수 있어야 한다.
_BLOCKED: dict[str, str] = {
    "진학": ("처치 정의가 성립하지 않아 제공하지 않음 — 학력코드 상승은 진학 사건이 "
             "아니다(입학 시점·전일제 여부·학위 구분 미관측). 표본 부족이 아니라 "
             "측정 타당성 문제이며, 근거는 artifacts/enroll_treatment_audit.json"),
}

# 관계 영역 결과변수. 두 아티팩트가 이름을 달리 쓰지 않도록 여기서 통일한다.
RELATIONSHIP_KEYS = ("가족관계만족", "친인척관계만족", "사회관계만족")

_LABELS = {
    "가족관계만족": "가족관계 만족",
    "친인척관계만족": "친인척관계 만족",
    "사회관계만족": "사회적 친분관계 만족",
    "가족만족": "가족관계 만족",
    "생활만족": "생활 만족",
    "전반만족": "전반적 만족",
    "직무만족": "일자리 만족",
    "주거만족": "주거 만족",
    "건강": "주관적 건강",
    "정신건강": "정신건강",
    "월소득_실질": "월소득",
    "가처분소득": "가구 가처분소득",
}

# KOWEPS 는 연령대 밴드가 나뉘어 있다. 청년 질문이 기본이라 좁은 밴드를 먼저 본다.
_KOWEPS_BANDS = ("20-39", "20-45")


def _load(name: str) -> dict:
    path: Path = settings.artifacts_abspath / name
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        log.warning("인과효과 아티팩트를 읽지 못함 %s: %s", name, exc)
        return {}


@lru_cache(maxsize=1)
def _artifacts() -> dict[str, dict]:
    return {"klips": _load(KLIPS_FILE), "koweps": _load(KOWEPS_FILE)}


def _normalise(key: str, rec: dict, *, source: str, meta: dict) -> dict | None:
    """아티팩트 레코드 → 서빙 스키마. 두 소스의 필드명 차이를 여기서 흡수한다."""
    if not isinstance(rec, dict) or rec.get("ate") is None:
        return None
    ci = rec.get("ci") or [None, None]
    uncontrolled = rec.get("without_baseline_control") or {}
    return {
        "key": key,
        "label": _LABELS.get(key, key),
        "ate": rec["ate"],
        "ci_low": ci[0],
        "ci_high": ci[1],
        "significant": bool(rec.get("significant")),
        # 5점 척도는 점 단위로 크기 감이 안 잡힌다 — 대조군 SD 대비로 읽어야 한다.
        "ate_sd": rec.get("ate_sd"),
        "control_mean": rec.get("control_mean"),
        # 단순 평균차. ATE 와 벌어진 폭이 곧 "평균 비교였으면 얼마나 틀렸는가".
        "naive_diff": rec.get("naive_diff"),
        "n": rec.get("n"),
        "n_treated": rec.get("n_treated"),
        "baseline_controlled": bool(rec.get("baseline_controlled")),
        "uncontrolled_ate": uncontrolled.get("ate"),
        "unit": meta.get("unit"),
        "scale": meta.get("scale"),
        "higher_is_better": meta.get("higher_is_better", True),
        "source": source,
        # 개인단위 인과추정이므로 근거강도 최상단. 비유의는 값이 아니라 플래그로 읽힌다.
        "evidence_level": "personal_model",
        "caveats": rec.get("caveats") or [],
    }


def blocked_reason(kind: str) -> str | None:
    """이 유형을 서빙하지 않는 이유. 없으면 None."""
    return _BLOCKED.get(kind)


def effects_for(kind: str, keys: tuple[str, ...] | None = None) -> list[dict]:
    """선택 유형의 인과효과 목록. 없으면 빈 리스트(억지로 채우지 않는다).

    keys 를 주면 그 결과변수만, 순서도 준 대로 돌려준다.
    """
    if kind in _BLOCKED or kind not in _ROUTES:
        return []
    source, treatment = _ROUTES[kind]
    art = _artifacts().get(source) or {}
    if not art:
        return []
    metas = art.get("outcomes") or {}

    if source == "klips":
        block = ((art.get("effects") or {}).get(treatment) or {}).get("outcomes") or {}
    else:
        bands = ((art.get("treatments") or {}).get(treatment) or {}).get("bands") or {}
        block = next((bands[b] for b in _KOWEPS_BANDS if bands.get(b)), {})

    wanted = keys if keys is not None else tuple(block)
    out = []
    for key in wanted:
        rec = _normalise(key, block.get(key, {}), source=source.upper(),
                         meta=metas.get(key) or {})
        if rec is not None:
            out.append(rec)
    return out


def relationship_effects(kind: str) -> list[dict]:
    """관계 3종만. KOWEPS 는 가족만족/사회관계만족 두 축만 존재한다."""
    keys = RELATIONSHIP_KEYS
    if _ROUTES.get(kind, ("", ""))[0] == "koweps":
        keys = ("가족만족", "사회관계만족")
    return effects_for(kind, keys)


def summary(kind: str) -> dict:
    """화면 한 덩어리. 유의/비유의를 나눠 담아 렌더가 판단하지 않게 한다."""
    reason = blocked_reason(kind)
    if reason:
        return {"available": False, "reason": reason, "effects": []}
    effects = relationship_effects(kind)
    if not effects:
        return {"available": False,
                "reason": "이 선택에는 관계 영역 인과효과 추정치가 없습니다.",
                "effects": []}
    art = _artifacts()[_ROUTES[kind][0]]
    return {
        "available": True,
        "effects": effects,
        "significant": [e for e in effects if e["significant"]],
        "indistinguishable": [e for e in effects if not e["significant"]],
        "estimator": art.get("estimator"),
        "source": art.get("source"),
        "horizon": art.get("horizon"),
        "note": ("개인단위 인과효과(직전 같은 문항을 통제한 정본). "
                 "신뢰구간이 0을 포함하면 두 선택이 이 축에서 구분되지 않는다는 뜻이며, "
                 "격차를 지어내지 않고 그대로 표시한다."),
    }
