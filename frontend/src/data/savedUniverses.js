// 보관함 저장소 — 시뮬 결과 스냅샷을 localStorage 에 보관. 보관함 화면(수인) 소관.
import { LIFE_DOMAINS, classifyChoice, detectLifeDomains } from "./choices.js";
import storage from "./safeStorage.js";

const KEY = "pm.universes.v1";
const DOMAIN_KEYS = new Set(LIFE_DOMAINS.map((domain) => domain.key));

// 선택 유형별 기본 영역 — 본문에서 영역 키워드를 못 찾았을 때만 쓴다.
const FALLBACK_DOMAINS = {
  이직: ["career"],
  진학: ["education", "finance"],
  창업: ["business", "finance"],
  유지: ["career", "long_term_values"],
};

// {a:[…], b:[…]} 또는 [ … ] → 유효한 영역 키만 남긴 중복 없는 배열
export function mergeDomains(source) {
  const list = Array.isArray(source) ? source : [...(source?.a || []), ...(source?.b || [])];
  return [...new Set(list)].filter((key) => DOMAIN_KEYS.has(key));
}

// 영역이 저장돼 있지 않은 옛 기록 보정 — 제목·선택지·헤드라인에서 추론한다.
function inferDomains(u) {
  const text = [u?.title, u?.choiceA, u?.choiceB, u?.headline].filter(Boolean).join(" ");
  const detected = detectLifeDomains(text);
  if (detected.length) return detected;
  return FALLBACK_DOMAINS[classifyChoice(text) || ""] || ["career"];
}

// 저장분마다 스키마가 조금씩 다를 수 있어(구버전) 읽는 시점에 한 번 맞춘다.
function normalizeUniverse(u) {
  const domains = mergeDomains(u?.domains);
  return {
    ...u,
    decision: u?.decision || "none",
    doneActions: Array.isArray(u?.doneActions) ? u.doneActions : [],
    reflection: u?.reflection || "",
    domains: domains.length ? domains : inferDomains(u),
    // 옛 기록은 결정 시각이 없다 → 저장일을 기준으로 삼아 회고 타이밍을 계산한다.
    decidedAt: u?.decidedAt || (u?.decision && u.decision !== "none" ? u?.savedAt || null : null),
  };
}

export function listUniverses() {
  try {
    const arr = JSON.parse(storage.getItem(KEY) || "[]");
    return Array.isArray(arr) ? arr.map(normalizeUniverse) : [];
  } catch {
    return [];
  }
}

function persist(arr) {
  try {
    storage.setItem(KEY, JSON.stringify(arr));
  } catch {
    /* 무시 */
  }
}

export function saveUniverse(u) {
  const arr = listUniverses();
  arr.unshift(u);
  persist(arr.slice(0, 50)); // 최근 50개까지
  return u;
}

export function updateUniverse(id, patch) {
  persist(listUniverses().map((u) => (u.id === id ? { ...u, ...patch } : u)));
}

// 결정은 회고 시점의 기준이 되므로 decidedAt 을 항상 함께 남긴다(보류로 되돌리면 지운다).
export function decideUniverse(id, decision) {
  updateUniverse(id, {
    decision,
    decidedAt: decision === "none" ? null : new Date().toISOString(),
  });
}

export function removeUniverse(id) {
  persist(listUniverses().filter((u) => u.id !== id));
}

// ResultContext 의 result + profile + choices → 저장용 스냅샷 객체
export function universeFromResult(result, profile, choices, domains) {
  const A = choices?.a || result?.option_a?.label || "A";
  const B = choices?.b || result?.option_b?.label || "B";
  let headline = result?.scenario?.comparison || "";
  if (!headline && result?.causal) {
    headline = `이직 순효과 ${result.causal.effect}% (관측 ${result.causal.descriptive}%)`;
  }
  // 입력 화면에서 고른 삶의 영역 → 카드 색·'오늘 할 일' 추천의 근거가 된다.
  const domainList = mergeDomains(domains || result?.domains);
  const base = {
    id: "u_" + Math.random().toString(36).slice(2, 9),
    savedAt: new Date().toISOString().slice(0, 10),
    title: `${A} vs ${B}`,
    choiceA: A,
    choiceB: B,
    domain: result?.planetDomain || null, // 어느 행성(삶의 영역) 얘기였는지 — '그 영역의 N년 뒤' 재료
    profileSnapshot: {
      age: profile?.age,
      income: profile?.income,
      value_ranking: profile?.value_ranking || [],
    },
    headline: (headline || "").slice(0, 90),
    reflection: "",
    decision: "none", // "A" | "B" | "none"(보류) — 탐험할 미래 선택
    decidedAt: null, // 결정을 내린 시각 — 회고를 언제 물을지 계산하는 기준
    doneActions: [], // 완료한 '오늘 할 일'(텍스트)
    result, // 전체 결과 스냅샷 — '다시 보기'로 그대로 복원
  };
  return { ...base, domains: domainList.length ? domainList : inferDomains(base) };
}
