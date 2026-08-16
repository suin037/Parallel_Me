// ─────────────────────────────────────────────────────────────
// 별자리 분류·명명 규칙. 나의 우주 화면(민주) 소관.
//
// 이름은 2축으로 정한다.
//   축1 모양(shape) = 그 7일 valence 의 평균(기운) × 표준편차(진폭) → 6가지 형
//   축2 주제(theme) = 사용자의 가치 순위 1순위가 속한 axis (valueCards.js)
//   → `${모양}형 ${주제} 별자리`   예) "도전형 성장 별자리"
//
// ⚠️ 이건 성격 진단이 아니다. "지난 7일 기록의 모양"을 부르는 이름일 뿐이며,
//    문구는 항상 기간을 명시하는 형태로 쓴다. (Parallel Me 데이터 정직성 원칙)
// ─────────────────────────────────────────────────────────────

import { topAxes } from "./valueCards.js";

// 이름을 붙이려면 최소 이만큼은 기록이 있어야 한다. 2~3일 기록으로 한 주를
// 규정하면 과잉 해석이 된다.
export const MIN_RECORDS_TO_NAME = 4;

// valence(-1~1) 임계값. 초안이며 실사용 로그 보고 조정 대상.
export const THRESHOLDS = {
  meanHigh: 0.15,
  meanLow: -0.15,
  sdWide: 0.35,
};

export const SHAPES = {
  cruise: { adj: "순항", line: "대체로 맑았고 흔들림이 적었어요" },
  leap: { adj: "도전", line: "높이 올라간 날도, 크게 흔들린 날도 있었어요" },
  balance: { adj: "균형", line: "큰 굴곡 없이 지나갔어요" },
  wave: { adj: "기복", line: "오르내림이 잦았어요" },
  endure: { adj: "인내", line: "낮게 가라앉은 채 버틴 날이 많았어요" },
  storm: { adj: "격동", line: "힘든 날과 버틴 날이 크게 엇갈렸어요" },
};

// ── 영역별 이름 ───────────────────────────────────────────────
// 나의 우주에서는 별자리가 어느 행성(삶의 영역)에 속하는지 분명하다. 그때는 가치
// 순위 대신 그 영역을 주제로 쓴다 — 안 그러면 다섯 행성이 전부 같은 이름이 된다.
// 문장도 영역마다 다르게 둔다. 같은 '인내형'이라도 진로에서 버틴 것과 관계에서
// 버틴 것은 다른 이야기다.
export const DOMAIN_THEME = {
  career: "진로", relation: "관계", health: "건강", growth: "성장", life: "일상",
};

const DOMAIN_LINES = {
  career: {
    cruise: "일이 손에 붙어 있던 구간이에요",
    leap: "밀어붙인 날과 흔들린 날이 함께 있었어요",
    balance: "큰 변화 없이 자리를 지킨 구간이에요",
    wave: "일에 대한 마음이 자주 오르내렸어요",
    endure: "버티는 쪽으로 기울어 있던 구간이에요",
    storm: "그만두고 싶던 날과 다시 붙잡은 날이 엇갈렸어요",
  },
  relation: {
    cruise: "사람과의 거리가 편안했던 구간이에요",
    leap: "가까워진 날도, 부딪힌 날도 있었어요",
    balance: "관계가 잔잔하게 지나갔어요",
    wave: "사람 때문에 마음이 자주 흔들렸어요",
    endure: "서운함을 안고 지나온 구간이에요",
    storm: "크게 가까워졌다 멀어졌다 했어요",
  },
  health: {
    cruise: "몸과 마음이 고르게 굴러간 구간이에요",
    leap: "무리한 날과 회복한 날이 함께 있었어요",
    balance: "큰 탈 없이 지나갔어요",
    wave: "컨디션이 자주 오르내렸어요",
    endure: "지친 채로 버틴 날이 많았어요",
    storm: "무너진 날과 겨우 챙긴 날이 크게 엇갈렸어요",
  },
  growth: {
    cruise: "배우던 것이 순하게 이어진 구간이에요",
    leap: "크게 나아간 날과 막힌 날이 함께 있었어요",
    balance: "꾸준히 같은 속도로 지나갔어요",
    wave: "해보다 멈추다를 반복했어요",
    endure: "잘 안 풀려도 놓지는 않은 구간이에요",
    storm: "확 늘었다 확 주저앉았다 했어요",
  },
  life: {
    cruise: "하루하루가 대체로 편안했어요",
    leap: "즐거운 날과 벅찬 날이 함께 있었어요",
    balance: "잔잔하게 흘러간 구간이에요",
    wave: "기분이 날마다 달랐어요",
    endure: "가라앉은 채 하루를 넘긴 날이 많았어요",
    storm: "좋았던 날과 힘들었던 날의 낙차가 컸어요",
  },
};

