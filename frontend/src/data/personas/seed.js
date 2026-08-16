// ─────────────────────────────────────────────────────────────
// 1년치 페르소나 데이터를 '나의 우주'에 심는 공용 시더.
//
// demoYear.js(지원)가 쓰던 절차를 그대로 꺼내 공용화했다. 페르소나가 7명이 되면서
// 같은 코드를 인물 수만큼 복사하면 규칙이 갈린다 — 심는 규칙은 여기 한 곳에서만 정한다.
//
// 배치 규칙(demoYear.js 에서 검증된 것):
//   · 마지막 주(YEAR[length-1])가 '이번 주'가 되도록 역산해서 첫 주의 월요일을 잡는다.
//   · 아직 오지 않은 날(미래)은 건너뛴다 — 실행 요일에 따라 이번 주가 잘린다.
//   · '오늘' 칸은 FINALE(1년 회고)로 덮어쓴다. 같은 날짜면 addCheckin 이 교체한다.
// ─────────────────────────────────────────────────────────────

import { addCheckin, resetUniverse, todayKey, weekStartKey } from "../myUniverse.js";
import storage from "../safeStorage.js";

const UNIVERSE_KEY = "pm.myuniverse.v1";

export function addDays(dateKey, n) {
  const d = new Date(dateKey + "T00:00:00");
  d.setDate(d.getDate() + n);
  const p = (x) => String(x).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

/**
 * 1년치 주별 배열을 '나의 우주'에 심는다. 기존 기록은 지우고 채운다.
 *
 * @param {Array<Array<object>>} YEAR   주 배열. 각 원소는 그 주에 기록을 남긴 날들.
 * @param {object|null} FINALE          '오늘' 칸에 덮어쓸 회고 기록(없으면 생략).
 * @param {{demoKind?: string}} opts     demoKind 는 주간 리포트 경로를 가르는 값.
 *                                       "year" 면 6주 데모용 고정 리포트를 재사용하지 않는다.
 * @returns {number} 실제로 심은 기록 수
 */
export function seedYear(YEAR, FINALE = null, opts = {}) {
  const { demoKind = "year" } = opts;

  resetUniverse();
  const today = todayKey();
  const thisMon = weekStartKey(today);
  const start = addDays(thisMon, -(YEAR.length - 1) * 7); // 첫 주의 월요일

  const put = (date, it) =>
    addCheckin({
      date,
      mood: it.m,
      valence: +((it.m - 3) / 2).toFixed(3),
      energy: it.e,
      skill: it.s,
      keyword: it.k,
      note: it.n,
      text: it.t,
      answers: it.qa ? it.qa.map(([q, a]) => ({ q, a })) : null,
      domains: it.dom,
    });

  let planted = 0;
  for (let w = 0; w < YEAR.length; w++) {
    for (const it of YEAR[w]) {
      const date = addDays(start, w * 7 + it.d);
      if (date > today) continue; // 아직 오지 않은 날은 건너뛴다
      put(date, it);
      planted += 1;
    }
  }
  if (FINALE) {
    put(today, FINALE); // 오늘 자리는 회고로 덮어쓴다(같은 날짜면 교체된다)
    planted += 1;
  }

  // demo 플래그 세우기(배지 유지) — addCheckin 이 persist 하므로 마지막에 한 번 더.
  try {
    const s = JSON.parse(storage.getItem(UNIVERSE_KEY) || "{}");
    s.demo = true;
    s.demoKind = demoKind;
    storage.setItem(UNIVERSE_KEY, JSON.stringify(s));
    if (typeof window !== "undefined") window.dispatchEvent(new Event("pm:universe"));
  } catch { /* 무시 */ }

  return planted;
}
