"""KLIPS 직장→직장 이동자의 직종 전이 관측표를 생성한다.

효과나 개인 미래를 추정하지 않는다. 현재 직종 대분류별로 실제 이직자의
도착 직종 분포와 Wilson 95% 구간을 저장한다.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "data" / "clean" / "klips_job_change_panel.csv"
OUTPUT = ROOT / "data" / "clean" / "job_transition_matrix.json"
AGE_MIN, AGE_MAX = 25, 35
LABELS = {
    1: "관리자", 2: "전문가 및 관련 종사자", 3: "사무 종사자",
    4: "서비스 종사자", 5: "판매 종사자", 6: "농림어업 숙련 종사자",
    7: "기능원 및 관련 기능 종사자", 8: "장치·기계 조작 및 조립 종사자",
    9: "단순노무 종사자",
}


def wilson(successes: int, total: int, z: float = 1.959964) -> list[float]:
    if total <= 0:
        return [0.0, 0.0]
    p = successes / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return [round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4)]


def build() -> dict:
    df = pd.read_csv(SOURCE, low_memory=False)
    employed = df.employment_status_t.notna() & df.employment_status_t1.notna()
    work = df[employed & df.age_t.between(AGE_MIN, AGE_MAX) & df.moved_t1.eq(1)].copy()
    work["origin"] = pd.to_numeric(work.occupation_t, errors="coerce").floordiv(100)
    work["destination"] = pd.to_numeric(work.occupation_t1, errors="coerce").floordiv(100)
    work = work[work.origin.between(1, 9) & work.destination.between(1, 9)].copy()
    work[["origin", "destination"]] = work[["origin", "destination"]].astype(int)

    origins = {}
    for origin, group in work.groupby("origin"):
        counts = group.destination.value_counts().sort_values(ascending=False)
        total = int(counts.sum())
        destinations = []
        for destination, count in counts.items():
            count = int(count)
            destinations.append({
                "code": int(destination), "label": LABELS[int(destination)],
                "count": count, "share": round(count / total, 4),
                "ci95": wilson(count, total),
                "same_occupation_group": int(destination) == int(origin),
            })
        origins[str(origin)] = {
            "code": int(origin), "label": LABELS[int(origin)], "sample_n": total,
            "distinct_people": int(group.pid.nunique()), "destinations": destinations,
        }

    return {
        "version": 1,
        "method": "KLIPS 직장→직장 이직자의 직종 대분류 도착 빈도",
        "claim_type": "observed_transition_not_causal_effect",
        "population": {"age_min": AGE_MIN, "age_max": AGE_MAX, "move_rows": int(len(work)), "people": int(work.pid.nunique())},
        "source": "KLIPS 패널 전처리본",
        "occupation_standard": "KSCO 대분류 1~9",
        "origins": origins,
    }


def main() -> None:
    result = build()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[완료] {OUTPUT}")
    print(result["population"])


if __name__ == "__main__":
    main()
