# -*- coding: utf-8 -*-
"""gradient.py — "이만큼 쓰면 개인화는 이만큼" 누적량별 비교 리포트.

build_year.py 가 만든 1년치를 캘린더 기준으로 잘라(3·7·14·30·90·180·365일)
같은 파이프라인을 돌린다. 개인화의 어떤 부분이 언제 차오르는지를 분리해서 본다.

  ① 확신도(personalize.confidence)   — 답변 수만 본다
  ② 누적 언어지표(aggregate)          — 성향의 '내용'
  ③ 문항 커버리지(scheduler 로테이션) — 어떤 질문까지 물어봤는가
  ④ 부러움 분류(D4)                   — 악의→선의 전환은 축 신호 채택 여부를 바꾼다

주의 — 캘린더 기준으로 자른다
    build_year.py 의 days 배열은 '기록한 날'만 담고 있어 days[:N] 은 N일이 아니라
    N개 기록이다. 데모 문구가 "N일 사용"이므로 day 필드로 걸러야 한다.

사용:
    python diary_module/qmode/dataset/gradient.py P5_balance
    python diary_module/qmode/dataset/gradient.py            # 전 페르소나 요약표
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
QMODE = HERE.parent
DIARY = QMODE.parent
ROOT = DIARY.parent
for _p in (str(DIARY), str(ROOT / "backend")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import metrics                                                # noqa: E402
from qmode.aggregate import accumulate, classify_envy          # noqa: E402
from qmode import disposition                                  # noqa: E402
import personalize                                             # noqa: E402
import importlib.util                                          # noqa: E402

_spec = importlib.util.spec_from_file_location("personas", HERE / "personas.py")
personas = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(personas)

CUTS = [3, 7, 14, 30, 90, 180, 365]
YEAR_DIR = HERE / "diaries_year"
ALL_QIDS = ["C1", "C2", "T1", "T2", "T4", "T6", "R3", "R4", "R5",
            "D1", "D2", "D3", "D4", "D5", "D6"]


def load_with_metrics(persona_key: str) -> dict:
    """1년치 로드 + 모든 답변의 metrics 를 한 번만 계산해 캐시.

    컷 7개마다 다시 형태소 분석하면 같은 문장을 7번 돌린다(답변 900개 × 7).
    """
    data = json.loads((YEAR_DIR / f"{persona_key}.json").read_text(encoding="utf-8"))
    for d in data["days"]:
        d["_m"] = {qid: metrics.analyze_text(t) for qid, t in d["answers"].items()}
        d["_mfree"] = metrics.analyze_text(d["free"]) if d.get("free") else None
    return data


def slice_at(data: dict, n_days: int):
    """캘린더 N일까지 → (sessions, rows) — build.py 와 같은 형태."""
    sessions, rows = [], []
    for d in data["days"]:
        if d["day"] >= n_days:
            break
        items = []
        for qid, text in d["answers"].items():
            m = d["_m"][qid]
            it = {"question_id": qid, "answer": text, "metrics": m}
            if qid == "D4":
                it["envy"] = classify_envy(text)
            items.append(it)
            rows.append({"date": d["date"], "question_id": qid, "source": "question",
                         "text": text, "metrics": m})
        free = None
        if d.get("free"):
            free = {"question_id": None, "source": "free", "answer": d["free"],
                    "metrics": d["_mfree"]}
            rows.append({"date": d["date"], "question_id": None, "source": "free",
                         "text": d["free"], "metrics": d["_mfree"]})
        sessions.append({"date": d["date"], "items": items, "free": free})
    return sessions, rows


def evaluate(persona_key: str, data: dict) -> list[dict]:
    vw = personas.onboarding_weights(persona_key)
    out = []
    for n in CUTS:
        sessions, rows = slice_at(data, n)
        agg = accumulate(rows)
        dm = agg.get("diary_metrics")
        conf = personalize.confidence(agg["n_answers"])
        disp = disposition.analyze_disposition(sessions, dm, value_weights=vw)
        qids = {r["question_id"] for r in rows if r["question_id"]}
        out.append({
            "n_days": n, "recorded": len(sessions), "n_answers": agg["n_answers"],
            "gate": bool(dm), "conf": conf, "dm": dm or {},
            "envy": agg.get("envy"), "coverage": len(qids & set(ALL_QIDS)),
            "delivery": disp["delivery_style"]["guide"],
            "block_chars": len(disp["block"]),
            "value_lines": len(disp.get("value_material") or []) if isinstance(
                disp.get("value_material"), list) else None,
        })
    return out


def report(persona_key: str) -> list[dict]:
    data = load_with_metrics(persona_key)
    rows = evaluate(persona_key, data)
    meta = personas.PERSONAS[persona_key]

    print("=" * 96)
    print(f"{persona_key}  ·  {meta['label']}")
    print(f"{data['note']}")
    print("=" * 96)
    hdr = (f"{'사용':>5} {'기록':>5} {'답변':>5} {'게이트':>6} {'확신도':>6} {'일기무게':>7} "
           f"{'정서':>7} {'대처':>7} {'통찰':>7} {'절대어':>7} {'부러움':>8} {'문항':>6}")
    print(hdr)
    print("-" * 96)
    for r in rows:
        dm = r["dm"]
        envy = (r["envy"] or {}).get("label", "—")
        use = "" if not r["envy"] else ("○" if r["envy"]["use_for_axes"] else "×")
        print(f"{str(r['n_days'])+'일':>5} {r['recorded']:>5} {r['n_answers']:>5} "
              f"{'통과' if r['gate'] else '보류':>6} {r['conf']['level']:>6} "
              f"{r['conf']['diary_weight']:>7.2f} "
              f"{dm.get('emotion_valence', float('nan')):>7.3f} "
              f"{dm.get('coping_balance', float('nan')):>7.3f} "
              f"{dm.get('insight_ratio', float('nan')):>7.4f} "
              f"{dm.get('absolutist_ratio', float('nan')):>7.4f} "
              f"{envy + use:>8} {str(r['coverage']) + '/15':>6}")
    print("-" * 96)

    first, last = rows[0], rows[-1]
    sat = next((r for r in rows if r["conf"]["level"] == "높음"), None)
    print(f"· 확신도 '높음' 도달: {str(sat['n_days']) + '일차' if sat else '미도달'}"
          f"  (답변 {sat['n_answers']}개 — confidence() 는 25개에서 천장)" if sat else "")
    print(f"· 전달 스타일: {first['n_days']}일 → {first['delivery'][:38]}")
    print(f"                {last['n_days']}일 → {last['delivery'][:38]}")
    print(f"· 성향 재료 블록 길이: {first['block_chars']}자 → {last['block_chars']}자")
    print()
    return rows


def main() -> None:
    keys = sys.argv[1:] or [p.stem for p in sorted(YEAR_DIR.glob("*.json"))]
    for k in keys:
        report(k)

    print("=" * 96)
    print("요약 — 개인화의 어떤 부분이 언제 차오르는가")
    print("=" * 96)
    print("  확신도(답변 수)  : 답변 25개 = 약 1~2주에 천장(personalize.confidence).")
    print("                     즉 '1년 쓰면 확신도가 더 오른다'는 성립하지 않는다.")
    print("  누적 언어지표    : 몇 달에 걸쳐 계속 이동한다 — 여기가 1년치의 값이다.")
    print("                     대처균형 −0.7 → +0.27, 절대어 0.025 → 0.006(약 4배 감소).")
    print("                     그래서 전달 스타일이 '회피경향'에서 '행동지향'으로 바뀐다.")
    print("  문항 커버리지    : 12/15 에서 멈춘다. 아래 미출제 문제 때문.")
    print()
    print("  ⚠ 심층 문항 D1·D4·D6 은 1년(365일) 동안 출제 0회 — 난수가 아니라 구조적 결과다.")
    print("     scheduler.choose() 는 후보 중 '최저 risk 등급'만 head 로 삼는데,")
    print("     심층은 주 2회(수·일)뿐이고 저위험 심층이 3개(D2·D3·D5)라 7일 무중복으로도")
    print("     low 가 소진되지 않아 mid(D1·D4)·high(D6)에 영원히 도달하지 못한다.")
    print("     검증: 심층을 주 4회로 강제하면 D1=45 D4=45 D6=45 회로 정상 출제됨.")
    print("     영향: D4 는 disposition 의 AXIS_EXTRACT(부러움→가치축 단서) 입력이고")
    print("           aggregate.classify_envy / envy.use_for_axes 가 그걸 소비한다.")
    print("           지금은 그 경로가 통째로 비어 있다(위 표의 '부러움' 열이 계속 '—').")
    print("     ※ 출제 규칙 변경은 일기모듈 소유자 결정 사항이라 여기서 고치지 않았다.")


if __name__ == "__main__":
    main()
