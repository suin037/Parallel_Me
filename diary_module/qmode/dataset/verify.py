# -*- coding: utf-8 -*-
"""verify.py — LLM 성향추출 '일관성(test-retest)' 검증.

같은 일기를 두 번 추출해 성향이 안정적으로 나오는지 본다. LLM은 매번 답이
흔들릴 수 있으므로, '믿을 수 있다'고 하려면 재현성을 실제로 재봐야 한다.

판정 기준(핵심 필드):
    coping.direction  : 정확히 일치해야 안정
    decision_style    : 정확히 일치
    risk_tolerance    : |차| ≤ 0.15 면 안정
    value 상위2축      : 집합 일치면 안정

    python diary_module/qmode/dataset/verify.py            # 전원 2회
    python diary_module/qmode/dataset/verify.py P1_stability
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))

_spec = importlib.util.spec_from_file_location("build", HERE / "build.py")
build = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build)

from qmode import disposition_llm as dl        # noqa: E402
from qmode.aggregate import accumulate         # noqa: E402

ORDER = ["P1_stability", "P2_growth", "P3_meaning", "P4_economy", "P5_balance"]


def _top2(extract):
    va = extract.get("value_axes", {})
    return set(sorted(va, key=lambda a: va[a].get("lean", 0), reverse=True)[:2])


def verify_one(key):
    diary = build.load_diary(key)
    sessions, _ = build.to_sessions_and_rows(diary)
    span = f"({build.personas.PERSONAS[key]['label']})"
    a, ea = dl.extract(sessions, span_label=span)
    b, eb = dl.extract(sessions, span_label=span)
    if not a or not b:
        return {"key": key, "ok": False, "err": ea or eb}
    ja, jb = a.get("job_change", {}), b.get("job_change", {})
    rt_a, rt_b = ja.get("risk_tolerance"), jb.get("risk_tolerance")
    checks = {
        "coping": a["coping"]["direction"] == b["coping"]["direction"],
        "decision": ja.get("decision_style") == jb.get("decision_style"),
        "risk_tol": (rt_a is not None and rt_b is not None and abs(rt_a - rt_b) <= 0.15),
        "top2_value": _top2(a) == _top2(b),
    }
    return {"key": key, "ok": True, "checks": checks,
            "a": (a["coping"]["direction"], rt_a, ja.get("decision_style"), _top2(a)),
            "b": (b["coping"]["direction"], rt_b, jb.get("decision_style"), _top2(b))}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("persona", nargs="?", default=None)
    args = ap.parse_args()
    keys = [args.persona] if args.persona else ORDER

    total = passed = 0
    for k in keys:
        r = verify_one(k)
        print("=" * 60)
        print(k)
        if not r["ok"]:
            print("  추출 실패:", r["err"]); continue
        for name, ok in r["checks"].items():
            total += 1; passed += ok
            print(f"  {'✅' if ok else '❌'} {name}")
        print(f"  run A: 대처={r['a'][0]} 위험={r['a'][1]} 결정={r['a'][2]} 상위2={r['a'][3]}")
        print(f"  run B: 대처={r['b'][0]} 위험={r['b'][1]} 결정={r['b'][2]} 상위2={r['b'][3]}")
    print("=" * 60)
    print(f"일관성: {passed}/{total} 항목 안정 ({100*passed//max(total,1)}%)")
