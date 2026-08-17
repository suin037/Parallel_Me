# -*- coding: utf-8 -*-
"""compare_keywords.py — 일기에서 '요즘 튄 말'을 뽑는다. LLM 없음.

## 왜 필요한가

시뮬 입력 화면의 추천 문구는 `frontend/src/data/choices.js` 의 고정 사전이 전부다
(영역 9개 × 문장 몇 개). 그래서 일기에 "팀장" 이 스무 번 나와도 칩에는
"새로운 회사나 역할로 옮기기" 라는 총칭 문장만 뜬다. `diarySignals.js` 의 LEX 도
같은 한계다 — **사전에 없는 말은 아무리 반복돼도 못 잡는다.**

## 무엇을 하나

Kiwi 형태소 분석으로 **사용자가 실제로 쓴 명사**를 뽑고, 최근 창에서 평소보다
튄 것만 남긴다. `interests.py` 가 취향 답변에 하던 것과 같은 방식이고, Kiwi
인스턴스도 그쪽 것을 그대로 쓴다(두 개 띄우면 상주 메모리만 두 배다).

빈도순이 아니라 **평소 대비 상승폭(lift)** 으로 고르는 이유: 그냥 세면 "회사·
생각·오늘" 처럼 그 사람이 늘 쓰는 말이 위로 온다. 늘 쓰는 말은 지금 무엇을
비교할지 알려주지 않는다. 알고 싶은 건 *평소와 달라진 것* 이다.

## 정직선

  · 예측 숫자(KLIPS 생존분석·인과효과)를 건드리지 않는다. 무엇을 비교할지
    **제안**하는 데만 쓴다 — diarySignals.js 상단과 같은 규칙이다.
  · LLM 을 부르지 않는다. 추출이지 생성이 아니다. 그래서 지연 0, 비용 0,
    결과가 결정적이라 회귀 테스트가 가능하다.
  · Kiwi 가 없거나 기록이 적으면 **빈 목록**을 돌려준다. 호출부(프론트)는 그때
    기존 고정 사전을 그대로 쓴다 — 폴백이 아니라 기본값이다.

standalone:
    python diary_module/qmode/compare_keywords.py
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
DIARY = HERE.parent
for _p in (str(DIARY), str(DIARY.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# 일기 본문에 흔해서 뽑아봐야 아무것도 알려주지 않는 명사.
#
# interests.py 의 _STOP 을 재사용하지 않고 따로 둔다 — 그쪽은 취향 답변(영화·책
# 제목)이 대상이라 "과하게 지우면 고유명사까지 날아간다"는 이유로 최소한만 담았다.
# 여기는 일기 본문 전체가 대상이라 걸러낼 게 훨씬 많다. 목적이 다르면 사전도 다르다.
_STOP = {
    # 시간
    "오늘", "어제", "내일", "요즘", "최근", "지금", "아침", "저녁", "점심", "밤",
    "하루", "이번", "다음", "주말", "평일", "새벽", "오전", "오후", "시간", "동안",
    # 사고·감정 일반어 (감정 키워드는 checkin.keyword 로 따로 있다)
    "생각", "기분", "느낌", "마음", "감정", "정도", "부분", "상황", "이야기", "얘기",
    "이유", "문제", "때문", "정리", "고민", "결정", "선택", "필요", "노력", "준비",
    # 사람·장소 총칭
    "사람", "우리", "자신", "본인", "여기", "거기", "저기", "쪽", "곳", "집안",
    # 의존명사·군더더기
    "때", "거", "것", "수", "게", "말", "일", "중", "안", "더", "좀", "잘", "그냥",
    "정말", "진짜", "조금", "약간", "역시", "다시", "계속", "아직", "이제", "번",
    "적", "만큼", "뿐", "듯", "채", "김", "덕분", "탓", "면", "지",
}

# 날짜 형식이 어긋난 기록은 창 계산에서 조용히 빠지느니 아예 버린다.
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# 스무딩 상수. 기록이 적을 때 lift 가 발산하는 걸 막는다.
# (창에 1일, 평소 0일이면 스무딩 없이는 lift 가 무한대가 된다)
_ALPHA = 0.08

_kiwi = None


def _kiwi_instance():
    """Kiwi 싱글턴. 이미 떠 있는 interests.py 것을 먼저 찾는다.

    Kiwi 는 기동 시 언어모델을 메모리에 올린다. api.py 가 interests 를 이미
    import 하므로(qmode/api.py) 그 인스턴스를 재사용하면 추가 비용이 0 이다.
    standalone 실행처럼 그쪽이 없을 때만 직접 만든다.
    """
    global _kiwi
    if _kiwi is None:
        try:
            from qmode.interests import _get_kiwi
            _kiwi = _get_kiwi()
        except Exception:                      # noqa: BLE001 - 단독 실행 경로
            from kiwipiepy import Kiwi
            _kiwi = Kiwi()
    return _kiwi


def _nouns(kiwi, text: str) -> set[str]:
    """한 기록 → 살아있는 명사 집합.

    같은 기록 안에서 몇 번 나왔는지는 세지 않는다(집합). 하루에 스무 번 쓴 말과
    스무 날에 걸쳐 한 번씩 쓴 말은 다른 신호인데, 빈도로 세면 앞의 것이 이긴다.
    diarySignals.js 가 '며칠에 걸쳐 나타났나' 로 세는 것과 같은 규칙이다.
    """
    out: set[str] = set()
    for tok in kiwi.tokenize(text or ""):
        if tok.tag not in ("NNG", "NNP"):
            continue
        form = tok.form
        # 1글자는 노이즈가 압도적이고, 너무 길면 대개 붙여쓴 복합어라 어색하다.
        if not (2 <= len(form) <= 6) or form in _STOP:
            continue
        out.add(form)
    return out


def _clean(records) -> list[tuple[str, str]]:
    """[{date, text}] → [(date, text)]. 날짜가 없거나 본문이 빈 것은 버린다."""
    rows: list[tuple[str, str]] = []
    for rec in records or []:
        if not isinstance(rec, dict):
            continue
        day = str(rec.get("date") or "").strip()
        if not _DATE_RE.match(day):
            continue
        text = str(rec.get("text") or rec.get("note") or "").strip()
        if text:
            rows.append((day, text))
    return rows


def extract(records, window_days: int = 28, top: int = 8,
            min_days: int = 2, baseline_min_days: int = 14) -> dict:
    """일기 기록 → 최근 창에서 튄 명사 키워드.

    Args:
        records: [{"date": "YYYY-MM-DD", "text": "..."}] — 순서 무관.
        window_days: '최근'으로 볼 구간. 기본 28일(diarySignals 의 창과 맞춘다).
        top: 최대 반환 개수.
        min_days: 최근 창에서 최소 며칠에 걸쳐 나와야 후보로 보나.
            1로 두면 하루짜리 단발 사건이 전부 올라온다.
        baseline_min_days: 평소(창 이전) 기록이 이보다 적으면 lift 를 쓰지 않는다.
            비교 대상이 없는데 상승폭을 말하면 근거 없는 숫자가 된다 —
            그 경우 등장일수 순으로만 답하고 `baseline_used=False` 로 밝힌다.

    Returns:
        {"ok", "keywords": [{"word","days","base_days","lift","samples"}],
         "window_days", "n_records", "n_recent_days", "baseline_used", "method"}

        실패(kiwi 없음·기록 부족)해도 예외를 내지 않는다. `ok=False` 에
        `reason` 을 담아 돌려주고, 호출부는 고정 사전을 그대로 쓴다.
    """
    rows = _clean(records)
    meta = {"window_days": window_days, "n_records": len(rows),
            "method": "kiwi-noun+recency-lift"}
    if len(rows) < 3:
        return {"ok": False, "reason": "기록이 적어 키워드를 뽑지 않았어요.",
                "keywords": [], **meta}

    try:
        kiwi = _kiwi_instance()
    except Exception as exc:                   # noqa: BLE001 - kiwi 미설치 등
        return {"ok": False, "reason": f"형태소 분석기를 쓸 수 없어요({type(exc).__name__}).",
                "keywords": [], **meta}

    # 기준일은 서버 시계가 아니라 **기록의 최신 날짜**다. 일기는 브라우저
    # localStorage 에 있어 사용자 시간대에서 찍히는데, 서버는 UTC 일 수 있다.
    # 서버 오늘을 쓰면 시차 때문에 마지막 하루가 통째로 창 밖으로 나간다.
    latest = max(day for day, _ in rows)
    cutoff = (date.fromisoformat(latest) - timedelta(days=window_days)).isoformat()

    recent_days: dict[str, set[str]] = defaultdict(set)
    base_days: dict[str, set[str]] = defaultdict(set)
    recent_dates: set[str] = set()
    base_dates: set[str] = set()
    # 단어별 근거 기록 — 프론트가 이걸로 영역을 판정한다(정본은 choices.js 하나).
    samples: dict[str, list[tuple[str, str]]] = defaultdict(list)

    for day, text in rows:
        is_recent = day > cutoff
        (recent_dates if is_recent else base_dates).add(day)
        bucket = recent_days if is_recent else base_days
        for word in _nouns(kiwi, text):
            bucket[word].add(day)
            if is_recent and len(samples[word]) < 3:
                samples[word].append((day, text[:90]))

    n_recent = len(recent_dates) or 1
    n_base = len(base_dates)
    baseline_used = n_base >= baseline_min_days

    scored = []
    for word, days in recent_days.items():
        hit = len(days)
        if hit < min_days:
            continue
        base_hit = len(base_days.get(word, ()))
        if baseline_used:
            rate_r = hit / n_recent
            rate_b = base_hit / n_base
            lift = round((rate_r + _ALPHA) / (rate_b + _ALPHA), 2)
        else:
            lift = 1.0                          # 비교할 평소가 없다 — 등장일수로만
        scored.append({
            "word": word,
            "days": hit,
            "base_days": base_hit,
            "lift": lift,
            # 최신 근거부터. 프론트가 detectLifeDomains 로 영역을 정할 재료다.
            "samples": [t for _, t in sorted(samples[word], reverse=True)],
        })

    scored.sort(key=lambda x: (-x["lift"], -x["days"], x["word"]))
    return {"ok": True, "keywords": scored[:max(1, top)],
            "n_recent_days": len(recent_dates), "baseline_used": baseline_used, **meta}


if __name__ == "__main__":                      # pragma: no cover - 손으로 확인용
    import json

    demo = [
        {"date": "2026-05-02", "text": "주말에 운동을 좀 했다. 날씨가 좋았다."},
        {"date": "2026-05-11", "text": "운동을 꾸준히 하니 체력이 붙는 느낌이다."},
        {"date": "2026-06-03", "text": "회사에서 새 프로젝트를 맡았다. 재밌다."},
        {"date": "2026-06-19", "text": "오랜만에 친구를 만났다. 좋았다."},
        {"date": "2026-07-01", "text": "프로젝트가 잘 굴러간다. 팀이 좋다."},
        {"date": "2026-07-21", "text": "운동은 계속 하고 있다."},
        {"date": "2026-08-02", "text": "팀장이 회의에서 또 몰아붙였다. 야근까지 했다."},
        {"date": "2026-08-05", "text": "팀장 눈치 보느라 하루가 다 갔다."},
        {"date": "2026-08-09", "text": "야근이 반복된다. 팀장과 대화가 안 통한다."},
        {"date": "2026-08-14", "text": "야근하고 집에 오니 아무것도 못 하겠다."},
    ]
    print(json.dumps(extract(demo, baseline_min_days=4), ensure_ascii=False, indent=2))
