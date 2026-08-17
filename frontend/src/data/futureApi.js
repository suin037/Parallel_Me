// 행성(삶의 영역) 하나의 'N년 뒤' — 그 영역 일기 + 시뮬레이션 + 회고를 서버로 보내
// 서사를 받아온다. 예측 수치가 아니라 '내 기록에서 끌어온 이야기'다.
import { loadUniverse, hasRecord } from "./myUniverse.js";
import { listUniverses } from "./savedUniverses.js";
import { doneExpeditions } from "./expeditions.js";
import { domainAnalysis } from "./diarySignals.js";
import { localPersonaBlock } from "./jobAnalysis.js";
import { API_BASE } from "./apiBase.js";
import { maskRecords } from "./outbound.js";
import storage from "./safeStorage.js";

const BASE = API_BASE;

// 한 번 쓴 이야기는 남겨둔다 — 같은 행성·같은 햇수로 다시 들어오면 그대로 보여주고,
// 새 기록이 쌓였을 때만 '다시 쓰기'로 갱신한다(매번 새로 부르면 느리고 말이 바뀐다).
const KEY = "pm.future.v1";
const cacheKey = (planetKey, years) => `${planetKey}:${years}`;

export function loadFutureCache() {
  try { return JSON.parse(storage.getItem(KEY) || "{}"); } catch { return {}; }
}
export function getCachedFuture(planetKey, years) {
  return loadFutureCache()[cacheKey(planetKey, years)] || null;
}
function putCachedFuture(planetKey, years, value) {
  try {
    const all = loadFutureCache();
    all[cacheKey(planetKey, years)] = value;
    storage.setItem(KEY, JSON.stringify(all));
  } catch { /* 저장 실패는 무시 — 화면엔 이미 떠 있다 */ }
}

// 그 영역의 일기 전체(최신순). 서버로는 이 중 앞 24개만 보낸다.
function domainRecordsAll(planetKey, s) {
  return s.checkins
    .filter((c) => hasRecord(c) && Array.isArray(c.domains) && c.domains.includes(planetKey))
    .sort((a, b) => b.date.localeCompare(a.date));
}

function domainRecords(planetKey, s) {
  // 여기서 나가는 text 는 사용자가 쓴 일기 본문 그대로다 — 외부 AI 로 보내기 전에 가린다.
  return maskRecords(
    domainRecordsAll(planetKey, s)
      .slice(0, 24)
      .map((c) => ({
        date: c.date,
        text: (c.text || c.note || "").slice(0, 200),
        mood: c.mood ?? null,
        emotion: c.keyword || "",
      })),
  );
}

// 그 영역에서 돌린 시뮬레이션 + 회고. 보관함에 저장된 우주만 회고를 가진다.
// 옛 저장본엔 domain 이 없어서, 없으면 선택지 문구로 그 영역인지 가늠한다.
const DOMAIN_HINTS = {
  career: ["이직", "퇴사", "회사", "직장", "취업", "연봉", "커리어", "창업", "부업"],
  relation: ["연애", "결혼", "이별", "친구", "가족", "관계", "동거"],
  health: ["운동", "건강", "수면", "다이어트", "병원", "치료"],
  growth: ["공부", "대학원", "유학", "자격증", "시험", "배우"],
  life: ["이사", "자취", "독립", "여행", "이주"],
};
function domainSims(planetKey) {
  const hints = DOMAIN_HINTS[planetKey] || [];
  return listUniverses()
    .filter((u) => {
      if (u.domain) return u.domain === planetKey;
      const t = `${u.choiceA || ""} ${u.choiceB || ""} ${u.title || ""}`;
      return hints.some((w) => t.includes(w));
    })
    .map((u) => ({
      savedAt: u.savedAt,
      choiceA: u.choiceA,
      choiceB: u.choiceB,
      headline: u.headline || "",
      decision: u.decision || "none",
      reflection: u.reflection || "",
      doneActions: u.doneActions || [],
    }));
}

// 위 세 묶음(일기·시뮬 회고·탐험 기록)은 전부 사용자가 쓴 문장이다.
// domainRecords 만 가리고 sims·trips 를 그냥 보내면 회고·탐험 노트로 그대로 새어 나간다.
function maskedSims(planetKey) {
  return maskRecords(domainSims(planetKey));
}

