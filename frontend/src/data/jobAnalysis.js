// 직무 분석 — 채용 공고 × 내 성향.
// 공고에서 요구역량만 뽑는 건 어디서나 되지만, 우리는 일기에서 만든 성향(persona_block)을
// 함께 넣어 '이 사람과 이 일이 만나는 지점 / 부딪히는 지점'까지 본다.
// 서버가 uid로 저장된 성향을 찾고, 없으면 공고만으로 분석한다(그때 friction 은 비워진다).
import { buildDisposition } from "./psychQuestions.js";
import { computeDiarySignals } from "./diarySignals.js";
import { CARD_BY_ID } from "./valueCards.js";
import { valueRankingLine } from "./careerNet.js";
import { API_BASE } from "./apiBase.js";

const BASE = API_BASE;

// 로컬 성향 재료 — 서버 DB에 저장된 성향이 없어도 분석이 개인화되도록 프론트에서 만든다.
// (기록은 브라우저에 있으니 이 경로가 기본이고, 서버 저장본은 uid 로 보조한다.)
export function localPersonaBlock(profile) {
  const lines = [];
  const values = (profile?.value_ranking || [])
    .slice(0, 4)
    .map((id) => CARD_BY_ID[id]?.label || id);
  if (values.length) lines.push(`가치 순서(중요한 순): ${values.join(" > ")}`);
  if (profile?.mbti && profile.mbti !== "모름") lines.push(`MBTI: ${profile.mbti}`);
  // 세부 검사를 했다면 검증된 척도가 우선 근거가 된다(커리어넷 직업가치관검사).
  const cn = valueRankingLine(profile?.career_values);
  if (cn) lines.push(cn);

  try {
    const sig = computeDiarySignals({ windowDays: 28 });
    if (sig?.ok) {
      const bits = [];
      if (sig.jobChangeDays) bits.push(`최근 4주 이직·진로 고민 ${sig.jobChangeDays}일`);
      (sig.signals || []).slice(0, 3).forEach((s) => bits.push(`${s.label} ${s.days}일`));
      // moodTrend 는 '후반 평균 − 전반 평균'(기울기)이라 숫자를 그대로 주면
      // 점수로 오해된다. 방향만 말로 전한다.
      if (sig.moodTrend != null) {
        const dir = sig.moodTrend > 0.15 ? "뒤로 갈수록 나아짐"
          : sig.moodTrend < -0.15 ? "뒤로 갈수록 가라앉음" : "큰 기복 없음";
        bits.push(`기분 흐름 ${dir}`);
      }
      if (bits.length) lines.push(`기록 신호(최근 4주): ${bits.join(" · ")}`);
    }
  } catch {
    /* 기록이 없으면 신호 없이 진행 */
  }

  const psych = buildDisposition(profile);
  const head = lines.length
    ? "[성향 재료 — 일기·온보딩에서 만든 것. 단정 말고 대조 근거로만 써라]\n" +
      lines.map((line) => "· " + line).join("\n")
    : "";
  return [head, psych.block].filter(Boolean).join("\n\n");
}

export async function analyzeJobPosting({ posting, choice = null, uid = "me", profile = null }) {
  const persona_block = profile ? localPersonaBlock(profile) : null;
  const res = await fetch(`${BASE}/job/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ posting, choice, uid, persona_block: persona_block || null }),
  });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

// 공고를 붙여넣었는지 판단 — 너무 짧으면 분석 버튼을 막는다.
export function isPostingReady(text) {
  return String(text || "").trim().length >= 30;
}

/** 공고 URL → 텍스트. 사이트가 JS 렌더링이면 얇게 잡히므로 thin 을 함께 준다. */
export async function extractFromUrl(url) {
  const res = await fetch(`${BASE}/job/extract-url`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

/** 공고 PDF → 텍스트(채용 페이지를 PDF로 저장해 오는 경우). */
export async function extractFromPdf(file) {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE}/job/extract-pdf`, { method: "POST", body: form });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}
