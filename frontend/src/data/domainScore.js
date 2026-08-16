// ─────────────────────────────────────────────────────────────
// 영역별 지표 — 영역마다 재는 방법이 다르다.
//
// 여태까지는 다섯 행성 모두 '그 영역을 적은 날의 기분 평균'을 점수처럼 보여줬다.
// 그건 영역 점수가 아니다. 세 가지가 어긋난다.
//
//   1) 하루 기분 하나가 여러 영역에 그대로 복사된다. 일과 관계를 같이 적은 날은
//      두 행성이 같은 값을 받는다.
//   2) 사람은 그 영역이 **힘들 때** 더 많이 쓴다. 그래서 신경 쓰는 영역일수록
//      낮게 나온다 — 실제로 나빠서가 아니라 표본이 그렇게 모여서.
//   3) 영역끼리 비교가 안 된다. 건강 3.8 > 진로 3.2 는 건강이 낫다는 뜻이 아니다.
//
// 그래서 영역마다 다르게 간다.
//
//   삶의 만족  기분 그대로. 이건 원래 기분으로 재는 게 맞는 영역이다.
//   건강      에너지 + 기분을 섞는다. 체크인이 에너지를 따로 받고 있어서,
//             몸 상태에 더 가까운 값을 만들 수 있다.
//   진로·관계·성장성
//             점수를 매기지 않는다. 일기 몇 줄로 관계나 커리어에 점수를 붙이는
//             건 근거가 없다. 대신 그 영역에서 아직 안 가본 길(기회)을 연다.
//
// 10점으로 보이는 건 삶의 만족·건강뿐이다. 입력이 5단계인데 억지로 10칸을 만들면
// 없는 정밀도를 지어내는 것이라, 환산해서 보여주되 근거를 함께 적는다.
// ─────────────────────────────────────────────────────────────

/** mood 1~5, energy 1~4 → 0~10 으로 맞춘다. */
const to10 = (v, max) => ((v - 1) / (max - 1)) * 10;

/** 웨어러블 수면 점수(0~100) → 0~10. 범위 밖 값은 버린다(오타·단위 착오). */
function sleepScoreTo10(v) {
  if (v == null || !Number.isFinite(v) || v < 0 || v > 100) return null;
  return v / 10;
}

/**
 * 잔 시간 → 0~10. 많이 잘수록 좋은 게 아니라 **7~8시간대가 가장 좋다**.
 *
 * 부족한 쪽을 더 세게 깎는다. 6시간이 9시간보다 몸에 나쁘게 작용하는 게
 * 일반적으로 알려진 바고, 늦잠은 대개 회복 과정이기도 하다.
 *   7~8h = 10 · 6h ≈ 7.6 · 5h ≈ 5.2 · 4h ≈ 2.8 · 9h ≈ 8.8 · 11h ≈ 6.4
 */
function sleepHourTo10(v) {
  if (v == null || !Number.isFinite(v) || v <= 0 || v > 24) return null;
  if (v >= 7 && v <= 8) return 10;
  const off = v < 7 ? 7 - v : v - 8;
  const perHour = v < 7 ? 2.4 : 1.2;   // 부족한 쪽이 더 가파르다
  return Math.max(0, 10 - off * perHour);
}

/**
 * 운동 시간(분) → 0~10. 처음 20~30분이 가장 크게 오르고, 그 뒤는 완만해진다.
 * 0분 0 · 20분 ≈ 5.8 · 30분 ≈ 7.1 · 60분 이상 10.
 */
function exerciseTo10(v) {
  if (v == null || !Number.isFinite(v) || v < 0) return null;
  return Math.min(10, 10 * Math.sqrt(Math.min(v, 60) / 60));
}

// 조사는 lib/josa.js 를 쓴다 — 같은 걸 두 벌 두면 한쪽만 고치게 된다.

