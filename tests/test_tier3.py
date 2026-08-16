"""티어3(시뮬레이션 속도·폴백 정직성) 회귀 테스트.

실행:  python test_tier3.py

검증 대상:
  ⑩ A/B 가 선택 무관 계산을 공유하는가 / 만족도 추적이 벡터 연산으로 바뀌고도
     **같은 값**을 내는가 / 응답시간이 목표 안인가
  ⑪ 지표를 측정 못 했을 때 그 지표로 심리카드를 뽑지 않는가
"""

import sys
import time
import types
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

# narrative(Claude API) 스텁 — main.py 가 import 하는 심볼을 **전부** 갖춰야 한다.
# (하나라도 빠지면 main import 단계에서 ImportError 로 죽는다)
_stub = types.ModuleType("utils.claude_api")
_stub.generate_narrative = lambda *a, **k: "(narrative 생략 — 테스트 모드)"
_stub.generate_scenarios = lambda *a, **k: {"_skipped": True}
# 기동 워밍업이 서사 스키마도 미리 컴파일한다 → 이 심볼도 스텁에 있어야 한다.
_stub.warm_narrative_schema = lambda *a, **k: False
sys.modules["utils.claude_api"] = _stub

from schemas import CompareRequest, Profile                    # noqa: E402
from compare import build_comparison                           # noqa: E402
import core                                                    # noqa: E402
import trajectory as T                                         # noqa: E402
import indicators as I                                         # noqa: E402
import main as M                                               # noqa: E402

# 이 안에서 /compare 가 끝나야 한다는 상한. 여유를 두되 회귀는 잡히게.
LATENCY_BUDGET_S = 0.60

_fail: list[str] = []


def check(cond: bool, label: str, detail: str = "") -> None:
    print(f"  {'[OK]  ' if cond else '[FAIL]'} {label}" + (f"  — {detail}" if detail else ""))
    if not cond:
        _fail.append(label)


def req(a="이직", b="창업", **over):
    p = dict(age=29, sex="1", major="공학", monthly_wage=320, edu_level=7,
             is_regular=1, firm_size=7)
    p.update(over)
    return CompareRequest(profile=Profile(**p), choice_a=a, choice_b=b)


# ---------------------------------------------------------------- ⑩ 동치
def _legacy_yp(features, horizon=3, k=300, min_n=15, treatment=None):
    """벡터화 이전의 루프 구현을 그대로 재현 — 값이 안 바뀌었는지 대조용."""
    P = T._yp_panel()
    by_pid = {p: g.set_index("wave") for p, g in P["long"].groupby("person_id")}
    _P, starts, _br = T._yp_starts(features, k, min_n, treatment, horizon)
    A = features.get("age")

    def series(col, agg):
        out = []
        for h in range(horizon + 1):
            vals = []
            for pid, w0 in starts:
                g = by_pid.get(pid)
                if g is None or col not in g.columns:
                    continue
                w = int(w0) + h
                if w in g.index:
                    r = g.loc[w]
                    r = r.iloc[0] if isinstance(r, pd.DataFrame) else r
                    if pd.notna(r[col]):
                        vals.append(float(r[col]))
            if len(vals) >= min_n:
                out.append((h, len(vals), agg(vals)))
        return out

    pts = [{"year": h, "age": int(A) + h, "sample_n": n,
            "satis_p25": round(float(np.percentile(v, 25)), 2),
            "satis_p50": round(float(np.percentile(v, 50)), 2),
            "satis_p75": round(float(np.percentile(v, 75)), 2)}
           for h, n, v in series("만족도", lambda v: v)]
    facets = {}
    for f in T.SATIS:
        s = [{"year": h, "age": int(A) + h, "sample_n": n,
              "mean": round(float(np.mean(v)), 2)}
             for h, n, v in series(f, lambda v: v)]
        if s:
            facets[f] = s
    return pts, facets


def test_equivalence() -> None:
    print("\n⑩-1 벡터화가 값을 바꾸지 않았는가")
    bad = []
    for age in (24, 27, 29, 31):
        for wage in (220, 380):
            for tr in (None, "move", "stay", "startup", "enroll"):
                f = {"age": age, "sex": 1.0, "monthly_wage": wage, "edu_level": 7}
                lp, lf = _legacy_yp(f, treatment=tr)
                new = T.yp_satisfaction(f, treatment=tr)
                if lp != new["points"] or lf != new["facets"]:
                    bad.append((age, wage, tr))
    check(not bad, "예전 루프 구현과 만족도·facet 결과가 완전히 동일",
          f"{4 * 2 * 5}조합 검사, 불일치 {len(bad)}건"
          + (f" {bad[:3]}" if bad else ""))


