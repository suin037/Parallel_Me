"""접속 폭주 가드 — 예산이 새는 걸 앱 층에서 한 번 더 막는다.

방어선이 셋이고, 이건 그중 마지막(사용자에게 곱게 말하는 층)이다.

    1) Anthropic·Cloudflare 콘솔 한도   진짜 안전망. 넘으면 API 가 거부한다
    2) Railway Usage Limit              서버 비용 상한. 넘으면 서비스가 멈춘다
    3) 여기                              멈추기 전에 **안내하고 우아하게 축소**한다

1·2 는 넘는 순간 화면이 그냥 깨진다. 관람객 입장에서는 "고장난 서비스"다.
그래서 그 앞에서 미리 걸어 "지금 보고 계신 분이 많다"고 말하고,
**아까운 것부터 남기고 비싼 것부터 뺀다.** 전시에서 가장 아까운 건
아무것도 안 나오는 화면이다.

비용이 드는 외부 호출이 둘이라 따로 센다.

    narrative  Claude 서사. 넘으면 수치·그래프는 그대로 두고 서사만 뺀다
    image      Cloudflare 장면 이미지. 넘으면 결과는 그대로 두고 이미지만 뺀다

이미지 쪽 기본 한도를 서사보다 훨씬 낮게 잡은 이유: 한 번 만들 때마다
A/B 두 장이 나가고, 장당 단가가 서사보다 크다. 관람객 1명 = 이미지 2장이므로
기본값 600 은 하루 300명분이다. 전시 규모에 맞춰 환경변수로 조정할 것.

세는 단위는 '오늘'(UTC 기준 날짜)이다. 프로세스 메모리에만 두므로 재배포하면
초기화된다 — 정확한 과금 추적이 아니라 폭주 차단이 목적이라 그걸로 충분하다.
정확한 금액은 1·2 가 본다.

환경변수
    DAILY_NARRATIVE_LIMIT   하루 서사 생성 상한. 0 이면 끈다(기본 2000)
    DAILY_IMAGE_LIMIT       하루 장면 이미지 상한. 0 이면 끈다(기본 600)
"""

from __future__ import annotations

import os
import threading
from datetime import date

_LOCK = threading.Lock()

# kind -> (환경변수 이름, 기본값, /health 에 실을 설명)
_KINDS: dict[str, tuple[str, int, str]] = {
    "narrative": (
        "DAILY_NARRATIVE_LIMIT",
        2000,
        "한도를 넘으면 수치·그래프는 그대로 두고 Claude 서사만 생략한다",
    ),
    "image": (
        "DAILY_IMAGE_LIMIT",
        600,
        "한도를 넘으면 결과는 그대로 두고 장면 이미지만 생략한다(1회 생성에 2장)",
    ),
}

_state: dict[str, dict] = {k: {"day": None, "count": 0} for k in _KINDS}


def _limit(kind: str) -> int:
    env, default, _ = _KINDS[kind]
    try:
        return int(os.getenv(env, str(default)))
    except ValueError:
        return default


def _today() -> str:
    return date.today().isoformat()


def take(kind: str = "narrative") -> bool:
    """해당 종류를 한 건 쓴다. 한도 안이면 True, 넘었으면 False.

    한도가 0 이면 항상 True(가드 끔).
    """
    if kind not in _KINDS:
        raise ValueError(f"알 수 없는 가드 종류: {kind}")
    limit = _limit(kind)
    if limit <= 0:
        return True
    with _LOCK:
        st = _state[kind]
        if st["day"] != _today():
            st.update(day=_today(), count=0)
        if st["count"] >= limit:
            return False
        st["count"] += 1
        return True


def _status_one(kind: str) -> dict:
    limit = _limit(kind)
    _, _, note = _KINDS[kind]
    with _LOCK:
        st = _state[kind]
        used = st["count"] if st["day"] == _today() else 0
    return {
        "enabled": limit > 0,
        "daily_limit": limit,
        "used_today": used,
        "remaining": max(0, limit - used) if limit > 0 else None,
        "note": note,
    }


def status() -> dict:
    """/health 에 실어 보낼 현황. 남은 양을 밖에서 볼 수 있게 한다."""
    return {kind: _status_one(kind) for kind in _KINDS}


# 한도를 넘었을 때 화면에 그대로 실어 보낼 안내.
# '고장'이 아니라 '지금 사람이 많다'로 읽히게 쓴다 — 실제로 그 상황이기도 하다.
BUSY_NOTICE = {
    "busy": True,
    "title": "지금 함께 보고 계신 분이 많아요",
    "body": "두 미래의 수치와 그래프는 그대로 보실 수 있어요. "
            "다만 이야기로 풀어주는 부분은 잠시 뒤에 다시 시도해 주세요.",
}

# 이미지 쪽은 결과 화면의 배너에 사유 문자열이 그대로 붙는다.
# 그래서 기술적인 영문 대신 관람객이 읽을 문장으로 둔다.
IMAGE_BUSY_MESSAGE = (
    "지금 함께 보고 계신 분이 많아 장면 이미지는 잠시 뒤에 만들어 드릴게요"
)
