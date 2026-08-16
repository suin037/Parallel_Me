"""로컬 테스트 — 서버/API 키 없이 /compare(A/B 비교 뷰)를 직접 호출해 출력.

실행:  python test_compare.py
  · 서버(uvicorn) 안 켜도 됨
  · narrative 는 비교에서 생략되므로 ANTHROPIC_API_KEY 불필요
  · 산출물 pkl 과 data/ lookup 이 제자리에 있어야 함
"""

import sys
import types
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

# narrative(Claude API) 스텁 — 실제 API 호출 없이 테스트
_stub = types.ModuleType("utils.claude_api")
_stub.generate_narrative = lambda *a, **k: "(narrative 생략 — 테스트 모드)"
sys.modules["utils.claude_api"] = _stub

from schemas import CompareRequest, Profile   # noqa: E402
from compare import build_comparison          # noqa: E402

CASES = [
    # (프로필, 선택A, 선택B)
    ({"age": 27, "sex": "2", "major": "사회", "monthly_wage": 250, "edu_level": 7}, "이직", "대학원 진학"),
    ({"age": 30, "sex": "1", "major": "공학", "monthly_wage": 320, "edu_level": 7}, "이직", "창업"),
    ({"age": 26, "sex": "2", "major": "자연", "edu_level": 7}, "창업", "대학원 진학"),
]


def _card(name: str, pts: list) -> None:
    cells = []
    for p in pts:
        if not p.available:
            cells.append(f"{p.year}y: —")
            continue
        # 만족도(1~5)·성장%처럼 작은 값은 소수1자리, 소득(만원)은 정수로
        d = 1 if p.value is not None and abs(p.value) < 20 else 0
        if p.p25 is not None:
            cells.append(f"{p.year}y: {p.value:.{d}f}({p.p25:.{d}f}~{p.p75:.{d}f})")
        else:
            cells.append(f"{p.year}y: {p.value:.{d}f}")
    print(f"     {name:10s} " + " | ".join(cells))


def run(profile: dict, ca: str, cb: str) -> None:
    req = CompareRequest(profile=Profile(**profile), choice_a=ca, choice_b=cb)
    res = build_comparison(req)
    print("=" * 78)
    print(f"입력  {profile}  |  A={ca}  vs  B={cb}")
    if res.note:
        print(f"note  {res.note}")
    for slot in ("A", "B"):
        s = res.scenarios[slot]
        print(f"  [{slot}] {s.choice}  ({s.kind})  — {s.coverage}")
        _card("만족도", s.satisfaction)
        if s.satisfaction_summary:
            ss = s.satisfaction_summary
            print(f"       └ 종합요약: {ss['start']}→{ss['latest']} ({ss['direction']}, "
                  f"{ss['span_years']}년, n={ss['sample_n']})")
        for f in s.satisfaction_facets:
            pv = " → ".join(f"{p.value:.2f}" for p in f.points)
            print(f"       · {f.label:16s} {pv}  ({f.direction}, n={f.points[-1].sample_n})")
        _card("소득", s.income)
        _card("후회리스크", s.regret)
        if s.regret_summary:
            rs = s.regret_summary
            print(f"       └ 요약: {rs['worst_year']}년 {rs['label']} {rs['worst_value']}{rs['unit']}")
        _card("(성장%)", s.growth_potential)
        if s.confidence.get("survival_c_index"):
            ci = s.confidence["survival_c_index"]
            print(f"     신뢰: L4 {ci['metric']} 테스트 {ci['c_index_test']} "
                  f"(n={ci['n_spells']}, {ci['source']})")
        if s.confidence.get("causal_effect_ci"):
            ec = s.confidence["causal_effect_ci"]
            print(f"           L3 ATE {ec['ate']:+.1f}만 (95% CI {ec['ci95_low']:+.1f}~{ec['ci95_high']:+.1f}) "
                  f"[{ec.get('method','')}]")
        if s.choice_context:
            ctx = ", ".join(f"{li.indicator} {li.value}{li.unit}" for li in s.choice_context)
            print(f"     선택맥락: {ctx}")


if __name__ == "__main__":
    for profile, ca, cb in CASES:
        run(profile, ca, cb)
    print("=" * 78)
    print("[OK] 전체 비교 케이스 통과")