// 이 행성으로 이야기를 쓸 재료가 있는지 — 버튼을 띄울지 판단용.
export function futureMaterials(planetKey, s = loadUniverse()) {
  const records = domainRecords(planetKey, s);
  const sims = maskedSims(planetKey);
  // 다녀온 탐험 — 상상이 아니라 실제로 겪고 온 것이라 회고와 같은 무게로 센다.
  const trips = maskRecords(
    doneExpeditions(planetKey)
      .filter((e) => (e.note || "").trim())
      .map((e) => ({
        title: e.title, step: e.step || "", note: e.note,
        startedAt: e.startedAt, doneAt: e.doneAt,
      })),
  );
  // total 은 상한 없는 실제 기록 수 — 24개를 넘겨도 "새 기록이 늘었다"를 알아채야 한다.
  const total = domainRecordsAll(planetKey, s).length;
  return {
    records,
    total,
    sims,
    trips,
    reflections: sims.filter((x) => (x.reflection || "").trim()).length,
    ready: total >= 3,
  };
}

// ── 아직 안 가본 길 ────────────────────────────────────────────
// 시뮬레이션은 사용자가 A/B를 직접 적어야 시작된다 — 그러면 이미 아는 두 길 사이에서만
// 고민하게 된다. 여기서 그 영역 기록을 읽어 저울에 올려본 적 없는 갈림길을 내민다.
const OPP_KEY = "pm.opportunity.v1";

export function getCachedOpportunities(planetKey) {
  try { return JSON.parse(storage.getItem(OPP_KEY) || "{}")[planetKey] || null; } catch { return null; }
}
function putCachedOpportunities(planetKey, value) {
  try {
    const all = JSON.parse(storage.getItem(OPP_KEY) || "{}");
    all[planetKey] = value;
    storage.setItem(OPP_KEY, JSON.stringify(all));
  } catch { /* 무시 */ }
}

export async function scanOpportunities(planet, { speech = "polite", state, profile = null } = {}) {
  const s = state || loadUniverse();
  const { records, sims, trips, total } = futureMaterials(planet.key, s);
  const a = domainAnalysis(planet.key, s);
  try {
    const res = await fetch(`${BASE}/opportunity/scan`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        domain: planet.key,
        label: planet.label,
        records,
        analysis: a?.ok ? { n: a.n, moodAvg: a.moodAvg, topEmotions: a.topEmotions } : null,
        sims,
        trips,
        persona: profile ? localPersonaBlock(profile) : null,
        speech,
      }),
    });
    if (!res.ok) throw new Error(`API ${res.status}`);
    const data = await res.json();
    if (data?.ok) {
      const value = { ...data, scannedAt: new Date().toISOString().slice(0, 10), nRecords: total };
      putCachedOpportunities(planet.key, value);
      return value;
    }
    return data;
  } catch {
    return { ok: false, reason: "길을 찾지 못했어요. 서버가 켜져 있는지 확인해 주세요." };
  }
}

export async function writeFuture(planet, years, { speech = "polite", state, profile = null } = {}) {
  const s = state || loadUniverse();
  const { records, sims, trips, total } = futureMaterials(planet.key, s);
  const a = domainAnalysis(planet.key, s);
  try {
    const res = await fetch(`${BASE}/future/scenario`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        domain: planet.key,
        label: planet.label,
        years,
        records,
        analysis: a?.ok
          ? { n: a.n, moodAvg: a.moodAvg, topEmotions: a.topEmotions, trend: a.trend }
          : null,
        sims,
        trips,
        persona: profile ? localPersonaBlock(profile) : null,
        speech,
      }),
    });
    if (!res.ok) throw new Error(`API ${res.status}`);
    const data = await res.json();
    if (data?.ok) {
      const value = { ...data, writtenAt: new Date().toISOString().slice(0, 10), nRecords: total };
      putCachedFuture(planet.key, years, value);
      return value;
    }
    return data; // { ok:false, reason }
  } catch {
    return { ok: false, reason: "이야기를 쓰지 못했어요. 서버가 켜져 있는지 확인해 주세요." };
  }
}
