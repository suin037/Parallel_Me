// 심리 성향 input — MBTI + 서술형 질문. 프로필 개인화 재료로 쓰인다(수인 설정 소관).
// 서술형 문항은 지윤 qmode/questions.json 의 성향 추출 문항(D2·D1·D4)에서 가져옴.

export const MBTI_TYPES = [
  "모름",
  "INTJ", "INTP", "ENTJ", "ENTP",
  "INFJ", "INFP", "ENFJ", "ENFP",
  "ISTJ", "ISFJ", "ESTJ", "ESFJ",
  "ISTP", "ISFP", "ESTP", "ESFP",
];

// 성향/가치 파악용 서술형 문항 (매일 감정 일기는 지윤 일기 탭 소관, 여긴 성향 심화)
export const PSYCH_QUESTIONS = [
  { id: "D2", label: "늘리고/줄이고 싶은 것", prompt: "지금 삶에서 늘리고 싶은 것 하나, 줄이고 싶은 것 하나를 꼽는다면?" },
  { id: "D1", label: "망설인 선택", prompt: "최근 망설인 선택이 있나요? 무엇이 마음에 걸렸나요?" },
  { id: "D4", label: "부러웠던 순간", prompt: "최근 누군가가 부러웠던 순간이 있나요? 무엇이 부러웠나요?" },
];

// 프로필의 mbti + 서술 답변 → 백엔드 disposition_block 텍스트 + 답변 수(n).
// 백엔드는 이 블록을 서사 프롬프트에 주입한다(단정 아님, 톤·강조 재료).
export function buildDisposition(profile) {
  const ans = profile?.psych_answers || {};
  const answered = PSYCH_QUESTIONS.filter((q) => (ans[q.id] || "").trim());
  const lines = [];
  if (profile?.mbti && profile.mbti !== "모름") lines.push(`MBTI: ${profile.mbti}`);
  for (const q of answered) lines.push(`${q.label}: "${ans[q.id].trim()}"`);
  const block = lines.length
    ? "[사용자 성향 서술 재료 — 단정 말고 서사 톤·강조에만 반영]\n" +
      lines.map((l) => "· " + l).join("\n")
    : "";
  return { block, n: answered.length };
}
