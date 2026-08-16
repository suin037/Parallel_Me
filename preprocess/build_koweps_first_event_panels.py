"""KOWEPS 레지스트리 기반 최초 사건 패널과 기술통계 보고서 생성."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "koweps" / "long" / "koweps_hp01_20_long_260331.dta"
OUT = ROOT / "data" / "clean" / "koweps"
PUBLIC_ARTIFACT = ROOT / "backend" / "models" / "artifacts" / "koweps_scenario_evidence.json"
REGISTRY_PATH = Path(__file__).with_name("koweps_domain_registry.json")
DICTIONARY = OUT / "koweps_variable_dictionary.csv"


def load_registry() -> dict:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def selected_specs(registry: dict) -> dict:
    return {
        key: spec for key, spec in registry["scenarios"].items()
        if spec.get("status") == "ready_for_panel"
    }


def required_columns(registry: dict) -> list[str]:
    specs = selected_specs(registry)
    return list(dict.fromkeys([
        *registry["core"], *registry["covariates"],
        *[spec["source"] for spec in specs.values()],
        *[spec["variable"] for spec in registry["outcomes"].values()],
    ]))


def load_data(registry: dict) -> pd.DataFrame:
    data = pd.read_stata(RAW, columns=required_columns(registry), convert_categoricals=False)
    for column in data.select_dtypes(include=["number"]).columns:
        if column not in {"year", "wv", "h_g4"}:
            data[column] = data[column].mask(data[column] < 0)
    for column, codes in registry.get("missing_values", {}).items():
        if column in data:
            data[column] = data[column].mask(data[column].isin(codes))
    data["age"] = data["year"] - data["h_g4"]
    return data.sort_values(["h_pid", "wv"]).reset_index(drop=True)


def make_event(data: pd.DataFrame, spec: dict) -> pd.Series:
    source = spec["source"]
    current = data[source]
    grouped = data.groupby("h_pid", sort=False)
    previous = grouped[source].shift(1)
    consecutive = data["wv"].sub(grouped["wv"].shift(1)).eq(1)
    if spec["mode"] == "yes":
        return current.eq(spec.get("yes_value", 1)).where(current.notna()).astype("float64")
    if spec["mode"] == "change":
        known = consecutive & current.notna() & previous.notna()
        result = current.ne(previous).where(known).astype("float64")
        if spec.get("exclude_waves"):
            result = result.mask(data["wv"].isin(spec["exclude_waves"]))
        return result
    if spec["mode"] == "positive_entry":
        known = consecutive & current.notna() & previous.notna()
        event = current.gt(0) & previous.le(0)
        stayed = current.le(0) & previous.le(0)
        return event.where(known & (event | stayed)).astype("float64")
    if spec["mode"] in {"increase", "decrease"}:
        known = consecutive & current.notna() & previous.notna()
        event = current.gt(previous) if spec["mode"] == "increase" else current.lt(previous)
        # 반대 방향 변화는 이 질문의 유지 비교군으로 넣지 않는다.
        stayed = current.eq(previous)
        return event.where(known & (event | stayed)).astype("float64")
    if spec["mode"] == "transition":
        at_risk = consecutive & previous.isin(spec["from_values"]) & current.notna()
        event = current.isin(spec["to_values"])
        stayed = current.isin(spec["from_values"])
        # 다른 상태로 이동한 행은 이 A/B 질문의 비교군이 아니다.
        return event.where(at_risk & (event | stayed)).astype("float64")
    raise ValueError(f"first-event panel에서 지원하지 않는 mode: {spec['mode']}")


def first_baselines(data: pd.DataFrame, event: pd.Series, age_range: list[int]) -> pd.DataFrame:
    grouped = data.groupby("h_pid", sort=False)
    has_pre = data["wv"].sub(grouped["wv"].shift(1)).eq(1)
    eligible = data["age"].between(*age_range) & event.notna() & has_pre
    events = data.loc[eligible & event.eq(1)].copy()
    events["treatment"] = 1
    events = events.sort_values(["h_pid", "wv"]).drop_duplicates("h_pid", keep="first")

    # 비교군은 대상 연령 동안 사건이 한 번도 없었던 사람만 사용한다. 최초 관측 한 행을
    # 선택하되, 이는 아직 매칭 전 기술통계 비교군이라는 한계를 보고서에 명시한다.
    ever_event = set(data.loc[eligible & event.eq(1), "h_pid"])
    controls = data.loc[eligible & ~data["h_pid"].isin(ever_event) & event.eq(0)].copy()
    controls["treatment"] = 0
    controls = controls.sort_values(["h_pid", "wv"]).drop_duplicates("h_pid", keep="first")
    return pd.concat([events, controls], ignore_index=True).sort_values(["treatment", "h_pid"])


def attach_outcomes(data: pd.DataFrame, baselines: pd.DataFrame, registry: dict) -> pd.DataFrame:
    lookup = data.set_index(["h_pid", "wv"])
    result = baselines.copy()
    pre_keys = pd.MultiIndex.from_arrays([result["h_pid"], result["wv"] - 1])
    for column in registry["covariates"]:
        result[f"{column}_pre"] = lookup[column].reindex(pre_keys).to_numpy()
    for horizon in registry["horizons"]:
        keys = pd.MultiIndex.from_arrays([result["h_pid"], result["wv"] + horizon])
        for name, meta in registry["outcomes"].items():
            result[f"{name}_t{horizon}"] = lookup[meta["variable"]].reindex(keys).to_numpy()
    return result


def numeric_summary(series: pd.Series) -> dict:
    values = pd.to_numeric(series, errors="coerce").dropna()
    if values.empty:
        return {"n": 0}
    return {
        "n": int(len(values)), "mean": round(float(values.mean()), 4),
        "p25": round(float(values.quantile(.25)), 4),
        "median": round(float(values.median()), 4),
        "p75": round(float(values.quantile(.75)), 4),
    }


def summarize(panel: pd.DataFrame, registry: dict, key: str, spec: dict) -> dict:
    report = {
        "scenario": key, "label": spec["label"], "source": spec["source"],
        "event_people": int(panel["treatment"].eq(1).sum()),
        "control_people": int(panel["treatment"].eq(0).sum()),
        "control_definition": "25~35세 관측 중 사건이 한 번도 없었던 사람의 최초 eligible row; 매칭 전",
        "baseline": {}, "followup": {},
    }
    for column in ["age", *[f"{name}_pre" for name in registry["covariates"]]]:
        if column in panel:
            report["baseline"][column] = {
                str(group): numeric_summary(block[column])
                for group, block in panel.groupby("treatment")
            }
    for horizon in registry["horizons"]:
        report["followup"][str(horizon)] = {}
        for name in registry["outcomes"]:
            column = f"{name}_t{horizon}"
            report["followup"][str(horizon)][name] = {
                str(group): numeric_summary(block[column])
                for group, block in panel.groupby("treatment")
            }
    return report


def coding_audit(data: pd.DataFrame, registry: dict) -> dict:
    dictionary = pd.read_csv(DICTIONARY, encoding="utf-8-sig").fillna("").set_index("variable")
    rows = {}
    for column in required_columns(registry):
        series = data[column]
        meta = dictionary.loc[column] if column in dictionary.index else {}
        by_wave = {}
        for wave, block in data.groupby("wv"):
            values = block[column].dropna()
            by_wave[str(int(wave))] = {
                "n": int(len(values)),
                "min": None if values.empty else float(values.min()),
                "max": None if values.empty else float(values.max()),
                "unique": int(values.nunique()),
            }
        rows[column] = {
            "label": meta.get("label", "") if hasattr(meta, "get") else "",
            "question": meta.get("question", "") if hasattr(meta, "get") else "",
            "waves_declared": meta.get("waves", "") if hasattr(meta, "get") else "",
            "non_null_n": int(series.notna().sum()),
            "missing_rate": round(float(series.isna().mean()), 6),
            "top_values": {str(k): int(v) for k, v in series.value_counts(dropna=False).head(15).items()},
            "by_wave": by_wave,
        }
    return {"claim_limit": "코드북 문항과 실측 분포 감사. 값 의미가 비어 있으면 추론하지 않음", "variables": rows}


def build() -> dict:
    registry = load_registry()
    data = load_data(registry)
    audit = coding_audit(data, registry)
    (OUT / "koweps_core_variable_coding_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    reports = {}
    for key, spec in selected_specs(registry).items():
        event = make_event(data, spec)
        baselines = first_baselines(data, event, registry["target_age"])
        panel = attach_outcomes(data, baselines, registry)
        safe_name = key.replace(".", "_")
        try:
            panel.to_parquet(OUT / f"koweps_{safe_name}_first_event_panel.parquet", index=False)
        except ImportError:
            # API는 아래 비식별 집계 JSON만 사용한다. pyarrow가 없는 개발 환경에서도
            # 집계 artifact 재생성을 막지 않고 개인행 parquet만 생략한다.
            print(f"[warn] parquet 엔진 없음 — {safe_name} 개인행 저장 생략")
        reports[key] = summarize(panel, registry, key, spec)
    result = {
        "target_age": registry["target_age"], "horizons": registry["horizons"],
        "claim_limit": "최초 사건 기술통계 패널. 매칭·가중·시간검증 전이며 인과효과나 개인예측이 아님",
        "reports": reports,
    }
    (OUT / "koweps_first_event_panel_report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # 개인 행은 data/clean에만 두고, API 배포에는 재식별 불가능한 집계치만 포함한다.
    PUBLIC_ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    PUBLIC_ARTIFACT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> None:
    result = build()
    for key, report in result["reports"].items():
        print(f"[{key}] 사건 {report['event_people']:,}명 / 비교 {report['control_people']:,}명")
        for horizon, outcomes in report["followup"].items():
            lo = min(item.get("1", {}).get("n", 0) for item in outcomes.values())
            hi = max(item.get("1", {}).get("n", 0) for item in outcomes.values())
            print(f"  +{horizon}차 사건군 결과 표본 {lo:,}~{hi:,}")


if __name__ == "__main__":
    main()