def test_sharing() -> None:
    print("\n⑩-2 A/B 가 선택 무관 계산을 공유하는가")
    calls = {"traj": 0, "life": 0}
    orig_traj, orig_life = core.project_trajectory, core.query_life_indicators

    def spy_traj(*a, **k):
        calls["traj"] += 1
        return orig_traj(*a, **k)

    def spy_life(*a, **k):
        calls["life"] += 1
        return orig_life(*a, **k)

    core.project_trajectory, core.query_life_indicators = spy_traj, spy_life
    try:
        build_comparison(req())
    finally:
        core.project_trajectory, core.query_life_indicators = orig_traj, orig_life
    check(calls["traj"] == 1, "L5 소득 궤적은 A/B 통틀어 1회만", f"{calls['traj']}회")
    check(calls["life"] == 1, "L1 생활지표는 A/B 통틀어 1회만", f"{calls['life']}회")

    # 캐시를 공유해도 선택별로 갈리는 값은 그대로 갈려야 한다
    c = build_comparison(req("이직", "현상 유지")).model_dump()
    a, b = c["scenarios"]["A"], c["scenarios"]["B"]
    check(a["raw"]["wellbeing_branch"].get("treatment")
          != b["raw"]["wellbeing_branch"].get("treatment"),
          "공유 캐시가 선택별 만족도 분기를 뭉개지 않는다",
          f"A={a['raw']['wellbeing_branch'].get('treatment')} "
          f"B={b['raw']['wellbeing_branch'].get('treatment')}")


def test_latency() -> None:
    print("\n⑩-3 응답시간")
    T._panel(), T._yp_panel()          # 패널 워밍(첫 기동 비용은 별도)
    build_comparison(req())
    ts = []
    for _ in range(3):
        t0 = time.perf_counter()
        build_comparison(req())
        ts.append(time.perf_counter() - t0)
    avg = sum(ts) / len(ts)
    check(avg < LATENCY_BUDGET_S, f"/compare 평균 < {LATENCY_BUDGET_S}s",
          f"{avg:.3f}s (개별 {[round(t, 3) for t in ts]})")
    check("by_pid" not in (T._yp_panel() or {}),
          "person_id별 DataFrame 사전을 만들지 않는다(첫 기동 지연 원인이었음)")


# ---------------------------------------------------------------- ⑪ 폴백
def test_fallback_cards() -> None:
    print("\n⑪ 측정 못 한 지표로 심리카드를 뽑지 않는가")
    # 지표가 하나도 측정되지 않은 상태를 만들어 넘긴다
    det = {"unmeasured": ["경제적안정도", "성장가능성", "삶의질"]}
    scores = {"경제적안정도": 0.5, "성장가능성": 0.5, "삶의질": 0.5}
    check(M._measured(scores, det, None) == {},
          "전부 미측정이면 심리카드에 넘길 지표가 남지 않는다")
    check(M._measured(scores, {"unmeasured": ["삶의질"]}, None).keys()
          == {"경제적안정도", "성장가능성"},
          "일부만 미측정이면 그 지표만 빠진다(초점 선택이 자리채우기에 안 좌우됨)")
    check(M._measured(scores, det, {"삶의질": 0.2}) == scores,
          "요청이 직접 준 지표는 그대로 통과(사용자 책임)")

    # 실제 산출물에도 unmeasured 가 실려야 호출측이 판단할 수 있다
    c = build_comparison(req()).model_dump()
    d = I.compute_indicators_detail(c["scenarios"]["A"], 320, 29)
    check("unmeasured" in d, "지표 상세에 미측정 목록이 실린다",
          f"unmeasured={d.get('unmeasured')}")

    src = (ROOT / "backend/main.py").read_text(encoding="utf-8")
    fb = src[src.index("def _simulate_without_artifacts"):
             src.index("def _measured(")]
    check("get_psych_evidence" not in fb,
          "아티팩트 폴백 경로에서 카드 검색 호출 자체가 사라졌다")
    check('"indicators": {"A": None, "B": None}' in fb,
          "폴백 지표를 0.5 가 아니라 null 로 내보낸다('측정 못 함' ≠ '중간')")


def test_warmup() -> None:
    """기동 워밍업 배선 — 실제 로딩(수십 초)은 돌리지 않고 계약만 확인한다."""
    print("\n⑩-4 기동 워밍업")
    from config import settings

    orig = settings.warmup_on_startup
    try:
        settings.warmup_on_startup = False
        M._warmup_state["started"] = False
        t0 = time.perf_counter()
        M._on_startup()
        check(time.perf_counter() - t0 < 0.1 and not M._warmup_state["started"],
              "설정으로 끄면 워밍업을 시작하지 않는다(테스트·CLI 용)")
    finally:
        settings.warmup_on_startup = orig

    src = (ROOT / "backend/main.py").read_text(encoding="utf-8")
    body = src[src.index("def _warmup()"):src.index("def _on_startup()")]
    check("except Exception" in body,
          "워밍업 단계가 실패해도 서버가 죽지 않는다(요청 시 지연 로딩으로 폴백)")
    hook = src[src.index("def _on_startup()"):src.index("# 프론트(Vite")]
    check("Thread(" in hook and "daemon=True" in hook,
          "백그라운드 스레드로 돈다 — 기동을 막지 않아 /health 가 즉시 뜬다")

    from rag import psych_retriever as pr
    check(hasattr(pr, "is_loaded") and hasattr(pr, "_load_lock"),
          "임베딩 모델 로딩에 락이 있다(워밍업과 첫 요청이 중복 로딩하지 않도록)")


def main() -> int:
    print("=" * 78)
    test_equivalence()
    test_sharing()
    test_latency()
    test_warmup()
    test_fallback_cards()
    print("=" * 78)
    if _fail:
        print(f"[FAIL] {len(_fail)}건 실패: {_fail}")
        return 1
    print("[OK] 티어3 전체 통과")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
