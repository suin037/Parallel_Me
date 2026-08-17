// ─────────────────────────────────────────────────────────────
// /simulate 응답 → 결과 화면이 읽는 형태({a, b})로 변환.
//
// 화면 컴포넌트들은 prediction.js(getPrediction) 의 필드 이름을 그대로 읽는다.
// 백엔드 compare 응답의 scenarios[A|B].raw 가 사실상 같은 계약(/predict 형태)이라
// 대부분 그대로 통과시키고, 아래 3가지만 손본다.
//
//  1) 선택별 근거 수준 보존 — 이직에만 L2/L3/L4 개인단위 모델을 적용한다.
//     유지·창업·진학·기타 선택에는 공통 생활지표와 관찰 기준선만 전달한다.
//  2) 생활지표 dimension 이름을 프론트 LIFE_DIMENSIONS 키에 맞춘다(아이콘·색 매칭용).
//  3) 백엔드가 주지 않는 값은 null 로 둔다. 절대 추정치를 만들어 채우지 않는다.
//     (descriptive_effect·down_ratio 가 그렇다 — 없으면 해당 UI 가 알아서 숨는다.)
// ─────────────────────────────────────────────────────────────

import { ACTION_CARDS } from "./prediction.js";
import { occupationLabel } from "./profileOptions.js";

// 백엔드 생활지표의 dimension 표기 → 프론트 LIFE_DIMENSIONS 키
const DIMENSION_ALIAS = {
  "삶의질(청년)": "삶의질",
  "진학/취업": "진학·취업",
};

function normalizeLifeIndicators(list) {
  return (list || []).map((it) => ({
    dimension: DIMENSION_ALIAS[it.dimension] || it.dimension,
    indicator: it.indicator,
    value: it.value,
    unit: it.unit,
    group: it.group ?? null,
    source: it.source ?? null,
    n: it.n ?? null,
    // 백엔드가 붙여 보내는 삶의 영역 태그. 화면이 지표 '이름 문자열'로 영역을
    // 추측하던 것을 대체한다(예전 방식은 관계에서 15개 중 14개를 버렸다).
    domains: it.domains || [],
    lower_is_better: it.lower_is_better ?? false,
    // 같은 지표의 전체 집단 값. 유병률·인지율에는 만점이 없어서 이게 있어야
    // '높다/낮다'를 말할 수 있다 — 화면은 이 값을 0으로 두고 격차를 그린다.
    baseline: it.baseline ?? null,
    baseline_group: it.baseline_group ?? null,
  }));
}

// 선택지별 소득 궤적. 선택 전용 모델 결과가 없으면 기준선(비슷한 사람들의 실제 경로)
// 하나만 전달한다. 화면은 이 선을 A/B 예측처럼 두 번 그리지 않는다.
// 그 경우 isBaseline=true 로 표시해 화면이 "갈래별 궤적"인 척하지 않게 한다.
function pickTrajectory(raw, choice) {
  const byScenario = raw.scenario_trajectories || {};
  const picked = byScenario[choice];
  if (Array.isArray(picked) && picked.length) return { rows: picked, isBaseline: false };
  return { rows: raw.trajectory || [], isBaseline: true };
}

const maxYear = (rows, fallback) =>
  Array.isArray(rows) && rows.length ? Math.max(...rows.map((p) => p.year ?? 0)) : fallback;

// 백엔드가 사용자 조건(입력한 월소득 수준)을 반영한 값은 `scenario.income` 에만 담긴다.
// 그런데 화면의 소득은 다섯 군데가 `trajectory` 를 직접 읽는다 — 비교표·평행뷰·
// 궤적그래프·상세인사이트·요약. 그래서 응답에는 280만원이 들어 있는데 화면에는
// 308만원(모델 원값)이 그대로 떴다.
//
// 컴포넌트를 다섯 개 고치는 대신 궤적을 한 번 맞춘다. 배율은 **백엔드 결과에서
// 그대로 끌어온다** — 같은 공식을 프론트에 다시 적으면 두 곳이 조용히 어긋난다.
//   배율 = income_series 의 첫 연차 값 ÷ trajectory 의 같은 연차 원값
function anchorFactor(trajectory, incomeSeries) {
  if (!Array.isArray(incomeSeries) || !Array.isArray(trajectory)) return 1;
  const shown = incomeSeries.find((p) => p?.available !== false && Number.isFinite(Number(p?.value)));
  if (!shown) return 1;
  const rawPoint = trajectory.find((p) => Number(p?.year) === Number(shown.year));
  const base = Number(rawPoint?.income_p50);
  if (!Number.isFinite(base) || base <= 0) return 1;
  const factor = Number(shown.value) / base;
  // 부동소수 오차로 매번 새 배열을 만들지 않도록 1에 가까우면 그대로 둔다.
  return Math.abs(factor - 1) < 1e-6 ? 1 : factor;
}

