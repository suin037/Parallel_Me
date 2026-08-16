"""이직 3지표 후보 모델의 반복 개인 단위 홀드아웃 검증."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from train_validate_job_change_models import (
    DATASETS,
    METRICS,
    ROOT,
    fit_metric,
    load_datasets,
    split_people,
)


SEEDS = [17, 29, 42, 73, 101]
REPORT_JSON = ROOT / "data" / "clean" / "job_change_model_robustness.json"
REPORT_MD = ROOT / "docs" / "JOB_CHANGE_MODEL_ROBUSTNESS.md"


def classify_stability(sign_rate: float, supported_rate: float, min_overlap: float) -> str:
    """배포가 아니라 다음 검증 단계 진입 여부를 위한 보수적 분류."""
    if min_overlap < 0.8:
        return "overlap 부족"
    if sign_rate >= 0.8 and supported_rate >= 0.8:
        return "안정 후보"
    if sign_rate >= 0.8 and supported_rate >= 0.4:
        return "방향 후보"
    return "근거 불충분"


def aggregate_metric(spec: dict, folds: list[dict]) -> dict:
    effects = np.array([fold["adjusted_effect_move_minus_stay"] for fold in folds], dtype=float)
    median = float(np.median(effects))
    reference_sign = 1 if median > 0 else -1 if median < 0 else 0
    signs = np.sign(effects)
    sign_rate = float(np.mean(signs == reference_sign)) if reference_sign else 0.0
    supported_rate = float(np.mean([fold["direction_supported"] for fold in folds]))
    min_overlap = float(min(fold["overlap_fraction"] for fold in folds))
    return {
        **{k: spec[k] for k in ("dataset", "indicator", "column", "label", "kind")},
        "folds": folds,
        "effect_median": round(median, 4),
        "effect_min": round(float(effects.min()), 4),
        "effect_max": round(float(effects.max()), 4),
        "same_direction_rate": round(sign_rate, 4),
        "ci_excludes_zero_rate": round(supported_rate, 4),
        "minimum_overlap": round(min_overlap, 4),
        "stability": classify_stability(sign_rate, supported_rate, min_overlap),
    }


def run_repeated_validation(seeds: list[int] | None = None) -> dict:
    seeds = seeds or SEEDS
    frames = load_datasets()
    all_folds = {spec["column"]: [] for spec in METRICS}

    for seed in seeds:
        splits = {name: split_people(frame, seed=seed) for name, frame in frames.items()}
        for spec in METRICS:
            train, test = splits[spec["dataset"]]
            metric, _ = fit_metric(train, test, spec, DATASETS[spec["dataset"]])
            all_folds[spec["column"]].append({
                "seed": seed,
                "effect": metric["adjusted_effect_move_minus_stay"],
                "ci95": metric["cluster_bootstrap_ci95"],
                "direction_supported": metric["direction_supported"],
                "overlap": metric["overlap_fraction"],
                "test_move": metric["test_move"],
                "predictive_test": metric["predictive_test"],
                # aggregate_metric과 기존 보고 포맷을 함께 쓰기 위한 키
                "adjusted_effect_move_minus_stay": metric["adjusted_effect_move_minus_stay"],
                "overlap_fraction": metric["overlap_fraction"],
            })

    metrics = [aggregate_metric(spec, all_folds[spec["column"]]) for spec in METRICS]
    return {
        "method": f"개인 단위 75/25 홀드아웃 {len(seeds)}회 반복; seeds={seeds}",
        "interpretation": "관측 혼재변수 보정 결과의 분할 안정성 검사이며 인과 확정 또는 배포 승인이 아님",
        "criteria": {
            "안정 후보": "동일 방향 80% 이상, CI가 0을 제외한 반복 80% 이상, 최소 overlap 80% 이상",
            "방향 후보": "동일 방향 80% 이상, CI가 0을 제외한 반복 40% 이상, 최소 overlap 80% 이상",
            "근거 불충분": "위 기준 미충족",
        },
        "metrics": metrics,
        "next_gate": [
            "안정·방향 후보에 대해 연도 기준 검증 수행",
            "선형 모델과 비선형 모델의 효과 추정 민감도 비교",
            "공식 코드북 척도 방향 확인",
            "최종 통과 지표만 API 후보 artifact로 승격",
        ],
    }


def render_markdown(report: dict) -> str:
    titles = {"financial_stability": "재정 안정도", "growth_potential": "성장 가능성", "quality_of_life": "삶의 질"}
    lines = [
        "# 이직 3지표 반복 검증", "", f"> {report['interpretation']}", "",
        "## 방법", "", report["method"], "",
        "## 결과", "",
        "| 지표 | 결과변수 | 효과 중앙값 | 반복 범위 | 동일 방향 | CI 0 제외 | 최소 overlap | 판정 |",
        "|---|---|---:|---|---:|---:|---:|---|",
    ]
    for metric in report["metrics"]:
        lines.append(
            f"| {titles[metric['indicator']]} | {metric['label']} | {metric['effect_median']:+.4f} | "
            f"{metric['effect_min']:+.4f} ~ {metric['effect_max']:+.4f} | "
            f"{metric['same_direction_rate']:.0%} | {metric['ci_excludes_zero_rate']:.0%} | "
            f"{metric['minimum_overlap']:.1%} | {metric['stability']} |"
        )
    lines += [
        "", "## 판정 기준", "",
        *[f"- **{key}**: {value}" for key, value in report["criteria"].items()],
        "", "## 주의", "",
        "- 반복 분할에서 안정적이어도 관측되지 않은 혼재변수의 영향은 남는다.",
        "- 삶의 질처럼 근거가 불충분한 지표에는 개인별 상승·하락 수치를 출력하지 않는다.",
        "", "## 다음 게이트", "",
        *[f"{i}. {item}" for i, item in enumerate(report["next_gate"], 1)],
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    report = run_repeated_validation()
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_MD.write_text(render_markdown(report), encoding="utf-8")
    print(f"[완료] {REPORT_JSON}")
    print(f"[완료] {REPORT_MD}")
    for metric in report["metrics"]:
        print(
            f"[{metric['indicator']}] {metric['label']}: {metric['effect_median']:+.4f} "
            f"({metric['effect_min']:+.4f}~{metric['effect_max']:+.4f}) / {metric['stability']}"
        )


if __name__ == "__main__":
    main()
