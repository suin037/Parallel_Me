// ─────────────────────────────────────────────────────────────
// /predict 응답 형태의 목업 (suin-model docs/API.md 계약 기준).
// 나중에 이 함수만 fetch('/predict') 결과로 갈아끼우면 됨.
//
// A/B 자유 구성: 각 슬롯을 {유지·이직·창업·진학} 중 자유 선택 → 각각 예측.
// choice에 따라 제공 필드가 다르다(coverage):
//  - 이직: 개인단위(유사인물 L2·인과 L3·재직생존 L4) 전부
//  - 창업: 개인단위 없음 → 창업 생존율·폐업 타임라인
//  - 진학: 개인단위 없음 → 계열 취업률·진학률
//  - 유지: 개인단위 없음 → 유지 시 통계·궤적(기준선)
//  - 생활지표·소득궤적은 모든 선택지에서 제공
//
// ※ 백엔드엔 '이직 vs 창업' 직접 인과모델은 없음. A/B가 둘 다 변화면
//   "두 개의 독립된 거울"이지 직접 인과비교가 아니다(UI 캡션에 명시).
//
// 목업 수치는 실측 관측값 근거(임금 고용형태별근로실태조사, 취업률 KEDI,
// 생존율 기업생멸, 스트레스 KNHANES/KWCS, 만족도 청년삶의질 등).
// ─────────────────────────────────────────────────────────────

import { occupationLabel } from "./profileOptions.js";

// A/B 슬롯에서 고를 수 있는 카테고리 (유지 포함)
export const SLOT_OPTIONS = [
  { key: "유지", label: "현상 유지", desc: "지금 그대로라면", emoji: "🌙" },
  { key: "이직", label: "이직", desc: "다른 회사·직무로 옮긴다", emoji: "🚀" },
  { key: "창업", label: "창업", desc: "내 사업을 시작한다", emoji: "🌱" },
  { key: "진학", label: "진학", desc: "대학원·유학으로 진학한다", emoji: "🎓" },
];

export const LIFE_DIMENSIONS = {
  경제: { icon: "💰", color: "#8B6CCF" },
  삶의질: { icon: "🌿", color: "#7FE0D4" },
  정신건강: { icon: "🧠", color: "#8B6CCF" },
  신체건강: { icon: "❤️", color: "#FF9EBC" },
  직업환경: { icon: "🏢", color: "#F5C86B" },
  "진학·취업": { icon: "🎓", color: "#8B6CCF" },
  창업: { icon: "🌱", color: "#7FE0A6" },
};

const BASE_LIFE = [
  { dimension: "경제", indicator: "또래 평균 월임금(전체근로자)", value: 269.1, unit: "만원", group: "29세이하·2025", source: "고용형태별근로실태조사(KOSIS)", n: null },
  { dimension: "삶의질", indicator: "삶의 만족도", value: 6.5, unit: "점/10", group: "청년 25-29·2024", source: "청년삶의질조사(국가데이터처)", n: null },
  { dimension: "정신건강", indicator: "스트레스 인지율", value: 30.7, unit: "%", group: "19-29세", source: "국민건강영양조사(KNHANES 제9기)", n: 1915 },
  { dimension: "직업환경", indicator: "업무 스트레스 경험", value: 33.0, unit: "%", group: "취업자·2023", source: "근로환경조사(KWCS 7차)", n: 50045 },
  { dimension: "신체건강", indicator: "주관적 건강 인지율", value: 71.2, unit: "%", group: "19-29세", source: "국민건강영양조사(KNHANES 제9기)", n: 1915 },
];

