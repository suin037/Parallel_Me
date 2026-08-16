// 가치 카드 8종 — 지윤 diary_module/qmode/value_ranking.py 의 CARDS 와 id·axis 를 반드시 일치.
// (id 가 backend value_ranking 계약이다. 라벨/이모지/문구는 프론트 표시용이라 자유롭게 조정 가능.)
export const VALUE_CARDS = [
  { id: "money",     emoji: "💰", label: "경제적 여유", axis: "경제" },
  { id: "status",    emoji: "🏅", label: "인정·지위",   axis: "경제" },
  { id: "family",    emoji: "❤️", label: "가족·사랑",   axis: "관계" },
  { id: "friends",   emoji: "👥", label: "친구·소속",   axis: "관계" },
  { id: "growth",    emoji: "🌱", label: "배움·성취",   axis: "성장" },
  { id: "freedom",   emoji: "🧭", label: "자유·자율",   axis: "자기실현" },
  { id: "meaning",   emoji: "✨", label: "의미·나다움", axis: "자기실현" },
  { id: "stability", emoji: "🛟", label: "건강·안정",   axis: "안정" },
];

export const CARD_BY_ID = Object.fromEntries(VALUE_CARDS.map((c) => [c.id, c]));

// 순위 상위에서 대표 '축'만 뽑아 표시("성장·안정 중심"). 가중치 계산이 아니라 라벨링용.
// (실제 가중치 axis_weights 변환은 backend 가 담당 — 여기선 중복 구현하지 않는다.)
export function topAxes(ranking, n = 2) {
  const seen = [];
  for (const id of ranking || []) {
    const ax = CARD_BY_ID[id]?.axis;
    if (ax && !seen.includes(ax)) seen.push(ax);
    if (seen.length >= n) break;
  }
  return seen;
}
