"""티어2(매칭 품질·지표 캘리브레이션) 회귀 테스트.

실행:  python test_tier2.py
  · 서버·API 키 불필요
  · 선행 산출물: scripts/build_indicator_reference.py, scripts/eval_matching.py

검증 대상:
  ⑧ 매칭이 준 입력을 실제로 쓰는가 / 안 준 항목을 중앙값으로 채워 중앙으로 쏠지 않는가
     / hold-out 평가에서 기존 서빙보다 실제로 나은가(측정 파일 기준)
  ⑨ 3지표가 백분위 척도인가 / 근거(컴포넌트)를 내보내는가 / 세 지표가 같은 척도라
     '최저 지표' 비교가 성립하는가 / 기준 분포가 없으면 정직하게 폴백하는가
"""

import json
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

_stub = types.ModuleType("utils.claude_api")
_stub.generate_narrative = lambda *a, **k: "(narrative 생략 — 테스트 모드)"
sys.modules["utils.claude_api"] = _stub

from schemas import CompareRequest, PredictRequest, Profile   # noqa: E402
from compare import build_comparison                          # noqa: E402
from core import run_prediction                               # noqa: E402
import indicators as I                                        # noqa: E402
import trajectory as T                                        # noqa: E402

ARTIFACTS = ROOT / "backend/models/artifacts"
_fail: list[str] = []


def check(cond: bool, label: str, detail: str = "") -> None:
    print(f"  {'[OK]  ' if cond else '[FAIL]'} {label}" + (f"  — {detail}" if detail else ""))
    if not cond:
        _fail.append(label)


def scen_for(age: int, wage: float, **extra) -> dict:
    p = dict(age=age, sex="1", major="공학", monthly_wage=wage, edu_level=7,
             is_regular=1, **extra)
    c = build_comparison(CompareRequest(profile=Profile(**p),
                                       choice_a="이직", choice_b="현상 유지"))
    return c.model_dump()["scenarios"]["A"]


# ---------------------------------------------------------------- ⑧ 매칭
def test_matching() -> None:
    print("\n⑧ 궤적 매칭 품질")
    lean = dict(age=29, sex="1", major="공학")
    rich = dict(age=29, sex="1", major="공학", monthly_wage=320, edu_level=7,
                is_regular=1, firm_size=7, job_category=312, tenure_years=4)

    r_lean = run_prediction(PredictRequest(**lean, choice="이직"), with_narrative=False)
    r_rich = run_prediction(PredictRequest(**rich, choice="이직"), with_narrative=False)
    check(len(r_rich.matched_on) > len(r_lean.matched_on),
          "입력이 많으면 매칭 축도 늘어난다",
          f"{len(r_lean.matched_on)}개 → {len(r_rich.matched_on)}개")
    check("직종소득지수" in r_rich.matched_on,
          "직종을 주면 매칭에 쓰인다(코드 → 직종별 평균 로그임금)")
    check("월임금_실질" not in r_lean.matched_on,
          "안 준 항목은 매칭 축에서 제외 — 중앙값으로 채워 중앙으로 쏠지 않는다",
          str(r_lean.matched_on))

    # 직종만 바꾸면 궤적이 달라져야 한다(같으면 그 축이 실제로 안 쓰이는 것)
    def p50(job):
        r = run_prediction(PredictRequest(**{**rich, "job_category": job},
                                         choice="이직"), with_narrative=False)
        return {p.year: p.income_p50 for p in r.trajectory}
    a, b = p50(312), p50(941)      # 312=경영·회계 사무원 / 941=단순노무
    shared = sorted(set(a) & set(b))
    check(any(a[y] != b[y] for y in shared), "직종이 다르면 궤적도 달라진다",
          f"312 {[a[y] for y in shared[:4]]} vs 941 {[b[y] for y in shared[:4]]}")

    # 측정 파일 기준으로 기존 서빙보다 나은지 (짝지은 차이의 95% 구간이 0을 안 넘는가)
    p = ARTIFACTS / "matching_eval.json"
    check(p.exists(), "hold-out 평가 결과 파일 존재",
          "없으면 python scripts/eval_matching.py")
    if p.exists():
        ev = json.loads(p.read_text(encoding="utf-8"))
        full = list(ev["paired_vs_legacy"])[-1]
        d = ev["paired_vs_legacy"][full]
        wins = [h for h, m in d.items()
                if m["delta_mae"] < 0 and abs(m["delta_mae"]) > m["ci95"]]
        check(len(wins) >= 2, "기존 서빙 대비 MAE 개선이 표본 흔들림 밖",
              " ".join(f"t+{h} {d[h]['delta_mae']:+.1f}±{d[h]['ci95']:.1f}" for h in d))
        hits = [ev["configs"][full][h]["band_hit"] for h in d]
        check(all(0.4 <= v <= 0.6 for v in hits),
              "p25~p75 밴드 적중률이 0.5 근처(과신·과대 아님)",
              str([round(v, 3) for v in hits]))