function scaleTrajectory(rows, factor) {
  if (factor === 1) return rows;
  return rows.map((p) => (Number(p?.year) <= 0 ? p : {
    // 0년차는 '지금의 나' 다. 조건은 앞으로의 이야기라 현재 소득을 바꾸면 안 된다
    // (SummaryView 가 이 값을 '현재 월소득'으로 쓰고, 증감률도 여기를 기준 삼는다).
    ...p,
    income_p25: Number.isFinite(Number(p.income_p25)) ? Math.round(Number(p.income_p25) * factor * 10) / 10 : p.income_p25,
    income_p50: Number.isFinite(Number(p.income_p50)) ? Math.round(Number(p.income_p50) * factor * 10) / 10 : p.income_p50,
    income_p75: Number.isFinite(Number(p.income_p75)) ? Math.round(Number(p.income_p75) * factor * 10) / 10 : p.income_p75,
  }));
}

function buildSide(scenario, choice, detail, profile, evidence, domainCov, domainStats, validatedPrediction, indicatorEvidence, kowepsEvidence, side) {
  const raw = scenario?.raw || {};
  // 자유입력 원문 대신 백엔드가 정규화한 유형을 사용한다. "개발자로 이직" 같은
  // 문구도 kind="이직"이면 개인모델 결과를 버리지 않아야 한다.
  const kind = scenario?.kind || raw.kind || choice;
  // scenario_trajectories 키는 사용자가 쓴 원문이 아니라 백엔드 정규화 유형
  // (유지·이직 등)이다. "현재 진로 유지" 같은 문장으로 조회하면 항상 공통
  // 기준선으로 떨어져 A/B 격차와 상세 인사이트가 사라진다.
  const { rows: rawTrajectory, isBaseline } = pickTrajectory(raw, kind);
  // 학습 데이터 범위 밖(해외 이동 등)이면 **원자료 궤적까지 지운다.**
  //
  // 백엔드는 scenario.income 을 비우는데, 화면의 월소득 행은 raw 쪽 trajectory 를
  // 읽는다(ResultQuickStats). 그래서 린의 B('런던에 남아 현지 취업')에 국내 잔류자
  // 궤적 211만원이 그대로 떴다 — '지금 대비 소득 증감'만 '—' 로 비어서 한쪽은
  // 막히고 한쪽은 안 막힌 상태였다. 근거가 없으면 어느 경로로도 보이면 안 된다.
  const outOfScope = Boolean(scenario?.out_of_scope);
  const trajectory = outOfScope
    ? []
    : scaleTrajectory(rawTrajectory, anchorFactor(rawTrajectory, scenario?.income));
  const wellbeing = outOfScope ? [] : (raw.wellbeing_trajectory || []);

  // 이직은 개인단위 모델, 창업은 artifact가 배포된 경우 개인단위 자영 이탈모델을 쓴다.
  // artifact가 없더라도 창업 risk_timeline에는 업종·규모별 기업생멸 통계가 들어온다.
  // 휴식(쉬어가기)도 개인단위다 — KLIPS 직업력 공백 스펠의 L3/L4.
  const hasIndividualPayload = raw.expected_wage != null
    || raw.causal_effect != null
    || raw.survival_months != null
    || (Array.isArray(raw.neighbors) && raw.neighbors.length > 0);
  const hasIndividual = !outOfScope && (kind === "이직"
    || hasIndividualPayload
    || (["창업", "휴식"].includes(kind) && raw.survival_months != null));
  const hasRisk = !outOfScope && (kind === "창업"
    || hasIndividual
    || (raw.risk_timeline && Object.keys(raw.risk_timeline).length > 0));

  return {
    choice,
    kind,
    detail,
    meta: {
      age: profile?.age ?? null,
      // 헤더에 쓰는 '나는 누구인가' 값 — 사용자가 온보딩에서 직접 고른 직종이다.
      // 예전엔 major(전공 계열)를 먼저 봤는데, 전공 칸은 교육 영역 비교에서만
      // 뜨는 조건부 입력이라(InputScreen.needMajor) 대부분의 사용자는 고른 적이
      // 없는 값이 헤더에 박혔다. 데모 경로(prediction.js)는 원래 직종을 썼기에
      // 실데이터로 붙는 순간 헤더가 직종→전공으로 바뀌는 불일치도 있었다.
      // (occupationLabel 이 온보딩 직종 → KSCO 대분류 순으로 고른다.)
      occupation: occupationLabel(profile) || "—",
      observe_years_income: maxYear(trajectory, 0),
      observe_years_wellbeing: maxYear(wellbeing, 0),
      source: "KLIPS·GOMS·YP · KNHANES·KWCS · KOSIS·KEDI (L1~L5)",
    },
    coverage: raw.coverage || scenario?.coverage || "",
    life_indicators: normalizeLifeIndicators(raw.life_indicators),
    trajectory,
    // true = 이 갈래 전용 궤적이 아니라 '비슷한 사람들'의 공통 기준선
    trajectory_is_baseline: isBaseline,
    wellbeing_trajectory: wellbeing,
    wellbeing_branch: raw.wellbeing_branch || {},
    satisfaction_summary: scenario?.satisfaction_summary || null,
    satisfaction_facets: scenario?.satisfaction_facets || [],
    growth_potential: scenario?.growth_potential || [],
    // 백엔드는 연차별 소득/만족도에 출처 문자열을 함께 준다. 화면은 raw.trajectory
    // 쪽만 써서 그 문자열이 통째로 유실됐는데, 거기 "명목 — 물가상승분 포함" 경고가
    // 들어 있다. 10년 뒤 소득을 명목으로 보여주면서 그 말을 빼면 실제보다 좋아 보인다.
    income_series: scenario?.income || [],
    // 공백 기간·초기비용이 반영된 누적 소득. 월소득 줄에는 안 들어 있다 —
    // "반년 쉬는데 1년차 월급이 남는 쪽보다 높다" 가 여기서 뒤집힌다.
    income_cumulative: scenario?.income_cumulative || [],
    // 사용자가 적은 조건 중 실제로 수치에 들어간 것. null 이면 반영된 게 없다.
    applied_conditions: scenario?.applied_conditions || null,
    // 범위 밖 사유 — 화면이 '왜 비었는지' 를 말할 수 있게 한다.
    out_of_scope: scenario?.out_of_scope || null,
    // KNHANES·KWCS 실측(스트레스인지율·우울장애유병률 등). 선택별로 갈리는 값이
    // 아니라 '같은 조건 집단은 지금 이렇다'는 배경 수치다.
    health_context: scenario?.health_context || [],
    choice_context: normalizeLifeIndicators(scenario?.choice_context || []),
    matched_on: raw.matched_on || [],
    regret_summary: scenario?.regret_summary || null,
    action_cards: ACTION_CARDS,
    narrative: "",

    expected_wage: hasIndividual ? raw.expected_wage ?? null : null,
    causal_effect: hasIndividual ? raw.causal_effect ?? null : null,
    // 인과 점추정의 95% 신뢰구간(있으면). 0을 포함하는지까지 화면이 판단할 수 있도록
    // ate·ci·method·source 를 통째로 넘긴다. 점추정만 보여주면 과신을 부른다.
    causal_ci: hasIndividual ? scenario?.confidence?.causal_effect_ci ?? null : null,
    confidence: hasIndividual ? scenario?.confidence || {} : {},
    // 백엔드는 '겉보기 효과'를 따로 주지 않는다. 없는 값을 만들지 않는다.
    descriptive_effect: null,
    survival_months: hasIndividual ? raw.survival_months ?? null : null,
    neighbors: hasIndividual ? raw.neighbors || [] : [],
    neighbor_changed_ratio: hasIndividual ? raw.neighbor_changed_ratio ?? null : null,
    down_ratio: null,
    risk_timeline: hasRisk ? raw.risk_timeline || {} : {},
    risk_label: hasRisk ? scenario?.regret_summary?.label ?? null : null,
    // 휴식 전용 — {개월: 복귀 누적확률}. risk_timeline(연차별 미복귀확률)의 반대편이다.
    // 쉬는 기간 중앙값이 1년 미만이라 연 단위로는 3·6개월 구간이 통째로 뭉개진다.
    return_timeline: raw.return_timeline || {},

    // 근거 수준(항목4) — 이 갈래가 어떤 강도의 근거인지 + 수치그래프 표시 정당성.
    evidence_level: evidence?.level || null,      // model | group_stat | rag | insufficient
    evidence_label: evidence?.label || null,      // "모델예측" 등
    // 정량 그래프 가드: false 면 이 영역엔 수치 데이터가 없어 그래프 대신 설명으로.
    quantitative_ok: domainCov ? domainCov.quantitative_ok !== false : true,
    graph_guard_note: domainCov?.guard_note || null,
    // 영역별 실측 집단통계 지표(항목3) — { domainKey: {label, evidence, indicators[]} }
    domain_stats: domainStats || {},
    // 새 후보 모델: 검증 집단효과와 실험적 개인 추정치가 분리된 원응답.
    validated_prediction: validatedPrediction || null,
    parallel_trajectory: validatedPrediction?.parallel_trajectory || null,
    observed_outcomes: validatedPrediction?.observed_outcomes || null,
    // 각 지표의 숫자와 그 숫자를 뒷받침하는 근거 수준을 분리한다.
    indicator_evidence: indicatorEvidence || null,
    // KOWEPS 사건군/유지군 종단 관측. 개인 예측이 아니라 선택과 대응되는
    // 집단의 1·3·5·10년 뒤 실제 분포이며 변화 흐름·상세 분석에서 사용한다.
    koweps_evidence: kowepsEvidence?.available ? kowepsEvidence : null,
    koweps_role: kowepsEvidence?.event_side === side ? "event" : "comparison",
  };
}

