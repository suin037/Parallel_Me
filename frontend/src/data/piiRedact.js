// ─────────────────────────────────────────────────────────────
// PII 마스킹 — 외부 AI(Claude API)로 텍스트를 보내기 전에 개인식별정보를 가린다.
//
// API 기반 앱의 핵심 방어: "원문 개인정보가 외부 모델로 나가지 않는다."
//   · 패턴 PII: 이메일·전화·주민번호·카드번호 → 토큰으로 치환
//   · 금액: 구체 숫자(연봉 등) → [금액]
//   · 알려진 PII: 사용자가 입력한 이름·회사명(정확 일치) → 토큰
//
// 정직선: 규칙 기반이라 100% 완벽하진 않다(임의 회사명·성명 전부는 못 잡음).
//   그래서 '알려진 PII(프로필)'는 정확히, 패턴 PII는 광범위하게 잡는 이중 전략.
// ─────────────────────────────────────────────────────────────
function escapeRegExp(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

const PATTERNS = [
  [/[\w.+-]+@[\w-]+\.[\w.-]+/g, "[이메일]"],
  [/01[016789][-.\s]?\d{3,4}[-.\s]?\d{4}/g, "[전화번호]"],
  [/\d{6}[-\s]?[1-4]\d{6}/g, "[주민번호]"],
  [/\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}/g, "[카드번호]"],
];

/**
 * @param {string} text
 * @param {{name?:string, company?:string}} known  프로필에서 온 알려진 PII
 * @param {{amounts?:boolean, company?:boolean}} opts
 *   amounts=false  금액을 남긴다. 채용공고·기업 분석처럼 **금액이 곧 분석 대상**인
 *                  요청에서 [금액] 으로 가리면 그 요청 자체가 무의미해진다.
 *                  (그런 요청도 이름·연락처·주민번호는 그대로 가린다.)
 *   company=false  회사명을 남긴다. 기업 조회는 회사명이 조회 키다.
 * @returns {{masked:string, hits:string[]}}
 */
export function redactPII(text, known = {}, opts = {}) {
  const { amounts = true, company = true } = opts;
  if (!text) return { masked: text || "", hits: [] };
  let s = String(text);
  const hits = [];

  // 금액(연봉·월급 등 구체 숫자) → [금액]
  if (amounts) {
    s = s.replace(/\d[\d,]*\s*(만원|원|만\s?원|억)/g, () => { hits.push("금액"); return "[금액]"; });
  }

  for (const [re, tok] of PATTERNS) {
    s = s.replace(re, () => { hits.push(tok); return tok; });
  }

  // 알려진 PII(정확 일치) — 이름·회사명
  const pairs = company
    ? [[known.name, "[이름]"], [known.company, "[회사]"]]
    : [[known.name, "[이름]"]];
  for (const [val, tok] of pairs) {
    const v = (val || "").trim();
    if (v.length >= 2) {
      s = s.replace(new RegExp(escapeRegExp(v), "g"), () => { hits.push(tok); return tok; });
    }
  }

  return { masked: s, hits: [...new Set(hits)] };
}

// 일기 entries 배열의 텍스트 필드를 통째로 마스킹(외부 전송용 사본). 원본은 안 건드림.
export function redactEntries(entries = [], known = {}) {
  const allHits = new Set();
  const masked = entries.map((e) => {
    const t = redactPII(e.text, known);
    t.hits.forEach((h) => allHits.add(h));
    let answers = e.answers;
    if (answers && typeof answers === "object" && !Array.isArray(answers)) {
      answers = Object.fromEntries(Object.entries(answers).map(([k, v]) => {
        const r = redactPII(v, known);
        r.hits.forEach((h) => allHits.add(h));
        return [k, r.masked];
      }));
    }
    return { ...e, text: t.masked, answers };
  });
  return { entries: masked, hits: [...allHits] };
}
