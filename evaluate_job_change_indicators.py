"""이직의 재정·성장·삶의 질 결과변수 1차 검증.

이 스크립트는 모델 artifact나 서비스 API를 변경하지 않는다. 현재 보유한 패널에서
결과변수의 전후 관측 가능성, 이직/유지 표본 수, 단순 변화 차이와 cluster bootstrap
구간을 계산해 다음 모델링 단계의 사용 가능성을 판정한다.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from preprocess.build_klips_job_change_panel import build_panel


ROOT = Path(__file__).resolve().parent
CLEAN = ROOT / "data" / "clean"
REPORT_JSON = CLEAN / "job_change_indicator_validation.json"
REPORT_MD = ROOT / "docs" / "JOB_CHANGE_INDICATOR_VALIDATION.md"
SEED = 42


def build_yp_growth_panel(age_min: int = 20, age_max: int = 45) -> pd.DataFrame:
    yp = pd.read_csv(CLEAN / "yp_clean.csv", low_memory=False)
    required = {
        "person_id", "wave", "year", "age", "sex", "edu_level", "income_now",
        "firm_size", "emp_status", "changed_job", "satis_growth", "satis_future",
    }
    missing = sorted(required - set(yp.columns))
    if missing:
        raise ValueError(f"YP 성장 패널 필수 열 누락: {missing}")

    yp = yp.sort_values(["person_id", "wave"]).reset_index(drop=True)
    nxt = yp.groupby("person_id", sort=False).shift(-1)
    panel = pd.DataFrame({
        "pid": yp["person_id"],
        "wave_t": yp["wave"], "wave_t1": nxt["wave"],
        "year_t": yp["year"], "year_t1": nxt["year"],
        "age_t": yp["age"], "sex_t": yp["sex"], "edu_t": yp["edu_level"],
        "income_t": yp["income_now"], "firm_size_t": yp["firm_size"],
        "emp_status_t": yp["emp_status"],
        "moved_t1": nxt["changed_job"],
        "growth_t": yp["satis_growth"], "growth_t1": nxt["satis_growth"],
        "future_t": yp["satis_future"], "future_t1": nxt["satis_future"],
        "work_t": yp["satis_work"], "work_t1": nxt["satis_work"],
        "stability_t": yp["satis_stability"], "stability_t1": nxt["satis_stability"],
    })
    panel = panel[
        ((panel.wave_t1 - panel.wave_t) == 1)
        & ((panel.year_t1 - panel.year_t) == 1)
        & panel.age_t.between(age_min, age_max)
    ].dropna(subset=["moved_t1"])
    panel["moved_t1"] = panel["moved_t1"].astype(int)
    for stem in ("growth", "future", "work", "stability"):
        panel[f"{stem}_change"] = panel[f"{stem}_t1"] - panel[f"{stem}_t"]
    return panel.reset_index(drop=True)


def clustered_bootstrap_difference(
    df: pd.DataFrame,
    value_col: str,
    cluster_col: str = "pid",
    iterations: int = 500,
    seed: int = SEED,
) -> tuple[float | None, float | None]:
    usable = df[[cluster_col, "moved_t1", value_col]].dropna()
    if usable.empty or usable.moved_t1.nunique() < 2:
        return None, None
    ids = usable[cluster_col].drop_duplicates().to_numpy()
    id_index = {pid: i for i, pid in enumerate(ids)}
    sums = np.zeros((len(ids), 2), dtype=float)
    counts = np.zeros((len(ids), 2), dtype=int)
    for (pid, moved), part in usable.groupby([cluster_col, "moved_t1"]):
        i, j = id_index[pid], int(moved)
        sums[i, j] = float(part[value_col].sum())
        counts[i, j] = int(len(part))
    rng = np.random.default_rng(seed)
    estimates = []
    for _ in range(iterations):
        sampled = rng.integers(0, len(ids), size=len(ids))
        total_counts = counts[sampled].sum(axis=0)
        if np.all(total_counts > 0):
            means = sums[sampled].sum(axis=0) / total_counts
            estimates.append(float(means[1] - means[0]))
    if not estimates:
        return None, None
    return tuple(round(float(v), 4) for v in np.percentile(estimates, [2.5, 97.5]))


def summarize_metric(df: pd.DataFrame, value_col: str, label: str, scale: str) -> dict:
    usable = df[["pid", "moved_t1", value_col]].dropna()
    groups = {}
    for moved in (0, 1):
        values = usable.loc[usable.moved_t1 == moved, value_col]
        groups[str(moved)] = {
            "n": int(len(values)),
            "people": int(usable.loc[usable.moved_t1 == moved, "pid"].nunique()),
            "mean_change": round(float(values.mean()), 4) if len(values) else None,
            "median_change": round(float(values.median()), 4) if len(values) else None,
        }
    if not groups["0"]["n"] or not groups["1"]["n"]:
        diff = None
    else:
        diff = round(groups["1"]["mean_change"] - groups["0"]["mean_change"], 4)
    ci = clustered_bootstrap_difference(usable, value_col)
    moved_n = groups["1"]["n"]
    status = "모델 검증 가능" if moved_n >= 500 else ("보조 분석" if moved_n >= 100 else "근거 부족")
    return {
        "label": label, "column": value_col, "scale": scale,
        "groups": groups,
        "unadjusted_mean_difference_move_minus_stay": diff,
        "cluster_bootstrap_ci95": list(ci),
        "status": status,
        "causal": False,
    }


def reason_distribution() -> dict:
    goms = pd.read_csv(CLEAN / "goms_clean.csv", low_memory=False)
    yp = pd.read_csv(CLEAN / "yp_clean.csv", low_memory=False)

    def counts(df: pd.DataFrame, col: str) -> dict:
        if col not in df:
            return {"available": False}
        values = pd.to_numeric(df[col], errors="coerce").dropna()
        return {
            "available": True,
            "n": int(len(values)),
            "codes": {str(int(k)): int(v) for k, v in values.value_counts().sort_index().items()},
        }

    return {
        "goms_quit_reason": counts(goms, "quit_reason"),
        "goms_move_reason": counts(goms, "move_reason"),
        "yp_quit_reason": counts(yp, "quit_reason"),
        "decision": "코드별 표본은 존재하지만 공식 값 라벨을 자발/비자발/전환 유형으로 매핑하기 전에는 모델을 분리하지 않음",
    }


def validate() -> dict:
    klips, klips_quality = build_panel()
    yp = build_yp_growth_panel()
    klips = klips[klips.wage_outlier == 0].copy()

    indicators = {
        "financial_stability": [
            summarize_metric(klips, "wage_change_pct", "실질임금 변화율", "%"),
            summarize_metric(klips, "wage_down_t1", "소득 감소 여부", "0/1"),
        ],
        "growth_potential": [
            summarize_metric(yp, "growth_change", "자기발전 만족도 변화", "1~5점 변화"),
            summarize_metric(yp, "future_change", "장래성 만족도 변화", "1~5점 변화"),
            summarize_metric(yp, "work_change", "직무 만족도 변화", "1~5점 변화"),
        ],
        "quality_of_life": [
            summarize_metric(klips, "life_satisfaction_change", "삶의 만족도 변화", "원척도 변화"),
            summarize_metric(klips, "happiness_change", "행복도 변화", "원척도 변화"),
            summarize_metric(klips, "health_score_change", "건강점수 변화", "원척도 변화"),
            summarize_metric(klips, "wellbeing_index_change", "웰빙지수 변화", "원척도 변화"),
        ],
    }
    return {
        "scope": "20~45세, 연속 t→t+1 전이",
        "interpretation": "표본·방향성 1차 검증이며 혼재변수를 보정한 인과효과가 아님",
        "klips_panel": {
            "rows_after_wage_outlier_filter": int(len(klips)),
            "people": int(klips.pid.nunique()),
            "move_rows": int(klips.moved_t1.sum()),
            "source_quality_report": klips_quality,
        },
        "yp_growth_panel": {
            "rows": int(len(yp)), "people": int(yp.pid.nunique()),
            "move_rows": int(yp.moved_t1.sum()),
        },
        "indicators": indicators,
        "job_change_reasons": reason_distribution(),
        "next_gate": [
            "공식 코드북으로 퇴직·이직 사유 라벨을 매핑한다.",
            "개인 단위 train/test 분리와 이직/유지 overlap을 검증한다.",
            "혼재변수 보정 후에도 결과 방향과 구간이 유지되는지 확인한다.",
            "검증을 통과한 결과만 3개 상위 지표 계산에 사용한다.",
        ],
    }


def render_markdown(report: dict) -> str:
    title = {"financial_stability": "재정 안정도", "growth_potential": "성장 가능성", "quality_of_life": "삶의 질"}
    lines = [
        "# 이직 3지표 1차 검증", "",
        f"범위: {report['scope']}", "",
        f"> {report['interpretation']}", "",
        "## 표본", "",
        f"- KLIPS: {report['klips_panel']['rows_after_wage_outlier_filter']:,} 전이, "
        f"{report['klips_panel']['people']:,}명, 이직 {report['klips_panel']['move_rows']:,}건",
        f"- YP 성장 패널: {report['yp_growth_panel']['rows']:,} 전이, "
        f"{report['yp_growth_panel']['people']:,}명, 이직 {report['yp_growth_panel']['move_rows']:,}건",
        "", "## 지표별 결과", "",
        "| 상위 지표 | 결과변수 | 유지 n | 이직 n | 이직-유지 평균변화 차이 | 95% cluster bootstrap | 판정 |",
        "|---|---|---:|---:|---:|---|---|",
    ]
    for key, metrics in report["indicators"].items():
        for metric in metrics:
            ci = metric["cluster_bootstrap_ci95"]
            ci_text = "-" if ci[0] is None else f"{ci[0]:.3f} ~ {ci[1]:.3f}"
            diff = metric["unadjusted_mean_difference_move_minus_stay"]
            diff_text = "-" if diff is None else f"{diff:.3f}"
            lines.append(
                f"| {title[key]} | {metric['label']} | {metric['groups']['0']['n']:,} | "
                f"{metric['groups']['1']['n']:,} | {diff_text} | {ci_text} | {metric['status']} |"
            )
    lines += [
        "", "## 해석 제한", "",
        "- 위 차이는 이직자와 유지자의 원래 차이를 보정하지 않은 기술통계다.",
        "- 신뢰구간이 0을 벗어나도 이직의 인과효과라고 결론 내릴 수 없다.",
        "- 결과변수 척도 방향과 코드 라벨은 공식 코드북으로 한 번 더 확인해야 한다.",
        "- 이직 사유는 코드 표본이 있지만 공식 라벨 매핑 전까지 자발/비자발로 나누지 않는다.",
        "", "## 다음 검증 게이트", "",
    ]
    lines += [f"{i}. {item}" for i, item in enumerate(report["next_gate"], 1)]
    return "\n".join(lines) + "\n"


def main() -> None:
    report = validate()
    CLEAN.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_MD.write_text(render_markdown(report), encoding="utf-8")
    print(f"[완료] {REPORT_JSON}")
    print(f"[완료] {REPORT_MD}")
    for key, metrics in report["indicators"].items():
        print(f"[{key}] " + ", ".join(f"{m['label']} n(move)={m['groups']['1']['n']}" for m in metrics))


if __name__ == "__main__":
    main()
