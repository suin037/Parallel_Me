"""티어1(예측모델 커버리지 확장) 회귀 테스트.

실행:  python test_tier1.py
  · 서버(uvicorn)·API 키 불필요
  · artifacts/ 산출물이 제자리에 있어야 함
    (preprocess_klips.py → klips_train.py → train_yp.py → train_treatments.py 순)

검증 대상 — 티어1 4개 항목:
  ④ 창업에 개인단위 L3/L4 가 붙는가 / 진학은 '표본 부족' 을 근거와 함께 말하는가
  ⑤ 만족도가 선택(A/B)에 따라 실제로 갈리는가
  ⑥ 인과효과가 연차별로 달라지고, 그 불확실성이 밴드 폭에 실리는가
  ⑦ 부정·대조가 섞인 자유입력을 제대로 분류하고, 커버리지를 계측하는가
"""

import sys
import types
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

_stub = types.ModuleType("utils.claude_api")
_stub.generate_narrative = lambda *a, **k: "(narrative 생략 — 테스트 모드)"
sys.modules["utils.claude_api"] = _stub

from schemas import PredictRequest                          # noqa: E402
from core import run_prediction                             # noqa: E402
from choice_classifier import classify, classification_stats, reset_stats  # noqa: E402
from models.dynamic_effect import profile_meta              # noqa: E402

YOUTH = dict(age=28, sex="1", major="공학", monthly_wage=320, edu_level=7, is_regular=1)

_fail: list[str] = []


def check(cond: bool, label: str, detail: str = "") -> None:
    print(f"  {'[OK]  ' if cond else '[FAIL]'} {label}" + (f"  — {detail}" if detail else ""))
    if not cond:
        _fail.append(label)


def predict(choice: str, **over):
    return run_prediction(PredictRequest(**{**YOUTH, **over}, choice=choice),
                          with_narrative=False)


# ---------------------------------------------------------------- ⑦ 분류
def test_classifier() -> None:
    print("\n⑦ 선택지 분류 — 부정·대조 처리와 확신도")
    # 기존 키워드 `in` 검사가 틀리던 것들. 한국어는 부정이 대상 **뒤**에 온다.
    cases = [
        ("박사 안 가고 취업할래", "이직"),
        ("이직 말고 창업", "창업"),
        ("대학원 진학 포기하고 이직", "이직"),
        ("유학 대신 국내 취업", "이직"),
        ("창업 접고 취업", "이직"),
        ("카페 차리기", "창업"),
        ("지금 회사 계속 다니기", "유지"),
        # 커리어 밖 생활사건 — KOWEPS 표본이 있어 유형을 연 것들.
        # ("결혼"은 예전엔 기타였다. 근거가 생겨 유형이 됐다.)
        ("결혼할까 말까", "결혼"),
        ("집을 살까 계속 전세로 살까", "주택"),
        ("대출 받아 집 살까", "주택"),
        ("서울로 이사갈까", "이사"),
        # 근거가 없는 것은 여전히 기타로 둔다 — 유형만 늘리면 빈손 화면이 는다.
        ("아이를 가질까", "기타"),
        ("이민 갈까", "기타"),
        # 활용형 — 어간만 넣으면 '계속 다니'가 '다닐까'를 못 잡는다(한국어 음절
        # 블록이 달라 부분문자열이 아니다). A/B 비교의 B쪽은 대개 '계속 다닐까'라
        # 이게 새면 유지 선택지가 통째로 기타로 떨어진다.
        ("지금 회사 계속 다닐까", "유지"),
        ("계속 다니는 게 나을까", "유지"),
        ("그냥 버틸까", "유지"),
        ("회사에 남을까", "유지"),
        ("다른 데로 옮길까", "이직"),
        ("카페 차릴까", "창업"),
        ("좀 쉴까", "휴식"),
        ("쉬는 게 나을까", "휴식"),
        # 부업을 본업으로 돌리는 결정 = 창업. ('회사 나와서'는 휴식·이직과도
        #  겹쳐 단서로 쓰지 않는다 — 무는 건 '본업으로'다.)
        ("회사 나와서 브랜드 본업으로", "창업"),
    ]
    for text, want in cases:
        got = classify(text)
        check(got.kind == want, f"'{text}' → {want}",
              f"실제 {got.kind} (conf {got.confidence}, {got.scores})")

    reset_stats()
    for text, _ in cases:
        classify(text)
    st = classification_stats()
    check(st["total_classified"] == len(cases), "분류 건수 계측",
          f"{st['total_classified']}건")
    check(st["other_ratio"] is not None, "기타 비율(커버리지 손실) 노출",
          f"other_ratio={st['other_ratio']}")


