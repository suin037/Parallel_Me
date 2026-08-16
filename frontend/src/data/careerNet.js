import { API_BASE } from "./apiBase.js";
// 커리어넷 오픈API 연결 — 서버(qmode api)가 키를 들고 대신 호출한다.
// 브라우저에서 직접 부르면 인증키가 노출되고 CORS 도 막히므로 프록시 구조가 맞다.
const BASE = API_BASE;

/** 직업가치관검사 28문항(대학/일반). */
export async function fetchValueTest() {
  const res = await fetch(`${BASE}/career/value-test`);
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

/** 응답 → 8개 가치 순위 + 커리어넷 공식 리포트 링크. */
export async function submitValueTest(answers) {
  const res = await fetch(`${BASE}/career/value-report`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ answers }),
  });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

/** 검사 결과를 성향 재료 한 줄로 — 직무 분석·서사 프롬프트에 얹는다. */
export function valueRankingLine(ranking) {
  if (!ranking?.length) return "";
  const top = ranking.slice(0, 4).map((v) => v.name).join(" > ");
  const low = ranking.slice(-2).map((v) => v.name).join("·");
  return `직업가치관검사(커리어넷) 상위: ${top} / 하위: ${low}`;
}
