import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { addCheckin, setDomains, syncDiaryEntries } from "./myUniverse.js";
import { tagDomain } from "./dispositionApi.js";
import { LIFE_DOMAINS, detectLifeDomains } from "./choices.js";
import storage from "./safeStorage.js";

// ─────────────────────────────────────────────────────────────
// 일기(오늘 기록) — 매일 한 줄 + 기분(1~5). localStorage로 영속.
// 자체 완결형: 감정감지(detectEmotions)까지 이 파일에 포함(외부 의존 X).
// 저장 시 최근 시뮬 기준으로 자동 태깅("이직 시뮬 #3 이후 47일째").
// ⚠️ 정직성: 이건 '당신의 주관적 기록'이지 실측 데이터가 아니다.
// ─────────────────────────────────────────────────────────────
const DiaryContext = createContext(null);
const KEY = "pm_diary_v5"; // 시드 갱신 시 버전업 → 옛 localStorage 무시하고 새 시드 로드

export const MOODS = [
  { v: 1, emoji: "😞", label: "힘듦" },
  { v: 2, emoji: "😕", label: "지침" },
  { v: 3, emoji: "😐", label: "그저그럼" },
  { v: 4, emoji: "🙂", label: "괜찮음" },
  { v: 5, emoji: "😄", label: "좋음" },
];
export const moodEmoji = (v) => MOODS.find((m) => m.v === v)?.emoji || "•";

// 자유서술 → 감정 신호어 감지 → 심리 이론카드 매칭
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

function iso(d) {
  return d.toISOString().slice(0, 10);
}
function daysAgo(n) {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d;
}

// 최근 시뮬 기록 (자동 태깅 + 아카이브 기준). 데모 시드.
export const SIM_LOG = [
  { id: 3, label: "이직 시뮬 #3", date: iso(daysAgo(47)), title: "27세 · 연구·공학기술", branch: "이직 vs 현상 유지", headline: "이직 순수효과 +7.9만원, 26%는 감소" },
  { id: 2, label: "진학 시뮬 #2", date: iso(daysAgo(120)), title: "26세 · 경영·사무", branch: "대학원 vs 현상 유지", headline: "같은 계열 취업률 70% · 진학률 4%" },
  { id: 1, label: "창업 시뮬 #1", date: iso(daysAgo(180)), title: "29세 · 보건·의료", branch: "창업 vs 현상 유지", headline: "창업 1년 생존율 64.6%, 5년 33%" },
];

// 최근 한 달(4주) 데모 일기 — 워라밸·이직 고민(은우). 1주 무기력 → 4주 '면접 결심'까지,
// 한 달에 걸쳐 기분이 회복되고 성향이 '움직이는 사람'으로 빌드업되는 흐름.
function seedEntries() {
  const rows = [
    // 4주 전(가장 오래) — 순수 번아웃·무기력
    { d: 28, mood: 1, text: "그냥 버틴다. 하루가 어떻게 갔는지 모르겠다." },
    { d: 27, mood: 1, text: "야근. 퇴근하고 넷플에 맥주 한 캔이 유일한 내 시간." },
    { d: 26, mood: 2, text: "무한도전 옛날 편 또 봄. 새로운 거 볼 기력도 없다." },
    { d: 25, mood: 1, text: "회의 내내 멍했다. 아무 생각이 없다." },    { d: 23, mood: 1, text: "다 놓고 싶다는 생각이 문득. 근데 그냥 출근한다." },
    { d: 22, mood: 2, text: "점심 한 시간이 하루의 유일한 낙." },
    // 3주 전 — 문제 자각
    { d: 21, mood: 2, text: "아침에 일어나기가 너무 힘들다. 번아웃인가." },
    { d: 20, mood: 2, text: "정시 퇴근 실패. 상사가 6시에 일 던짐." },
    { d: 19, mood: 2, text: "이게 맞나 싶다. 연봉은 나쁘지 않은데 삶이 없다." },    { d: 17, mood: 2, text: "주말 출근 얘기에 거절을 못 했다. 자책." },
    { d: 16, mood: 2, text: "몸이 자꾸 신호를 보낸다. 두통, 소화불량." },
    { d: 15, mood: 3, text: "친구들이랑 저녁. 회사 밖 사람 만나니 숨통 트임." },
    // 2주 전 — 준비 시작
    { d: 14, mood: 2, text: "친구가 워라밸 좋은 데로 이직했다는 소식. 부러웠다." },    { d: 12, mood: 3, text: "주말 등산. 정상서 김밥 꿀맛. 이 맛에 버틴다." },
    { d: 11, mood: 3, text: "이력서 초안을 드디어 썼다. 미루던 걸 시작해 후련." },    { d: 9, mood: 3, text: "이직한 선배한테 조언 구하려고 먼저 연락했다." },
    { d: 8, mood: 3, text: "이직 지원 두 군데 넣음. 겁나도 일단 넣으니 되긴 하네.",
      answers: { C2: "지원 버튼 누르기까지 오래 걸렸다. 겁났지만 결국 눌렀다.",
                 D2: "저녁 있는 삶을 늘리고 싶고, 의미 없는 야근을 줄이고 싶다." } },
    // 이번 주(가장 최근) — 결심
    { d: 7, mood: 3, text: "일요일 늦잠에 브런치. 이런 여유가 오랜만." },
    { d: 6, mood: 3, text: "지원 버튼 앞에서 또 망설였다. 그래도 정시 퇴근은 지켰다." },
    { d: 5, mood: 3, text: "부당한 요청에 처음으로 선을 그었다. 늘 참던 나인데." },
    // 한 줄 없이 '질문 일기'만 쓴 날 (표시·분석 둘 다 되는지 데모)
    { d: 4, mood: 3, text: "",
      answers: { C2: "면접 제안이 왔는데 안정 놓기가 무서워 답장을 미뤘다. 이 망설임이 계속 나를 잡는다.",
                 R4: "평소 도전 안 하던 내가 이직을 진지하게 보는 게 좀 나답지 않다." } },
    { d: 3, mood: 4, text: "퇴근하고 홈트하니 개운. 이직한 선배에게 조언도 구했다.",
      answers: { C1: "홈트 끝나고 개운했던 저녁.",
                 R3: "먼저 연락해 선배한테 조언 구한 것. 움직이니까 정보가 생긴다." } },
    { d: 2, mood: 3, text: "면접 볼지 조건 표로 비교 중. 결정을 못 내리는 내가 제일 지친다." },
    { d: 1, mood: 4, text: "결국 면접 보기로 답장했다. 미루기만 하던 내가 움직였다.",
      answers: { C1: "면접 보기로 답장을 보낸 순간.",
                 C2: "안정을 놓기가 무서웠지만 지금처럼 사는 게 더 무서웠다. 결국 눌렀다.",
                 R3: "미루기만 하던 내가 움직인 것. 지친 저녁 판단 말고 개운한 날 결정한 게 컸다." } },
  ];
  return rows.map((r, i) => ({
    id: `seed-${i}`, date: iso(daysAgo(r.d)), mood: r.mood, text: r.text,
    ...(r.answers ? { answers: r.answers } : {}),
  }));
}

