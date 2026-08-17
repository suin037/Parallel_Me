// 수치가 없는 영역(관계·건강·일상·성장)의 두 길 비교.
//
// 예측 엔진(KLIPS)은 진로·소득 데이터로 만들어졌다. '먼저 말 꺼내기 vs 지금처럼 두기'
// 같은 갈림길에 그 수치를 붙이면 맞지도 않고, 지표 필터에 하나도 안 걸려 화면이
// 통째로 비었다(관계가 실제로 그랬다). 그 자리를 기록 기반 장면 비교로 채운다.
import { API_BASE } from "./apiBase.js";
import { loadUniverse, hasRecord, todayKey } from "./myUniverse.js";
import { localPersonaBlock } from "./jobAnalysis.js";
import { DOMAIN_LABEL } from "./diarySignals.js";
import storage from "./safeStorage.js";
import { maskRecords, maskText } from "./outbound.js";

// 진로 계열은 예측 수치가 실제로 있으니 그대로 둔다. 나머지가 이 화면의 대상이다.
const SOFT_PLANETS = ["relation", "health", "life", "growth"];
const CHOICE_TO_PLANET = {
  career: "career", finance: "career", business: "career",
  education: "growth", long_term_values: "growth",
  health: "health", relationship: "relation",
  housing: "life", lifestyle: "life",
};

/** 이 선택지들이 수치 비교가 안 맞는 영역인가 → 그렇다면 그 행성 key. */
export function softDomainOf(domains = []) {
  const planets = [...new Set(domains.map((d) => CHOICE_TO_PLANET[d]).filter(Boolean))];
  if (!planets.length) return null;
  // 진로가 섞여 있으면 수치 비교가 성립하므로 기존 화면을 쓴다.
  if (planets.includes("career")) return null;
  return planets.find((p) => SOFT_PLANETS.includes(p)) || null;
}

const KEY = "pm.softCompare.v1";
const cacheKey = (planet, a, b) => `${planet}|${a}|${b}`;

export function getCachedSoft(planet, a, b) {
  try { return JSON.parse(storage.getItem(KEY) || "{}")[cacheKey(planet, a, b)] || null; }
  catch { return null; }
}

function putCached(planet, a, b, value) {
  try {
    const all = JSON.parse(storage.getItem(KEY) || "{}");
    all[cacheKey(planet, a, b)] = value;
    storage.setItem(KEY, JSON.stringify(all));
  } catch { /* 무시 */ }
}

// 그 영역 기록 — 태그가 있으면 태그로, 없으면 최근 기록으로 채운다.
// (자동 태깅이 안 붙은 기록이 많아 태그만 믿으면 재료가 0이 된다.)
function domainRecords(planet, s, limit = 20) {
  const all = s.checkins.filter(hasRecord).sort((a, b) => b.date.localeCompare(a.date));
  const tagged = all.filter((c) => Array.isArray(c.domains) && c.domains.includes(planet));
  const pool = tagged.length >= 4 ? tagged : all;
  // 일기 본문이 그대로 나가는 자리 — 외부 AI 로 보내기 전에 가린다.
  return maskRecords(pool.slice(0, limit).map((c) => ({
    date: c.date,
    text: (c.text || c.note || "").slice(0, 200),
    mood: c.mood ?? null,
  })));
}

export async function fetchSoftCompare(planet, choiceA, choiceB, { speech = "polite", profile = null } = {}) {
  const cached = getCachedSoft(planet, choiceA, choiceB);
  if (cached) return cached;
  const s = loadUniverse();
  try {
    const res = await fetch(`${API_BASE}/compare/soft`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        choiceA: maskText(choiceA), choiceB: maskText(choiceB),
        domain: planet,
        label: DOMAIN_LABEL[planet] || "",
        records: domainRecords(planet, s),
        persona: profile ? localPersonaBlock(profile) : null,
        speech,
      }),
    });
    if (!res.ok) throw new Error(`API ${res.status}`);
    const data = await res.json();
    if (data?.ok) {
      const value = { ...data, writtenAt: todayKey() };
      putCached(planet, choiceA, choiceB, value);
      return value;
    }
    return data;
  } catch {
    return { ok: false, reason: "비교를 불러오지 못했어요. 서버가 켜져 있는지 확인해 주세요." };
  }
}
