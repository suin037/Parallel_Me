// ─────────────────────────────────────────────────────────────
// 백엔드 /simulate 연동 + 응답 → 화면(MOCK_RESULT) 형태 어댑터.
import { occupationGroupLabel } from "./data/occupationGroups.js";
// 엔진(L1~L5) 수치 + RAG 근거 + Claude 서사를 프론트 컴포넌트가 읽는 형태로 매핑한다.
// ─────────────────────────────────────────────────────────────

import { buildDisposition } from "./data/psychQuestions.js";
import { maskAnswers, maskFunctional, maskText } from "./data/outbound.js";

// 기본은 Vite의 same-origin /api 프록시. 외부 임시 터널에서도 프론트 URL
// 하나만 열면 되며, 배포 API가 따로 있을 때만 VITE_API_BASE로 덮어쓴다.
const API_BASE = import.meta.env.VITE_API_BASE || "/api";

const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
const availPts = (arr) => (arr || []).filter((p) => p && p.available);
const lastAvail = (arr) => {
  const a = availPts(arr);
  return a.length ? a[a.length - 1].value : null;
};

// 표준정규 CDF (소득이 기준선 아래일 확률 추정용)
function erf(x) {
  const t = 1 / (1 + 0.3275911 * Math.abs(x));
  const y =
    1 -
    ((((1.061405429 * t - 1.453152027) * t + 1.421413741) * t - 0.284496736) * t +
      0.254829592) *
      t *
      Math.exp(-x * x);
  return x >= 0 ? y : -y;
}
const normCdf = (z) => 0.5 * (1 + erf(z / Math.SQRT2));

// income p25/p75(만원)로 정규분포 근사 → 기준소득 미만 비율(%)
function shareBelow(median, p25, p75, baseline) {
  if (median == null || p25 == null || p75 == null || !baseline) return null;
  const sigma = Math.max((p75 - p25) / 1.349, 1e-6);
  return Math.round(normCdf((baseline - median) / sigma) * 100);
}

// 지표 축 정본 — backend indicators.INDICATOR_KEYS 및 온보딩 가치축과 같은 순서.
export const AXES = ["경제", "성장", "관계", "자기실현", "안정"];

function toOption(scen, label, baseline, ind, detail) {
  const inc = availPts(scen.income);
  const first = inc.length ? inc[0].value : null;
  const last = inc.length ? inc[inc.length - 1].value : null;
  const lastPt = inc.length ? inc[inc.length - 1] : {};
  const change = first && last ? +(((last - first) / first) * 100).toFixed(1) : 0;

  const satis = scen.satisfaction_summary?.latest ?? 3.5; // 1~5
  const growth = lastAvail(scen.growth_potential) ?? 0; // %
  const regret = scen.regret_summary?.worst_value ?? 0; // %
  const base = baseline || first || 300;

  const down = shareBelow(last, lastPt.p25, lastPt.p75, base) ?? Math.max(0, Math.round(30 - change));
  const n = inc.length ? Math.max(...inc.map((p) => p.sample_n || 0)) : scen.satisfaction_summary?.sample_n || 0;

  // 레이더 5축(0~100). 백엔드 indicators(0~1) 정본 사용, 없으면 파생 폴백.
  // 축 이름은 온보딩 가치축(경제·성장·관계·자기실현·안정)과 같다 — 사용자가 정렬한
  // 답과 결과 화면이 같은 어휘를 쓴다.
  const scores = ind
    ? Object.fromEntries(
        AXES.map((ax) => [ax, clamp(Math.round((ind[ax] ?? 0.5) * 100), 8, 100)]),
      )
    : {
        경제: clamp(Math.round(35 + change * 1.4 + (last ? (last - 300) / 8 : 0)), 8, 100),
        성장: clamp(Math.round(45 + growth * 1.5), 8, 100),
        관계: 50,
        자기실현: 50,
        안정: clamp(Math.round(satis * 20 - regret * 0.25), 8, 100),
      };
  // 근거가 없어 중립값(0.5)만 채워진 축. 화면은 이걸 보고 '측정 근거 없음'으로
  // 표시한다 — 0.5 를 측정값처럼 그리면 없는 근거를 있는 것처럼 만든다.
  const unmeasured = detail?.unmeasured ?? (ind ? [] : ["관계", "자기실현"]);
  return {
    label, n: n || 30, income_change_med: change, income_down_pct: down,
    scores, unmeasured,
  };
}

