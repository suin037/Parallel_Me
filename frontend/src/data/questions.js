// 질문형 일기 문항 — qmode diary_module/qmode/questions.json 미러(프론트 데모용).
// 고정 2(C1·C2) + 랜덤 2(취향 1 + 관계 1). 성향 신호의 핵심.
// 실서비스에선 backend scheduler.plan_day()가 출제 → 여기 하드코딩 대체.

export const CORE = [
  { id: "C1", layer: "core", text: "오늘 가장 기억에 남는 순간 하나만 편하게 적어주세요." },
  { id: "C2", layer: "core", text: "오늘 가장 마음이 걸린 순간, 그때 나는 무엇을 했나요? 옆에서 본 사람이라면 뭐가 보였을까요?" },
];

const TASTE = [
  { id: "T1", layer: "taste", text: "최근 꽂힌 영화·책·영상 하나. 어떤 장면이나 인물이 남았나요?" },
  { id: "T4", layer: "taste", text: "요즘 시간이 가장 잘 녹아 없어지는 활동은? 하고 난 뒤 어떤 기분이 남나요?" },
  { id: "T2", layer: "taste", text: "요즘 반복해서 듣는 노래나 플레이리스트 있나요? 주로 언제 손이 가나요?" },
  { id: "T7", layer: "taste", text: "오늘 에너지를 가장 크게 받은 일이 있다면 무엇인가요? 그게 왜 힘이 됐을까요?" },
];

const RELATION = [
  { id: "R3", layer: "relation", text: "오늘 잘 됐던 일 하나만 꼽는다면? 그게 왜 잘 됐다고 생각하나요?" },
  { id: "R4", layer: "relation", text: "최근 '이건 좀 나답지 않다' 싶었던 순간이 있었나요?" },
  { id: "R5", layer: "relation", text: "이번 주 나를 가장 지치게 한 건? 같은 상황의 친구라면 뭐가 필요해 보일까요?" },
];

// 성향 심화(구 설정 화면의 성향 질문 D2·D1·D4를 이 리스트로 이관 — 매일 하나 로테이션).
const DEPTH = [
  { id: "D2", layer: "depth", text: "지금 삶에서 늘리고 싶은 것 하나, 줄이고 싶은 것 하나를 꼽는다면?" },
  { id: "D1", layer: "depth", text: "최근 망설인 선택이 있나요? 무엇이 마음에 걸렸나요?" },
  { id: "D4", layer: "depth", text: "최근 누군가가 부러웠던 순간이 있나요? 무엇이 부러웠나요?" },
];

// 날짜 기반 결정적 픽(같은 날 = 같은 문항). 실제 scheduler의 7일 무중복은 backend 몫.
function pickBy(arr, seed) {
  return arr[seed % arr.length];
}

export function todayQuestions(date = new Date()) {
  const seed = date.getFullYear() * 1000 + (date.getMonth() + 1) * 40 + date.getDate();
  return [...CORE, pickBy(TASTE, seed), pickBy(RELATION, seed + 1), pickBy(DEPTH, seed + 2)];
}

// qid → 질문 텍스트 (답변 표시에 "어떤 질문이었는지" 보여주기 위함)
const ALL = [...CORE, ...TASTE, ...RELATION, ...DEPTH];
export function questionText(qid) {
  return ALL.find((q) => q.id === qid)?.text || qid;
}

// 질문 텍스트 → qid (체크인 answers[{q,a}] → 성향 API 형식 {qid:a} 변환용).
export function qidByText(text) {
  return ALL.find((q) => q.text === text)?.id || null;
}

// 30초 데일리 체크인 — 칩 3개. 감정 키워드가 그날 별의 밝기(mood 1~5)를 정한다.
export const CHECKIN = {
  energy: {
    q: "오늘 에너지 레벨은?",
    opts: [
      { v: 1, label: "낮음" },
      { v: 2, label: "보통" },
      { v: 3, label: "좋음" },
      { v: 4, label: "넘침" },
    ],
  },
  competency: {
    q: "오늘 주로 쓴 역량·시간은?",
    opts: ["기술", "소통", "기획", "리더십", "개인공부", "휴식"],
  },
  emotion: {
    q: "오늘 감정 키워드 하나는?",
    opts: [
      { key: "성취감", mood: 5 },
      { key: "설렘", mood: 4 },
      { key: "답답함", mood: 2 },
      { key: "지침", mood: 1 },
    ],
  },
};

// 기분 5단계 — 그날 별의 밝기(mood 1~5).
export const MOODS = [
  { v: 1, emoji: "😞", label: "힘듦" },
  { v: 2, emoji: "😕", label: "지침" },
  { v: 3, emoji: "😐", label: "그저" },
  { v: 4, emoji: "🙂", label: "괜찮음" },
  { v: 5, emoji: "😄", label: "좋음" },
];
