"""예측 코어 — `/predict` 와 `/compare` 가 공유하는 단일 진실.

기존 main.predict() 의 본문을 그대로 옮긴 것. 엔드포인트는 이 함수를 호출만 한다.
(compare 는 이 함수를 A/B 두 번 호출해 비교 뷰로 재구성한다.)

## v2 — 커버리지 확장
예전엔 L2/L3/L4 가 전부 `kind == "이직"` 안에만 있었다. 창업·진학·유지는 L1 룰베이스
와 집단통계뿐이라 A/B 둘 다 이직이 아니면 비교할 수치가 사실상 없었다. 이제:

  · **창업** — KLIPS 임금근로→자영 전이를 treatment 로 학습한 L3(인과)·L4(자영 이탈
    위험)가 붙는다. 폐업 타임라인이 집단통계(KOSIS)에서 개인단위 생존모델로 바뀐다.
  · **진학** — 개인단위 인과는 여전히 없다. 현재 처리본은 실제 입학이 아니라
    학력코드 상승을 대리사건으로 쓰며, 최신 유효 표본 수와 게이트 결과는
    artifacts/treatment_report.json 에 기록한다.
  · **만족도** — 모든 선택 유형에서 '실제로 그 선택을 한 유사인' 으로 분기한다.
    예전엔 A와 B의 만족도 궤적이 같은 값이었다.
  · **소득 궤적** — L3 효과를 상수로 더하지 않고 연차별 프로파일 + CI 밴드로 반영한다.
"""

from schemas import PredictRequest, PredictResponse
from choice_classifier import classify, extract_startup_context
from models.knn_model import find_neighbors
from models.econml_model import estimate_effect
from models.lifelines_model import estimate_survival, risk_timeline, return_timeline
from models.dynamic_effect import shift_at, profile_meta
from rulebase import (query_choice_indicators, query_life_indicators,
                      startup_closure_timeline, startup_context_meta)
from trajectory import project_trajectory, yp_satisfaction, matched_features
from utils.scoring import build_feature_vector
from utils.claude_api import generate_narrative
from causal_effects import summary as relationship_causal_summary

# 선택 유형 → 학습된 treatment 키(train_treatments.py / klips_train.py 와 동일 명명).
# 매핑이 없으면 개인단위 인과·생존을 붙이지 않는다.
KIND_TREATMENT = {"이직": "move", "창업": "startup", "휴식": "break"}
# 만족도 분기는 인과모델이 없어도 가능하다(관측 하위집단만 있으면 됨).
KIND_SATIS_BRANCH = {"이직": "move", "창업": "startup",
                     "진학": "enroll", "유지": "stay"}
# 커리어 밖 생활사건 — KOWEPS 처치효과는 있으나 임금·근속 레이어는 해당 없음.
# `KIND_TREATMENT` 에 넣지 않는 이유: 그 매핑은 KLIPS 로 학습한 econml/lifelines
# artifact 를 켜는 스위치인데, 이 선택들엔 그 artifact 가 없다(있어도 임금 결과라
# 질문이 다르다). 넣으면 없는 모델을 찾다가 조용히 빈 값이 흐른다.
LIFE_EVENT_KINDS = {"결혼", "주택", "이사"}


def new_profile_cache() -> dict:
    """A/B 가 공유할 '프로필만으로 정해지는' 계산 결과 보관함.

    `/compare` 는 같은 프로필로 시나리오를 두 번 그린다. 그런데 L1 생활지표,
    L5 소득 궤적, L2 이웃, 매칭 축은 **선택(choice)을 전혀 안 본다** — 두 번 돌려도
    같은 값이 나온다. 요청 하나 안에서만 사는 캐시라 요청 간 오염이 없다.
    (선택별로 갈리는 건 인과효과·생존·만족도 분기뿐이며 그건 캐시하지 않는다.)
    """
    return {}


