import { ArrowLeftRight, Maximize2, Users } from "lucide-react";
import { labelOf } from "../../data/prediction.js";

const SIDE = {
  A: { color: "#B79BF5", bg: "rgba(139,108,207,.10)" },
  B: { color: "#F5C86B", bg: "rgba(245,200,107,.09)" },
};

// 인사이트 종류별 아이콘·이름. 카드 세 장이 전부 '제목+본문+각주'로 똑같이
// 생겨서 무엇에 대한 이야기인지 다 읽어야 알 수 있었다. 아이콘과 이름표를
// 앞에 세워 훑기만 해도 종류가 구분되게 한다.
const KIND = {
  gap: { icon: ArrowLeftRight, label: "격차" },
  spread: { icon: Maximize2, label: "결과 범위" },
  sample: { icon: Users, label: "표본" },
};

const number = (value) => {
  if (value === null || value === undefined || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
};

const closest = (rows, year) => {
  const valid = (rows || []).filter((point) => Number.isFinite(Number(point?.year)));
  return valid.sort((left, right) => Math.abs(Number(left.year) - year) - Math.abs(Number(right.year) - year))[0] || null;
};

const medianOf = (point, type) => number(type === "income" ? point?.income_p50 : point?.satis_p50);

function comparisonInsight(a, b, futureYears) {
  const candidates = [
    { type: "income", label: "월소득", unit: "만원", rowsA: a.trajectory, rowsB: b.trajectory },
    { type: "wellbeing", label: "삶의 만족", unit: "점", rowsA: a.wellbeing_trajectory, rowsB: b.wellbeing_trajectory },
  ];
  for (const item of candidates) {
    const yearsA = new Set((item.rowsA || []).map((point) => Number(point.year)));
    const common = (item.rowsB || []).map((point) => Number(point.year)).filter((year) => year > 0 && yearsA.has(year)).sort((x, y) => x - y);
    const differences = common.map((year) => {
      const left = (item.rowsA || []).find((point) => Number(point.year) === year);
      const right = (item.rowsB || []).find((point) => Number(point.year) === year);
      const av = medianOf(left, item.type);
      const bv = medianOf(right, item.type);
      return av == null || bv == null ? null : { year, av, bv, delta: bv - av };
    }).filter(Boolean).filter((row) => Math.abs(row.delta) >= (item.type === "income" ? 1 : 0.05));
    if (!differences.length) continue;
    const first = differences[0];
    const target = differences.reduce((best, row) => Math.abs(row.year - futureYears) < Math.abs(best.year - futureYears) ? row : best, differences[0]);
    const winner = target.delta > 0 ? "B" : "A";
    return {
      kind: "gap",
      side: winner,
      metric: `${Math.abs(target.delta).toFixed(item.type === "income" ? 0 : 1)}${item.unit}`,
      caption: `${target.year}년 시점 ${item.label} 격차`,
      body: `${first.year}년 차부터 벌어지기 시작하며, ${target.year}년 시점에는 ${winner}(${labelOf(winner === "A" ? a.choice : b.choice)})가 더 높습니다.`,
      note: "유사집단 관측 격차이며 개인의 확정 미래나 인과효과를 뜻하지 않습니다.",
    };
  }
  return null;
}

function spreadInsight(a, b, futureYears) {
  const make = (side) => {
    const point = closest(side.trajectory, futureYears);
    const low = number(point?.income_p25);
    const high = number(point?.income_p75);
    return low == null || high == null ? null : { width: high - low, year: point.year };
  };
  const left = make(a);
  const right = make(b);
  if (!left || !right || Math.abs(left.width - right.width) < 1) return null;
  const wider = left.width > right.width ? "A" : "B";
  const narrow = wider === "A" ? "B" : "A";
  return {
    kind: "spread",
    side: wider,
    metric: `${Math.round(Math.abs(left.width - right.width))}만원`,
    caption: `중간 50% 범위 차이 · ${Math.min(left.year, right.year)}년 관측`,
    // 두 값을 나란히 보여줘야 '넓다/좁다'가 감이 온다.
    pair: [
      { tag: "A", text: `${Math.round(left.width)}만원` },
      { tag: "B", text: `${Math.round(right.width)}만원` },
    ],
    body: `${wider}의 결과 범위가 더 넓고, ${narrow}가 상대적으로 좁은 분포를 보입니다.`,
    note: "범위가 넓다는 것은 성공 가능성이 높다는 뜻이 아니라 관측 편차가 크다는 뜻입니다.",
  };
}

// 소득(KLIPS)과 만족도(YP)는 **서로 다른 패널**이라 표본 수가 따로 논다.
// 예전엔 둘을 한 배열에 합쳐 연차로 정렬했는데, 그러면 300(소득0년) → 282(만족0년)
// → 226(소득1년) → 162(만족1년) 처럼 두 계열이 섞여 감소폭이 실제와 달라졌다.
// 계열별로 따로 재고 가장 심한 하나를 고른다.
const SAMPLE_SERIES = [
  { key: "trajectory", label: "소득 궤적", source: "KLIPS 종단" },
  { key: "wellbeing_trajectory", label: "삶의 만족", source: "YP 청년패널" },
];

function sampleInsight(a, b) {
  const inspect = (side, tag) => SAMPLE_SERIES.map(({ key, label, source }) => {
    const rows = (side?.[key] || [])
      .filter((point) => number(point?.sample_n) != null)
      .sort((left, right) => Number(left.year) - Number(right.year));
    if (rows.length < 2) return null;
    const series = rows.map((point) => ({ year: Number(point.year), n: number(point.sample_n) }));
    const first = series[0].n;
    const last = series.at(-1).n;
    const drop = first > 0 ? Math.round((1 - last / first) * 100) : 0;
    return drop >= 20 ? { tag, label, source, series, first, last, drop, year: series.at(-1).year } : null;
  }).filter(Boolean);

  const items = [...inspect(a, "A"), ...inspect(b, "B")];
  if (!items.length) return null;
  const worst = items.sort((x, y) => y.drop - x.drop)[0];
  // 100명당 몇 명이 남았는지 — 퍼센트보다 사람 수가 직관적이다.
  const per100 = Math.max(1, Math.round((worst.last / worst.first) * 100));
  return {
    kind: "sample",
    side: worst.tag,
    metric: `−${worst.drop}%`,
    caption: `${worst.label} · 장기 관측 표본 감소폭`,
    // 연차별 남은 인원. 카드가 이걸 막대로 그려 "얼마나 큰 감소인지"를 보여준다.
    series: worst.series,
    body: `시작 ${worst.first.toLocaleString()}명 중 ${worst.year}년 차까지 남은 사람은 `
      + `${worst.last.toLocaleString()}명입니다 — 100명이면 ${per100}명. `
      + `그 시점 수치는 이 ${worst.last.toLocaleString()}명의 중앙값입니다.`,
  };
}

// facet.delta 는 **그 선택을 한 유사인 집단이 관측 기간(0→마지막 연차) 동안
// 스스로 얼마나 오르내렸는가**다. A와 B의 격차가 아니다.
//
// 예전엔 A의 상위 3개와 B의 상위 3개를 각각 뽑아 그냥 이어 붙였다. 그러면 같은
// 항목(자기발전 만족)의 A가 1번 칸, B가 4번 칸에 떨어져서 A/B 비교가 물리적으로
// 불가능했다 — 카드 제목은 비교인데 화면은 두 개의 독립된 순위표였던 셈이다.
// 이제 항목 기준으로 짝지어 한 블록에 A·B를 위아래로 놓는다.
function facetPairs(a, b) {
  const byKey = new Map();
  const collect = (side, tag) => {
    (Array.isArray(side.satisfaction_facets) ? side.satisfaction_facets : []).forEach((facet) => {
      const delta = number(facet.delta);
      if (delta == null) return;
      const id = facet.key || facet.label;
      if (!byKey.has(id)) byKey.set(id, { id, label: facet.label, A: null, B: null });
      const points = Array.isArray(facet.points) ? facet.points : [];
      byKey.get(id)[tag] = {
        delta,
        start: number(facet.start),
        latest: number(facet.latest),
        direction: facet.direction,
        // 변화량을 믿어도 되는지 판단할 재료. 마지막 시점의 추적 인원이다.
        lastSample: points.length ? number(points.at(-1)?.sample_n) : null,
      };
    });
  };
  collect(a, "A");
  collect(b, "B");
  return [...byKey.values()]
    .filter((row) => row.A && row.B && facetLevelGap(row) != null)
    // **출발점 격차** 순으로 정렬한다. 예전엔 변화량 순이었는데, 실제 데이터에서
    // 변화량은 전부 ±0.08(5점 척도의 1.5%) 안쪽이고 그걸 만든 표본이 18~35명이라
    // 사실상 노이즈다. 그걸 크기순으로 줄세우면 없는 신호에 순위를 매기게 된다.
    // 같은 데이터에서 훨씬 큰 신호는 두 집단의 출발 수준 차이(0.16~0.27)다.
    .sort((left, right) => Math.abs(facetLevelGap(right)) - Math.abs(facetLevelGap(left)));
}

// A와 B가 관측 시작 시점에 얼마나 달랐는가. 양수면 A가 높다.
const facetLevelGap = (row) => (
  Number.isFinite(row.A?.start) && Number.isFinite(row.B?.start)
    ? row.A.start - row.B.start : null
);

// 변화량을 해석해도 되는가. 5점 척도에서 0.1 미만은 눈금 해상도 아래이고,
// 마지막 표본이 30명 미만이면 한두 사람 값에 흔들린다. 둘 중 하나라도 걸리면
// 숫자는 보여주되 '판단하기 어렵다'고 밝힌다 — 조용히 빼면 없는 것처럼 보이고,
// 그냥 두면 노이즈가 결론처럼 읽힌다.
const MIN_READABLE_DELTA = 0.1;
const MIN_READABLE_SAMPLE = 30;
const deltaIsReadable = (item) => (
  item && Math.abs(item.delta) >= MIN_READABLE_DELTA
  && (item.lastSample == null || item.lastSample >= MIN_READABLE_SAMPLE)
);

function educationRows(side, tag) {
  const context = side.choice_context?.length
    ? side.choice_context
    : (side.life_indicators || []).filter((item) => ["진학·취업", "진학/취업"].includes(item.dimension));
  return context.map((item) => ({ tag, ...item }));
}

// 숫자를 먼저 크게 보여주고 문장은 그 뒤를 받친다. 예전엔 "3년 시점에는
// B가 약 20만원 높습니다" 처럼 핵심 수치가 10.5px 문장 한가운데 묻혀 있어서
// 카드 세 장을 전부 읽어야 뭐가 중요한지 알 수 있었다.
// 왼쪽 세로 띠는 그 인사이트가 가리키는 쪽(A/B)의 색이다.
function InsightCard({ insight }) {
  const meta = KIND[insight.kind] || KIND.gap;
  const Icon = meta.icon;
  const side = SIDE[insight.side];
  return (
    <article className="relative overflow-hidden rounded-2xl border border-white/[.07] bg-white/[.025] p-3.5 pl-4">
      {side && <span className="absolute inset-y-0 left-0 w-[3px]" style={{ background: side.color }} aria-hidden="true" />}

      <div className="flex items-center justify-between gap-2">
        <span className="flex items-center gap-1.5 text-[9.5px] font-bold tracking-[.08em] text-mut">
          <span className="flex h-5 w-5 items-center justify-center rounded-md bg-white/[.06] text-violet-300">
            <Icon size={11} strokeWidth={2.2} />
          </span>
          {meta.label}
        </span>
        {insight.side && (
          <span
            className="rounded-full px-2 py-0.5 text-[9px] font-black"
            style={{ color: side.color, background: side.bg }}
          >
            {insight.side}
          </span>
        )}
      </div>

      <strong className="mt-2 block text-[24px] font-bold leading-none tracking-[-.02em] tabular-nums text-ink">
        {insight.metric}
      </strong>
      <p className="mt-1.5 text-[9.5px] leading-4 text-mut">{insight.caption}</p>

      {insight.pair && (
        <div className="mt-2.5 flex items-center gap-1.5">
          {insight.pair.map((item) => (
            <span key={item.tag} className="flex min-w-0 flex-1 items-baseline justify-between gap-1 rounded-lg bg-white/[.035] px-2 py-1.5">
              <span className="truncate text-[8.5px] text-mut">{item.tag}</span>
              <b className="shrink-0 text-[10px] tabular-nums text-sub">{item.text}</b>
            </span>
          ))}
        </div>
      )}

      {insight.series && <SampleDecay series={insight.series} />}

      <p className="mt-2.5 text-[10.5px] leading-[1.65] text-sub">{insight.body}</p>
      {insight.note && (
        <p className="mt-2.5 border-t border-white/[.06] pt-2 text-[9px] leading-4 text-mut">{insight.note}</p>
      )}
    </article>
  );
}

// 연차별로 몇 명이 남았는지 — 퍼센트 하나로는 '−94%'가 얼마나 큰 건지 감이 안 온다.
// 막대를 나란히 두면 300에서 18로 무너지는 모양이 그대로 보인다.
//
// 첫 연차를 100%로 두는 0 기준 막대다. 축을 자르거나 각 막대를 자기 최댓값으로
// 정규화하면(다른 카드에서 그랬다) 감소가 완만해 보여 경고의 뜻이 사라진다.
function SampleDecay({ series }) {
  const max = Math.max(...series.map((point) => point.n), 1);
  return (
    <figure className="mt-2.5 rounded-lg bg-white/[.03] px-2.5 pb-1.5 pt-2">
      <figcaption className="sr-only">연차별 추적 인원</figcaption>
      <div className="flex items-end gap-1" style={{ height: 40 }}>
        {series.map((point, index) => {
          const last = index === series.length - 1;
          return (
            <div key={point.year} className="flex min-w-0 flex-1 flex-col items-center justify-end gap-1">
              <span className={`text-[8px] tabular-nums ${last ? "font-bold text-[#F0846B]" : "text-mut"}`}>
                {point.n.toLocaleString()}
              </span>
              <div
                className="w-full rounded-sm"
                style={{
                  // 1px 최소 높이 — 18명처럼 작은 값이 아예 사라지면 '없음'으로 읽힌다.
                  height: `${Math.max(1, (point.n / max) * 24)}px`,
                  background: last ? "#F0846B" : "rgba(183,155,245,.55)",
                }}
              />
            </div>
          );
        })}
      </div>
      <div className="mt-1 flex gap-1 border-t border-white/[.06] pt-1">
        {series.map((point) => (
          <span key={point.year} className="min-w-0 flex-1 text-center text-[8px] text-mut">{point.year}년</span>
        ))}
      </div>
    </figure>
  );
}

/**
 * 항목 하나 = [이름] [출발점 격차 배지] [A·B를 같은 축에 찍은 점] [변화량 각주].
 *
 * 축은 모든 항목이 공유한다(domain). 관측값이 3.4~4.1 언저리에 몰려 있어 1~5점
 * 전체를 그리면 다섯 항목이 전부 같은 자리에 겹친다 — 그래서 실제 값 범위로
 * 좁히고 양 끝 눈금을 항상 적는다. 길이가 아니라 **위치**를 읽는 그림이라
 * 0에서 시작하지 않아도 값을 부풀리지 않는다.
 */
function FacetPair({ row, domain }) {
  const gap = facetLevelGap(row);
  const lead = gap > 0 ? "A" : "B";
  const at = (value) => {
    if (!Number.isFinite(value) || !domain || domain.max === domain.min) return 50;
    return ((value - domain.min) / (domain.max - domain.min)) * 100;
  };
  const meaningful = Math.abs(gap) >= 0.05;
  return (
    <div className="rounded-xl border border-white/[.06] bg-white/[.02] px-3 py-2.5">
      <div className="mb-2 flex items-baseline justify-between gap-2">
        <span className="min-w-0 truncate text-[10.5px] font-semibold text-sub">{row.label}</span>
        {meaningful && (
          <span className="shrink-0 text-[9px] font-bold tabular-nums" style={{ color: SIDE[lead].color }}>
            {lead}가 {Math.abs(gap).toFixed(2)}점 높게 출발
          </span>
        )}
      </div>

      {/* 두 점과 그 사이를 잇는 선 — 선의 길이가 곧 두 집단의 차이다. */}
      <div className="relative h-5">
        <div className="absolute inset-x-0 top-1/2 h-px -translate-y-1/2 bg-white/[.10]" />
        <div
          className="absolute top-1/2 h-[3px] -translate-y-1/2 rounded-full bg-white/25"
          style={{ left: `${Math.min(at(row.A.start), at(row.B.start))}%`,
                   width: `${Math.abs(at(row.A.start) - at(row.B.start))}%` }}
        />
        {["B", "A"].map((side) => (
          <span
            key={side}
            className="absolute top-1/2 h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full ring-2 ring-[#0B1424]"
            style={{ left: `${at(row[side].start)}%`, background: SIDE[side].color }}
            aria-label={`${side} ${row[side].start}`}
          />
        ))}
      </div>
      <div className="flex justify-between text-[8px] tabular-nums text-mut">
        <span>{domain.min.toFixed(1)}</span>
        <span className="font-semibold" style={{ color: SIDE.A.color }}>A {row.A.start}</span>
        <span className="font-semibold" style={{ color: SIDE.B.color }}>B {row.B.start}</span>
        <span>{domain.max.toFixed(1)}</span>
      </div>

      {/* 변화량은 부차적으로 내린다. 읽을 수 없는 값은 그렇게 밝힌다. */}
      <p className="mt-1.5 border-t border-white/[.06] pt-1.5 text-[8.5px] leading-4 text-mut">
        관측 기간 변화 {["A", "B"].map((side, index) => (
          <span key={side}>
            {index > 0 && " · "}
            <b style={{ color: SIDE[side].color }}>{side}</b>{" "}
            <span className={deltaIsReadable(row[side]) ? "text-sub" : ""}>
              {row[side].delta > 0 ? "+" : ""}{row[side].delta.toFixed(2)}
            </span>
          </span>
        ))}
        {!deltaIsReadable(row.A) && !deltaIsReadable(row.B) && " — 표본이 얇고 변화폭이 작아 방향을 판단하기 어렵습니다"}
      </p>
    </div>
  );
}

function SectionHead({ title, desc }) {
  return (
    <div className="mb-2">
      <h3 className="text-[12px] font-semibold text-ink">{title}</h3>
      {desc && <p className="mt-0.5 text-[9px] leading-4 text-mut">{desc}</p>}
    </div>
  );
}

export default function DetailedInsights({ a, b, futureYears = 3 }) {
  const facets = facetPairs(a, b);
  // 항목이 공유하는 축. 실제 관측 범위에 약간의 여백만 둔다 — 1~5 전체를 쓰면
  // 값이 전부 3.4~4.1 에 몰려 다섯 항목이 같은 자리에 겹친다.
  const facetDomain = (() => {
    const values = facets.flatMap((row) => [row.A?.start, row.B?.start]).filter(Number.isFinite);
    if (!values.length) return null;
    const min = Math.min(...values);
    const max = Math.max(...values);
    const pad = Math.max(0.05, (max - min) * 0.15);
    return { min: min - pad, max: max + pad };
  })();
  // 다섯 항목이 모두 한쪽으로 기울면 그건 항목별 특징이 아니라 집단 자체의
  // 성격이다. 한 줄로 짚어주지 않으면 사용자가 카드 다섯 개를 각각 읽고 끝난다.
  const leanSide = (() => {
    const gaps = facets.map(facetLevelGap).filter((gap) => Math.abs(gap) >= 0.05);
    if (gaps.length < 3) return null;
    if (gaps.every((gap) => gap > 0)) return "A";
    if (gaps.every((gap) => gap < 0)) return "B";
    return null;
  })();
  const education = [...educationRows(a, "A"), ...educationRows(b, "B")]
    .filter((item, index, rows) => rows.findIndex((candidate) => candidate.tag === item.tag && candidate.indicator === item.indicator) === index);
  const insights = [comparisonInsight(a, b, futureYears), spreadInsight(a, b, futureYears), sampleInsight(a, b)].filter(Boolean);
  if (!facets.length && !education.length && !insights.length) return null;

  return (
    <section className="mb-5 overflow-hidden rounded-[22px] border border-white/10 bg-[#0B1424]/90" aria-labelledby="detailed-insights-title">
      <div className="border-b border-white/[.07] px-4 py-3.5">
        <p className="text-[9px] font-bold tracking-[.16em] text-violet-300">DETAILED INSIGHTS</p>
        <h2 id="detailed-insights-title" className="mt-1 text-[15px] font-bold text-ink">결과에서 더 읽을 수 있는 것</h2>
        <p className="mt-1 text-[10px] leading-4 text-mut">새 점수를 만들지 않고, 연결된 관측값의 변화·범위·표본을 해석합니다.</p>
      </div>

      <div className="space-y-4 p-4">
        {insights.length > 0 && (
          <div className="grid gap-2.5 sm:grid-cols-2 xl:grid-cols-3">
            {insights.map((insight) => <InsightCard key={insight.kind} insight={insight} />)}
          </div>
        )}

        {facets.length > 0 && (
          <div>
            <SectionHead
              title="만족도 세부 항목 · 두 집단의 출발점"
              desc="각 선택을 한 유사인 집단이 관측 시작 시점에 어느 수준이었는지입니다(1~5점 척도). 선택의 효과가 아니라 '어떤 사람들이 그 선택을 했는가'를 보여줍니다."
            />
            {leanSide && (
              <p className="mb-2 rounded-lg bg-white/[.03] px-3 py-2 text-[9.5px] leading-4 text-sub">
                <b style={{ color: SIDE[leanSide].color }}>{leanSide}</b> 집단이 <b className="font-semibold">모든 항목에서</b> 높게 출발했습니다.
                항목별 차이라기보다 두 집단의 성격 차이로, <b className="font-semibold">선택이 만든 결과가 아니라 선택 이전의 상태</b>입니다
                — 지금 만족도가 낮은 쪽이 그 선택을 택하는 경향으로 읽는 편이 안전합니다.
              </p>
            )}
            <div className="grid gap-2 sm:grid-cols-2">
              {facets.map((row) => <FacetPair key={row.id} row={row} domain={facetDomain} />)}
            </div>
          </div>
        )}

        {education.length > 0 && (
          <div className="border-t border-white/[.07] pt-4">
            <SectionHead title="진학 이후 참고 경로" desc="해당 계열 졸업자 집단 통계이며 개인 취업 확률이 아닙니다." />
            {/* 예전엔 값까지 통째로 들어간 알약이 줄바꿈되며 흘러서, 지표 이름과
                숫자가 매번 다른 자리에 놓여 세로로 훑을 수가 없었다. */}
            <ul className="grid gap-1.5 sm:grid-cols-2">
              {education.map((item) => (
                <li key={`${item.tag}-${item.indicator}`} className="flex items-baseline justify-between gap-2 rounded-lg bg-white/[.025] px-2.5 py-2">
                  <span className="min-w-0">
                    <span className="block truncate text-[10px] text-sub">
                      <b style={{ color: SIDE[item.tag].color }}>{item.tag}</b> · {item.indicator}
                    </span>
                    {item.source && <span className="block truncate text-[8px] text-mut">{item.source}</span>}
                  </span>
                  <strong className="shrink-0 text-[12px] tabular-nums text-ink">
                    {number(item.value)?.toLocaleString()}{item.unit}
                  </strong>
                </li>
              ))}
            </ul>
          </div>
        )}

      </div>
    </section>
  );
}