export const DOMAIN_METRIC = {
  life: {
    kind: "score",
    label: "삶의 만족도",
    basis: "그날 고른 기분",
    note: "이 영역은 기분으로 재는 게 맞아요. 적은 날만 반영돼요.",
  },
  health: {
    kind: "score",
    label: "몸 상태",
    basis: "루미의 몸·마음 체크",
    note: "수면 점수·수면 시간·에너지·운동이 중심이고(85%), 기분은 보조로 10%만 반영해요. 수면은 7~8시간을 가장 높게 보고, 부족한 쪽을 더 크게 깎아요. 적지 않은 항목은 계산에서 빠져요.",
  },
  career: { kind: "opportunity", label: "진로", why: "일기 몇 줄로 커리어에 점수를 매길 수는 없어요. 대신 아직 안 가본 길을 찾아드려요." },
  relation: { kind: "opportunity", label: "관계", why: "관계는 좋고 나쁨을 한 숫자로 줄이면 오해가 생겨요. 대신 지금 해볼 수 있는 걸 찾아드려요." },
  // 성장성은 점수가 아니라 **분포**로 본다. 무엇을 얼마나 썼는지가 곧 쌓인 것이고,
  // 비어 있는 칸이 다음에 열어볼 방향이다. 한 숫자로 줄이면 그 정보가 사라진다.
  growth: { kind: "mix", label: "성장성", why: "역량은 점수가 아니라 무엇을 쌓았는지예요. 쓴 시간의 분포로 보여드려요." },
};

export function metricOf(planetKey) {
  return DOMAIN_METRIC[planetKey] || { kind: "opportunity", label: planetKey, why: "" };
}

export function isScored(planetKey) {
  return metricOf(planetKey).kind === "score";
}

/**
 * 그 영역의 10점 지표. 점수를 쓰지 않는 영역이면 null.
 *
 * @param stars 그 영역으로 분류된 기록들
 * @returns {{value:number, n:number, basis:string, label:string}|null}
 */
export function domainScore(planetKey, stars = []) {
  const m = metricOf(planetKey);
  if (m.kind !== "score" || !stars.length) return null;

  const vals = [];
  for (const c of stars) {
    if (planetKey === "life") {
      if (c.mood != null) vals.push(to10(c.mood, 5));
      continue;
    }
    // 건강 — 루미의 몸·마음 체크(수면 점수·시간·질)와 에너지가 중심.
    // 기분은 곁들이는 정도(10%)만 넣는다.
    //
    // 기분을 크게 넣으면 '기분 좋은 날 = 몸이 좋은 날'이 돼버린다. 4시간 자고도
    // 신나는 날이 있고, 푹 자고도 우울한 날이 있다.
    //
    // 없는 항목은 0으로 치지 않는다 — 안 적었다고 몸이 나쁜 게 아니다.
    // 있는 항목끼리 가중치를 다시 정규화한다.
    const h = c.health || {};

    // 몸에 대한 값이 하나도 없으면 이 날은 건너뛴다.
    //
    // 없는 항목을 빼고 정규화하다 보면, 기분만 적은 날은 기분이 100% 가중치를
    // 가져가 '기분 5점 = 몸 10점'이 된다. 그건 이 지표가 피하려던 바로 그 착각이다.
    const body = [h.sleepScore, h.sleepHours, h.exerciseMin, c.energy];
    if (!body.some((v) => v != null)) continue;

    const parts = [
      // 주요 네 가지
      [sleepScoreTo10(h.sleepScore), 0.25],  // 수면 점수(0~100)
      [sleepHourTo10(h.sleepHours), 0.25],   // 잔 시간 — 7~8시간이 가장 높다
      [c.energy != null ? to10(c.energy, 4) : null, 0.2],   // 에너지
      [exerciseTo10(h.exerciseMin), 0.15],   // 운동 시간
      // 보조
      [c.mood != null ? to10(c.mood, 5) : null, 0.1],       // 기분
      [h.sleepQual != null ? to10(h.sleepQual, 5) : null, 0.05],
      [h.stress != null ? 10 - to10(h.stress, 5) : null, 0.05], // 스트레스는 낮을수록 좋다
    ].filter(([v]) => v != null);
    if (!parts.length) continue;
    const wsum = parts.reduce((a, [, w]) => a + w, 0);
    vals.push(parts.reduce((a, [v, w]) => a + v * w, 0) / wsum);
  }
  if (!vals.length) return null;

  const value = vals.reduce((a, b) => a + b, 0) / vals.length;
  return { value: +value.toFixed(1), n: vals.length, basis: m.basis, label: m.label, note: m.note };
}