def _memo(cache: dict, key: str, fn):
    """없을 때만 계산. dict.setdefault 는 값을 먼저 만들어서 못 쓴다."""
    if key not in cache:
        cache[key] = fn()
    return cache[key]


def choice_kind(choice: str) -> str:
    """자유입력을 근거가 있는 유형으로만 정규화한다.

    실제 분류는 `choice_classifier.classify()` 가 한다(부정·대조 처리, 확신도,
    커버리지 계측). 여기선 기존 호출부 호환을 위해 문자열만 돌려준다.
    """
    return classify(choice).kind


def _scenario_paths(trajectory: list[dict], kind: str, treatment: str,
                    effect: float) -> dict:
    """기준 경로(유지) vs 선택 경로. 연차별 효과 + 인과 불확실성 밴드를 반영한다.

    예전엔 `effect` 하나를 p25/p50/p75 **전부에 같은 값**으로 10년 내내 더했다.
    그러면 (a) 효과의 시간 변화가 사라지고 (b) 분포 폭이 그대로라 인과추정의
    불확실성이 밴드에 전혀 안 실린다. 이제 p50 은 연차별 효과만큼 밀고,
    p25/p75 는 그 연차 ATE 의 95% CI 폭만큼 **추가로** 벌린다.
    """
    if not trajectory:
        return {}
    picked = []
    for p in trajectory:
        y = p["year"]
        if y == 0:                       # 현재 시점엔 아직 효과가 없다
            picked.append(dict(p))
            continue
        s = shift_at(treatment, y, effect)
        if s is None:                    # 프로파일 없음 → 기존처럼 상수 오프셋
            shift, lo, hi, extrap = effect, 0.0, 0.0, False
        else:
            shift, lo, hi = s["shift"], s["band_low"], s["band_high"]
            extrap = s["extrapolated"]
        picked.append({
            **p,
            "income_p25": round(p["income_p25"] + shift + lo, 1),
            "income_p50": round(p["income_p50"] + shift, 1),
            "income_p75": round(p["income_p75"] + shift + hi, 1),
            "effect_applied": round(shift, 1),
            "effect_extrapolated": extrap,
        })
    return {"유지": trajectory, kind: picked}


