import { API_BASE } from "./apiBase.js";
// 기업 분석 — OpenDART(공시·재무) + AI 요약. 서버가 인증키를 들고 대신 호출한다.
// 공고 분석이 뽑아낸 회사명으로 바로 이어진다.
const BASE = API_BASE;

/** 재무 5개년 + 최근 공시(근거 자료). 키 없으면 {ok:false, reason:"no_dart_key"}. */
export async function fetchCompanySummary(name) {
  const res = await fetch(`${BASE}/company/summary?name=${encodeURIComponent(name)}`);
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

/** 재무·공시 + AI 요약(흐름·최근 관심사·지원동기 포인트).
 *  corpCode 를 주면 그 회사로 확정한다(이름이 비슷한 회사가 여럿일 때 사용자가 고른 값). */
export async function analyzeCompany(name, corpCode = null) {
  const res = await fetch(`${BASE}/company/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, corp_code: corpCode || null, uid: "me" }),
  });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

/** 원 단위 → 조/억. 공시 원문 단위를 그대로 쓰되 읽기 쉽게만 바꾼다. */
export function formatWon(v) {
  if (v == null) return "—";
  const abs = Math.abs(v);
  if (abs >= 1e12) return `${(v / 1e12).toFixed(1)}조원`;
  if (abs >= 1e8) return `${Math.round(v / 1e8).toLocaleString()}억원`;
  return `${v.toLocaleString()}원`;
}

/** 첫 해 대비 마지막 해 증감률 — 막대 위 추세 표시용. */
export function growthRate(rows, key) {
  const vals = (rows || []).map((r) => r[key]).filter((v) => v != null);
  if (vals.length < 2 || !vals[0]) return null;
  return ((vals[vals.length - 1] - vals[0]) / Math.abs(vals[0])) * 100;
}