# ---------------------------------------------------------------- ⑨ 지표
def test_indicators() -> None:
    print("\n⑨ 3지표 캘리브레이션")
    check((ARTIFACTS / "indicator_reference.json").exists(),
          "기준 분포 파일 존재", "없으면 python scripts/build_indicator_reference.py")

    s = scen_for(29, 320)
    det = I.compute_indicators_detail(s, 320, 29)
    check(det["method"].startswith("percentile-rank"), "백분위 방식으로 산출",
          det["method"])
    check(set(det["scores"]) == set(I.INDICATOR_KEYS), "계약 키 5축 유지")
    check(all(isinstance(v, float) for v in det["scores"].values()),
          "compute_indicators 는 float 만 반환(min() 비교가 터지지 않게)")
    check(any(v is not None for v in det["components"].values()),
          "구성요소 백분위를 근거로 노출", str(det["components"]))
    check(det["income_age_band"] != det["age_band"] or det["income_at_year"] == 0,
          "소득 백분위는 그 소득이 실현되는 시점 나이대에 댄다",
          f"{det['age_band']} → {det['income_age_band']} (t+{det['income_at_year']})")

    # 소득이 오르면 경제적안정도 백분위도 올라야 한다(단조성)
    lo = I.compute_indicators_detail(scen_for(29, 230), 230, 29)
    hi = I.compute_indicators_detail(scen_for(29, 520), 520, 29)
    check(hi["components"]["income_level"] > lo["components"]["income_level"],
          "소득이 높으면 소득 백분위도 높다(단조)",
          f"{lo['components']['income_level']} → {hi['components']['income_level']}")

    # 구공식은 성장 축이 상한(1.0)에 붙어 지표로 못 쓰였다 → 포화 해소 확인
    old = [I._legacy(scen_for(a, w), w)["성장"]
           for a, w in ((26, 200), (29, 250), (33, 300))]
    new = [I.compute_indicators_detail(scen_for(a, w), w, a)["scores"]["성장"]
           for a, w in ((26, 200), (29, 250), (33, 300))]
    check(any(v >= 0.999 for v in old) and all(v < 0.99 for v in new),
          "구공식의 성장 축 포화(1.0)가 해소됨",
          f"구식 {old} → 신규 {new}")

    # ★v3 회귀: 한 구성요소가 두 축에 들어가면 같은 근거를 두 번 세는 것이다.
    #   예전엔 income_growth 가 경제적안정도·성장가능성에, low_exit_risk 가
    #   경제적안정도·삶의질에 중복 투입돼 '성장가능성' 이 경제의 부분집합이었다.
    seen: dict = {}
    dup = [f"{c}({seen[c]}·{ax})" for ax, mix in I.WEIGHTS.items()
           for c in mix if (c in seen) or seen.setdefault(c, ax) and False]
    check(not dup, "축 간 구성요소 중복 투입 없음", str(dup or "없음"))

    # 가치축(온보딩)과 지표 키가 같아야 사용자의 정렬 답이 결과까지 살아남는다.
    from personalize import INDICATORS
    check(set(INDICATORS) == set(I.INDICATOR_KEYS),
          "온보딩 가치축 ↔ 지표 키 항등", f"{INDICATORS}")

    # 기준 분포가 없으면 조용히 이상한 값을 내지 말고 폴백을 밝힌다
    I._reference.cache_clear()
    orig = I.settings.artifacts_dir
    try:
        I.settings.artifacts_dir = "backend/models/__no_such_dir__"
        I._reference.cache_clear()
        d = I.compute_indicators_detail(s, 320, 29)
        check(d["method"].startswith("legacy"), "기준 분포 없으면 폴백을 명시",
              d["method"][:60])
        check(set(d["scores"]) == set(I.INDICATOR_KEYS), "폴백도 계약 키 유지")
    finally:
        I.settings.artifacts_dir = orig
        I._reference.cache_clear()


def main() -> int:
    print("=" * 78)
    test_matching()
    test_indicators()
    print("=" * 78)
    if _fail:
        print(f"[FAIL] {len(_fail)}건 실패: {_fail}")
        return 1
    print("[OK] 티어2 전체 통과")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
