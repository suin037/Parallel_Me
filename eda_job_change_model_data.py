"""현재 이직 후보 모델이 실제 사용하는 KLIPS/YP 학습표의 재현 가능한 EDA.

산출물:
  data/clean/job_change_eda_summary.json
  data/clean/job_change_eda_missingness.csv
  data/clean/job_change_eda_group_balance.csv
  data/clean/job_change_eda_outcomes.csv
  docs/JOB_CHANGE_DATA_EDA.md
  docs/assets/job_change_eda_*.png (matplotlib 사용 가능 시)
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from train_validate_job_change_models import DATASETS, METRICS, load_datasets


ROOT = Path(__file__).resolve().parent
CLEAN = ROOT / "data" / "clean"
DOCS = ROOT / "docs"
ASSETS = DOCS / "assets"


def _number(value):
    if pd.isna(value):
        return None
    if isinstance(value, (np.integer, int)):
        return int(value)
    return round(float(value), 4)


def _smd(a: pd.Series, b: pd.Series) -> float | None:
    a = pd.to_numeric(a, errors="coerce").dropna()
    b = pd.to_numeric(b, errors="coerce").dropna()
    if len(a) < 2 or len(b) < 2:
        return None
    pooled = np.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2)
    return _number((b.mean() - a.mean()) / pooled) if pooled > 0 else 0.0


def _categorical_gap(df: pd.DataFrame, col: str) -> float | None:
    tab = pd.crosstab(df[col].astype("string").fillna("__MISSING__"), df.moved_t1, normalize="columns")
    if not {0, 1}.issubset(tab.columns):
        return None
    return _number((tab[1] - tab[0]).abs().max())


def dataset_eda(name: str, df: pd.DataFrame) -> tuple[dict, list[dict], list[dict], list[dict]]:
    spec = DATASETS[name]
    numeric = [c for c in spec["numeric"] if c in df]
    categorical = [c for c in spec["categorical"] if c in df]
    outcomes = [m for m in METRICS if m["dataset"] == name and m["column"] in df]
    relevant = list(dict.fromkeys(["pid", "year_t", "wave_t", "moved_t1", *numeric, *categorical,
                                   *[m["baseline"] for m in outcomes], *[m["column"] for m in outcomes]]))

    missing_rows, balance_rows, outcome_rows = [], [], []
    for col in relevant:
        if col not in df:
            continue
        stay_missing = df.loc[df.moved_t1.eq(0), col].isna().mean()
        move_missing = df.loc[df.moved_t1.eq(1), col].isna().mean()
        missing_rows.append({
            "dataset": name, "column": col, "dtype": str(df[col].dtype),
            "non_null_n": int(df[col].notna().sum()),
            "missing_n": int(df[col].isna().sum()),
            "missing_rate": _number(df[col].isna().mean()),
            "stay_missing_rate": _number(stay_missing),
            "move_missing_rate": _number(move_missing),
            "missing_rate_gap_move_minus_stay": _number(move_missing - stay_missing),
            "unique_n": int(df[col].nunique(dropna=True)),
        })

    stay, move = df[df.moved_t1.eq(0)], df[df.moved_t1.eq(1)]
    for col in numeric:
        balance_rows.append({
            "dataset": name, "feature": col, "type": "numeric",
            "stay_n": int(stay[col].notna().sum()), "move_n": int(move[col].notna().sum()),
            "stay_mean": _number(pd.to_numeric(stay[col], errors="coerce").mean()),
            "move_mean": _number(pd.to_numeric(move[col], errors="coerce").mean()),
            "standardized_difference": _smd(stay[col], move[col]),
            "max_category_rate_gap": None,
        })
    for col in categorical:
        balance_rows.append({
            "dataset": name, "feature": col, "type": "categorical",
            "stay_n": int(stay[col].notna().sum()), "move_n": int(move[col].notna().sum()),
            "stay_mean": None, "move_mean": None, "standardized_difference": None,
            "max_category_rate_gap": _categorical_gap(df, col),
        })

    for metric in outcomes:
        col = metric["column"]
        for moved, group in ((0, stay), (1, move)):
            values = pd.to_numeric(group[col], errors="coerce").dropna()
            outcome_rows.append({
                "dataset": name, "indicator": metric["indicator"], "outcome": col,
                "label": metric["label"], "moved": moved, "n": int(len(values)),
                "missing_rate": _number(group[col].isna().mean()),
                "mean": _number(values.mean()), "std": _number(values.std()),
                "p01": _number(values.quantile(.01)), "p25": _number(values.quantile(.25)),
                "median": _number(values.median()), "p75": _number(values.quantile(.75)),
                "p99": _number(values.quantile(.99)),
            })

    by_year = []
    if "year_t" in df:
        for year, group in df.groupby("year_t", dropna=False):
            by_year.append({"year": _number(year), "rows": int(len(group)),
                            "people": int(group.pid.nunique()), "move_rate": _number(group.moved_t1.mean())})

    numeric_summary = {}
    for col in numeric:
        s = pd.to_numeric(df[col], errors="coerce")
        numeric_summary[col] = {
            "min": _number(s.min()), "p01": _number(s.quantile(.01)), "median": _number(s.median()),
            "mean": _number(s.mean()), "p99": _number(s.quantile(.99)), "max": _number(s.max()),
            "zero_rate": _number(s.eq(0).mean()),
        }

    categorical_summary = {}
    for col in categorical:
        counts = df[col].astype("string").fillna("__MISSING__").value_counts(dropna=False)
        categorical_summary[col] = {
            "levels": int(len(counts)),
            "top": [{"value": str(k), "n": int(v), "rate": _number(v / len(df))}
                    for k, v in counts.head(10).items()],
        }

    per_person = df.groupby("pid").size()
    move_per_person = df.groupby("pid").moved_t1.sum()
    info = {
        "rows": int(len(df)), "columns": int(df.shape[1]), "people": int(df.pid.nunique()),
        "move_rows": int(df.moved_t1.sum()), "move_rate": _number(df.moved_t1.mean()),
        "duplicate_pid_wave": int(df.duplicated(["pid", "wave_t"]).sum()) if "wave_t" in df else None,
        "invalid_target_values": sorted(str(x) for x in set(df.moved_t1.dropna().unique()) - {0, 1}),
        "transitions_per_person": {
            "mean": _number(per_person.mean()), "median": _number(per_person.median()),
            "p95": _number(per_person.quantile(.95)), "max": int(per_person.max()),
        },
        "people_with_any_move": int(move_per_person.gt(0).sum()),
        "people_with_repeated_moves": int(move_per_person.gt(1).sum()),
        "years": by_year,
        "numeric": numeric_summary,
        "categorical": categorical_summary,
    }
    return info, missing_rows, balance_rows, outcome_rows


def make_plots(frames: dict[str, pd.DataFrame]) -> list[str]:
    try:
        import matplotlib.pyplot as plt
    except Exception:
        return []
    ASSETS.mkdir(parents=True, exist_ok=True)
    made = []
    for name, df in frames.items():
        fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
        yearly = df.groupby("year_t").moved_t1.agg(["mean", "size"]).reset_index()
        axes[0].plot(yearly.year_t, yearly["mean"] * 100, marker="o", linewidth=1.8)
        axes[0].set(title=f"{name.upper()} move rate by year", xlabel="year", ylabel="move rate (%)")
        axes[0].grid(alpha=.25)
        miss_cols = list(dict.fromkeys([*DATASETS[name]["numeric"], *DATASETS[name]["categorical"],
                                       *[m["column"] for m in METRICS if m["dataset"] == name]]))
        rates = df[[c for c in miss_cols if c in df]].isna().mean().sort_values()
        axes[1].barh(rates.index, rates.values * 100)
        axes[1].set(title="Model-column missingness", xlabel="missing (%)")
        fig.tight_layout()
        path = ASSETS / f"job_change_eda_{name}.png"
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        made.append(str(path.relative_to(ROOT)).replace("\\", "/"))
    return made


def render_markdown(summary: dict, missing: pd.DataFrame, balance: pd.DataFrame,
                    outcomes: pd.DataFrame) -> str:
    lines = [
        "# 현재 이직 모델 학습 데이터 EDA", "",
        "> 모델 입력 직전 데이터 기준. KLIPS는 `wage_outlier=0` 필터 후, YP는 연속 연도 전이표 생성 후 분석했다.", "",
        "## 데이터 구성", "",
        "| 데이터 | 담당 지표 | 행 | 사람 | 이직 행 | 이직률 | 1인당 전이(중앙값) |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    roles = {"klips": "경제적 안정도·삶의 질", "yp": "성장 가능성"}
    for name, d in summary["datasets"].items():
        lines.append(f"| {name.upper()} | {roles[name]} | {d['rows']:,} | {d['people']:,} | "
                     f"{d['move_rows']:,} | {d['move_rate']:.1%} | {d['transitions_per_person']['median']:.1f} |")

    lines += ["", "## 결과변수 기술통계", "",
              "| 데이터 | 결과변수 | 유지 n | 이직 n | 유지 평균 | 이직 평균 | 이직 결측률 |",
              "|---|---|---:|---:|---:|---:|---:|"]
    for (ds, label), part in outcomes.groupby(["dataset", "label"], sort=False):
        s = part.set_index("moved")
        lines.append(f"| {ds.upper()} | {label} | {int(s.loc[0,'n']):,} | {int(s.loc[1,'n']):,} | "
                     f"{s.loc[0,'mean']:.3f} | {s.loc[1,'mean']:.3f} | {s.loc[1,'missing_rate']:.1%} |")

    flagged_missing = missing[missing.missing_rate >= .2].sort_values("missing_rate", ascending=False)
    flagged_missing_gap = missing[missing.missing_rate_gap_move_minus_stay.abs() >= .1].sort_values(
        "missing_rate_gap_move_minus_stay", key=lambda s: s.abs(), ascending=False)
    flagged_num = balance[(balance.type == "numeric") & balance.standardized_difference.abs().ge(.1)]
    flagged_cat = balance[(balance.type == "categorical") & balance.max_category_rate_gap.ge(.1)]
    lines += ["", "## 주요 품질 경고", ""]
    if len(flagged_missing):
        lines.append("- 결측률 20% 이상: " + ", ".join(
            f"{r.dataset.upper()}.{r.column} {r.missing_rate:.1%}" for r in flagged_missing.itertuples()))
    else:
        lines.append("- 모델 열 중 결측률 20% 이상인 열은 없다.")
    if len(flagged_missing_gap):
        lines.append("- 이직/유지 결측률 차이 ≥10%p: " + ", ".join(
            f"{r.dataset.upper()}.{r.column} {r.missing_rate_gap_move_minus_stay:+.1%}p"
            for r in flagged_missing_gap.itertuples()))
    if len(flagged_num):
        lines.append("- 이직/유지 간 표준화 차이 |SMD|≥0.1: " + ", ".join(
            f"{r.dataset.upper()}.{r.feature} {r.standardized_difference:+.2f}" for r in flagged_num.itertuples()))
    if len(flagged_cat):
        lines.append("- 범주 비율 최대 차이 ≥10%p: " + ", ".join(
            f"{r.dataset.upper()}.{r.feature} {r.max_category_rate_gap:.1%}" for r in flagged_cat.itertuples()))
    for name, d in summary["datasets"].items():
        rates = [y["move_rate"] for y in d["years"] if y["move_rate"] is not None]
        if rates:
            lines.append(f"- {name.upper()} 연도별 이직률 범위: {min(rates):.1%}~{max(rates):.1%}")
        if d["duplicate_pid_wave"]:
            lines.append(f"- {name.upper()} pid-wave 중복 {d['duplicate_pid_wave']:,}건")
    yp_age = summary["datasets"]["yp"]["numeric"]["age_t"]
    lines.append(f"- YP의 실제 연령 범위는 {yp_age['min']:.0f}~{yp_age['max']:.0f}세라서 31~45세 성장 예측으로 일반화할 수 없다.")

    lines += ["", "## 모델링 해석", "",
              "- 동일 인물이 여러 연도에 반복 등장하므로 행 단위 무작위 분리는 누수다. 현재처럼 pid 단위 분리를 유지해야 한다.",
              "- 이직률이 낮고 연도별로 변하므로 정확도보다 ROC-AUC·Brier·overlap과 연도 외부검증을 함께 봐야 한다.",
              "- `*_change`는 결과변수이고 `*_t1`은 미래 정보다. 둘 다 입력 피처로 사용하면 안 된다.",
              "- 이직/유지의 사전 특성 차이가 크면 단순 평균 차이가 아니라 propensity/AIPW 보정이 필요하다.",
              "- 성장·삶의 질은 주관척도 변화량이므로 척도 방향, 천장효과, 회귀-평균 효과를 추가 확인해야 한다.",
              "", "## EDA 결론과 즉시 조치", "",
              "1. **KLIPS 타깃 코호트 재정의:** 이직 행 중 약 42%는 t 시점 직업정보가 통째로 없다. "
              "현재 삶의 질 모델에는 실업→취업 전이가 이직과 섞일 수 있으므로, t와 t+1 모두 취업 상태인 직장 간 이동만 별도 추출해야 한다.",
              "2. **YP 분석대상 명시:** 성장 문항은 전체 전이의 약 36%에서만 전후 관측된다. 결과가 있는 취업자 코호트와 "
              "전체 코호트를 분리하고, 관측 여부를 만드는 선택편향을 검증해야 한다.",
              "3. **연령 적용범위 제한:** YP 성장 표본은 실제 20~30세뿐이다. 데이터 보강 전까지 성장 결과를 31세 이상에게 일반화하지 않는다.",
              "4. **결측을 단순 대체하지 않기:** 기업규모와 고용 관련 결측은 무작위 결측이 아니다. 고용상태 필터·결측 사유 범주·완전사례 민감도 분석을 비교한다.",
              "5. **그 다음 재학습:** 위 코호트 수정 후 3지표를 다시 학습하고 기존 결과와 표본 수·효과 방향·시간검증을 비교한다.",
              "", "## 생성 파일", "",
              "- `data/clean/job_change_eda_summary.json`", "- `data/clean/job_change_eda_missingness.csv`",
              "- `data/clean/job_change_eda_group_balance.csv`", "- `data/clean/job_change_eda_outcomes.csv`",
              "- `docs/assets/job_change_eda_klips.png`, `docs/assets/job_change_eda_yp.png`", ""]
    return "\n".join(lines)


def main() -> None:
    frames = load_datasets()
    summary = {"scope": "current model-ready frames", "datasets": {}, "plots": []}
    missing_rows, balance_rows, outcome_rows = [], [], []
    for name, frame in frames.items():
        info, miss, bal, out = dataset_eda(name, frame)
        summary["datasets"][name] = info
        missing_rows += miss
        balance_rows += bal
        outcome_rows += out
    summary["plots"] = make_plots(frames)

    missing = pd.DataFrame(missing_rows)
    balance = pd.DataFrame(balance_rows)
    outcomes = pd.DataFrame(outcome_rows)
    CLEAN.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)
    (CLEAN / "job_change_eda_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    missing.to_csv(CLEAN / "job_change_eda_missingness.csv", index=False, encoding="utf-8-sig")
    balance.to_csv(CLEAN / "job_change_eda_group_balance.csv", index=False, encoding="utf-8-sig")
    outcomes.to_csv(CLEAN / "job_change_eda_outcomes.csv", index=False, encoding="utf-8-sig")
    (DOCS / "JOB_CHANGE_DATA_EDA.md").write_text(
        render_markdown(summary, missing, balance, outcomes), encoding="utf-8")
    print(json.dumps({name: {k: d[k] for k in ("rows", "people", "move_rows", "move_rate")}
                      for name, d in summary["datasets"].items()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
