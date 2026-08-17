// 오늘 해볼 만한 것 — 최근 기록을 보고 작게 권한다.
// 기회(futureApi.scanOpportunities)가 인생 갈림길 크기라면 여기는 오늘 크기다.
import { loadUniverse, hasRecord, todayKey } from "./myUniverse.js";
import { API_BASE } from "./apiBase.js";
import storage from "./safeStorage.js";
import { maskRecords } from "./outbound.js";

const BASE = API_BASE;

// 하루에 한 번만 만든다 — 홈에 들어올 때마다 새로 부르면 느리고 말이 계속 바뀐다.
const KEY = "pm.suggest.v1";

export function getTodaySuggestion() {
  try {
    const v = JSON.parse(storage.getItem(KEY) || "null");
    return v && v.date === todayKey() ? v : null;
  } catch {
    return null;
  }
}

function save(value) {
  try { storage.setItem(KEY, JSON.stringify(value)); } catch { /* 무시 */ }
}

// 최근 2주 기록(최신순). 그 이상 거슬러 올라가면 '오늘'의 제안이 아니게 된다.
function recentRecords(s, days = 14) {
  const from = new Date(Date.now() - days * 86400000).toISOString().slice(0, 10);
  const rows = s.checkins
    .filter((c) => hasRecord(c) && c.date >= from)
    .sort((a, b) => b.date.localeCompare(a.date))
    .slice(0, 14)
    .map((c) => ({
      date: c.date,
      text: (c.text || c.note || "").slice(0, 200),
      mood: c.mood ?? null,
      emotion: c.keyword || "",
    }));
  // 오늘의 제안·추천곡 둘 다 이 배열을 외부 AI 로 보낸다.
  return maskRecords(rows);
}

export function suggestMaterials(s = loadUniverse()) {
  const records = recentRecords(s);
  const moods = records.map((r) => r.mood).filter((m) => m != null);
  return {
    records,
    moodAvg: moods.length ? Number((moods.reduce((a, b) => a + b, 0) / moods.length).toFixed(1)) : null,
    ready: records.length >= 2,
  };
}

// ── 기분 전환용 노래 ──────────────────────────────────────────
// 곡 정보는 서버가 Deezer(키 불필요)에서 받아온다 — 제목·아티스트·링크·발매일이
// 전부 실재하는 값이라, 모델이 없는 곡을 지어낼 수가 없다.
const TRACK_KEY = "pm.tracks.v1";

export function getTodayTracks() {
  try {
    const v = JSON.parse(storage.getItem(TRACK_KEY) || "null");
    return v && v.date === todayKey() ? v : null;
  } catch {
    return null;
  }
}

export async function fetchTracks({ speech = "polite", state } = {}) {
  const s = state || loadUniverse();
  const { records } = suggestMaterials(s);
  try {
    const res = await fetch(`${BASE}/media/tracks`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ records, speech, limit: 3 }),
    });
    if (!res.ok) throw new Error(`API ${res.status}`);
    const data = await res.json();
    if (data?.ok) {
      const value = { ...data, date: todayKey() };
      try { storage.setItem(TRACK_KEY, JSON.stringify(value)); } catch { /* 무시 */ }
      return value;
    }
    return data;
  } catch {
    return { ok: false, reason: "노래를 불러오지 못했어요." };
  }
}

export async function fetchSuggestion({ speech = "polite", state } = {}) {
  const s = state || loadUniverse();
  const { records, moodAvg } = suggestMaterials(s);
  try {
    const res = await fetch(`${BASE}/suggest/daily`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ records, moodAvg, speech }),
    });
    if (!res.ok) throw new Error(`API ${res.status}`);
    const data = await res.json();
    // care(무거운 날엔 권하지 않음)도 그날의 응답으로 저장한다 — 다시 부르면 또 물어보게 된다.
    if (data?.ok || data?.care) save({ ...data, date: todayKey(), n: records.length });
    return data;
  } catch {
    return { ok: false, reason: "제안을 불러오지 못했어요. 서버가 켜져 있는지 확인해 주세요." };
  }
}
