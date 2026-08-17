// ─────────────────────────────────────────────────────────────
// 외부로 나가는 요청의 단일 통로 — 여기를 지나지 않으면 마스킹이 안 걸린다.
//
// 왜 만들었나: 마스킹(redactPII)은 있었는데 **호출부 두 곳**에만 붙어 있었다
//   (RelationshipInput 의 대화 전문, Result 의 선택지 두 줄). 나머지 8개 모듈의
//   fetch 26곳은 전부 우회했고, 그중 futureApi 는 일기 본문 200자를 그대로
//   records 에 담아 보내고 있었다. 화면 컴포넌트마다 기억해서 붙이는 구조라
//   기능이 하나 늘 때마다 또 뚫렸다.
//
// 그래서 정책을 **필드가 아니라 이 파일**에 모은다. 새 요청을 추가하는 사람은
//   maskRecords / maskText / maskPosting 중 하나를 고르기만 하면 된다.
//
// ── 왜 일괄 마스킹이 아닌가 ──────────────────────────────────
// redactPII 는 금액도 [금액] 으로 바꾼다. 그런데 채용공고 분석·기업 분석은
//   **금액과 회사명이 곧 분석 대상**이라, 거기에 같은 규칙을 걸면 요청이 무의미해진다
//   ("연봉 [금액] 인 [회사] 가 나와 맞나요?"). 그래서 자유서술은 전부 가리되,
//   기능 입력은 이름·연락처·주민번호만 가리고 금액·회사명은 남긴다(maskPosting).
//
// 정직선: 규칙 기반이라 임의의 성명·회사명을 전부 잡지는 못한다. 프로필에 적힌
//   이름·회사는 정확히, 패턴 PII(이메일·전화·주민·카드)는 광범위하게 잡는 이중 전략.
// ─────────────────────────────────────────────────────────────

import storage from "./safeStorage.js";
import { redactPII } from "./piiRedact.js";

const PROFILE_KEY = "pm.profile.v1";

/**
 * 마스킹 기준이 되는 '알려진 PII'.
 *
 * 이 모듈들은 React 밖(순수 함수)에서 불리므로 컨텍스트를 못 쓴다. ResultContext 가
 * 쓰는 것과 같은 키를 직접 읽는다 — 프로필이 없으면 패턴 PII 만 걸린다.
 */
export function knownPII() {
  try {
    const p = JSON.parse(storage.getItem(PROFILE_KEY) || "null");
    return { name: (p?.name || "").trim(), company: (p?.company || "").trim() };
  } catch {
    return {};
  }
}

/** 자유서술 한 줄 — 일기·회고·대화·선택지 문장. 전부 가린다. */
export function maskText(text) {
  return redactPII(text, knownPII()).masked;
}

/**
 * 기능 입력 — 금액·회사명이 **계산에 쓰이는** 텍스트.
 * 채용공고 원문, 사용자가 적은 조건("연봉 6000만원", "runway 8개월") 등.
 * 여기에 [금액] 을 씌우면 그 요청이 하는 일 자체가 없어진다.
 * 이름·연락처·주민번호·카드번호는 똑같이 가린다.
 */
export function maskFunctional(text) {
  return redactPII(text, knownPII(), { amounts: false, company: false }).masked;
}

/** 채용공고 원문 — maskFunctional 과 같은 정책. 호출부에서 뜻이 드러나게 이름만 따로 둔다. */
export const maskPosting = maskFunctional;

/** 조건 입력 객체({ key: "6000만원" }) — 값만 기능 입력 정책으로 가린다. */
export function maskAnswers(obj) {
  if (!obj || typeof obj !== "object") return obj;
  return Object.fromEntries(
    Object.entries(obj).map(([k, v]) => [k, typeof v === "string" ? maskFunctional(v) : v]),
  );
}

// 사용자가 직접 쓴 문장이 담기는 자리 전부.
//   text/note        일기 본문
//   title/step       작은 탐험 (무엇을 다녀왔나 · 첫 걸음)
//   choiceA/choiceB  저장된 시뮬레이션의 두 갈림길
//   headline/reflection  결과 요약 · 결정 후 회고
// 새 필드를 payload 에 실을 때 여기에 추가하지 않으면 그 필드는 안 가려진다.
const TEXT_FIELDS = [
  "text", "note", "title", "step", "chatSummary",
  "choiceA", "choiceB", "headline", "reflection",
];

// 값이 문자열 배열인 자리(할 일 목록 등).
const LIST_FIELDS = ["doneActions"];

/**
 * 일기·탐험 레코드 배열 — 원본은 건드리지 않고 마스킹된 사본을 만든다.
 * answers 처럼 값이 문장인 객체도 같이 훑는다.
 */
export function maskRecords(records = []) {
  const known = knownPII();
  return records.map((r) => {
    if (!r || typeof r !== "object") return r;
    const out = { ...r };
    for (const f of TEXT_FIELDS) {
      if (typeof out[f] === "string" && out[f]) out[f] = redactPII(out[f], known).masked;
    }
    for (const f of LIST_FIELDS) {
      if (Array.isArray(out[f])) {
        out[f] = out[f].map((v) => (typeof v === "string" ? redactPII(v, known).masked : v));
      }
    }
    if (out.answers && typeof out.answers === "object" && !Array.isArray(out.answers)) {
      out.answers = Object.fromEntries(
        Object.entries(out.answers).map(([k, v]) => [
          k,
          typeof v === "string" ? redactPII(v, known).masked : v,
        ]),
      );
    }
    return out;
  });
}

/** 대화 메시지 배열 — {role, content} 의 content 만 가린다. */
export function maskMessages(messages = []) {
  const known = knownPII();
  return messages.map((m) =>
    m && typeof m.content === "string" ? { ...m, content: redactPII(m.content, known).masked } : m,
  );
}
