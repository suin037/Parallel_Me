// ─────────────────────────────────────────────────────────────
// 목업 결과 데이터.
// 나중에 백엔드 POST /simulate 응답으로 이 객체만 갈아끼우면 된다.
// 데이터 접근은 useResult() 훅 한 곳으로 모은다. (ResultContext.jsx)
// ─────────────────────────────────────────────────────────────
export const MOCK_RESULT = {
  meta: {
    age: 27,
    occupation: "연구·공학기술",
    n_sample: 306,
    observe_years: 3,
    source: "GOMS2019 · YP2021",
  },
  option_a: {
    label: "이직",
    scores: { 경제: 62, 성장: 71, 관계: 54, 자기실현: 50, 안정: 58 },
    income_change_med: 11.1,
    income_down_pct: 26.0,
    n: 43,
  },
  option_b: {
    label: "현직 유지",
    scores: { 경제: 58, 성장: 49, 관계: 57, 자기실현: 50, 안정: 61 },
    income_change_med: 0.0,
    income_down_pct: 34.0,
    n: 157,
  },
  causal: { descriptive: 11.1, effect: 6.2, ci: [2.1, 10.3] },
  survival: {
    points: [
      { year: 1, risk: 0.21 },
      { year: 2, risk: 0.34 },
      { year: 3, risk: 0.42 },
    ],
  },
  scenario: {
    a: "당신과 비슷한 27세 연구·공학기술 종사자 중 이직을 택한 43명은, 새 조직에서 성장 기회를 더 넓게 얻은 편이었습니다. 다만 그 길이 모두에게 상승은 아니었습니다.",
    b: "현직에 남은 157명은 소득 변화의 중앙값이 0%로, 큰 도약도 큰 하락도 드물었습니다. 안정 속에서 삶의 질 지표가 상대적으로 높게 유지됐습니다.",
    comparison:
      "이직한 사람들은 성장 지표가 높았고, 남은 사람들은 삶의 질이 높았습니다. 어느 쪽이 정답이라 말할 수 없습니다 — 데이터는 두 갈래에서 살아간 실제 사람들의 기록일 뿐입니다.",
  },
};

// A(이직)=시안, B(잔류)=골드 — 앱 전체에서 끝까지 일관.
export const A_COLOR = "#8B6CCF";
export const B_COLOR = "#F5C86B";

// 유사인물 총원 (43 + 157). 목업이 200 기준으로 서술되어 있어 파생값으로 고정.
export function totalNeighbors(result) {
  return result.option_a.n + result.option_b.n; // 43 + 157 = 200
}

// 아카이브 목업 (지난 시뮬 카드)
export const MOCK_ARCHIVE = [
  {
    id: "0427",
    date: "2026-07-20",
    title: "27세 · 연구·공학기술",
    branch: "이직 vs 현직 유지",
    headline: "이직 43명 소득 중앙값 +11%, 4명 중 1명은 감소",
    reflection: null, // "그 후 어떻게 됐나요?" — placeholder
  },
  {
    id: "0391",
    date: "2026-06-11",
    title: "26세 · 경영·사무",
    branch: "대학원 vs 취업 유지",
    headline: "진학 18명 중 소득 회복까지 중앙값 2년",
    reflection: "3개월 지나 보니, 그때 남기로 한 선택이 아직은 맞는 것 같다.",
  },
  {
    id: "0355",
    date: "2026-05-02",
    title: "29세 · 보건·의료",
    branch: "지방 이전 vs 수도권 잔류",
    headline: "이전 27명, 삶의 질 지표는 올랐으나 소득은 정체",
    reflection: null,
  },
];

