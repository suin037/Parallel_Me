// 시뮬 추천 문구에 끼울 '요즘 튄 말' — 서버가 Kiwi 형태소 분석으로 뽑는다.
//
// 왜 서버인가: 한국어 명사 추출에는 형태소 분석기가 필요한데(조사·활용이 붙는다)
// 그건 JS 에 없다. diarySignals.js 의 다른 계산이 전부 로컬인 것과 달리 여기만
// 왕복이 있는 이유다. 대신 LLM 은 부르지 않아 지연이 짧고 비용이 0 이다.
//
// 정직선: 이 값은 예측 숫자를 건드리지 않는다. 어떤 문구를 위에 올릴지에만 쓴다.
import { loadUniverse, hasRecord } from "./myUniverse.js";
import { API_BASE } from "./apiBase.js";
import storage from "./safeStorage.js";

// 하루에 한 번만 부른다. 다만 그날 일기를 새로 쓰면 키워드도 따라 바뀌어야 하므로
// 기록 수까지 캐시 키에 넣는다 — 날짜만 보면 오늘 쓴 일기가 내일까지 반영이 안 된다.
const KEY = "pm.compareKeywords.v1";

// 본문 발췌 상한. 전 기간을 보내므로 상한이 없으면 요청이 수백 KB 로 붇는다.
const MAX_RECORDS = 400;
const MAX_TEXT = 300;

function textOf(c) {
  const parts = [c.text, c.note];
  if (Array.isArray(c.answers)) for (const qa of c.answers) parts.push(qa?.a);
  else if (c.answers && typeof c.answers === "object") parts.push(...Object.values(c.answers));
  if (Array.isArray(c.experiments)) for (const e of c.experiments) parts.push(e?.text);
  return parts.filter(Boolean).join(" ").slice(0, MAX_TEXT);
}

/** 서버로 보낼 재료. 최근 것부터 MAX_RECORDS 개까지. */
export function keywordMaterials(s = loadUniverse()) {
  return (s.checkins || [])
    .filter((c) => hasRecord(c))
    .sort((a, b) => b.date.localeCompare(a.date))
    .slice(0, MAX_RECORDS)
    .map((c) => ({ date: c.date, text: textOf(c) }))
    .filter((r) => r.text);
}

export function getCachedKeywords(n) {
  try {
    const v = JSON.parse(storage.getItem(KEY) || "null");
    return v && v.n === n ? v : null;
  } catch {
    return null;
  }
}

/**
 * 최근 창에서 튄 명사를 받아온다.
 * 실패하면 null — 호출부는 기존 고정 사전을 그대로 쓴다(폴백이 아니라 기본값).
 */
export async function fetchCompareKeywords({ state, windowDays = 28 } = {}) {
  const records = keywordMaterials(state || loadUniverse());
  // 기록이 적으면 서버도 빈 목록을 돌려준다. 왕복을 아낀다.
  if (records.length < 3) return null;

  const cached = getCachedKeywords(records.length);
  if (cached) return cached;

  try {
    const res = await fetch(`${API_BASE}/suggest/compare-keywords`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ records, windowDays, top: 8 }),
    });
    if (!res.ok) throw new Error(`API ${res.status}`);
    const data = await res.json();
    if (!data?.ok) return null;
    const value = { ...data, n: records.length };
    try { storage.setItem(KEY, JSON.stringify(value)); } catch { /* 무시 */ }
    return value;
  } catch {
    return null;   // 서버가 꺼져 있어도 추천 칩은 고정 문구로 정상 동작한다
  }
}
