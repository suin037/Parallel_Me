// ─────────────────────────────────────────────────────────────
// 월별 대표 별자리(황도 12궁) — 그 달 밤하늘에 걸리는 별자리를 달 성단의 '모양'으로 쓴다.
//
// 정직선: 성격 진단·운세가 아니다. 그 달을 알아보게 하는 계절 표식이자 장식이며,
//   기록의 의미는 여전히 색(기분)·개수(기록량)가 담는다.
//
// 매핑 기준: 각 달을 가장 많이 차지하는 궁(예: 1월 1~19일 염소자리 vs 20~31일 물병자리 → 염소자리).
// 좌표: -1~1 정규화(y는 화면 좌표계라 아래가 +). lines = stars 인덱스 쌍.
// ─────────────────────────────────────────────────────────────

export const ZODIAC = [
  { month: 1, sym: "♑", ko: "염소자리", en: "Capricornus",
    stars: [[-0.9, -0.35], [-0.45, -0.7], [0.15, -0.5], [0.65, -0.1], [0.9, 0.4], [0.35, 0.7], [-0.25, 0.6], [-0.75, 0.15]],
    lines: [[0, 1], [1, 2], [2, 3], [3, 4], [4, 5], [5, 6], [6, 7], [7, 0]] },

  { month: 2, sym: "♒", ko: "물병자리", en: "Aquarius",
    stars: [[-0.9, -0.5], [-0.5, -0.15], [-0.1, -0.55], [0.3, -0.2], [0.75, -0.6], [0.15, 0.25], [0.4, 0.65], [-0.05, 0.9]],
    lines: [[0, 1], [1, 2], [2, 3], [3, 4], [3, 5], [5, 6], [6, 7]] },

  { month: 3, sym: "♓", ko: "물고기자리", en: "Pisces",
    stars: [[-0.9, -0.7], [-0.55, -0.35], [-0.2, -0.05], [0.15, 0.25], [0.5, -0.05], [0.85, -0.45], [0.45, 0.65], [0.8, 0.9]],
    lines: [[0, 1], [1, 2], [2, 3], [3, 4], [4, 5], [3, 6], [6, 7]] },

  { month: 4, sym: "♈", ko: "양자리", en: "Aries",
    stars: [[-0.85, 0.35], [-0.3, 0.0], [0.3, -0.25], [0.85, -0.15]],
    lines: [[0, 1], [1, 2], [2, 3]] },

  { month: 5, sym: "♉", ko: "황소자리", en: "Taurus",
    stars: [[-0.9, 0.7], [-0.45, 0.3], [0.0, 0.0], [0.45, 0.3], [0.9, 0.7], [-0.7, -0.55], [0.75, -0.6]],
    lines: [[0, 1], [1, 2], [2, 3], [3, 4], [1, 5], [3, 6]] },

  { month: 6, sym: "♊", ko: "쌍둥이자리", en: "Gemini",
    stars: [[-0.6, -0.85], [-0.5, -0.25], [-0.4, 0.3], [-0.3, 0.85], [0.35, -0.85], [0.45, -0.3], [0.55, 0.25], [0.65, 0.8]],
    lines: [[0, 1], [1, 2], [2, 3], [4, 5], [5, 6], [6, 7], [0, 4], [1, 5]] },

  { month: 7, sym: "♋", ko: "게자리", en: "Cancer",
    stars: [[0.0, -0.1], [-0.75, -0.7], [0.7, -0.75], [0.12, 0.5], [0.3, 0.9]],
    lines: [[1, 0], [2, 0], [0, 3], [3, 4]] },

  { month: 8, sym: "♌", ko: "사자자리", en: "Leo",
    stars: [[-0.75, 0.45], [-0.85, -0.05], [-0.55, -0.5], [-0.1, -0.65], [0.15, -0.3], [0.65, -0.15], [0.9, 0.5], [0.05, 0.6]],
    lines: [[0, 1], [1, 2], [2, 3], [3, 4], [4, 5], [5, 6], [6, 7], [7, 0]] },

  { month: 9, sym: "♍", ko: "처녀자리", en: "Virgo",
    stars: [[-0.9, -0.55], [-0.4, -0.3], [0.05, -0.55], [0.1, 0.05], [0.6, 0.3], [0.25, 0.8], [-0.45, 0.5]],
    lines: [[0, 1], [1, 2], [1, 3], [3, 4], [3, 5], [3, 6]] },

  { month: 10, sym: "♎", ko: "천칭자리", en: "Libra",
    stars: [[0.0, -0.7], [-0.75, -0.05], [0.75, -0.1], [-0.55, 0.65], [0.6, 0.6]],
    lines: [[1, 0], [0, 2], [1, 3], [2, 4]] },

  { month: 11, sym: "♏", ko: "전갈자리", en: "Scorpius",
    stars: [[-0.9, -0.6], [-0.5, -0.55], [-0.15, -0.4], [0.1, -0.1], [0.28, 0.3], [0.55, 0.65], [0.9, 0.72], [0.92, 0.3]],
    lines: [[0, 1], [1, 2], [2, 3], [3, 4], [4, 5], [5, 6], [6, 7]] },

  { month: 12, sym: "♐", ko: "사수자리", en: "Sagittarius",
    stars: [[-0.8, 0.1], [-0.45, -0.5], [0.0, -0.2], [0.4, -0.6], [0.75, 0.05], [0.3, 0.55], [-0.3, 0.6]],
    lines: [[0, 1], [1, 2], [2, 3], [3, 4], [4, 5], [5, 6], [6, 0], [2, 5]] },
];

