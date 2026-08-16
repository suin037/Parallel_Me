# -*- coding: utf-8 -*-
"""scheduler.py — 질문형 일기 출제 로직.

기존 diary_module 파일은 하나도 수정하지 않는다(A/B 비교를 위해).

출제 구조
    평일   : C1, C2 + 로테이션 2 (취향 1 + 관계 1)   → 4문항
    심층일 : 위 + 심층 1                              → 5문항 (주 2회)

제약 (질문풀_설계.md §6)
    1. 최근 7일 내 출제 문항 재출제 금지
    2. 위기 '고' 문항 연속 배치 금지 · 주 1개 초과 금지
    3. 직전 7일 내 crisis 플래그 발생 → 심층 배정 중단, crisis_safe 문항으로 대체
    4. 신규 유저 첫 3일은 risk='low' 문항만
    5. R3(긍정 앵커) 주 2회 이상 강제 편성

사용:
    from qmode.scheduler import Scheduler
    sch = Scheduler()
    qs = sch.pick(date="2026-07-26", history=hist, crisis_recent=False, user_day=12)
"""

from __future__ import annotations

import json
import random
from datetime import date as _date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
POOL_PATH = HERE / "questions.json"

DEEP_WEEKDAYS = {2, 6}          # 수(2)·일(6) 심층 배정
RISK_ORDER = {"low": 0, "mid": 1, "high": 2}


def _d(s):
    if isinstance(s, _date):
        return s
    y, m, dd = (int(x) for x in str(s).split("-"))
    return _date(y, m, dd)