// 선택지별 소득 궤적 형태 (년: 0,1,2,3,4,5,7,10). 관찰 분포(예측 아님).
const YEARS = [0, 1, 2, 3, 4, 5, 7, 10];
const SAMPLE_N = { 0: 300, 1: 262, 2: 205, 3: 168, 4: 131, 5: 96, 7: 58, 10: 24 };
const GROWTH = {
  유지: [1, 1.02, 1.04, 1.06, 1.08, 1.1, 1.13, 1.18],
  이직: [1, 1.05, 1.1, 1.15, 1.19, 1.24, 1.31, 1.42],
  창업: [1, 0.9, 1.0, 1.15, 1.28, 1.4, 1.55, 1.85], // 변동 큼
  진학: [1, 0.72, 0.78, 1.05, 1.2, 1.33, 1.46, 1.62], // 초반 하락 후 반등
};
const SPREAD = { 유지: 0.14, 이직: 0.2, 창업: 0.42, 진학: 0.26 }; // p25~p75 폭

function incomeTrajectory(baseWage, choice) {
  const g = GROWTH[choice] || GROWTH["유지"];
  const s = SPREAD[choice] ?? 0.18;
  return YEARS.map((y, i) => {
    const mid = Math.round(baseWage * g[i]);
    return {
      year: y,
      age: 27 + y,
      sample_n: SAMPLE_N[y],
      income_p25: Math.round(mid * (1 - s)),
      income_p50: mid,
      income_p75: Math.round(mid * (1 + s)),
      job_change_cum: y === 0 || choice !== "이직" ? null : +Math.min(0.62, y * 0.075).toFixed(3),
    };
  });
}

function wellbeingTrajectory() {
  const pts = [
    { year: 0, satis: 3.3 }, { year: 1, satis: 3.4 }, { year: 2, satis: 3.5 },
    { year: 3, satis: 3.6 }, { year: 4, satis: 3.6 },
  ];
  const nByYear = { 0: 280, 1: 236, 2: 190, 3: 150, 4: 118 };
  return pts.map((p) => ({
    year: p.year, age: 27 + p.year, sample_n: nByYear[p.year],
    satis_p25: +(p.satis - 0.5).toFixed(1), satis_p50: p.satis, satis_p75: +(p.satis + 0.5).toFixed(1),
  }));
}

function neighbors() {
  const rows = [];
  const jobs = ["소프트웨어 개발", "연구직", "기계·전자", "데이터 분석", "기술영업"];
  for (let i = 0; i < 12; i++) {
    const isGOMS = i % 3 !== 0;
    rows.push({
      source: isGOMS ? "GOMS" : "YP",
      similarity: +(0.92 - i * 0.02).toFixed(2),
      monthly_wage: 230 + ((i * 13) % 90),
      job_category: isGOMS ? jobs[i % jobs.length] : null,
      satis_overall: 3 + (i % 3),
      life_satis: isGOMS ? 4 + (i % 2) : null,
      job_changed: i % 2,
    });
  }
  return rows;
}

export const ACTION_CARDS = [
  {
    concept: "가능자기 (Possible selves)",
    theory: "미래자기 · Markus & Nurius (1986)",
    summary: "'되고 싶은 나 / 되기 두려운 나 / 될 것 같은 나'를 구체적으로 그리면 현재 선택의 방향이 또렷해집니다.",
    interventions: [
      "3년 뒤 '되고 싶은 나'의 하루를 장면 하나로 적어보기(어디서·무엇을·누구와).",
      "'절대 되고 싶지 않은 나'도 한 장면 적고, 이번 주 바꿀 작은 습관 하나 정하기.",
    ],
    source: "American Psychologist, 41(9)",
  },
  {
    concept: "반사실적 사고 (Counterfactual)",
    theory: "의사결정 후회 이론",
    summary: "'그때 다른 선택을 했다면'을 건강하게 다루면 후회가 학습으로 바뀝니다. 지나친 상향 반사실은 무기력을 부릅니다.",
    interventions: [
      "선택하지 않은 길의 '좋은 점'과 '힘든 점'을 각각 2개씩 적어 균형 맞추기.",
      "지금 선택에서 내가 통제할 수 있는 것 한 가지에 집중하기.",
    ],
    source: "Decision-making & Regret",
  },
];