// ─────────────────────────────────────────────────────────────
// '나의 우주' 대시보드 목업 (게이미피케이션 = 개인화 공간).
// ※ 결과/데이터 화면의 정직성과 분리된, 사용자의 우주를 꾸미는 레이어.
//   이 수치들은 실측 데이터가 아니라 앱 참여 지표(별=체크인 등)다.
// ─────────────────────────────────────────────────────────────
// @deprecated — 실제 값은 data/myUniverse.js 의 universeSummary() 에서 파생한다.
// 다른 브랜치가 참조 중일 수 있어 상수만 남겨둠. 병합 정리 후 삭제 예정.
export const MY_UNIVERSE = {
  level: 23,
  title: "우주 탐험가",
  xp: 12450,
  xpMax: 15000,
  starsToday: 3,
  starsGoal: 3,
  checkinDays: 93,
  // 별자리 라인 (수집한 별의 궤적) — 참여 기록일 뿐, 미래 예측 아님
  constellation: [
    { i: 1, v: 2 },
    { i: 2, v: 4 },
    { i: 3, v: 3 },
    { i: 4, v: 2 },
    { i: 5, v: 5 },
    { i: 6, v: 3 },
  ],
  stats: { simulations: 12, stars: 187, universes: 8 },
};

// 행성 = 삶의 영역. 선택하면 그 영역의 시뮬레이션 우주로.
//
// kind 는 실제 raster 표면 위에 적용할 물리 재질만 고른다.
// 화면 텍스처는 data/planetSurface.js의 행성별 고해상도 PNG를 사용한다.
export const PLANETS = [
  // 진로 — 목성·토성형 가스행성. 네온 보라가 아니라 먼지 낀 라벤더·모브.
  { key: "career", label: "진로", kind: "gas", from: "#382E4C", to: "#B7A5CE" },
  // 삶의 만족 — 화성·금성형 암석행성. 채도 높은 주황이 아니라 테라코타·복숭앗빛 먼지.
  { key: "life", label: "삶의 만족", kind: "rocky", from: "#553321", to: "#D2A183" },
  // 관계 — 화성형 붉은 암석행성. 산화철 붉은색·차분한 진홍. 위 테라코타보다 어둡고 붉다.
  { key: "relation", label: "관계", kind: "rocky", from: "#45180F", to: "#AE5740" },
  // 건강 — 천왕성형 얼음행성. 선명한 초록이 아니라 씨폼·탁한 청록.
  { key: "health", label: "건강", kind: "ice", from: "#2A5651", to: "#A3CFC7" },
  // 성장성 — 해왕성·지구형 바다행성. 네이비·코발트에 흰 구름.
  { key: "growth", label: "성장성", kind: "ocean", from: "#0E2145", to: "#7BA5D6" },
];

// 저장된 평행우주 슬롯
export const SAVED_UNIVERSES = [
  { id: "A", label: "우주 A", sub: "취업 경로", from: "#3a2a6d", to: "#6d4aa0", current: true },
  { id: "B", label: "우주 B", sub: "연구 경로", from: "#12324d", to: "#1f6fa0", current: false },
  { id: "C", label: "우주 C", sub: "창업 시나리오", from: "#4d1230", to: "#a01f5a", current: false },
];

// 가이드 마스코트 (Nova/Lumi/Cosmo)
export const MASCOTS = {
  nova: { key: "nova", name: "노바 · Nova", role: "COMET GUIDE", tag: "유성 가이드", color: "#FF9EC0", desc: "예상치 못한 기회와 변화를 전해주는 에너지 넘치는 가이드예요.", traits: ["호기심", "순발력", "활력"] },
  lumi: { key: "lumi", name: "루미 · Lumi", role: "STAR GUIDE", tag: "별빛 가이드", color: "#FFD97A", desc: "별자리와 기록을 돌보며 사용자의 성장을 응원하는 다정한 안내자예요.", traits: ["다정함", "꾸준함", "응원"] },
  cosmo: { key: "cosmo", name: "코스모 · Cosmo", role: "PLANET EXPLORER", tag: "행성 탐험가", color: "#8B6CCF", desc: "데이터와 결과를 분석해 침착하게 미래를 안내하는 탐험가예요.", traits: ["차분함", "분석력", "신뢰"] },
};
