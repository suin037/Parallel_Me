"""서빙 중인 모델 아티팩트의 단일 명세(manifest)를 만든다.

## 왜 필요한가
`training_report.json` 은 `train_models.py`(GOMS 단면) 가 쓰는 **그 스크립트만의** 리포트다.
그런데 실제 서빙은 연령대에 따라 `econml_yp.pkl` / `econml_klips.pkl` 을 고르고
(`backend/models/econml_model.py`), 생존모델도 마찬가지다. 그래서 training_report 만 보면
"지금 무엇이 서빙되고 있고 그 성능이 얼마인지" 를 알 수 없다 — 실제로 두 파일의 내용이
서로 어긋나 있었다.

이 스크립트는 artifacts/ 에 **실제로 존재하는 파일을 열어** 각자의 출처·표본수·핵심
성능지표를 뽑고, 라우팅 규칙과 학습 데이터 빈티지까지 한 파일에 모은다.
`/health` 가 이 파일을 읽어 런타임에도 같은 내용을 노출한다.

사용법:
    python scripts/build_artifact_manifest.py
출력:
    backend/models/artifacts/manifest.json
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import joblib

ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS = ROOT / "backend/models/artifacts"

# 파일 → (레이어, 역할). 서빙 라우팅은 아래 ROUTING 에 따로 적는다.
KNOWN = {
    "knn.pkl":            ("L2", "유사인물 매칭 (GOMS 단면, 전공 포함)"),
    "knn_yp.pkl":         ("L2", "유사인물 매칭 (YP 청년패널)"),
    "econml.pkl":         ("L3", "이직→소득 인과효과 (GOMS 단면, 최후 폴백)"),
    "econml_klips.pkl":   ("L3", "이직→소득 인과효과 (KLIPS 종단)"),
    "econml_yp.pkl":      ("L3", "이직→소득 인과효과 (YP 청년패널 종단)"),
    "econml_klips_startup.pkl": ("L3", "창업(임금근로→자영)→소득 인과효과 (KLIPS 종단)"),
    "econml_klips_break.pkl": ("L3", "쉬어가기(자발 퇴직 후 2개월 이상 공백)→소득 인과효과 (KLIPS 종단)"),
    "lifelines.pkl":      ("L4", "재직 생존분석 (GOMS 폴백)"),
    "lifelines_klips.pkl": ("L4", "재직 생존분석 (KLIPS 스펠)"),
    "lifelines_yp.pkl":   ("L4", "재직 생존분석 (YP 스펠)"),
    "lifelines_klips_startup.pkl": ("L4", "자영(창업) 상태 이탈 생존분석 (KLIPS 자영 스펠)"),
    "lifelines_klips_break.pkl": ("L4", "복귀까지 걸리는 기간 (KLIPS 직업력 공백 스펠)"),
    "layer1_lookup.pkl":  ("L1", "룰베이스 생활지표 조회표"),
    "encoders.pkl":       ("-",  "GOMS 인코더/중앙값 (knn.pkl·econml.pkl 전용)"),
}

# backend/models/*.py 의 _select() 와 같은 규칙. 코드가 바뀌면 여기도 갱신할 것.
ROUTING = {
    "treatment": "선택 유형 → treatment: 이직=move / 창업=startup / 쉬어가기=break / "
                 "진학=매핑 없음(표본 부족)",
    "L2 (knn)": "이직에만 적용. age ≤ 31 이면 GOMS + YP 를 절반씩 섞고, 그 외엔 GOMS 단독",
    "L3 (econml)": "move: age ≤ 31 → yp → klips → goms, 그 외 → klips → yp → goms / "
                   "startup: klips 단독(연령 라우팅 대상 없음) / break: klips 단독",
    "L4 (lifelines)": "move: age ≤ 31 → yp → klips → goms, 그 외 → klips → yp → goms / "
                      "startup: klips 자영 스펠 단독 / "
                      "break: klips 공백 스펠 단독. **이벤트가 '복귀' 라 방향이 반대** — "
                      "곡선을 그대로 후회 리스크로 부르면 뒤집힌다(core.py 의 return_timeline 참조)",
    "동적효과": "dynamic_effects.json 의 상대시간별 ATE 로 연차별 효과·CI 밴드 구성 "
                "(관측 밖 연차는 마지막 관측값 유지 + extrapolated 표시)",
    "L5 (궤적 매칭)": "가중 z-거리 + 직종 목적변수 인코딩. 요청에 없는 항목은 거리에서 제외"
                     "(중앙값 대체 안 함). 가중치는 scripts/eval_matching.py --tune 로 탐색",
    "3지표": "indicator_reference.json 의 나이대별 분포에 대는 백분위 순위 "
             "(예전 손튜닝 상수 폐기). 소득은 실현 시점 나이대에 댄다",
}


def git_version() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"],
                                       cwd=ROOT, text=True,
                                       stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "nogit"


def _round(v, n=3):
    return None if v is None else round(float(v), n)


def summarize(art: dict) -> dict:
    """아티팩트 dict → 사람이 읽는 핵심 지표만. 없는 키는 조용히 건너뛴다."""
    out: dict = {}
    if (src := art.get("source")) is not None:
        out["source"] = str(src)
    if (n := art.get("n")) is not None:
        out["n"] = int(n)
    for k in ("treatment", "n_treated", "event_label", "caveat"):
        if art.get(k) is not None:
            out[k] = art[k]

    # L3 인과: LinearDML(해석 가능한 analytic CI) 우선, CausalForest ATE 도 같이
    if art.get("linear_ate") is not None:
        lo, hi = art.get("linear_ci") or (None, None)
        out["causal"] = {"method": "LinearDML", "ate_manwon": _round(art["linear_ate"], 2),
                         "ci95": [_round(lo, 2), _round(hi, 2)],
                         "significant": bool(lo is not None and hi is not None
                                             and (lo > 0 or hi < 0))}
    if art.get("ate") is not None:
        lo, hi = art.get("ate_ci") or (None, None)
        out.setdefault("causal_forest", {})
        out["causal_forest"] = {"method": "CausalForestDML",
                                "ate_manwon": _round(art["ate"], 2),
                                "ci95": [_round(lo, 2), _round(hi, 2)]}

    # L4 생존: 교차검증 C-index
    if (cv := art.get("cv_concordance")):
        out["survival"] = {"metric": "5-fold C-index", **cv,
                           "max_horizon_years": art.get("max_horizon_years")}

    # L2 매칭: 학습 시 평가치
    if (ev := art.get("evaluation")):
        out["matching"] = ev

    for k in ("x_cols", "cov_cols", "feature_cols"):
        if art.get(k):
            out["features"] = list(art[k])
            break
    return out


def main() -> int:
    entries = {}
    for name, (layer, role) in KNOWN.items():
        path = ARTIFACTS / name
        if not path.exists():
            entries[name] = {"layer": layer, "role": role, "present": False}
            continue
        stat = path.stat()
        entry = {
            "layer": layer, "role": role, "present": True,
            "size_mb": round(stat.st_size / 1e6, 2),
            "modified": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
        }
        try:
            art = joblib.load(path)
            if isinstance(art, dict):
                entry.update(summarize(art))
        except Exception as exc:                      # 손상/버전 불일치도 사실로 기록
            entry["load_error"] = f"{type(exc).__name__}: {exc}"[:200]
        entries[name] = entry

    # 학습 데이터 빈티지 — 전처리 리포트를 그대로 물고 온다
    data_vintage = {}
    for label, rel in (("klips", "data/raw/klips/klips_build_report.json"),):
        p = ROOT / rel
        if p.exists():
            r = json.loads(p.read_text(encoding="utf-8"))
            data_vintage[label] = {k: r[k] for k in
                                   ("waves", "years", "deflated", "cpi_base_year",
                                    "rows", "persons", "wage_median_real",
                                    "job_change_rate") if k in r}

    # treatment 커버리지 — 어떤 선택 유형에 개인단위 인과가 붙고, 안 붙으면 왜인지
    tp = ARTIFACTS / "treatment_report.json"
    treatments = json.loads(tp.read_text(encoding="utf-8")) if tp.exists() else None
    dp = ARTIFACTS / "dynamic_effects.json"
    dyn = json.loads(dp.read_text(encoding="utf-8")) if dp.exists() else None

    # 매칭 품질 측정치 + 3지표 기준 분포 — "개선했다"를 수치로 남긴다
    mp = ARTIFACTS / "matching_eval.json"
    match_eval = None
    if mp.exists():
        m = json.loads(mp.read_text(encoding="utf-8"))
        match_eval = {k: m[k] for k in ("measured_at", "queries", "k", "weights",
                                        "paired_vs_legacy", "metric_note") if k in m}
    ip = ARTIFACTS / "indicator_reference.json"
    ind_ref = None
    if ip.exists():
        r = json.loads(ip.read_text(encoding="utf-8"))
        ind_ref = {"built_at": r.get("built_at"), "age_bands": r.get("age_bands"),
                   "sources": r.get("sources"),
                   "dists": {k: sorted(v) for k, v in (r.get("dists") or {}).items()}}

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git": git_version(),
        "routing": ROUTING,
        "treatments": treatments,
        "dynamic_effects": {k: {"label": v.get("label"),
                                "years": sorted(int(h) for h in v.get("horizons", {}))}
                            for k, v in (dyn or {}).items()},
        "matching_eval": match_eval,
        "indicator_reference": ind_ref,
        "data_vintage": data_vintage,
        "artifacts": entries,
        "missing": sorted(n for n, e in entries.items() if not e["present"]),
    }
    out = ARTIFACTS / "manifest.json"
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[manifest] {out.relative_to(ROOT)}")
    for name, e in entries.items():
        if not e["present"]:
            print(f"  MISSING  {name:22s} {e['role']}")
            continue
        bits = [e.get("source", "?")]
        if c := e.get("causal"):
            sig = "유의" if c["significant"] else "비유의"
            bits.append(f"ATE {c['ate_manwon']:+.1f}만 CI{c['ci95']} ({sig})")
        if s := e.get("survival"):
            bits.append(f"C-index {s.get('test')}")
        if m := e.get("matching"):
            bits.append(f"동일전공 {m.get('same_major_rate')}")
        print(f"  OK       {name:22s} {' | '.join(str(b) for b in bits)}")
    if manifest["missing"]:
        print(f"\n  ⚠ 없는 아티팩트: {', '.join(manifest['missing'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