// 단일 선택지 예측 조립
export function getPrediction({ profile, choice = "이직", detail = "" } = {}) {
  const baseWage = profile?.income || 250;
  const traj = incomeTrajectory(baseWage, choice);
  const meta = {
    age: profile?.age || 27,
    // 직종을 안 고른 사람에게 특정 직종을 지어 보여주지 않는다(예전 기본값은
    // "연구·공학기술" 이었다 — 화면상 사용자가 입력한 값처럼 보인다).
    occupation: occupationLabel(profile) || "—",
    observe_years_income: 10,
    observe_years_wellbeing: 4,
    source: "GOMS·YP · KOSIS · KNHANES·KWCS · KEDI",
  };
  const common = {
    choice, detail, meta,
    life_indicators: [...BASE_LIFE],
    trajectory: traj,
    wellbeing_trajectory: wellbeingTrajectory(),
    action_cards: ACTION_CARDS,
    narrative: "",
    expected_wage: null, causal_effect: null, descriptive_effect: null, survival_months: null,
    neighbors: [], neighbor_changed_ratio: null, down_ratio: null,
    risk_timeline: {}, risk_label: null,
    return_timeline: {},   // 쉬어가기 전용 — {개월: 복귀 누적확률}
  };

  if (choice === "이직") {
    return {
      ...common,
      coverage: "이직: 개인단위 매칭(L2)·인과(L3)·재직생존(L4) + 생활지표(L1)",
      expected_wage: Math.round(baseWage * 0.98 + 5),
      causal_effect: 7.9,
      descriptive_effect: 14.1,
      survival_months: 86.0,
      neighbors: neighbors(),
      neighbor_changed_ratio: 0.215,
      down_ratio: 0.26,
      risk_timeline: { 1: 0.028, 3: 0.18, 5: 0.336 },
      risk_label: "재이직 확률",
    };
  }
  if (choice === "창업") {
    return {
      ...common,
      coverage: "창업: 개인단위 없음 → 창업 생존율·폐업 타임라인 + 생활지표",
      risk_timeline: { 1: 0.354, 3: 0.62, 5: 0.667 },
      risk_label: "폐업 확률",
      life_indicators: [
        ...BASE_LIFE,
        { dimension: "창업", indicator: "창업 1년 생존율", value: 64.6, unit: "%", group: "전체 업종", source: "기업생멸행정통계(KOSIS)", n: null },
        { dimension: "창업", indicator: "창업 5년 생존율", value: 33.3, unit: "%", group: "전체 업종", source: "기업생멸행정통계(KOSIS)", n: null },
      ],
    };
  }
  if (choice === "진학") {
    return {
      ...common,
      coverage: "진학: 개인단위 없음 → 계열 취업률·진학률 + 생활지표",
      life_indicators: [
        ...BASE_LIFE,
        { dimension: "진학·취업", indicator: "공학계열 취업률", value: 69.1, unit: "%", group: "2024 졸업자", source: "고등교육기관 졸업자 상황(KEDI)", n: 160328 },
        { dimension: "진학·취업", indicator: "공학계열 진학률", value: 10.6, unit: "%", group: "2024 졸업자", source: "고등교육기관 졸업자 상황(KEDI)", n: 160328 },
      ],
    };
  }
  if (choice === "휴식") {
    // 데모 수치는 지어내지 않고 실제 학습 결과(KLIPS 직업력 공백 스펠 5,209건)의
    // 전체 KM 곡선을 그대로 쓴다. 실서버가 붙으면 개인 조건으로 갈릴 뿐 결이 같다.
    return {
      ...common,
      coverage: "쉬어가기: 인과(L3)·복귀생존(L4) + 생활지표 / L4는 '후회'가 아니라 복귀까지 걸리는 기간",
      causal_effect: 18.0,
      survival_months: 15.0,
      return_timeline: { 3: 0.202, 6: 0.335, 12: 0.489, 24: 0.679 },
      risk_timeline: { 1: 0.511, 3: 0.29, 5: 0.198 },
      risk_label: "미복귀확률",
    };
  }
  // 유지 (기준선)
  return {
    ...common,
    coverage: "현상 유지: 유지 시 또래 통계 + 소득·만족도 궤적(기준선)",
  };
}

