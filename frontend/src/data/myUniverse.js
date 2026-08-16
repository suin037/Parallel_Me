// ─────────────────────────────────────────────────────────────
// '나의 우주' 로컬 저장소 — 체크인(별)·XP·행성·핀 슬롯. 나의 우주 화면(민주) 소관.
// savedUniverses.js / prefs.js 와 같은 패턴: localStorage + 순수함수, 외부 의존 없음.
//
// 확정된 규칙
//  · 별 1개 = 하루 1개. 같은 날 다시 기록하면 그날 별을 덮어쓴다(upsert).
//  · 별자리 1개 = 별 7개(1주). 주간 리포트 주기와 맞춘다.
//  · XP 는 저장하지 않고 활동 기록에서 매번 파생한다(중복 적립·불일치 방지).
// ─────────────────────────────────────────────────────────────

import { listUniverses } from "./savedUniverses.js";
import storage from "./safeStorage.js";

const KEY = "pm.myuniverse.v1";
const HIGHEST_LEVEL_KEY = "pm.highestLevel.v1";

// 별자리 하나를 이루는 별 수. 12(황도12궁)는 완성까지 12일이라 신규 사용자가
// 첫 별자리를 영영 못 본다. 7일이면 1주 리듬 + 주간 리포트와 주기가 맞는다.
export const STARS_PER_CONSTELLATION = 7;

const DEFAULTS = {
  checkins: [], // [{ date, mood, valence, energy, skill, keyword, note, hasDiary }]
  pinnedSlots: { A: null, B: null, C: null }, // savedUniverses 의 id 포인터 (데이터 복사 X)
  planet: "career",
  simRuns: 0, // 시뮬레이션 실행 횟수 (다른 저장소에 카운터가 없어 여기서 센다)
  demo: false, // 예시 기록으로 채워진 상태인가 (화면에 배지로 항상 표시)
  scenarios: [], // [{ date, domain, title, br }] 그 날 그 영역에서 만든 평행우주 시나리오 → 지구본 ◆
};

// ── 저장/로드 ────────────────────────────────────────────────
export function loadUniverse() {
  try {
    const raw = JSON.parse(storage.getItem(KEY) || "{}");
    return {
      ...DEFAULTS,
      ...raw,
      checkins: Array.isArray(raw.checkins) ? raw.checkins : [],
      scenarios: Array.isArray(raw.scenarios) ? raw.scenarios : [],
      pinnedSlots: { ...DEFAULTS.pinnedSlots, ...(raw.pinnedSlots || {}) },
    };
  } catch {
    return { ...DEFAULTS, checkins: [], pinnedSlots: { ...DEFAULTS.pinnedSlots } };
  }
}

function persist(state) {
  try {
    storage.setItem(KEY, JSON.stringify(state));
  } catch {
    /* localStorage 불가 환경(사파리 프라이빗 등) — 메모리로만 동작 */
  }
  // 같은 탭에선 storage 이벤트가 안 뜨므로 직접 알린다 → 화면 즉시 갱신(자동 태깅 반영 등).
  if (typeof window !== "undefined") window.dispatchEvent(new Event("pm:universe"));
  return state;
}

function patch(fn) {
  const s = loadUniverse();
  return persist(fn(s) || s);
}

