// ─────────────────────────────────────────────────────────────
// 집단 학습 기여(익명) — 원문·개인정보 대신 '비식별 집계'만 뽑아 집단 모델에 기여한다.
//
// 플라이휠의 핵심: 많이 쓸수록 모델↑, 모두 혜택↑ — 그런데 원문은 기기 밖으로 안 나간다.
//   · 내보내는 것: 신호 카운트·기분추세 버킷·영역·기록 수 (개인 식별 불가)
//   · 절대 안 내보내는 것: 이름·일기 원문·연락처·정확한 날짜/연봉
//   · anonId: PII에서 파생하지 않은 무작위 값(역추적 방지)
//
// 정직선: 지금은 '기여 페이로드를 만들어 보여주는' 실증 단계. 실제 서버 수집·차등
//   프라이버시·연합학습은 로드맵(구현 전이면 구현했다 하지 않는다).
// ─────────────────────────────────────────────────────────────
import { computeDiarySignals, dominantDomain } from "./diarySignals.js";
import storage from "./safeStorage.js";

const ANON_KEY = "pm.anonId.v1";
const CONSENT_KEY = "pm.contribConsent.v1";

function anonId() {
  try {
    let id = storage.getItem(ANON_KEY);
    if (!id) {
      const rnd = crypto.getRandomValues(new Uint8Array(8));
      id = "anon_" + [...rnd].map((b) => b.toString(16).padStart(2, "0")).join("");
      storage.setItem(ANON_KEY, id);
    }
    return id;
  } catch {
    return "anon_local";
  }
}

export function getConsent() {
  try {
    return storage.getItem(CONSENT_KEY) === "1";
  } catch {
    return false;
  }
}
export function setConsent(on) {
  try {
    storage.setItem(CONSENT_KEY, on ? "1" : "0");
  } catch {
    /* 무시 */
  }
}

// 절대 포함하지 않는 항목(감사·투명성용으로 화면에 함께 표시).
export const EXCLUDED = ["이름", "일기 원문", "질문 답변 원문", "연락처", "정확한 날짜", "정확한 연봉"];

/** 비식별 기여 페이로드 생성. 기록 없으면 null. */
export function buildContribution() {
  const sig = computeDiarySignals({ windowDays: 28 });
  if (!sig.ok) return null;
  const trend = sig.moodTrend;
  return {
    anonId: anonId(),
    appVersion: "pm-1",
    domain: dominantDomain({ windowDays: 28 }) || "unknown",
    recordCount: sig.days, // 며칠 기록했나(대략)
    signals: Object.fromEntries((sig.signals || []).map((s) => [s.key, s.days])), // 신호별 일수
    moodTrendBucket: trend == null ? "n/a" : trend > 0.1 ? "up" : trend < -0.1 ? "down" : "flat",
  };
}