/** 월(1~12) → 그 달의 대표 별자리. */
export function zodiacOf(month) {
  return ZODIAC[Math.max(0, Math.min(11, Number(month) - 1))];
}

/** 기록 개수만큼 좌표를 만든다 — 별자리 꼭짓점부터 채우고, 남으면 꼭짓점 주위에 흩뿌린다.
 *  기록이 적으면 별자리가 듬성듬성, 많이 쌓이면 또렷해진다(기록량이 곧 밀도). */
export function zodiacPoints(month, n, radius = 13) {
  const z = zodiacOf(month);
  const anchors = z.stars;
  const out = [];
  for (let i = 0; i < n; i++) {
    const a = anchors[i % anchors.length];
    const round = Math.floor(i / anchors.length); // 두 바퀴째부터는 꼭짓점 곁에 작게 붙는다
    const spread = round === 0 ? 0 : 0.1 + round * 0.055;
    const angle = i * 2.39996;
    out.push([
      (a[0] + Math.cos(angle) * spread) * radius,
      (a[1] + Math.sin(angle) * spread) * radius * 0.92,
    ]);
  }
  return out;
}

/** 별자리 선분 좌표 — 꼭짓점(첫 바퀴)만 잇는다. 기록이 꼭짓점 수보다 적으면 그만큼만. */
export function zodiacLines(month, n, radius = 13) {
  const z = zodiacOf(month);
  const have = Math.min(n, z.stars.length);
  return z.lines
    .filter(([i, j]) => i < have && j < have)
    .map(([i, j]) => [
      z.stars[i][0] * radius, z.stars[i][1] * radius * 0.92,
      z.stars[j][0] * radius, z.stars[j][1] * radius * 0.92,
    ]);
}

/** 별자리 밑그림을 '도트'로 — 선을 일정 간격 점으로 쪼개 픽셀 아트처럼 깔아둔다.
 *  격자에 스냅해서 손그림 선이 아니라 도트로 읽히게 한다. */
export function zodiacDots(month, radius = 13, step = 1.9) {
  const z = zodiacOf(month);
  const pt = (i) => [z.stars[i][0] * radius, z.stars[i][1] * radius * 0.92];
  const grid = step;                      // 이 간격 격자에 스냅 → 도트 느낌
  const snap = (v) => Math.round(v / grid) * grid;
  const seen = new Set();
  const out = [];
  const push = (x, y, big = false) => {
    const key = `${snap(x)},${snap(y)}`;
    if (seen.has(key)) return;
    seen.add(key);
    out.push({ x: snap(x), y: snap(y), big });
  };
  for (const [i, j] of z.lines) {
    const [x1, y1] = pt(i);
    const [x2, y2] = pt(j);
    const len = Math.hypot(x2 - x1, y2 - y1);
    const n = Math.max(1, Math.round(len / step));
    for (let k = 0; k <= n; k++) push(x1 + ((x2 - x1) * k) / n, y1 + ((y2 - y1) * k) / n);
  }
  z.stars.forEach((_, i) => {            // 꼭짓점은 큰 도트로 — 별자리의 마디가 보이게
    const [x, y] = pt(i);
    const key = `${snap(x)},${snap(y)}`;
    const hit = out.find((d) => `${d.x},${d.y}` === key);
    if (hit) hit.big = true;
    else push(x, y, true);
  });
  return out;
}

/** 별자리 밑그림 — 기록이 없어도 그 달의 별자리 형태가 연하게 보이도록.
 *  기록은 이 자리 위에서 하나씩 밝아진다(밑그림=별자리, 밝은 별=내 기록). */
export function zodiacGhost(month, radius = 13) {
  const z = zodiacOf(month);
  const pt = (i) => [z.stars[i][0] * radius, z.stars[i][1] * radius * 0.92];
  return {
    dots: z.stars.map((_, i) => pt(i)),
    lines: z.lines.map(([i, j]) => [...pt(i), ...pt(j)]),
  };
}