class Scheduler:
    def __init__(self, pool_path: Path | str = POOL_PATH, seed: int | None = None):
        self.pool = json.loads(Path(pool_path).read_text(encoding="utf-8"))
        self.fixed = self.pool["fixed"]
        self.rotation = self.pool["rotation"]
        self.by_id = {q["id"]: q for q in self.fixed + self.rotation}
        self.rng = random.Random(seed)

    # ── 조회 헬퍼 ────────────────────────────────────────────────
    def _layer(self, layer):
        return [q for q in self.rotation if q["layer"] == layer]

    @staticmethod
    def _recent_ids(history, ref, days=7):
        """history: [{"date": "2026-07-20", "question_ids": [...]}, ...]"""
        cut = _d(ref) - timedelta(days=days)
        out = set()
        for h in history:
            if cut <= _d(h["date"]) < _d(ref):
                out.update(h.get("question_ids", []))
        return out

    @staticmethod
    def _last_ids(history, ref):
        prev = [h for h in history if _d(h["date"]) < _d(ref)]
        if not prev:
            return set()
        prev.sort(key=lambda h: _d(h["date"]))
        return set(prev[-1].get("question_ids", []))

    def _high_risk_count_this_week(self, history, ref):
        cut = _d(ref) - timedelta(days=7)
        n = 0
        for h in history:
            if cut <= _d(h["date"]) < _d(ref):
                n += sum(1 for i in h.get("question_ids", [])
                         if self.by_id.get(i, {}).get("risk") == "high")
        return n

    def _r3_count_this_week(self, history, ref):
        cut = _d(ref) - timedelta(days=7)
        return sum(1 for h in history
                   if cut <= _d(h["date"]) < _d(ref)
                   and "R3" in h.get("question_ids", []))

    # ── 핵심 ────────────────────────────────────────────────────
    def pick(self, date, history=None, *, crisis_recent=False, user_day=999,
             force_deep=None):
        """하루치 문항 목록을 돌려준다.

        date          : "YYYY-MM-DD"
        history       : [{"date":..., "question_ids":[...]}, ...]
        crisis_recent : 직전 7일 내 crisis.py 플래그 발생 여부
        user_day      : 가입 후 경과일 (0=가입일). 3 미만이면 저위험 문항만.
        force_deep    : None이면 요일 기준, True/False로 강제 가능
        """
        history = history or []
        ref = _d(date)
        recent = self._recent_ids(history, ref, days=7)
        last = self._last_ids(history, ref)
        high_used = self._high_risk_count_this_week(history, ref)
        newbie = user_day < 3

        is_deep = (ref.weekday() in DEEP_WEEKDAYS) if force_deep is None else force_deep
        if newbie:
            is_deep = False          # 규칙 4 — 신규 3일은 심층 없음
        # 규칙 3 — 위기 주간엔 심층을 끄지 않고 crisis_safe(D5·BPS)로 좁힌다.
        #          King(2001)에서 BPS 글쓰기는 트라우마 글쓰기보다 덜 괴로웠으므로
        #          위기 주간에 '심층 전면 중단'은 과잉 대응이다.

        def safe_for_state(q):
            """위기·신규 상태에서 이 문항을 내도 되는가 (안전 규칙 — 절대 완화 안 함)."""
            if newbie and q["risk"] != "low":
                return False
            if crisis_recent and not q.get("crisis_safe") and q["risk"] != "low":
                return False
            if q["risk"] == "high" and (q["id"] in last or high_used >= 1):
                return False        # 규칙 2 — 연속·주1개 초과 금지
            return True

        def choose(cands):
            """완화 사다리: 안전 규칙은 고정, 다양성 규칙만 단계적으로 푼다.
            1) 7일 재출제 금지 + 안전
            2) 직전일만 회피 + 안전   (저위험 풀이 작을 때 발생)
            3) 안전만                 (마지막 수단 — 이틀 연속 같은 문항 허용)
            """
            base = [q for q in cands if safe_for_state(q)]
            for ok in ([q for q in base if q["id"] not in recent],
                       [q for q in base if q["id"] not in last],
                       base):
                if ok:
                    ok.sort(key=lambda q: RISK_ORDER[q["risk"]])
                    lo = RISK_ORDER[ok[0]["risk"]]
                    head = [q for q in ok if RISK_ORDER[q["risk"]] == lo]
                    return self.rng.choice(head)
            return None

        picked = list(self.fixed)

        # 규칙 5 — R3 주 2회 강제
        r3 = self.by_id["R3"]
        need_r3 = self._r3_count_this_week(history, ref) < 2 and "R3" not in last

        taste = choose(self._layer("taste"))
        if taste:
            picked.append(taste)

        if need_r3 and "R3" not in recent:
            picked.append(r3)
        else:
            rel = choose(self._layer("relation"))
            if rel:
                picked.append(rel)

        if is_deep:
            deep_pool = self._layer("deep")
            if crisis_recent:
                deep_pool = [q for q in deep_pool if q.get("crisis_safe")]
            deep = choose(deep_pool)
            if deep:
                picked.append(deep)

        return picked

    def onboarding(self, profile_done=False):
        """최초 로그인 시 '제일 처음' 1회 낼 가치 순위(value_ranking) = 성향 파악 게이트.
        특정 '날'이 아니라 '성향 프로파일이 아직 없을 때'로 판단한다. 드래그 정렬 UI라
        pick() 목록과 분리해 돌려준다. 이미 순위를 매겼으면(profile_done=True) None."""
        if profile_done:
            return None
        try:
            from qmode import value_ranking          # 패키지로 import 될 때
        except ImportError:                            # 스크립트 단독 실행 시
            import value_ranking
        return value_ranking.onboarding_question()

    def plan_day(self, date, history=None, *, profile_done=False, user_day=999, **kw):
        """로그인 편성 = {onboarding(프로파일 없으면 '제일 처음'), questions[]}.
        가치순위는 첫날이 아니라 '성향 프로파일이 아직 없을 때' 최초 1회 게이트로 낸다.
        일기 문항은 pick()이 7일 무중복 사다리로 로테이션한다(중복 회피)."""
        return {"onboarding": self.onboarding(profile_done),
                "questions": self.pick(date, history, user_day=user_day, **kw)}

    def explain(self, picked):
        lines = []
        for q in picked:
            ev = {"strong": "근거 강함", "partial": "부분 근거",
                  "none": "근거 없음"}.get(q.get("evidence"), "?")
            dist = " · 거리두기" if q.get("distancing") else ""
            lines.append(f"[{q['id']}] {q['layer']:8s} risk={q['risk']:4s} "
                         f"{ev}{dist}\n     {q['text']}")
        return "\n".join(lines)


if __name__ == "__main__":
    sch = Scheduler(seed=7)
    hist = []
    print("=" * 72)
    print("14일 시뮬레이션 (신규 유저, 위기 없음)")
    print("=" * 72)
    start = _date(2026, 7, 27)          # 월요일
    for i in range(14):
        d = start + timedelta(days=i)
        qs = sch.pick(d.isoformat(), hist, user_day=i)
        ids = [q["id"] for q in qs]
        tag = "심층" if len(ids) == 5 else "평일"
        wd = "월화수목금토일"[d.weekday()]
        print(f"{d} ({wd}) {tag} · {len(ids)}문항 → {' '.join(ids)}")
        hist.append({"date": d.isoformat(), "question_ids": ids})

    print()
    print("=" * 72)
    print("위기 플래그 발생 주간 (crisis_recent=True)")
    print("=" * 72)
    for i in range(14, 18):
        d = start + timedelta(days=i)
        qs = sch.pick(d.isoformat(), hist, crisis_recent=True, user_day=i)
        ids = [q["id"] for q in qs]
        risks = [q["risk"] for q in qs]
        print(f"{d} → {' '.join(ids)}   위기등급={risks}")
        hist.append({"date": d.isoformat(), "question_ids": ids})

    print()
    print(sch.explain(sch.pick("2026-07-29", [], user_day=30, force_deep=True)))
