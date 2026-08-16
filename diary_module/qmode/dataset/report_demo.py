# -*- coding: utf-8 -*-
"""report_demo.py — 페르소나 데이터셋 → 실제 유저 리포트 (model-free + 서사 API).

감정모델(1.3GB) 없이 dataset 세션으로 리포트를 뽑는다. 서사만 API로 생성(새 NARR_SYSTEM).
리포트 말투 변경(AI티 제거)이 실제 출력에서 어떻게 나오는지 확인용.

    python diary_module/qmode/dataset/report_demo.py P1_stability
    python diary_module/qmode/dataset/report_demo.py P1_stability --no-narrative
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
QMODE = HERE.parent
DIARY = QMODE.parent
ROOT = DIARY.parent
for p in (str(DIARY), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from qmode import disposition, interests, report as RPT     # noqa: E402
import report_one as R1                                      # noqa: E402

_spec = importlib.util.spec_from_file_location("build", HERE / "build.py")
build = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build)


def run(persona_key, with_narrative=True):
    diary = build.load_diary(persona_key)
    sessions, rows = build.to_sessions_and_rows(diary)
    from qmode.aggregate import accumulate
    agg = accumulate(rows)
    vw = build.personas.onboarding_weights(persona_key)
    disp = disposition.analyze_disposition(sessions, agg.get("diary_metrics"), value_weights=vw)
    interests_prof = interests.collect(sessions)
    interests_block = interests.build_block(interests_prof)

    narrative = None
    if with_narrative:
        R1._load_dotenv()
        prompt = RPT.build_narrative_prompt(sessions, agg, None,
                                            disp["block"], interests_block)
        narrative, err = RPT.generate_narrative(prompt)
        if err:
            print(f"[서사 생성 실패: {err}]\n")

    user = RPT.render_user_report(sessions, agg=agg, health_result=None,
                                  narrative=narrative, interests_profile=interests_prof,
                                  source_label=f"({build.personas.PERSONAS[persona_key]['label']} · 2주)")
    return user


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("persona", nargs="?", default="P1_stability")
    ap.add_argument("--no-narrative", action="store_true")
    args = ap.parse_args()
    print(run(args.persona, with_narrative=not args.no_narrative))