def run_prediction(req: PredictRequest, with_narrative: bool = True,
                   shared: dict | None = None) -> PredictResponse:
    """현재의 나 + 진로 선택 1개 → 평행우주 추정(L1~L5).

    with_narrative=False 면 narrative(Claude API) 호출을 건너뛴다
    (compare 는 A/B 두 번 호출하므로 기본적으로 서사를 생략해 비용·지연을 줄인다).
    shared 는 `new_profile_cache()` — 같은 프로필로 두 번 호출할 때 선택 무관
    계산(L1·L5 소득 궤적·L2·매칭 축)을 재사용한다. 없으면 매번 새로 계산한다.
    """
    features = build_feature_vector(req)
    cache = shared if shared is not None else {}
    cls = classify(req.choice)
    kind = cls.kind
    treatment = KIND_TREATMENT.get(kind)

    # 창업이면 자유입력에서 업종을 뽑아 features 에 실는다. L4 자영 생존모델이
    # 업종 더미를 covariate 로 갖고 있어서, 이게 없으면 '평균 업종' 위험만 나온다.
    if kind == "창업":
        features["ksic_section"] = extract_startup_context(req.choice).ksic_section

    # Layer 1: 룰베이스 생활지표 패널 — 선택지 무관 항상 제공
    # 선택 의존 지표(창업 업종·규모별 생존율)는 캐시에 태우지 않고 매번 계산한다.
    # 태우면 A('카페 창업')의 업종 숫자가 B('이직')에도 그대로 실린다.
    # `+` 로 새 리스트를 만든다 — extend 하면 공유 캐시 자체가 오염된다.
    life_indicators = (_memo(cache, "life", lambda: query_life_indicators(features))
                       + query_choice_indicators(features))

    # Layer 5: 종단 궤적 — 비슷한 사람들의 향후 N년 실제 경로 분포
    # 소득 궤적은 선택 무관(기준 경로) → A/B 공유. 선택 반영은 아래 인과효과에서.
    trajectory = _memo(cache, "traj", lambda: project_trajectory(features))
    # 만족도·facet 은 '실제로 그 선택을 한 유사인' 으로 분기 (선택별 A/B 비교의 핵심)
    # → 여기는 선택별로 갈리므로 캐시하지 않는다. 다만 둘을 한 번에 계산한다.
    sb = KIND_SATIS_BRANCH.get(kind)
    ys = yp_satisfaction(features, treatment=sb)
    wellbeing_trajectory, wellbeing_meta = ys["points"], ys["branch"]
    satisfaction_facets = ys["facets"]
    scenario_trajectories: dict = {}

    neighbors: list = []
    expected_wage = changed_ratio = effect = survival = None
    timeline: dict = {}
    back_timeline: dict = {}
    effect_profile = None
    available_layers = ["생활지표(L1)"]

    # L2 개인단위 매칭은 이직에만 붙인다. 매칭 풀(GOMS/YP)에 '창업했는지' 표시가
    # 없어서, 창업에 갖다 붙이면 '창업한 유사인' 이 아니라 그냥 프로필이 비슷한
    # 사람이 나온다 — 이름만 개인단위 매칭인 셈이라 켜지 않는다.
    if kind == "이직":
        def _neighbors():
            try:
                return find_neighbors(features)
            except (FileNotFoundError, RuntimeError):
                return []
        neighbors = _memo(cache, "neighbors", _neighbors)
        if neighbors:
            available_layers.append("개인단위 매칭(L2)")
        if neighbors:
            expected_wage = sum(n.monthly_wage or 0 for n in neighbors) / len(neighbors)
            changed_ratio = sum(1 for n in neighbors if n.job_changed) / len(neighbors)

    if treatment:
        try:
            effect = estimate_effect(features, treatment)
            available_layers.append("인과(L3)")
        except (FileNotFoundError, RuntimeError):
            effect = None
        try:
            survival = estimate_survival(features, treatment)
            if treatment == "break":
                # 이벤트가 '복귀' 라 곡선을 그대로 리스크로 부르면 뒤집힌다.
                # · return_timeline = 개월별 **복귀** 누적확률 (좋은 쪽)
                # · risk_timeline   = 연차별 **미복귀** 확률 (= 1 - 복귀), 후회 축에 맞는 값
                # 개월을 따로 두는 건 쉬는 기간 중앙값이 1년 미만이라 연 단위로는
                # 의사결정에 필요한 구간(3·6개월)이 통째로 뭉개지기 때문이다.
                back_timeline = return_timeline(features, treatment=treatment)
                timeline = {y: round(1 - v, 3) for y, v
                            in risk_timeline(features, treatment=treatment).items()}
            else:
                timeline = risk_timeline(features, treatment=treatment)
            available_layers.append("생존(L4)")
        except (FileNotFoundError, RuntimeError):
            survival = None
            timeline = {}
            back_timeline = {}
        effect_profile = profile_meta(treatment)
        if trajectory and effect is not None:
            scenario_trajectories = _scenario_paths(trajectory, kind, treatment, effect)

    if kind == "창업" and not timeline:
        # L4 자영 스펠 모델이 없을 때만 집단통계(KOSIS 기업생멸)로 후퇴
        timeline = startup_closure_timeline(features)

    # 관계 영역 인과효과(소득 외 Y). 커리어 3종은 KLIPS, 생활사건 2종은 KOWEPS 에서
    # 오며 없으면 조용히 비운다 — 값이 없다는 사실은 coverage 문구가 대신 말한다.
    relationship_summary = relationship_causal_summary(kind)
    if relationship_summary.get("available"):
        available_layers.append("관계 인과(L3)")

    coverage = _coverage(kind, available_layers, survival, effect, wellbeing_meta,
                         startup_context_meta(features) if kind == "창업" else {},
                         relationship_summary)

    # narrative 는 3번 팀원 RAG/Claude API 담당. 키 미설정·호출 실패 시에도
    # 예측(L1~L4)은 정상 반환되도록 방어.
    narrative = ""
    if with_narrative:
        try:
            narrative = generate_narrative(
                req,
                expected_wage or 0,
                effect or 0,
                survival or 0,
                persona_block=req.persona_block,
            )
        except Exception:
            narrative = ""

    return PredictResponse(
        choice=req.choice,
        kind=kind,
        choice_confidence=cls.confidence,
        matched_on=_memo(cache, "matched_on", lambda: matched_features(features)),
        coverage=coverage,
        expected_wage=expected_wage,
        causal_effect=effect,
        causal_effect_profile=effect_profile,
        survival_months=survival,
        neighbors=neighbors,
        neighbor_changed_ratio=changed_ratio,
        risk_timeline=timeline,
        return_timeline=back_timeline,
        life_indicators=life_indicators,
        trajectory=trajectory,
        wellbeing_trajectory=wellbeing_trajectory,
        wellbeing_branch=wellbeing_meta,
        satisfaction_facets=satisfaction_facets,
        scenario_trajectories=scenario_trajectories,
        relationship_effects=relationship_summary,
        narrative=narrative,
    )