// 이직(A) 인과: 겉보기(관측) vs 순수효과(EconML). 만원 → % 변환.
function toCausal(scenA, baseline, optA) {
  const raw = scenA.raw || {};
  const conf = scenA.confidence?.causal_effect || {};
  const base = baseline || 320;
  const ateWon = conf.linear_ate ?? conf.ate ?? raw.causal_effect ?? null; // 만원
  const effect = ateWon != null ? +((ateWon / base) * 100).toFixed(1) : 6.0;
  const descriptive = Math.max(optA.income_change_med, effect); // 관측(편향 포함) ≥ 순수효과
  let ci;
  const ciWon = conf.linear_ci || conf.ate_ci;
  if (Array.isArray(ciWon) && ciWon.length === 2) {
    ci = [+((ciWon[0] / base) * 100).toFixed(1), +((ciWon[1] / base) * 100).toFixed(1)];
  } else {
    ci = [+(effect * 0.7).toFixed(1), +(effect * 1.3).toFixed(1)];
  }
  return { descriptive, effect, ci };
}

// 이직(A) 이탈/후회 리스크 → survival 곡선(0~1)
function toSurvival(scenA) {
  const pts = availPts(scenA.regret).map((p) => ({ year: p.year, risk: (p.value || 0) / 100 }));
  return { points: pts.length ? pts : [{ year: 1, risk: 0 }] };
}

export function mapSimulateToResult(sim) {
  const cmp = sim.compare;
  const prof = cmp.profile || {};
  const A = cmp.scenarios.A;
  const B = cmp.scenarios.B;
  const baseline = prof.monthly_wage || (availPts(A.income)[0]?.value) || 300;

  const optA = toOption(A, cmp.choice_a, baseline, sim.indicators?.A, sim.indicator_detail?.A);
  const optB = toOption(B, cmp.choice_b, baseline, sim.indicators?.B, sim.indicator_detail?.B);

  const incYears = availPts(A.income).map((p) => p.year);
  const nSample = Math.max(optA.n, optB.n);

  const nar = sim.narrative || {};

  return {
    meta: {
      age: prof.age,
      occupation: occupationGroupLabel(prof.occupation_group) || prof.occupation || prof.major || "—",
      n_sample: nSample,
      observe_years: incYears.length ? Math.max(...incYears) : 5,
      source: "GOMS · YP2021 · KLIPS (L1~L5)",
    },
    option_a: optA,
    option_b: optB,
    causal: toCausal(A, baseline, optA),
    survival: toSurvival(A),
    scenario: {
      a: nar.a || "",
      b: nar.b || "",
      comparison: nar.comparison || "",
    },
    // 부가: 일기·근거(화면 확장용)
    _diary: sim.diary,
    _evidence: sim.evidence,
    _support: sim.support_note,
    _api_used: sim.api_used,
  };
}

