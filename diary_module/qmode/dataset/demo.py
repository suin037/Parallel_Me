# -*- coding: utf-8 -*-
"""demo.py — 시연용. 페르소나 전원의 '같은 이직, 다른 미래 프레임'을 한 방에.

온보딩 순위 → (일기 → LLM 성향추출 → 갱신) → 이직 서사용 재료. 5명 나란히 대조.

    python diary_module/qmode/dataset/demo.py            # 온보딩만(즉시, API 불필요)
    python diary_module/qmode/dataset/demo.py --llm      # 일기 반영 풀버전(API)
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DIARY = HERE.parent.parent
sys.path.insert(0, str(DIARY))

_spec = importlib.util.spec_from_file_location("build", HERE / "build.py")
build = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build)

from qmode import disposition, disposition_llm as dl   # noqa: E402

ORDER = ["P1_stability", "P2_growth", "P3_meaning", "P4_economy", "P5_balance"]


def run(use_llm=False):
    for k in ORDER:
        p = build.personas.PERSONAS[k]
        vw = build.personas.onboarding_weights(k)
        top = sorted(vw, key=vw.get, reverse=True)[:2]
        extract = None
        note = "온보딩만"
        if use_llm:
            diary = build.load_diary(k)
            sessions, rows = build.to_sessions_and_rows(diary)
            from qmode.aggregate import accumulate
            agg = accumulate(rows)
            extract, err = dl.extract(sessions, span_label=f"({p['label']} 2주)")
            if extract:
                b = dl.blend_weights(vw, extract, n_answers=agg["n_answers"])
                vw = b["weights"]
                note = b["note"]
            else:
                note = f"LLM 실패({err})"

        print("=" * 70)
        print(f"{k}  ·  {p['label']}")
        print("=" * 70)
        print(f"온보딩 1·2순위: {' > '.join(top)}")
        if extract:
            jc = extract.get("job_change", {})
            print(f"대처: {extract['coping']['direction']} · "
                  f"위험감수도: {jc.get('risk_tolerance')} · 결정: {jc.get('decision_style')}")
            print(f"지키려는 것: {jc.get('protect_most')}")
        print(f"[갱신: {note}]")
        print(disposition.build_jobchange_material(vw, extract))
        print()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", action="store_true")
    args = ap.parse_args()
    run(use_llm=args.llm)
