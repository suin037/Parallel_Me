// 내 성향모델 API. 메인 백엔드가 qmode 앱을 /qmode 아래에 마운트한다.
// 프론트 일기/체크인 → 진짜 DispositionModel + report.py → 결과.
const BASE = import.meta.env.VITE_QMODE_API_URL || "http://localhost:8000/qmode";

export async function analyzeDisposition({ ranked_cards, mbti, entries }) {
  const res = await fetch(`${BASE}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ranked_cards, mbti, entries }),
  });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

// 온보딩+일기 저장 + persona_block 계산해 DB에 보관 (uid="me")
export async function saveMe({ ranked_cards, mbti, profile, entries }) {
  const res = await fetch(`${BASE}/save`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ uid: "me", ranked_cards, mbti, profile, entries }),
  });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

// 저장된 persona_block을 예측 수치와 함께 이직 서사로 생성
export async function getScenario({ uid = "me", choice, expected_wage, causal_effect, survival_months, age, major }) {
  const res = await fetch(`${BASE}/scenario`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ uid, choice, expected_wage, causal_effect, survival_months, age, major }),
  });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

// A/B 외의 '제3의 길'을 성향+일기신호에 근거해 생성 (재구성 제안, 수치 예측 아님)
export async function getThirdPath({ choice_a, choice_b, entries, signal_block, age, major, uid }) {
  const res = await fetch(`${BASE}/third-path`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ choice_a, choice_b, entries, signal_block, age, major, uid }),
  });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}