function buildSimulateBody({ profile, choiceA, choiceB, choiceADetail, choiceBDetail, choiceADomains, choiceBDomains, choiceAContext, choiceBContext, futureYears = 3, diary }) {
  const body = {
    profile: {
      age: profile.age,
      // 성별은 선택 정보다. 없으면 그대로 비워 보내고 백엔드가 전체 표본으로
      // 떨어뜨린다. 예전엔 `|| "1"` 로 남성을 채웠는데, 고른 적 없는 성별의
      // 유사집단 통계가 붙었다.
      sex: profile.sex || null,
      // 전공 계열은 '사용자가 실제로 고른 경우'에만 보낸다.
      // 예전엔 `profile.major || profile.occupation || "공학"` 이었다. major 는 교육
      // 영역 비교에서만 뜨는 조건부 입력이라 대부분 비어 있는데, 그때 조용히 "공학"이
      // 들어가 서사가 "공학 배경은 창업의 기술적 기초가 될 수 있지만…" 처럼 없는
      // 사실을 말했다. 직종(occupation, 8분류)으로 대신 채우는 것도 안 된다 —
      // 백엔드 major 는 계열명(인문·사회·…)을 기대하는 자리라 값의 종류가 다르다.
      ...(profile.major ? { major: profile.major } : {}),
      monthly_wage: Number(profile.income ?? profile.monthly_wage) > 0 ? Number(profile.income ?? profile.monthly_wage) : null,
      edu_level: profile.edu_level ?? 7,
      occupation_group: profile.occupation_group ?? null,
      employment_status: profile.employment_status ?? null,
      tenure_years: profile.tenure_years ?? null,
      firm_size: profile.firm_size ?? null,
      // MBTI는 수치 예측 피처가 아니라 결과 설명 방식의 약한 prior로만 사용한다.
      // 백엔드가 4개 축을 구조화해 해석하므로 원문 disposition_block에만 의존하지 않는다.
      ...(profile.mbti && profile.mbti !== "모름" ? { mbti: profile.mbti } : {}),
      // 성향 개인화 입력: 온보딩/설정 가치 순위(카드 id). 있을 때만 실어 보낸다.
      // 백엔드가 qmode.value_ranking.axis_weights 로 가중치 변환 → 강조·초점·서사 개인화.
      ...(profile.value_ranking?.length ? { value_ranking: profile.value_ranking } : {}),
    },
    // 두 갈림길 문장도 사용자가 직접 쓴 자유서술이다. 다만 여기 적힌 금액·회사명은
    // 분류·계산에 쓰이므로(choice_classifier, scenarioIntake) 기능 입력 정책으로 가린다.
    choice_a: maskFunctional(choiceA),
    choice_b: maskFunctional(choiceB),
    future_years: futureYears,
  };
  if (profile.value_ranking?.length) body.value_ranking = profile.value_ranking;
  // 상세·조건은 금액이 계산에 쓰이므로(origin 의 '사용자가 적은 조건을 수치에 반영') 금액은
  // 남기고 이름·연락처만 가린다. 반대로 diary 는 순수 자유서술이라 전부 가린다.
  if (choiceADetail?.trim()) body.choice_a_detail = maskFunctional(choiceADetail.trim());
  if (choiceBDetail?.trim()) body.choice_b_detail = maskFunctional(choiceBDetail.trim());
  // 새 삶의 영역 계약용 필드. 현재 백엔드는 extra 필드를 무시하므로 기존 API와 호환된다.
  if (choiceADomains?.length) body.choice_a_domains = choiceADomains;
  if (choiceBDomains?.length) body.choice_b_domains = choiceBDomains;
  if (choiceAContext && Object.keys(choiceAContext).length) body.choice_a_context = maskAnswers(choiceAContext);
  if (choiceBContext && Object.keys(choiceBContext).length) body.choice_b_context = maskAnswers(choiceBContext);
  if (diary) body.diary = maskText(diary);

  // 심리 성향 서술(MBTI + 서술형 답변) → disposition_block + 답변 수(확신도).
  // 백엔드가 서사 프롬프트에 주입 → 개인화 심화.
  const disp = buildDisposition(profile);
  if (disp.block) {
    body.disposition_block = disp.block;
    body.diary_n_answers = disp.n;
  }

  return body;
}

