"""이직 후보 지표의 과거 학습 → 최근 연도 검증."""

from __future__ import annotations

import json

from train_validate_job_change_models import ACTIVE_METRICS, DATASETS, ROOT, fit_metric, load_datasets


REPORT_JSON = ROOT / "data" / "clean" / "job_change_model_temporal_validation.json"
REPORT_MD = ROOT / "docs" / "JOB_CHANGE_MODEL_TEMPORAL_VALIDATION.md"
CANDIDATE_COLUMNS = {metric["column"] for metric in ACTIVE_METRICS}
CUTOFFS = {"klips": 2021, "yp": 2022}


def temporal_split(frame, cutoff: int, strict_people: bool = False):
    train = frame[frame.year_t <= cutoff].copy()
    test = frame[frame.year_t > cutoff].copy()
    if strict_people:
        test = test[~test.pid.isin(train.pid)].copy()
    if train.empty or test.empty:
        raise ValueError(f"시간 분리 후 표본 없음: cutoff={cutoff}, strict_people={strict_people}")
    return train, test


def verdict(metric: dict) -> str:
    ci = metric["cluster_bootstrap_ci95"]
    if metric["overlap_fraction"] < 0.8:
        return "overlap_insufficient"
    direction = metric.get("favorable_direction", "positive")
    if direction == "negative" and ci[1] < 0:
        return "favorable_association"
    if direction == "positive" and ci[0] > 0:
        return "favorable_association"
    if (direction == "negative" and ci[0] > 0) or (direction == "positive" and ci[1] < 0):
        return "adverse_association"
    return "inconclusive"


def run_temporal_validation() -> dict:
    frames = load_datasets()
    results = []
    for spec in (item for item in ACTIVE_METRICS if item["column"] in CANDIDATE_COLUMNS):
        dataset = spec["dataset"]
        cutoff = CUTOFFS[dataset]
        train, test = temporal_split(frames[dataset], cutoff)
        metric, _ = fit_metric(train, test, spec, DATASETS[dataset])
        metric.update({
            "protocol": "recent_year",
            "train_years": [int(train.year_t.min()), int(train.year_t.max())],
            "test_years": [int(test.year_t.min()), int(test.year_t.max())],
            "person_overlap": int(len(set(train.pid).intersection(test.pid))),
            "temporal_verdict": verdict(metric),
        })
        results.append(metric)

        # KLIPS는 최근 유입자만 남긴 더 엄격한 검증도 표본이 가능하다.
        if dataset == "klips" and spec["indicator"] == "financial_stability":
            strict_train, strict_test = temporal_split(frames[dataset], cutoff, strict_people=True)
            strict_metric, _ = fit_metric(strict_train, strict_test, spec, DATASETS[dataset])
            strict_metric.update({
                "protocol": "recent_year_new_people",
                "train_years": [int(strict_train.year_t.min()), int(strict_train.year_t.max())],
                "test_years": [int(strict_test.year_t.min()), int(strict_test.year_t.max())],
                "person_overlap": 0,
                "temporal_verdict": verdict(strict_metric),
            })
            results.append(strict_metric)

    passed = [
        m["column"] for m in results
        if m["protocol"] == "recent_year" and m["temporal_verdict"] == "favorable_association"
    ]
    return {
        "method": "과거 전이로 학습하고 이후 연도 전이로 홀드아웃 검증",
        "cutoffs": CUTOFFS,
        "results": results,
        "recent_year_passed": passed,
        "limitations": [
            "YP는 동일 코호트 3개 연도이므로 시간 테스트의 train/test 인물이 겹친다.",
            "YP의 신규 인물 일반화는 이전 5회 개인 단위 반복 검증으로 보완한다.",
            "KLIPS 신규 인물 검증은 표본이 작아 신뢰구간이 넓을 수 있다.",
            "관측자료 보정치이므로 검증 통과가 무작위실험 수준의 인과 확정을 뜻하지 않는다.",
        ],
    }


def render_markdown(report: dict) -> str:
    indicator = {
        "financial_stability": "재정 안정도",
        "growth_potential": "성장 가능성",
        "quality_of_life": "삶의 질",
    }
    protocol = {"recent_year": "최근 연도", "recent_year_new_people": "최근 연도·신규 인물"}
    lines = [
        "# 이직 후보 지표 연도 기준 검증", "", f"> {report['method']}", "",
        "## 결과", "",
        "| 지표 | 결과변수 | 검증 방식 | 학습 연도 | 테스트 연도 | 테스트 이직 n | 인물 중복 | overlap | 보정 효과 | 95% CI | 판정 |",
        "|---|---|---|---|---|---:|---:|---:|---:|---|---|",
    ]
    for m in report["results"]:
        ci = m["cluster_bootstrap_ci95"]
        lines.append(
            f"| {indicator[m['indicator']]} | {m['label']} | {protocol[m['protocol']]} | "
            f"{m['train_years'][0]}~{m['train_years'][1]} | {m['test_years'][0]}~{m['test_years'][1]} | "
            f"{m['test_move']:,} | {m['person_overlap']:,} | {m['overlap_fraction']:.1%} | "
            f"{m['adjusted_effect_move_minus_stay']:+.4f} | {ci[0]:+.4f} ~ {ci[1]:+.4f} | {m['temporal_verdict']} |"
        )
    lines += ["", "## 제한", "", *[f"- {item}" for item in report["limitations"]]]
    return "\n".join(lines) + "\n"


def main() -> None:
    report = run_temporal_validation()
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_MD.write_text(render_markdown(report), encoding="utf-8")
    print(f"[완료] {REPORT_JSON}")
    print(f"[완료] {REPORT_MD}")
    for metric in report["results"]:
        print(f"[{metric['protocol']}] {metric['label']}: {metric['adjusted_effect_move_minus_stay']:+.4f} {metric['cluster_bootstrap_ci95']} / {metric['temporal_verdict']}")


if __name__ == "__main__":
    main()