/** 그 영역의 말로 바꾼 한 줄. 영역을 모르면 공통 문장을 쓴다. */
export function shapeLineFor(domain, shapeKey) {
  return DOMAIN_LINES[domain]?.[shapeKey] || SHAPES[shapeKey]?.line || "";
}

function mean(xs) {
  return xs.reduce((a, b) => a + b, 0) / xs.length;
}

function stdev(xs) {
  if (xs.length < 2) return 0;
  const m = mean(xs);
  return Math.sqrt(mean(xs.map((x) => (x - m) ** 2)));
}

export function shapeOf(values) {
  const m = mean(values);
  const sd = stdev(values);
  const wide = sd >= THRESHOLDS.sdWide;
  let key;
  if (m >= THRESHOLDS.meanHigh) key = wide ? "leap" : "cruise";
  else if (m <= THRESHOLDS.meanLow) key = wide ? "storm" : "endure";
  else key = wide ? "wave" : "balance";
  return { key, mean: +m.toFixed(3), sd: +sd.toFixed(3), ...SHAPES[key] };
}

/**
 * 별자리 하나를 분류한다.
 * @param {{stars:Array, complete:boolean, filled:number}} group  myUniverse.constellationGroups() 의 원소
 * @param {string[]} valueRanking  profile.value_ranking (가치 카드 id 순위)
 */
export function classifyConstellation(group, valueRanking) {
  const stars = group?.stars || [];
  const values = stars.map((s) => s.valence).filter((v) => v != null);
  const theme = topAxes(valueRanking, 1)[0] || "성장";

  // 진행 중 — 이번 주가 아직 안 끝났다
  if (!group?.complete) {
    const left = group?.remaining ?? 0;
    return {
      status: "growing",
      name: "아직 이름 없음",
      caption: left
        ? `별 ${group?.filled || 0}개 · ${left}일 더 지나면 이름이 붙어요`
        : `별 ${group?.filled || 0}개 · 오늘 밤 이름이 붙어요`,
      theme,
      shape: null,
    };
  }

  // 한 주는 지났지만 기록이 너무 적다 — 이름을 붙이지 않는다
  if (values.length < MIN_RECORDS_TO_NAME) {
    return {
      status: "sparse",
      name: "흐린 별자리",
      caption: `7일 중 ${values.length}일만 기록돼 모양을 부르지 않았어요`,
      theme,
      shape: null,
    };
  }

  const shape = shapeOf(values);
  return {
    status: "named",
    name: `${shape.adj}형 ${theme} 별자리`,
    // 기간을 반드시 앞에 둔다 — "당신은 ○○형" 으로 읽히면 안 된다.
    caption: `이 7일은 ${shape.line}`,
    theme,
    shape,
    records: values.length,
  };
}

/** 별자리 카드 상단 배지에 쓰는 짧은 라벨. */
export function badgeLabel(c) {
  return c.status === "named" ? `✏️ ${c.name}` : `✦ ${c.name}`;
}

/** 화면 하단 고지 — 게이미피케이션과 예측을 구분하는 문장. */
export const HONESTY_NOTE =
  "별자리는 기록한 날들의 모양에 붙인 이름이며, 성격 진단이나 미래 예측이 아닙니다.";