export async function runSimulateRaw(args) {
  const body = buildSimulateBody(args);

  const res = await fetch(`${API_BASE}/simulate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`simulate ${res.status}`);
  return res.json();
}

export async function runCompareRaw(args) {
  const body = buildSimulateBody(args);
  const res = await fetch(`${API_BASE}/compare`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      profile: body.profile,
      choice_a: body.choice_a,
      choice_b: body.choice_b,
      future_years: body.future_years,
      ...(body.choice_a_detail ? { choice_a_detail: body.choice_a_detail } : {}),
      ...(body.choice_b_detail ? { choice_b_detail: body.choice_b_detail } : {}),
      // 삶의 영역(항목3·4) — /compare 도 영역지표·근거수준·그래프 가드를 반환하도록 함께 전송
      ...(body.choice_a_domains ? { choice_a_domains: body.choice_a_domains } : {}),
      ...(body.choice_b_domains ? { choice_b_domains: body.choice_b_domains } : {}),
      ...(body.choice_a_context ? { choice_a_context: body.choice_a_context } : {}),
      ...(body.choice_b_context ? { choice_b_context: body.choice_b_context } : {}),
    }),
  });
  if (!res.ok) throw new Error(`compare ${res.status}`);
  return res.json();
}

export async function classifyChoicePair({ choiceA, choiceB, domainsA = [], domainsB = [] }) {
  const res = await fetch(`${API_BASE}/choices/classify-pair`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      choice_a: maskFunctional(choiceA),
      choice_b: maskFunctional(choiceB),
      choice_a_domain_hints: domainsA,
      choice_b_domain_hints: domainsB,
    }),
  });
  if (!res.ok) throw new Error(`choice classification ${res.status}`);
  return res.json();
}

// 검증 중인 이직 재정 모델을 단독 확인할 때 사용한다.
// 집단 검증값(population_evidence)과 개인 실험값(personalized_estimate)을 구분해 읽어야 한다.
export async function getJobChangeFinancialImpact(profile) {
  const body = buildSimulateBody({ profile, choiceA: "이직", choiceB: "유지" }).profile;
  const res = await fetch(`${API_BASE}/models/job-change/financial-impact`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`job-change financial impact ${res.status}`);
  return res.json();
}

// KOWEPS 25~35세 종단 관측 근거. 개인예측/인과효과가 아니라 사건군·비교군 분포다.
export async function getKowepsEvidence(payload) {
  const res = await fetch(`${API_BASE}/evidence/koweps`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`koweps evidence ${res.status}`);
  return res.json();
}

export async function runSimulate(args) {
  return mapSimulateToResult(await runSimulateRaw(args));
}

// 타임아웃은 백엔드의 실제 상한보다 넉넉해야 한다. 예전엔 60초였는데 백엔드는
// 한 장에 최대 90초(재시도 포함 그 이상)를 쓸 수 있어, 프론트가 먼저 끊고 나면
// 백엔드는 아직 그리는 중인 어긋난 상태가 됐다 — 그때 뜬 게 'Failed to fetch' 다.
// 정상 생성은 두 장 동시에 12초대라 이 값이 실제로 쓰일 일은 드물다.
export async function generateSceneImages({ avatarBlob, avatarSpec, choiceA, choiceB, futureYears = 3, narrative, timeoutMs = 150000 }) {
  const storyText = (story) => {
    if (typeof story === "string") return story;
    const detail = story?.detail || {};
    return [story?.summary, detail.present, detail.transition, detail.future, story?.gain, story?.cost]
      .filter(Boolean)
      .join(" ");
  };
  const form = new FormData();
  // 결과 장면은 화면 크기와 무관하게 데스크톱용 가로 이미지 하나만 생성한다.
  // 같은 시뮬레이션이 모바일/데스크톱 접속 여부에 따라 서로 다른 캐시 키와
  // 이미지 호출을 만들지 않도록 생성 규격을 고정한다.
  const visualSize = { width: 768, height: 432, format: "landscape 16:9" };
  form.append("avatar", avatarBlob, "avatar.png");
  form.append("avatar_spec", JSON.stringify(avatarSpec || {}));
  form.append("choice_a", choiceA);
  form.append("choice_b", choiceB);
  form.append("future_years", String(futureYears));
  form.append("visual_width", String(visualSize.width));
  form.append("visual_height", String(visualSize.height));
  form.append("visual_format", visualSize.format);
  form.append("narrative_a", storyText(narrative.a));
  form.append("narrative_b", storyText(narrative.b));
  form.append("visual_a", JSON.stringify(narrative.visual_a || {}));
  form.append("visual_b", JSON.stringify(narrative.visual_b || {}));

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  let res;
  try {
    res = await fetch(`${API_BASE}/visualize`, {
      method: "POST",
      body: form,
      signal: controller.signal,
    });
  } catch (error) {
    if (error?.name === "AbortError") throw new Error("이미지 생성 시간이 길어 기본 아바타로 전환했습니다.");
    throw error;
  } finally {
    clearTimeout(timeout);
  }
  if (!res.ok) {
    let detail = `visualize ${res.status}`;
    try { detail = (await res.json()).detail || detail; } catch { /* no-op */ }
    throw new Error(detail);
  }
  return res.json();
}

/**
 * SVG 아바타를 구운 PNG 를 참조 이미지로 넘겨 실사 아바타를 생성한다.
 * @param {string} referencePng  "data:image/png;base64,..." (svgElementToPng 결과)
 * @param {string} prompt        buildAvatarPrompt 결과
 * @returns {Promise<string>}    생성된 이미지의 dataURL
 */
export async function generateAvatarPhoto(referencePng, prompt) {
  const res = await fetch(`${BASE_URL}/avatar/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reference_png: referencePng, prompt }),
  });
  if (!res.ok) {
    // 백엔드가 이유를 알려주면 그대로 보여준다(키 미설정 등).
    let detail = `API error: ${res.status}`;
    try {
      const body = await res.json();
      if (body.detail) detail = body.detail;
    } catch { /* 본문이 JSON 이 아니면 상태코드만 */ }
    throw new Error(detail);
  }
  const { image } = await res.json();
  return image;
}