// ── 날짜 유틸 ────────────────────────────────────────────────
// toISOString() 은 UTC 라 한국 시간 자정 근처에서 하루가 밀린다. 로컬 기준으로 만든다.
export function todayKey(d = new Date()) {
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

function dayDiff(a, b) {
  return Math.round((new Date(b + "T00:00:00") - new Date(a + "T00:00:00")) / 86400000);
}

function addDays(dateKey, n) {
  const d = new Date(dateKey + "T00:00:00");
  d.setDate(d.getDate() + n);
  return todayKey(d);
}

/** 그 날짜가 속한 주의 월요일. 별자리는 달력 주(월~일) 단위다. */
export function weekStartKey(dateKey) {
  const d = new Date(dateKey + "T00:00:00");
  const dow = (d.getDay() + 6) % 7; // 월=0 … 일=6
  d.setDate(d.getDate() - dow);
  return todayKey(d);
}

// mood(1~5) → valence(-1~1). 일기 모듈이 valence 를 직접 주면 그 값을 우선한다.
export function moodToValence(mood) {
  if (mood == null) return null;
  return +(((Number(mood) - 3) / 2).toFixed(3));
}

// ── 쓰기 ─────────────────────────────────────────────────────
/**
 * 하루치 체크인 기록(=별 1개). 같은 날짜면 덮어쓴다.
 * @param {{date?:string, mood?:number, valence?:number, energy?:number,
 *          skill?:string, keyword?:string, note?:string, diaryId?:string}} entry
 */
export function addCheckin(entry = {}) {
  const date = entry.date || todayKey();
  const valence =
    entry.valence != null ? Number(entry.valence) : moodToValence(entry.mood);
  const answerValues = Array.isArray(entry.answers)
    ? entry.answers
    : Object.values(entry.answers || {});
  const star = {
    date,
    mood: entry.mood ?? null,
    valence: valence ?? null,
    energy: entry.energy ?? null, // 소현 체크인 3문항: 에너지 레벨
    skill: entry.skill ?? null, //                  오늘 쓴 역량
    keyword: entry.keyword ?? null, //              감정 키워드
    note: entry.note ?? "", // 한 줄 기록
    text: entry.text ?? "", // 일기 본문
    answers: entry.answers ?? null, // 질문별 답 [{ q, a }]
    domains: entry.domains ?? null, // 자동 분류 영역(행성) key 배열 — /tag 결과
    insights: entry.insights ?? null,
    chatSummary: entry.chatSummary ?? null,
    diaryId: entry.diaryId ?? null,
    hasDiary: Boolean(
      entry.text?.trim() || entry.note?.trim()
      || answerValues.some((value) => String(value?.a ?? value ?? "").trim())
      || entry.diaryId,
    ),
  };
  return patch((s) => {
    const previous = s.checkins.find((c) => c.date === date);
    if (previous) {
      star.domains = entry.domains ?? previous.domains ?? null;
      star.experiments = entry.experiments ?? previous.experiments ?? [];
      star.insights = entry.insights ?? previous.insights ?? null;
      star.chatSummary = entry.chatSummary ?? previous.chatSummary ?? null;
    }
    const rest = s.checkins.filter((c) => c.date !== date);
    s.checkins = [...rest, star].sort((a, b) => a.date.localeCompare(b.date));
    return s;
  });
}

/**
 * JY diary entries(pm_diary_v5)를 나의 우주 별 저장소에 병합한다.
 * 나의 우주에서 생성한 domains/experiments는 보존하고 일기 원문과 체크인 값만 갱신한다.
 */
export function syncDiaryEntries(entries = []) {
  if (!Array.isArray(entries) || !entries.length) return loadUniverse();
  return patch((s) => {
    const byDate = new Map(s.checkins.map((item) => [item.date, item]));
    for (const entry of entries) {
      if (!entry?.date) continue;
      const previous = byDate.get(entry.date) || {};
      const answers = entry.answers ?? previous.answers ?? null;
      const answerValues = Array.isArray(answers) ? answers : Object.values(answers || {});
      const text = entry.text ?? previous.text ?? "";
      const note = entry.note ?? text ?? previous.note ?? "";
      byDate.set(entry.date, {
        ...previous,
        date: entry.date,
        mood: entry.mood ?? previous.mood ?? null,
        valence: entry.valence ?? moodToValence(entry.mood) ?? previous.valence ?? null,
        energy: entry.energy ?? previous.energy ?? null,
        skill: entry.competency ?? entry.skill ?? previous.skill ?? null,
        keyword: entry.emotion ?? entry.keyword ?? previous.keyword ?? null,
        note,
        text,
        answers,
        insights: entry.insights ?? previous.insights ?? null,
        chatSummary: entry.chatSummary ?? previous.chatSummary ?? null,
        diaryId: entry.id ?? entry.diaryId ?? previous.diaryId ?? `e-${entry.date}`,
        domains: previous.domains ?? entry.domains ?? null,
        experiments: previous.experiments ?? entry.experiments ?? [],
        hasDiary: Boolean(
          String(text).trim() || String(note).trim()
          || answerValues.some((value) => String(value?.a ?? value ?? "").trim()),
        ),
      });
    }
    s.checkins = [...byDate.values()].sort((a, b) => a.date.localeCompare(b.date));
    return s;
  });
}

export function setPlanet(key) {
  return patch((s) => {
    s.planet = key;
    return s;
  });
}

export function pinSlot(slotId, universeId) {
  return patch((s) => {
    s.pinnedSlots = { ...s.pinnedSlots, [slotId]: universeId };
    return s;
  });
}

export function unpinSlot(slotId) {
  return pinSlot(slotId, null);
}

// 시뮬레이션을 한 번 돌렸을 때 호출 (ResultContext.runSimulation 성공 시).
export function noteSimulationRun() {
  return patch((s) => {
    s.simRuns = (s.simRuns || 0) + 1;
    return s;
  });
}

export function resetUniverse() {
  try {
    storage.removeItem(KEY);
  } catch {
    /* 무시 */
  }
}

// ── 파생 계산 ────────────────────────────────────────────────
/**
 * 별 하나 = 기록 하나. 기분만 찍고 지나간 날은 별이 되지 않는다.
 *
 * 전에는 기분값만 있어도 별로 셌는데, 정작 그 별을 눌러 보는 분석(대표 문장·감정 칩·
 * 영역 리포트)은 전부 본문을 읽는다. 그래서 "별 254개"인데 읽을 일기는 136개인
 * 어긋남이 났다. 세는 자리마다 규칙이 갈리지 않게 여기 한 곳에서 정한다.
 */
export function hasRecord(c) {
  if (!c || c.empty) return false;
  if ((c.text || "").trim() || (c.note || "").trim()) return true;
  const answers = Array.isArray(c.answers) ? c.answers : Object.values(c.answers || {});
  return Boolean(c.diaryId) || answers.some((v) => String(v?.a ?? v ?? "").trim());
}

export function totalStars(s = loadUniverse()) {
  return s.checkins.filter(hasRecord).length;
}

export function diaryDays(s = loadUniverse()) {
  return s.checkins.filter(hasRecord).length;
}

export function hasCheckedInToday(s = loadUniverse()) {
  const t = todayKey();
  return s.checkins.some((c) => c.date === t);
}

/** 연속 기록일. 오늘 안 했으면 어제까지의 연속을 인정한다(자정에 0으로 깨지지 않게). */
export function streakDays(s = loadUniverse()) {
  if (!s.checkins.length) return 0;
  const dates = [...new Set(s.checkins.map((c) => c.date))].sort().reverse();
  const gapFromToday = dayDiff(dates[0], todayKey());
  if (gapFromToday > 1) return 0;
  let streak = 1;
  for (let i = 1; i < dates.length; i++) {
    if (dayDiff(dates[i], dates[i - 1]) === 1) streak++;
    else break;
  }
  return streak;
}

/**
 * 별자리 = 달력 한 주(월~일). 슬롯은 항상 7칸이라 레이아웃이 흔들리지 않고,
 * 기록이 없는 날은 건너뛰지 않고 빈 자리로 남는다 —
 * 별자리는 "기록한 날들"이 아니라 "지나간 날들"의 모양이어야 한다.
 * 주간 리포트와 주기가 같아 그대로 재사용할 수 있다.
 */
export function constellationGroups(s = loadUniverse()) {
  const cs = s.checkins;
  if (!cs.length) return [];

  const today = todayKey();
  const firstWeek = weekStartKey(cs[0].date);
  const lastWeek = weekStartKey(cs[cs.length - 1].date > today ? cs[cs.length - 1].date : today);
  // 기록이 없는 날(기분만 찍은 날)은 빈 자리로 남긴다 — 별 개수 = 일기 개수.
  const byDate = Object.fromEntries(cs.filter(hasRecord).map((c) => [c.date, c]));

  const groups = [];
  for (let ws = firstWeek; ws <= lastWeek; ws = addDays(ws, 7)) {
    const stars = Array.from({ length: STARS_PER_CONSTELLATION }, (_, i) => {
      const key = addDays(ws, i);
      return byDate[key] || { date: key, valence: null, empty: true, future: key > today };
    });
    const weekEnd = addDays(ws, STARS_PER_CONSTELLATION - 1);
    const elapsed = Math.min(STARS_PER_CONSTELLATION, dayDiff(ws, today) + 1);
    groups.push({
      index: groups.length,
      weekStart: ws,
      weekEnd,
      stars,
      complete: weekEnd < today,
      remaining: Math.max(0, STARS_PER_CONSTELLATION - elapsed),
      filled: stars.filter((x) => !x.empty).length,
    });
  }
  return groups;
}

/** 지금 만들고 있는(=이번 주) 별자리. 기록이 없으면 null. */
export function currentConstellation(s = loadUniverse()) {
  const g = constellationGroups(s);
  return g.length ? g[g.length - 1] : null;
}

export function completedCount(s = loadUniverse()) {
  return constellationGroups(s).filter((g) => g.complete && g.filled > 0).length;
}

// 특정 날 체크인에 자동분류 영역(행성 key 배열)을 나중에 채운다(/tag 응답 도착 시).
export function setDomains(date, domains) {
  return patch((s) => {
    const c = s.checkins.find((x) => x.date === date);
    if (c) c.domains = domains;
    return s;
  });
}

// 행성(도메인) 렌즈 — 그 영역 기록을 '독립 축적'해 별자리를 만든다.
// 달력 주와 무관하게, 그 영역 기록 7개가 모이면 별자리 1개 완성(각 행성이 자기 별자리를 쌓음).
// planetKey 없으면 기존 달력 주 기준(전체).
export function groupsByPlanet(planetKey, s = loadUniverse()) {
  if (!planetKey) return constellationGroups(s);
  const legacyKeys = ["career", "life", "relation", "health", "growth"];
  const domainsOf = (checkin) => {
    if (Array.isArray(checkin.domains) && checkin.domains.length) return checkin.domains;
    const text = `${checkin.text || ""} ${checkin.note || ""}`;
    const inferred = [];
    if (/회사|직장|이직|취업|진로|업무|면접|돈|소득|연봉/.test(text)) inferred.push("career");
    if (/건강|수면|잠|운동|병원|스트레스|불안|체력/.test(text)) inferred.push("health");
    if (/가족|친구|연인|동료|관계|사람/.test(text)) inferred.push("relation");
    if (/공부|배움|성장|자격증|시험|목표/.test(text)) inferred.push("growth");
    if (inferred.length) return [...new Set(inferred)];
    // 예시 기록은 과거 버전에 영역 값이 없었으므로 날짜 기준으로 고르게 복구한다.
    if (s.demo) {
      const hash = String(checkin.date || "").split("").reduce((sum, char) => sum + char.charCodeAt(0), 0);
      return [legacyKeys[hash % legacyKeys.length]];
    }
    return ["life"];
  };
  const filtered = {
    ...s,
    checkins: s.checkins.filter((c) => domainsOf(c).includes(planetKey)),
  };
  return constellationGroups(filtered);
}

// 적응형 별자리 묶기 — 기록 수에 맞춰 묶어 별자리가 너무 많아지지도, 너무 비지도 않게.
//  · 항상 그룹 ≤ 8개, 각 그룹 ≥ 7별(마지막 제외) → 분석(4개↑)이 항상 가능.
//  · 전체(planetKey 없음)면 모든 기록, 도메인이면 그 영역만.
//  · 달력이 아니라 '기록 순서' 기준이라 희박한 영역도 텅 빈 별자리가 안 생긴다.
export function adaptiveGroups(planetKey, s = loadUniverse()) {
  const all = !planetKey || planetKey === "all";
  const stars = s.checkins
    .filter(
      (c) =>
        hasRecord(c) &&
        (all || (Array.isArray(c.domains) && c.domains.includes(planetKey))),
    )
    .sort((a, b) => a.date.localeCompare(b.date));
  if (!stars.length) return [];

  const size = Math.max(STARS_PER_CONSTELLATION, Math.ceil(stars.length / 8));
  const groups = [];
  for (let i = 0; i < stars.length; i += size) {
    const chunk = stars.slice(i, i + size);
    groups.push({
      index: groups.length,
      stars: chunk,
      filled: chunk.length,
      complete: true,
      remaining: 0,
      label: `${chunk[0].date.slice(5)}~${chunk[chunk.length - 1].date.slice(5)}`,
    });
  }
  return groups;
}

/**
 * 3D 우주에 띄울 그 영역의 기록 별자리 — 정확히 7개씩 끊고, 개수 제한을 두지 않는다.
 *
 * adaptiveGroups 는 그룹을 8개로 묶느라 한 별자리에 7개보다 많은 별이 들어갈 수 있는데,
 * 3D 쪽은 별자리당 7개만 그린다. 그래서 기록이 많아질수록 그릴수록 별이 조용히 사라졌다.
 * 여기서는 7개 고정으로 끊어, 띄운 별의 총합이 곧 그 영역의 기록 수가 되게 한다.
 */
export function starGroupsOf(planetKey, s = loadUniverse()) {
  const stars = s.checkins
    .filter((c) => hasRecord(c)
      && (!planetKey || (Array.isArray(c.domains) && c.domains.includes(planetKey))))
    .sort((a, b) => a.date.localeCompare(b.date));
  const groups = [];
  for (let i = 0; i < stars.length; i += STARS_PER_CONSTELLATION) {
    const chunk = stars.slice(i, i + STARS_PER_CONSTELLATION);
    groups.push({
      index: groups.length,
      domain: planetKey || null,
      stars: chunk,
      filled: chunk.length,
      complete: chunk.length === STARS_PER_CONSTELLATION,
      weekStart: `${planetKey || "all"}-${chunk[0].date}`,
      label: `${chunk[0].date.slice(5)}~${chunk[chunk.length - 1].date.slice(5)}`,
    });
  }
  return groups;
}

// 그 날 그 영역에서 평행우주 시나리오를 만들었음을 기록 → 지구본 ◆. (date,domain) upsert.
export function recordScenario({ domain, title, br = [], date } = {}) {
  const d = date || todayKey();
  return patch((s) => {
    const rest = (s.scenarios || []).filter((x) => !(x.date === d && x.domain === domain));
    s.scenarios = [...rest, { date: d, domain, title: title || "평행우주 시나리오", br }];
    return s;
  });
}

// 그 행성(영역)에서 만든 시나리오들 — PlanetGlobe scenarios prop 용.
export function scenariosByPlanet(planetKey, s = loadUniverse()) {
  return (s.scenarios || []).filter((x) => x.domain === planetKey);
}

// 결과 화면 '작은 실험'에 적은 답을 그날 기록에 덧붙인다.
// 별(mood)을 덮어쓰지 않고 experiments[] 에 누적 → 다음 diarySignals 분석에 반영된다.
// (actionId 당 1개 upsert. 같은 실험을 다시 적으면 덮어씀.)
export function logExperiment({ actionId, prompt, text, date } = {}) {
  const v = (text || "").trim();
  const d = date || todayKey();
  return patch((s) => {
    let c = s.checkins.find((x) => x.date === d);
    if (!c) {
      c = { date: d, mood: null, valence: null, energy: null, skill: null, keyword: null, note: "", text: "", answers: null, domains: null, diaryId: null, experiments: [], hasDiary: true };
      s.checkins = [...s.checkins, c].sort((a, b) => a.date.localeCompare(b.date));
    }
    const rest = (c.experiments || []).filter((e) => e.actionId !== actionId);
    c.experiments = v ? [...rest, { actionId, prompt: prompt || "", text: v }] : rest;
    if (v) c.hasDiary = true;
    return s;
  });
}

// ── XP / 레벨 ────────────────────────────────────────────────
// 참여 지표다. 실측 데이터와 무관하며 값은 팀 재량으로 정한 것.
export const XP_RULES = {
  checkin: 10, // 하루 체크인
  diary: 15, // 그날 일기까지 작성
  simulation: 50, // 시뮬레이션 1회 실행
  universeSaved: 30, // 우주 보관함 저장
  reflection: 40, // 저장한 우주에 회고 작성
};

/** 레벨 n → n+1 에 필요한 XP. */
export function xpMaxFor(level) {
  return 500 + (level - 1) * 400;
}

export function levelFrom(xp) {
  let level = 1;
  let rest = Math.max(0, xp);
  let need = xpMaxFor(level);
  while (rest >= need && level < 99) {
    rest -= need;
    level += 1;
    need = xpMaxFor(level);
  }
  return { level, xpInLevel: rest, xpMax: need };
}

function storedHighestLevel() {
  try {
    return Math.max(1, Number(storage.getItem(HIGHEST_LEVEL_KEY) || 1));
  } catch {
    return 1;
  }
}

function rememberHighestLevel(level) {
  const highest = Math.max(storedHighestLevel(), level);
  try {
    storage.setItem(HIGHEST_LEVEL_KEY, String(highest));
  } catch {
    // localStorage 불가 환경에서는 현재 계산 레벨만 사용한다.
  }
  return highest;
}

export const LEVEL_TITLES = [
  [1, "첫 별 관측자"],
  [3, "성운 여행자"],
  [6, "별자리 수집가"],
  [10, "궤도 항해사"],
  [15, "은하 탐사대"],
  [20, "우주 탐험가"],
];

export function titleFor(level) {
  let t = LEVEL_TITLES[0][1];
  for (const [min, name] of LEVEL_TITLES) if (level >= min) t = name;
  return t;
}

/** 활동 기록 → 총 XP (저장하지 않고 매번 계산). */
export function totalXp(s = loadUniverse(), universes = safeUniverses()) {
  const reflections = universes.filter((u) => (u.reflection || "").trim()).length;
  return (
    totalStars(s) * XP_RULES.checkin +
    diaryDays(s) * XP_RULES.diary +
    (s.simRuns || 0) * XP_RULES.simulation +
    universes.length * XP_RULES.universeSaved +
    reflections * XP_RULES.reflection
  );
}

function safeUniverses() {
  try {
    return listUniverses();
  } catch {
    return [];
  }
}

// ── 화면용 요약 (MyUniverse · HomeHub 가 같이 쓰는 단일 소스) ──
export function universeSummary() {
  const s = loadUniverse();
  const universes = safeUniverses();
  const xp = totalXp(s, universes);
  const { level, xpInLevel, xpMax } = levelFrom(xp);
  // 데모 데이터로 얻은 레벨은 실제 계정 보상으로 영구 저장하지 않는다.
  const highestLevel = isDemo(s) ? level : rememberHighestLevel(level);
  const cur = currentConstellation(s);

  return {
    state: s,
    level,
    highestLevel,
    title: titleFor(level),
    xp,
    xpInLevel,
    xpMax,
    xpPct: Math.min(100, Math.round((xpInLevel / xpMax) * 100)),
    stars: totalStars(s),
    streak: streakDays(s),
    checkedInToday: hasCheckedInToday(s),
    current: cur,
    currentFilled: cur ? cur.filled : 0,
    completed: completedCount(s),
    stats: {
      simulations: s.simRuns || 0,
      stars: totalStars(s),
      universes: universes.length,
    },
  };
}

// ── 예시 기록 (둘러보기 모드) ────────────────────────────────
// 홈의 체크인 UI(소현 파트)가 붙기 전까지, 그리고 처음 들어온 사람이 별자리가
// 무엇인지 보려면 기록이 필요하다. 개발 모드에서만 열면 배포본/발표용 URL 에서
// 빈 화면이 뜨므로 **프로덕션에서도 명시적 버튼으로** 쓸 수 있게 둔다.
//
// 대신 조용히 넣지 않는다 — `demo: true` 플래그를 세우고 화면에 "예시 데이터"
// 배지를 항상 띄운다. 남의 기록을 내 기록인 척 보여주지 않는 것이 이 프로젝트 원칙.
// 은우의 6주 — 번아웃 → 자각 → 준비 → 도전 → 결심 → (진행 중).
// 주마다 모양(형)이 달라 별자리와 리포트가 다르게 나온다.
const DEMO_WEEKS = [
  // 5주 전 — 번아웃(인내형: 평균 크게↓, 진폭↓), 금요일 미기록
  [-0.6, -0.7, -0.5, -0.8, null, -0.6, -0.5],
  // 4주 전 — 문제 자각(기복형: 오르내림)
  [-0.5, -0.3, -0.6, 0.1, -0.4, -0.2, 0.3],
  // 3주 전 — 준비 시작(상승형), 토요일 미기록
  [-0.2, 0.1, -0.1, 0.3, 0.2, null, 0.4],
  // 2주 전 — 도전형(평균↑ 진폭↑)
  [0.5, 0.2, 0.8, -0.3, 0.7, 0.1, 0.6],
  // 지난 주 — 결심(균형형: 평균↑ 진폭↓)
  [0.3, 0.4, 0.2, 0.5, 0.6, 0.4, 0.5],
  // 이번 주 — 오늘까지만 채운다(진행 중)
  [0.4, 0.5, 0.3, 0.6, 0.45, 0.5, 0.4],
];

const DEMO_NOTES = [
  "면접 준비를 시작했다.",
  "팀 회의가 길었다. 그래도 정리는 됐다.",
  "오랜만에 푹 잤다.",
  "결정을 미루고 있는 게 스스로 보인다.",
];

// 예시 일기 — `${주}-${요일}` 키(주 0=5주전 … 4=지난주). 클릭·리포트에서 실제 일기가 보이도록.
// 6주 서사: 번아웃 → 자각 → 준비 → 도전 → 결심.
const DEMO_DIARY = {
  // 5주 전 — 번아웃
  "0-0": {
    note: "그냥 버텼다.",
    text: "하루가 어떻게 갔는지 모르겠다. 그냥 버틴다는 말밖에 안 나온다.",
    answers: [
      { q: "오늘 가장 마음이 걸린 순간, 그때 나는 무엇을 했나요? 옆에서 본 사람이라면 뭐가 보였을까요?", a: "회의 내내 멍하게 앉아만 있었다. 아무 말도 못 하고 시간만 흘려보냈다. 옆에서 봤다면 완전히 방전된 사람처럼 보였을 거다." },
    ],
  },
  "0-3": {
    note: "다 놓고 싶었다.",
    text: "다 놓고 싶다는 생각이 문득 들었다. 근데 그냥 출근했다.",
    answers: [
      { q: "오늘 가장 기억에 남는 순간 하나만 편하게 적어주세요.", a: "점심에 혼자 10분 걸은 것. 오늘 유일하게 숨 쉰 것 같은 시간이었다." },
    ],
  },
  // 4주 전 — 자각
  "1-2": {
    note: "번아웃인가 싶다.",
    text: "아침에 일어나기가 너무 힘들다. 몸이 자꾸 신호를 보낸다 — 두통, 소화불량.",
    answers: [
      { q: "오늘 가장 마음이 걸린 순간, 그때 나는 무엇을 했나요? 옆에서 본 사람이라면 뭐가 보였을까요?", a: "6시에 상사가 일을 또 던졌을 때. 거절하고 싶었지만 결국 알겠다고 했다. 옆에서 봤다면 또 참는구나 했을 거다." },
    ],
  },
  "1-6": {
    note: "숨통이 트였다.",
    text: "친구들이랑 저녁. 회사 밖 사람을 만나니 숨통이 트였다.",
    answers: [
      { q: "오늘 잘 됐던 일 하나만 꼽는다면? 그게 왜 잘 됐다고 생각하나요?", a: "회사 밖 친구들을 만난 것. 내가 먼저 연락해서 잡은 약속이라 더 좋았다. 사람을 만나니 숨통이 트였다." },
    ],
  },
  // 3주 전 — 준비
  "2-3": {
    note: "이력서 초안을 썼다.",
    text: "미루던 이력서를 드디어 열었다. 한 줄 쓰기까지가 제일 어려웠고, 쓰고 나니 후련했다.",
    answers: [
      { q: "오늘 잘 됐던 일 하나만 꼽는다면? 그게 왜 잘 됐다고 생각하나요?", a: "미루던 이력서를 열고 지원 두 곳에 버튼을 누른 것. 겁났지만 눌렀다는 게 스스로 대견했다." },
      { q: "최근 '이건 좀 나답지 않다' 싶었던 순간이 있었나요?", a: "평소 한참 미루는 나인데, 겁나도 일단 지원한 게 좀 나답지 않아서 낯설고 좋았다." },
    ],
  },
  // 2주 전 — 도전
  "3-2": {
    note: "면접 제안이 왔다.",
    text: "면접 제안이 왔다. 설레면서도 안정을 놓기가 무섭다.",
    answers: [
      { q: "오늘 가장 마음이 걸린 순간, 그때 나는 무엇을 했나요? 옆에서 본 사람이라면 뭐가 보였을까요?", a: "면접 제안에 답장을 못 하고 미룬 것. 안정을 놓기가 무서웠다. 옆에서 봤다면 왜 저렇게 망설이나 했을 거다." },
    ],
  },
  "3-4": {
    note: "등산으로 머리를 비웠다.",
    text: "주말 등산. 정상에서 먹는 김밥. 이 맛에 버틴다.",
    answers: [{ q: "오늘 에너지를 가장 크게 받은 일이 있다면 무엇인가요? 그게 왜 힘이 됐을까요?", a: "주말 등산. 정상에서 김밥 먹고 몸을 움직이니 며칠 만에 머리가 맑아졌다." }],
  },
  // 지난 주 — 결심
  "4-3": {
    note: "결정을 못 내리는 내가 지친다.",
    text: "면접 볼지 조건을 표로 비교 중. 결정을 못 내리는 내가 제일 지친다.",
    answers: [
      { q: "이번 주 나를 가장 지치게 한 건? 같은 상황의 친구라면 뭐가 필요해 보일까요?", a: "조건을 표로 비교만 하며 결정을 못 내리는 나 자신. 친구가 이랬다면 '연봉 말고 저녁 있는 삶도 표에 넣어봐'라고 했을 거다." },
    ],
  },
  "4-6": {
    note: "결국 면접 보기로 했다.",
    text: "결국 면접 보기로 답장했다. 미루기만 하던 내가 움직였다.",
    answers: [
      { q: "오늘 가장 기억에 남는 순간 하나만 편하게 적어주세요.", a: "면접 보겠다고 답장 버튼을 누른 순간. 미루기만 하던 내가 움직여서 개운했다." },
      { q: "오늘 잘 됐던 일 하나만 꼽는다면? 그게 왜 잘 됐다고 생각하나요?", a: "지친 저녁이 아니라 개운한 아침에 결정한 것. 컨디션 좋을 때 정하니 후회가 없었다." },
    ],
  },
};

// 예시 기록의 영역(행성) 태그 — 데모에서도 행성별 그래프·리포트가 보이도록.
// 일기 있는 날은 내용에 맞는 영역, 나머지(기분만 남긴 날)는 '삶의 만족(life)'.
const DEMO_DOMAINS = {
  "0-0": ["career"], "0-3": ["career", "health"],
  "1-2": ["health", "career"], "1-6": ["relation"],
  "2-3": ["career", "growth"],
  "3-2": ["career"], "3-4": ["health"],
  "4-3": ["career", "growth"], "4-6": ["career", "growth"],
};

/** 예시 기록 3주치를 넣는다. 달력 주(월~일)에 맞춰 넣어 요일과 무관하게 같은 모양이 나온다. */
export function seedDemoCheckins() {
  const today = todayKey();
  const thisMonday = weekStartKey(today);
  const start = addDays(thisMonday, -35); // 5주 전 월요일부터(총 6주치)

  let noteAt = 0;
  DEMO_WEEKS.forEach((week, w) => {
    week.forEach((v, d) => {
      const date = addDays(start, w * 7 + d);
      if (v == null || date > today) return; // 미기록 날 / 아직 오지 않은 날
      const diary = DEMO_DIARY[`${w}-${d}`];
      addCheckin({
        date,
        valence: v,
        mood: Math.round(v * 2 + 3),
        note: diary?.note ?? ((w * 7 + d) % 4 === 1 ? DEMO_NOTES[noteAt++ % DEMO_NOTES.length] : ""),
        text: diary?.text ?? "",
        answers: diary?.answers ?? null,
        domains: DEMO_DOMAINS[`${w}-${d}`] ?? ["life"],
      });
    });
  });

  return patch((s) => {
    s.demo = true;
    return s;
  });
}

export function isDemo(s = loadUniverse()) {
  return Boolean(s.demo);
}

/**
 * 배포본에서도 예시 기록을 열 수 있는 진입점.
 *  · `?demo=1` 로 들어오면 자동으로 채운다(발표·심사용 링크).
 * 이미 기록이 있으면 건드리지 않는다.
 */
export function initDemoFromUrl() {
  try {
    if (!new URLSearchParams(window.location.search).has("demo")) return false;
    if (loadUniverse().checkins.length) return false;
    seedDemoCheckins();
    return true;
  } catch {
    return false;
  }
}