function load() {
  try {
    const raw = storage.getItem(KEY);
    if (raw) return JSON.parse(raw);
  } catch (_) {}
  return seedEntries();
}

export function DiaryProvider({ children }) {
  const [entries, setEntries] = useState(load);

  useEffect(() => {
    try {
      storage.setItem(KEY, JSON.stringify(entries));
    } catch (_) {}
    // JY 일기 저장소의 기존 기록까지 나의 우주 별/별자리 데이터로 연결한다.
    syncDiaryEntries(entries);
  }, [entries]);

  // 오늘 기록 추가/갱신 (하루 1개, 같은 날이면 덮어씀).
  // answers: {qid: 답변} — 질문형 일기(자세히 쓰기). 없으면 빠른 체크인만.
  function saveToday(mood, text, answers = null, extra = {}) {
    const today = iso(new Date());
    const forTag = [text, ...(answers ? Object.values(answers) : [])]
      .filter((s) => (s || "").trim())
      .join(" ");
    const immediateDomains = detectLifeDomains(forTag);
    // 일기 저장과 나의 우주 별 저장을 같은 사용자 행동으로 동기화한다.
    addCheckin({
      date: today,
      mood,
      energy: extra.energy,
      skill: extra.competency,
      keyword: extra.emotion,
      note: text,
      text,
      answers,
      insights: extra.insights ?? null,
      chatSummary: extra.chatSummary ?? null,
      domains: immediateDomains.length ? immediateDomains : null,
      diaryId: `e-${today}`,
    });
    // 영역(행성) 자동 분류 — 저장 후 비동기로 태깅해 그날 체크인에 domains 를 채운다(지구본 렌즈용).
    if (forTag) {
      tagDomain(forTag).then((r) => {
        const validKeys = new Set(LIFE_DOMAINS.map((domain) => domain.key));
        // 서버가 구형 5행성 키를 반환해도 9영역 저장값을 덮어쓰지 않는다.
        const serverDomains = (r?.domains || []).filter((key) => validKeys.has(key));
        const merged = [...new Set([...immediateDomains, ...serverDomains])];
        if (merged.length) setDomains(today, merged);
      });
    }
    setEntries((prev) => {
      const rest = prev.filter((e) => e.date !== today);
      const entry = { id: `e-${today}`, date: today, mood, text, ...extra }; // extra: energy·competency·emotion
      if (answers && Object.values(answers).some((v) => (v || "").trim())) {
        entry.answers = answers;
      }
      return [...rest, entry].sort((a, b) => (a.date < b.date ? -1 : 1));
    });
  }

  const todayEntry = entries.find((e) => e.date === iso(new Date())) || null;
  const lastSim = SIM_LOG[0];

  function entriesSince(dateStr) {
    return entries.filter((e) => e.date >= dateStr).sort((a, b) => (a.date < b.date ? -1 : 1));
  }
  function daysSince(dateStr) {
    const ms = new Date(iso(new Date())) - new Date(dateStr);
    return Math.max(0, Math.round(ms / 86400000));
  }

  const value = useMemo(
    () => ({ entries, saveToday, todayEntry, lastSim, entriesSince, daysSince }),
    [entries],
  );
  return <DiaryContext.Provider value={value}>{children}</DiaryContext.Provider>;
}

export function useDiary() {
  const ctx = useContext(DiaryContext);
  if (!ctx) throw new Error("useDiary must be used within <DiaryProvider>");
  return ctx;
}
