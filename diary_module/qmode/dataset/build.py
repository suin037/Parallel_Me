# -*- coding: utf-8 -*-
"""build.py — 페르소나 일기(JSON) → metrics 누적 → 성향 프로파일 (model-free).

감정모델(1.3GB) 불필요. Kiwi 언어지표만으로 30일 누적 성향을 만든다.
'하루는 노이즈, 한 달은 신호'를 실제로 보여주는 러너.

사용:
    python diary_module/qmode/dataset/build.py P1_stability
    python diary_module/qmode/dataset/build.py P1_stability --days 7   # 앞 N일만(누적 성장 비교)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
QMODE = HERE.parent
DIARY = QMODE.parent
for p in (str(DIARY),):
    if p not in sys.path:
        sys.path.insert(0, p)

import metrics                                              # noqa: E402
from qmode.aggregate import accumulate, classify_envy      # noqa: E402
from qmode import disposition                               # noqa: E402
from qmode import disposition_llm as dl                     # noqa: E402
import importlib.util                                       # noqa: E402

# personas.py 를 파일 경로로 로드(패키지 아님)
_spec = importlib.util.spec_from_file_location("personas", HERE / "personas.py")
personas = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(personas)


def load_diary(persona_key):
    return json.loads((HERE / "diaries" / f"{persona_key}.json").read_text(encoding="utf-8"))


def to_sessions_and_rows(diary, limit_days=None):
    """일기 JSON → (sessions[disposition용], rows[accumulate용]). metrics 계산 포함."""
    sessions, rows = [], []
    days = diary["days"]
    if limit_days:
        days = days[:limit_days]
    for d in days:
        items = []
        for qid, text in d["answers"].items():
            m = metrics.analyze_text(text)
            it = {"question_id": qid, "answer": text, "metrics": m}
            if qid == "D4":
                it["envy"] = classify_envy(text)
            items.append(it)
            rows.append({"date": d["date"], "question_id": qid,
                         "source": "question", "text": text, "metrics": m})
        free = None
        if d.get("free"):
            fm = metrics.analyze_text(d["free"])
            free = {"question_id": None, "source": "free", "answer": d["free"], "metrics": fm}
            rows.append({"date": d["date"], "question_id": None, "source": "free",
                         "text": d["free"], "metrics": fm})
        sessions.append({"date": d["date"], "items": items, "free": free})
    return sessions, rows


def analyze(persona_key, limit_days=None, use_llm=False):
    diary = load_diary(persona_key)
    sessions, rows = to_sessions_and_rows(diary, limit_days)
    agg = accumulate(rows)
    vw = personas.onboarding_weights(persona_key)
    disp = disposition.analyze_disposition(sessions, agg.get("diary_metrics"), value_weights=vw)
    res = {"persona": persona_key, "meta": personas.PERSONAS[persona_key],
           "n_days": len(sessions), "agg": agg, "value_weights": vw, "disp": disp}
    if use_llm:
        span = f"({personas.PERSONAS[persona_key]['label']} {len(sessions)}일)"
        obj, err = dl.extract(sessions, span_label=span)
        res["llm"], res["llm_err"] = obj, err
        if obj:
            res["blend"] = dl.blend_weights(vw, obj, n_answers=agg["n_answers"])
    return res


def _print(res):
    p = res["meta"]
    agg = res["agg"]
    dm = agg.get("diary_metrics")
    print("=" * 64)
    print(f"{res['persona']}  ·  {p['label']}  ({res['n_days']}일)")
    print("=" * 64)
    print(f"[온보딩 가치 가중치] {json.dumps(res['value_weights'], ensure_ascii=False)}")
    print(f"[게이트 통과 답변]  {agg['n_answers']}개  (제출 {agg['n_submitted']})")
    if dm:
        print(f"[누적 언어지표] 정서극성 {dm.get('emotion_valence')} · "
              f"대처균형 {dm.get('coping_balance')} · 통찰 {dm.get('insight_ratio')} · "
              f"절대어 {dm.get('absolutist_ratio')} · 1인칭 {dm.get('first_person_ratio')}")
    else:
        print(f"[누적 언어지표] {agg.get('gate_note')}")
    print(f"[전달 스타일·사전지표] {res['disp']['delivery_style']['guide']}")

    if res.get("llm_err"):
        print(f"[LLM 추출] 실패 — {res['llm_err']}")
    elif res.get("llm"):
        o = res["llm"]
        b = res["blend"]
        print()
        print("─" * 64)
        print("★ LLM 구조화 추출 (사전지표 대체)")
        print("─" * 64)
        print(f"  대처: {o['coping']['direction']} (conf {o['coping']['confidence']})")
        print(f"    근거: {' / '.join(o['coping'].get('evidence', [])[:3])}")
        print(f"  전달 스타일: {disposition.delivery_from_llm(o)}")
        print(f"  요약: {o.get('summary','')}")
        print()
        print(f"  [갱신] 온보딩 → LLM증거 블렌딩  ({b['note']})")
        print(f"    온보딩 : " + "  ".join(f"{k} {v:.2f}" for k, v in b['prior'].items()))
        print(f"    LLM증거: " + "  ".join(f"{k} {v:.2f}" for k, v in b['evidence'].items()))
        print(f"    갱신후 : " + "  ".join(f"{k} {v:.2f}" for k, v in b['weights'].items()))
    print()
    print(res["disp"]["block"])
    print()


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("persona", nargs="?", default="P1_stability")
    ap.add_argument("--days", type=int, default=None, help="앞 N일만 누적(성장 비교용)")
    ap.add_argument("--llm", action="store_true", help="구조화 LLM 추출 + 갱신 블렌딩(API 키 필요)")
    args = ap.parse_args()
    _print(analyze(args.persona, args.days, use_llm=args.llm))