def _relationship_note(rel: dict | None) -> str | None:
    """관계 인과효과를 한 줄로. 유의/비유의를 뭉뚱그리지 않고 갈라 적는다."""
    if not rel:
        return None
    if not rel.get("available"):
        return f"관계 인과 미적용 — {rel.get('reason', '')}" if rel.get("reason") else None
    hit = rel.get("significant") or []
    miss = rel.get("indistinguishable") or []
    bits = []
    if hit:
        bits.append("유의: " + ", ".join(
            f"{e['label']} {e['ate']:+.3f}점({e['ate_sd']:+.2f}SD, "
            f"95%CI {e['ci_low']:+.3f}~{e['ci_high']:+.3f})" for e in hit))
    if miss:
        # 비유의를 감추면 화면이 '유의한 것만 있는 세계'를 그린다. 그대로 남긴다.
        bits.append("구분되지 않음(신뢰구간이 0을 포함): " + ", ".join(e["label"] for e in miss))
    if not bits:
        return None
    src = rel.get("source", "")
    return (f"관계 인과효과({src}, 직전 같은 문항 통제) — " + " / ".join(bits))


def _coverage(kind: str, layers: list[str], survival, effect, wb_meta: dict,
              su_meta: dict | None = None, rel: dict | None = None) -> str:
    """무엇이 적용됐고 무엇이 왜 빠졌는지 한 줄로. 빈 자리는 이유까지 적는다."""
    parts = [f"{kind}: " + "·".join(layers)]
    if kind == "진학":
        parts.append("개인단위 인과·생존 미제공 — KLIPS 학력상승 전이가 학습 최소표본에 "
                     "미달(근거: artifacts/treatment_report.json). 계열 취업률·진학률(KEDI)로 대체")
    elif kind == "유지":
        parts.append("관측 기준 궤적 — 선택 인과효과는 적용하지 않음(기준선 그 자체)")
    elif kind == "기타":
        parts.append("해당 선택의 전용 예측모델 없음 — 집단 생활지표만 제공")
    elif kind in LIFE_EVENT_KINDS:
        # 커리어 밖 선택(결혼·주택·이사). KOWEPS 종단 처치효과는 있지만 커리어
        # 레이어(L2 유사인물·L3 임금인과·L4 근속생존·L5 소득궤적)는 이 질문에
        # 해당하지 않는다. 아무 말도 안 하면 '왜 비었는지' 를 화면이 설명하지
        # 못하므로(기타는 그 문구가 있는데 이 유형들은 없었다) 여기서 밝힌다.
        # 관계 인과효과가 붙기 전에는 이 유형이 통째로 '기술통계뿐' 이었다. 이제
        # 축마다 성격이 갈린다 — 만족 축은 개인단위 인과(KOWEPS DML), 소득·나머지는
        # 여전히 기술통계다. 뭉뚱그려 "인과가 아님" 이라고 쓰면 이제 거짓이 된다.
        parts.append(
            f"커리어 예측(L2·L3·L5) 미적용 — {kind}은 임금·근속 경로의 선택이 아님. "
            "만족 축 외의 수치는 KOWEPS 최초 사건 전후의 기술통계이며 인과효과나 "
            "개인예측이 아님. 근거는 artifacts/koweps_scenario_evidence.json"
        )
    elif kind == "창업":
        if survival is not None:
            parts.append("후회 리스크 = KLIPS 자영 스펠 이탈확률(개인단위). "
                         "'사업체 폐업' 이 아니라 '자영 상태 이탈'(폐업·업종전환·재취업 포함)")
        else:
            parts.append("L4 자영 스펠 artifact 부재 → KOSIS 기업생멸 집단통계로 대체")
        if effect is not None:
            parts.append("⚠소득 효과는 임금(임금근로자)과 사업소득(자영)을 비교한 값 — "
                         "개념이 달라 '창업하면 이만큼 번다' 로 읽으면 안 됨")
        if su_meta:
            # 어떤 업종·규모 기준의 생존율인지. 업종을 못 뽑았으면 그것도 밝힌다
            # (전체 평균은 업종별 26~67% 를 뭉갠 값이라 그냥 쓰면 오해를 부른다).
            if su_meta.get("industry"):
                parts.append(f"생존율 기준: {su_meta['label']}")
            else:
                parts.append(f"생존율 기준: {su_meta['label']} — 자유입력에서 업종을 "
                             "특정하지 못해 전체 평균(업종별 5년 26~67%로 갈림)")
            if su_meta.get("scale_inferred"):
                parts.append("규모는 개인 창업으로 가정(상용 1~4인). 기업생멸통계는 "
                             "고용원 없는 1인 자영업을 아예 빼고 집계해 실제보다 낙관적")
    elif kind == "휴식":
        if survival is not None:
            parts.append("L4는 '후회 리스크'가 아니라 **복귀까지 걸리는 기간** — "
                         "KLIPS 직업력의 일자리 사이 공백 스펠(자발 퇴직·2개월 이상). "
                         "미복귀는 우측 중도절단으로 처리(‘복귀 안 함’ 으로 세지 않음)")
        else:
            parts.append("L4 공백 스펠 artifact 부재 → 복귀기간 미제공")
        if effect is not None:
            parts.append("⚠소득 효과는 **복귀한 사람만** 보고 잰 값 — 아직 안 돌아왔으면 "
                         "소득이 없어 표본에서 빠진다. '쉬면 이만큼 번다' 가 아니라 "
                         "'쉬었다 돌아온 사람이 이만큼 관측된다' 로 읽을 것")
            parts.append("⚠자발적으로 쉬는 선택엔 쉴 여유가 필요하다 — 자산·배우자소득 "
                         "같은 미관측 여유는 통제되지 않아 효과가 낙관적일 수 있음")
    elif kind == "이직" and survival is None:
        parts.append("생존 L4는 artifact 부재로 미제공")

    if wb_meta.get("branched"):
        parts.append(f"만족도는 '{wb_meta['label']}' 한 유사인 {wb_meta['branch_n']}명 "
                     f"기준(관측 경로 — 선택의 순효과 아님)")
    elif wb_meta.get("reason"):
        parts.append(f"만족도 선택별 분기 미적용({wb_meta['reason']})")
    if (rel_note := _relationship_note(rel)):
        parts.append(rel_note)
    return " / ".join(parts)