/**
 * /simulate 원응답 → { a, b } (결과 화면 형태).
 * 수치를 하나라도 만들어내지 못하면 null 을 돌려준다 — 호출측이 목업으로 되돌리도록.
 *
 * @param {object} sim              runSimulateRaw() 응답
 * @param {{choiceA:string, choiceB:string, detailA?:string, detailB?:string}} ctx
 *        choiceA/B 는 사용자가 화면에서 고른 4분류(유지·이직·창업·진학) 라벨.
 */
export function mapSimulateToPair(sim, { choiceA, choiceB, detailA = "", detailB = "" }) {
  const cmp = sim?.compare;
  const A = cmp?.scenarios?.A;
  const B = cmp?.scenarios?.B;
  if (!A || !B) return null;

  const profile = cmp.profile || {};
  // 근거수준·영역지표·가드는 이제 /compare 응답(cmp)에 실려온다. (구 /simulate 최상위도 폴백 지원)
  const ev = cmp.evidence_levels || sim.evidence_levels || {};
  const dc = cmp.domain_coverage || sim.domain_coverage || {};
  const ds = cmp.domain_stats || sim.domain_stats || {};
  const vp = cmp.validated_predictions || sim.validated_predictions || {};
  const ie = cmp.indicator_evidence || sim.indicator_evidence || {};
  const ke = cmp.koweps_evidence || sim.koweps_evidence || null;
  const keA = ke?.comparison_mode === "independent_events" ? ke.side_evidence?.A : ke;
  const keB = ke?.comparison_mode === "independent_events" ? ke.side_evidence?.B : ke;
  const a = buildSide(A, choiceA, detailA, profile, ev.A, dc.A, ds.A, vp.A, ie.A, keA, "A");
  const b = buildSide(B, choiceB, detailB, profile, ev.B, dc.B, ds.B, vp.B, ie.B, keB, "B");
  const measuredScores = (side) => {
    const scores = sim.indicators?.[side] || {};
    const unmeasured = new Set(sim.indicator_detail?.[side]?.unmeasured || []);
    return Object.fromEntries(Object.entries(scores).filter(([key, value]) =>
      !unmeasured.has(key) && Number.isFinite(Number(value))));
  };
  a.indicator_scores = measuredScores("A");
  b.indicator_scores = measuredScores("B");
  // 왜 지웠는지도 함께 넘긴다. 값만 빼면 화면에는 그냥 "—" 로 떠서, 측정을 못 한
  // 것인지 값이 0 인지 구분이 안 된다. 성민(창업)의 B 가 정확히 그 경우였다 —
  // 백엔드는 unmeasured 로 "못 쟀다" 고 말하는데 응답의 indicators 에는 중립값
  // 0.5 가 들어 있어, 실측 0.314 와 나란히 놓이면 큰 격차처럼 보였다.
  a.indicator_unmeasured = sim.indicator_detail?.A?.unmeasured || [];
  b.indicator_unmeasured = sim.indicator_detail?.B?.unmeasured || [];
  // 장기 가치는 별도 미래점수가 아니라 어떤 결과를 먼저 읽을지 정하는 개인화 축이다.
  // /compare 미리보기에는 없고 /simulate 최종 응답부터 적용된다.
  a.personalization = sim.personalization || null;
  b.personalization = sim.personalization || null;

  // 실데이터가 하나라도 있으면 실수치 모드. 연차별 궤적이 비어도(관측범위 밖/표본부족)
  // 이웃·인과·기대임금·지표 같은 실측이 있으면 목업으로 되돌리지 않는다.
  const hasReal = (s) =>
    (s.trajectory && s.trajectory.length) ||
    (s.neighbors && s.neighbors.length) ||
    s.causal_effect != null || s.expected_wage != null || s.survival_months != null ||
    s.parallel_trajectory?.status === "available" ||
    s.koweps_evidence?.available ||
    (s.life_indicators && s.life_indicators.length);
  if (!hasReal(a) && !hasReal(b)) return null;
  return { a, b };
}