// A/B 쌍 예측
export function getPredictionPair({ profile, choiceA = "이직", choiceB = "유지", detail = "" }) {
  return {
    a: getPrediction({ profile, choice: choiceA, detail }),
    b: getPrediction({ profile, choice: choiceB, detail }),
  };
}

export function pairHasIndividual(pair) {
  return pair.a.choice === "이직" || pair.b.choice === "이직";
}

// 화면 표시용 라벨 (유지 → 현상 유지)
export const labelOf = (c) => (c === "유지" ? "현상 유지" : c);

// ── 자유서술 → 카테고리 자동분류 (백엔드 choice 분류 규칙 미러) ──
// 우선순위 검사: '이직' 행동어가 있으면 목적지(스타트업 등)보다 이직을 우선한다.
// 예) "스타트업으로 이직할지" → 창업(X) → 이직(O)
const KW = {
  이직: ["이직", "옮기", "옮길", "전직", "갈아타", "이직할", "회사 옮", "다른 회사로"],
  진학: ["진학", "대학원", "유학", "석사", "박사", "학위", "로스쿨", "편입", "공부하러"],
  창업: ["창업", "사업", "자영", "개업", "장사", "내 사업", "법인", "대표", "차릴", "차리", "스타트업 차"],
  // '퇴사'는 여기 둔다. 갈 곳이 정해졌으면 보통 '이직·입사'를 같이 쓰고,
  // 그 경우 위의 이직 검사가 먼저 잡는다(행동어 최우선).
  휴식: ["휴직", "쉬어가", "쉬고 싶", "쉬려", "잠시 쉬", "좀 쉬", "퇴사", "그만두", "그만둘",
        "번아웃", "공백기", "갭이어", "안식년", "재충전"],
  유지: ["유지", "그대로", "현직", "잔류", "남을", "남기", "계속 다니", "계속 있", "안 옮", "지금 회사"],
};
export function classifyChoice(text) {
  if (!text || !text.trim()) return null;
  if (KW.이직.some((k) => text.includes(k))) return "이직"; // 행동어 최우선
  if (KW.진학.some((k) => text.includes(k))) return "진학";
  if (KW.창업.some((k) => text.includes(k))) return "창업";
  if (KW.휴식.some((k) => text.includes(k))) return "휴식";
  if (KW.유지.some((k) => text.includes(k))) return "유지";
  return null; // 판단 근거가 없으면 자동으로 이직을 만들지 않는다.
}

// ── 자유서술 → 감정 신호어 감지 → 심리 이론카드 매칭 (RAG 트리거 미리보기) ──
const EMOTION_MAP = [
  { kw: ["막막", "방향", "무기력", "공허", "모르겠"], keyword: "막막함", card: "미래자기 · 가능자기" },
  { kw: ["불안", "두려", "걱정", "압박", "겁", "초조"], keyword: "불안", card: "인지적 평가 · 위협→도전" },
  { kw: ["후회", "아쉬", "그때", "미련"], keyword: "후회", card: "반사실적 사고" },
  { kw: ["지치", "번아웃", "소진", "힘들", "버겁"], keyword: "소진", card: "문제중심 대처" },
  { kw: ["설레", "기대", "신남", "두근"], keyword: "기대", card: "긍정정서 · 확장" },
];
export function detectEmotions(text) {
  if (!text) return [];
  const out = [];
  for (const e of EMOTION_MAP) {
    if (e.kw.some((k) => text.includes(k))) out.push({ keyword: e.keyword, card: e.card });
  }
  return out;
}
