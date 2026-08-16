"""현재 보유 데이터로 '대학원 진학' 소득 모델을 만들 수 있는지 감사한다.

학력코드 상승을 실제 입학으로 오인하지 않도록, 사용 가능한 사건 변수와 연차별
표본 손실을 별도 JSON에 기록한다. 이 스크립트는 모델 artifact를 만들거나 덮어쓰지
않는다.

Usage:
    python scripts/audit_enroll_treatment.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
KLIPS = ROOT / "data/raw/klips/klips_base.pkl"
YP = ROOT / "data/clean/yp_clean.csv"
OUT = ROOT / "backend/models/artifacts/enroll_treatment_audit.json"
TREATMENT_REPORT = ROOT / "backend/models/artifacts/treatment_report.json"
HORIZONS = (1, 3, 5)
AGE_MIN, AGE_MAX = 20, 45
TRAINING_REQUIRED = {"월소득_실질", "종사상지위", "자영여부"}

# 이 중 하나라도 있어야 학력 완료가 아닌 실제 재학/입학 사건을 만들 수 있다.
ENROLLMENT_TOKENS = ("재학", "입학", "학교유형", "대학원재학", "enroll", "attendance")


def enrollment_columns(columns) -> list[str]:
    return [str(col) for col in columns
            if any(token.lower() in str(col).lower() for token in ENROLLMENT_TOKENS)]


def klips_counts(panel: pd.DataFrame) -> dict:
    panel = panel.sort_values(["pid", "wave"]).reset_index(drop=True)
    grouped = panel.groupby("pid", sort=False)
    nxt = grouped.shift(-1)
    result = {}
    for horizon in HORIZONS:
        future_income = grouped["월임금_실질"].shift(-horizon)
        future_wave = grouped["wave"].shift(-horizon)
        continuous = (nxt["wave"] - panel["wave"] == 1) & (future_wave - panel["wave"] == horizon)
        age_ok = panel["나이"].between(AGE_MIN, AGE_MAX)
        proxy_event = nxt["학력"].gt(panel["학력"])
        eligible_proxy = continuous & age_ok & proxy_event
        current_income_observed = panel["월임금_실질"].notna()
        future_income_observed = future_income.notna()
        positive_income = panel["월임금_실질"].gt(0) & future_income.gt(0)
        result[str(horizon)] = {
            "education_level_increase_rows": int(eligible_proxy.sum()),
            "with_current_and_future_income": int((eligible_proxy & current_income_observed & future_income_observed).sum()),
            "with_positive_current_and_future_income": int((eligible_proxy & positive_income).sum()),
        }
    return result


def main() -> None:
    if not KLIPS.exists():
        raise FileNotFoundError(KLIPS)

    klips = pd.read_pickle(KLIPS)
    yp_columns = list(pd.read_csv(YP, nrows=0).columns) if YP.exists() else []
    stored_report = json.loads(TREATMENT_REPORT.read_text(encoding="utf-8")) if TREATMENT_REPORT.exists() else {}
    stored_enroll = (stored_report.get("treatments") or {}).get("enroll") or {}
    counts = klips_counts(klips)
    current_h1 = counts["1"]["with_positive_current_and_future_income"]
    report = {
        "built_at": datetime.now(timezone.utc).isoformat(),
        "decision": "blocked_pending_true_enrollment_event",
        "serving_policy": "do_not_train_or_serve_choice_specific_enroll_income_effect",
        "minimum_treated_policy": {
            "value": 200,
            "type": "operational_safety_gate_not_power_analysis",
            "note": "기준을 낮추는 대신 연차별 신뢰구간과 교차검증을 통과해야 한다.",
        },
        "klips": {
            "path": str(KLIPS.relative_to(ROOT)),
            "rows": int(len(klips)),
            "columns": list(map(str, klips.columns)),
            "true_enrollment_columns": enrollment_columns(klips.columns),
            "training_required_columns_missing": sorted(TRAINING_REQUIRED - set(klips.columns)),
            "current_proxy": "next-wave education level > current education level",
            "proxy_limitation": "입학·재학이 아니라 학력 단계 완료를 포착하며 대학원 재학생을 누락할 수 있음",
            "horizon_counts": counts,
        },
        "yp": {
            "path": str(YP.relative_to(ROOT)),
            "available": YP.exists(),
            "columns": yp_columns,
            "true_enrollment_columns": enrollment_columns(yp_columns),
            "note": "현재 정제본에는 실제 대학원 입학·재학 사건 변수가 없음",
        },
        "required_next_data": [
            "대학원 입학 또는 재학 상태와 시작 시점",
            "전일제/병행 여부와 석사/박사 구분",
            "무소득·미취업을 포함한 1·3·5년 후 소득",
            "같은 시점에 진학하지 않고 계속 근무한 대조군",
        ],
        "artifact_consistency": {
            "stored_treatment_report_n_treated": stored_enroll.get("n_treated"),
            "current_h1_positive_income_n_treated": current_h1,
            "matches": stored_enroll.get("n_treated") == current_h1,
            "note": "불일치하면 저장 리포트와 현재 전처리 입력이 같은 스냅샷이 아님",
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\n감사 리포트 저장: {OUT}")


if __name__ == "__main__":
    main()
