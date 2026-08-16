import { API_BASE } from "./apiBase.js";
import storage from "./safeStorage.js";
// 내 성향모델 로컬 API 연결 (diary_module/qmode/api.py, uvicorn :8000).
// 체크인(별) → 진짜 DispositionModel + report.py → 주간 리포트 서사 + 내일 할 거리.
//
// 주간 리포트는 '완성된 주'에만 만든다. 한 번 만들면 DB(week_reports)에 저장되고,
// 지난 주는 재생성 없이 저장본(getSavedReport)을 즉시 불러온다.
const BASE = API_BASE;
export const REPORT_UID = "me";

// 저장된 주간 리포트 조회 → { found, report, actions, ... }
export async function getSavedReport(uid, weekKey) {
  const res = await fetch(
    `${BASE}/report/${encodeURIComponent(uid)}/${encodeURIComponent(weekKey)}`,
  );
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

// 저장된 주간 리포트 전체 삭제(데모 재시드/비우기 시 옛 리포트 제거). 서버 없어도 조용히 무시.
export async function clearSavedReports(uid) {
  try {
    await fetch(`${BASE}/reports/${encodeURIComponent(uid)}`, { method: "DELETE" });
  } catch {
    /* 서버 미가동 — 무시 */
  }
}

// 일기 텍스트 → 인생 영역(행성) 자동 분류. { primary, domains:[key...] } 또는 실패 시 null.
export async function tagDomain(text) {
  try {
    const res = await fetch(`${BASE}/tag`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

// 말투 — 사용자가 대화 화면에서 켜고 끈 값. 마스코트가 말하는 곳이면 어디서든 이걸 따른다.
export const SPEECH_KEY = "pm.speech.v1";
export function loadSpeech() {
  try {
    return storage.getItem(SPEECH_KEY) === "casual" ? "casual" : "polite"; // 기본 존댓말
  } catch {
    return "polite";
  }
}

// 마스코트 대화 한 턴 → { reply, stage, suggest_compose }. 실패 시 간단 폴백.
//  · context: 프론트가 가진 기억 {recent:[{date,emotion,text}], hardStreak} — 로컬 우선이라 이 경로가 기본.
//  · speech : 말투 "polite"(기본) | "casual". 사용자가 화면에서 켜고 끈다.
//  · role   : 이 대화의 역할(일상 되묻기 / 마음 살피기 / 건강 체크).
export async function chatTurn(messages, opts = {}) {
  const { persona = "lumi", context = null, speech = "polite", role = null } = opts;
  try {
    const res = await fetch(`${BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages, persona, context, speech, role }),
    });
    if (!res.ok) throw new Error();
    return await res.json();
  } catch {
    return {
      reply: speech === "casual" ? "그랬구나." : "그러셨군요.",
      stage: "open",
      suggest_compose: false,
    };
  }
}

// 한 주치 기록 → 위로 한마디(주 1회). 리포트가 아니라 말 한마디만.
export async function weeklyComfort(entries, { persona = "lumi", speech = "polite" } = {}) {
  try {
    const res = await fetch(`${BASE}/chat/comfort`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ entries, persona, speech }),
    });
    if (!res.ok) throw new Error();
    return ((await res.json()).text || "").trim() || null;
  } catch {
    return null; // 서버 없으면 위로 칸을 아예 띄우지 않는다
  }
}

// 일기 텍스트 → 내가 만든 감정모델 추론 { ok, emotion, mood, crisis_level }. 감정 미선택 시 폴백용.
// 체크포인트 없으면 { ok:false } → 호출부가 LLM 폴백으로 강등.
export async function analyzeEmotion(text) {
  try {
    const res = await fetch(`${BASE}/emotion`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    if (!res.ok) return null;
    const j = await res.json();
    return j && j.ok ? j : null;
  } catch {
    return null;
  }
}

// 대화 전체 → 1인칭 일기 { text, mood, emotion, domains }. 체크인 저장용.
export async function composeDiary(messages) {
  try {
    const res = await fetch(`${BASE}/diary/compose`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages }),
    });
    if (!res.ok) throw new Error();
    return await res.json();
  } catch {
    const text = messages.filter((m) => m.role !== "bot").map((m) => m.text).join(" ");
    return { text, mood: 3, emotion: "", domains: ["life"] };
  }
}

// 분석·서사 생성. uid+week_key 주면 결과가 DB에 저장된다.
export async function analyzeDisposition({ ranked_cards, mbti, entries, uid, week_key }) {
  const res = await fetch(`${BASE}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ranked_cards, mbti, entries, uid, week_key }),
  });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}