# ---------------------------------------------------------------- ④ 커버리지
def test_treatment_coverage() -> None:
    print("\n④ 이직 외 선택지의 개인단위 레이어")
    startup = predict("창업")
    check(startup.kind == "창업", "창업으로 분류")
    check(startup.causal_effect is not None, "창업 L3 인과효과 제공",
          f"{startup.causal_effect:+.1f}만원" if startup.causal_effect else "None")
    check(startup.survival_months is not None, "창업 L4 자영 유지기간 제공",
          f"{startup.survival_months}개월" if startup.survival_months else "None")
    check(bool(startup.risk_timeline), "창업 후회 리스크 타임라인",
          str(startup.risk_timeline))
    check("사업소득" in startup.coverage or "개념이 달라" in startup.coverage,
          "창업 소득효과의 측정 개념 차이를 coverage 에 명시")

    move = predict("이직")
    check(move.causal_effect is not None and move.survival_months is not None,
          "이직 L3/L4 회귀 없음")

    enroll = predict("대학원 진학")
    check(enroll.causal_effect is None, "진학은 인과 미제공(표본 부족)")
    check("최소표본" in enroll.coverage or "미달" in enroll.coverage,
          "진학 미제공 사유를 근거와 함께 표기", enroll.coverage[:80])


# ---------------------------------------------------------------- ⑥ 동적 효과
def test_dynamic_effect() -> None:
    print("\n⑥ 동적 처치효과 + 불확실성 밴드")
    meta = profile_meta("move")
    check(meta is not None, "이직 연차별 ATE 프로파일 존재")
    if meta:
        ates = [v["ate"] for v in meta["by_year"].values()]
        check(len(set(ates)) > 1, "효과가 연차별로 다름(상수 아님)", str(ates))

    pr = predict("이직")
    paths = pr.scenario_trajectories
    check("유지" in paths and "이직" in paths, "평행우주 경로 2개 생성")
    if "유지" in paths and "이직" in paths:
        base = {p.year: p for p in paths["유지"]}
        pick = {p.year: p for p in paths["이직"]}
        yrs = [y for y in sorted(pick) if y > 0 and y in base]
        applied = [pick[y].effect_applied for y in yrs]
        check(len(set(applied)) > 1, "연차별로 다른 효과가 적용됨", str(applied[:6]))
        widened = [y for y in yrs
                   if (pick[y].income_p75 - pick[y].income_p25)
                   > (base[y].income_p25 * 0 + base[y].income_p75 - base[y].income_p25)]
        check(len(widened) == len(yrs), "인과 CI 만큼 분포 밴드가 넓어짐",
              f"{len(widened)}/{len(yrs)} 연차")
        extrap = [y for y in yrs if pick[y].effect_extrapolated]
        check(all(pick[y].effect_extrapolated is not None for y in yrs),
              "관측범위 밖 연차 표시", f"extrapolated={extrap}")


# ---------------------------------------------------------------- ⑤ 만족도 분기
def test_satisfaction_branch() -> None:
    print("\n⑤ 만족도의 선택별 분기")
    move = predict("이직")
    stay = predict("현상 유지")
    for name, pr in (("이직", move), ("유지", stay)):
        b = pr.wellbeing_branch or {}
        check(bool(b.get("branched")), f"{name} 만족도 분기 적용",
              f"n={b.get('branch_n')}/{b.get('matched_n')} {b.get('reason', '')}")

    mv = {p.year: p.satis_p50 for p in move.wellbeing_trajectory}
    st = {p.year: p.satis_p50 for p in stay.wellbeing_trajectory}
    shared = sorted(set(mv) & set(st))
    check(any(mv[y] != st[y] for y in shared),
          "이직과 유지의 만족도 궤적이 실제로 다름",
          f"이직 {[mv[y] for y in shared]} vs 유지 {[st[y] for y in shared]}")

    # 분기가 안 될 때는 이유를 남겨야 한다(조용히 배경 궤적으로 바꿔치기 금지)
    enroll = predict("대학원 진학")
    b = enroll.wellbeing_branch or {}
    check(b.get("branched") or b.get("reason"), "분기 실패 시 사유 명시",
          str(b.get("reason", ""))[:70])


def main() -> int:
    print("=" * 78)
    test_classifier()
    test_treatment_coverage()
    test_dynamic_effect()
    test_satisfaction_branch()
    print("=" * 78)
    if _fail:
        print(f"[FAIL] {len(_fail)}건 실패: {_fail}")
        return 1
    print("[OK] 티어1 전체 통과")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
