# -*- coding: utf-8 -*-
"""interests.py — 취향·관심사 기억 → 라포·개인화·비유 재료.

왜 따로 두나
    T1(영화·책·애니)·T4(취미)는 언어지표·성향축으로는 신호가 약하다(T1 evidence=none).
    하지만 '무슨 영화를 좋아하는지, 무슨 취미로 시간을 보내는지'라는 내용 자체는
    라포·개인화·비유의 강력한 재료다. 지금 파이프라인은 이 내용을 버리고 지표만 뽑는다.
    이 모듈은 취향 답변을 '기억'해 두었다가 나중에 서사가 참조하게 한다.

역할
    · 지표/축과 무관한 '내용 메모리'. 예측 수치엔 안 들어간다.
    · 라포·비유·개인화 재료로만 쓴다 — 조언을 취향에 억지로 엮거나 취향을 판단하지 말 것.

무엇을 모으나
    scheduler 의 taste 레이어(T1·T4) 답변 + (선택) 자유칸. 원문 로그 + 살린 키워드(명사).
    지속 저장(유저별 누적)은 앱 DB 몫 — 이 모듈은 넘겨받은 세션들에서 프로파일을 만든다.

standalone:
    python diary_module/qmode/interests.py
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
DIARY = HERE.parent
if str(DIARY) not in sys.path:
    sys.path.insert(0, str(DIARY))

from qmode.scheduler import Scheduler          # noqa: E402  (taste 레이어 판별)

_SCH = Scheduler()
_TASTE_IDS = {q["id"] for q in _SCH.rotation if q.get("layer") == "taste"}

# 키워드에서 걸러낼 흔한 명사(신호 약함). 최소한만 — 과하게 지우면 고유명사까지 날아감.
_STOP = {"오늘", "요즘", "최근", "생각", "사람", "시간", "기분", "느낌", "부분", "정도",
         "때", "거", "것", "수", "게", "말", "일", "중", "안", "더", "좀", "잘", "그냥"}

_kiwi = None


def _get_kiwi():
    global _kiwi
    if _kiwi is None:
        from kiwipiepy import Kiwi
        _kiwi = Kiwi()
    return _kiwi


def _keywords(texts, top=8):
    """취향 답변들 → 살아있는 명사 키워드(빈도순). 고유명사(NNP) 가중."""
    try:
        kiwi = _get_kiwi()
    except Exception:                              # kiwi 없으면 키워드 생략
        return []
    cnt = Counter()
    for t in texts:
        for tok in kiwi.tokenize(t or ""):
            if tok.tag in ("NNG", "NNP") and len(tok.form) >= 2 and tok.form not in _STOP:
                cnt[tok.form] += 2 if tok.tag == "NNP" else 1   # 고유명사 가중
    return cnt.most_common(top)


def collect(sessions, include_free=False):
    """세션들 → 취향 프로파일.

    반환: {
      "log": [{date, question_id, answer}],   # 취향 답변 원문 로그(최신순)
      "recent": [answer, ...],                # 최근 답변 텍스트(서사 참조용)
      "keywords": [(단어, 빈도), ...],         # 살린 명사 키워드
      "n": int,
    }
    """
    log = []
    for s in sessions:
        for it in s.get("items", []):
            if it.get("skipped"):
                continue
            qid = it.get("question_id")
            ans = it.get("answer", "")
            if qid in _TASTE_IDS and ans:
                log.append({"date": s.get("date"), "question_id": qid, "answer": ans})
        if include_free and s.get("free") and s["free"].get("answer"):
            log.append({"date": s.get("date"), "question_id": None,
                        "answer": s["free"]["answer"]})
    log.sort(key=lambda x: x.get("date") or "", reverse=True)
    texts = [x["answer"] for x in log]
    return {"log": log, "recent": texts[:5], "keywords": _keywords(texts), "n": len(log)}


def build_block(profile):
    """서사 프롬프트에 붙일 '취향/관심사(라포)' 재료 블록.

    라포·비유·개인화 재료로만 쓰라는 가드를 함께 넣는다.
    """
    if not profile or not profile.get("n"):
        return ""
    lines = [
        "[사용자 취향·관심사 — 라포·비유·개인화 재료로만. 조언을 억지로 취향에 엮지 말고,",
        " 취향 자체를 판단하지 말 것. 자연스러울 때만 슬쩍 참조.]",
    ]
    kw = profile.get("keywords", [])
    if kw:
        lines.append("· 관심 키워드: " + ", ".join(f"{w}({c})" for w, c in kw))
    if profile.get("recent"):
        lines.append("· 최근 언급:")
        for a in profile["recent"]:
            lines.append(f"   - 「{a[:40]}…」" if len(a) > 40 else f"   - 「{a}」")
    return "\n".join(lines)


if __name__ == "__main__":
    import json

    # 며칠에 걸쳐 취향 답변이 쌓인 상황(모델 불필요).
    sessions = [
        {"date": "2026-07-25", "items": [
            {"question_id": "T1", "answer": "최근에 본 애니 '프리렌' 진짜 좋았다. 여운이 오래 남았다."},
            {"question_id": "C2", "answer": "회의에서 말을 삼켰다."}]},
        {"date": "2026-07-27", "items": [
            {"question_id": "T4", "answer": "주말에 클라이밍하면 시간 순삭이다. 끝나고 개운함이 크다."},
            {"question_id": "C1", "answer": "친구가 보낸 영상 보고 웃었다."}]},
        {"date": "2026-07-29", "items": [
            {"question_id": "T1", "answer": "무라카미 하루키 소설을 다시 읽는다. 문장이 좋다."}]},
    ]
    prof = collect(sessions)
    print("=== 취향 프로파일 ===")
    print("취향 답변 수:", prof["n"])
    print("키워드:", prof["keywords"])
    print("최근 언급:", prof["recent"])
    print("\n=== 서사 주입 블록 ===")
    print(build_block(prof))
    print("\n=== 취향 답변 없을 때 ===")
    print(repr(build_block(collect([{"date": "2026-07-30", "items": [
        {"question_id": "C1", "answer": "그냥 그랬다."}]}]))))