/**
 * 표본이 적으면 숫자를 앞세우면 안 된다 — 며칠 치로 영역을 평가한 것처럼 읽힌다.
 * 몇 개부터 보여줄지 한 곳에서 정한다.
 */
export const MIN_FOR_SCORE = 5;

// ── 점수를 안 내는 영역: 얼마나 자주 떠올랐나 ────────────────────
//
// 진로·관계·성장성에 '기분 흐름' 그래프를 그리면, 점수는 안 매긴다고 해놓고
// 그래프로는 매기는 셈이 된다. 그 기분은 그날 하루 전체의 기분이지 그 영역의
// 상태가 아니다(같은 날 여러 영역에 똑같이 복사된다).
//
// 대신 셀 수 있는 것을 센다 — **주마다 이 영역 이야기가 몇 번 나왔는지.**
// 이건 좋고 나쁨이 아니라 '요즘 이게 얼마나 마음에 걸리는지'다. 왜곡이 없다:
// 많이 적혔으면 실제로 많이 적힌 것이다.
export function domainMentions(entries = [], weeks = 8) {
  const today = new Date();
  const bins = [];
  for (let i = weeks - 1; i >= 0; i -= 1) {
    const end = new Date(today);
    end.setDate(end.getDate() - i * 7);
    const start = new Date(end);
    start.setDate(start.getDate() - 6);
    bins.push({
      from: start.toISOString().slice(0, 10),
      to: end.toISOString().slice(0, 10),
      label: `${start.getMonth() + 1}/${start.getDate()}`,
      count: 0,
    });
  }
  for (const c of entries) {
    if (!c?.date) continue;
    const b = bins.find((x) => c.date >= x.from && c.date <= x.to);
    if (b) b.count += 1;
  }
  const recent = bins.slice(-4).reduce((a, b) => a + b.count, 0);
  const before = bins.slice(0, -4).reduce((a, b) => a + b.count, 0);
  return {
    bins,
    weeks,
    total: bins.reduce((a, b) => a + b.count, 0),
    max: Math.max(...bins.map((b) => b.count), 1),
    // 최근 4주가 그 앞 4주보다 늘었나 — '요즘 부쩍'을 말할 근거.
    rising: before > 0 ? recent > before : null,
    recent,
    before,
  };
}

// ── 성장성: 역량 분포 ────────────────────────────────────────
// 체크인의 '오늘 주로 쓴 역량'이 그대로 쌓인다. 이걸 세면 무엇에 시간을 썼는지가
// 나온다 — 두터운 칸이 쌓은 것, 비어 있는 칸이 아직 안 가본 쪽이다.
//
// '휴식'은 역량이 아니라 쉰 날이라 따로 뺀다. 섞으면 "휴식 95일"이 제일 큰 막대가
// 되어, 쉰 걸 성장으로 읽게 만든다.
export const SKILL_ORDER = ["기술", "소통", "기획", "리더십", "개인공부"];
const REST = "휴식";

/**
 * @returns {{items:[{key,count,pct}], total:number, rest:number,
 *            top:string|null, gap:string|null}}
 */
export function skillMix(checkins = [], windowDays = 56) {
  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - windowDays);
  const from = cutoff.toISOString().slice(0, 10);

  const count = Object.fromEntries(SKILL_ORDER.map((k) => [k, 0]));
  let rest = 0;
  for (const c of checkins) {
    if (!c || c.empty || !c.skill || (c.date && c.date < from)) continue;
    if (c.skill === REST) { rest += 1; continue; }
    if (count[c.skill] != null) count[c.skill] += 1;
  }

  const total = SKILL_ORDER.reduce((a, k) => a + count[k], 0);
  const items = SKILL_ORDER.map((k) => ({
    key: k,
    count: count[k],
    pct: total ? Math.round((count[k] / total) * 100) : 0,
  }));

  const sorted = [...items].sort((a, b) => b.count - a.count);
  return {
    items,
    total,
    rest,
    windowDays,
    top: total ? sorted[0].key : null,
    // 가장 비어 있는 칸 — 다음에 열어볼 방향. 0인 칸이 있으면 그게 우선이다.
    gap: total ? sorted[sorted.length - 1].key : null,
  };
}
