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

function sampleInsight(a, b) {
  const inspect = (side, tag) => {
    const rows = [...(side.trajectory || []), ...(side.wellbeing_trajectory || [])]
      .filter((point) => number(point?.sample_n) != null)
      .sort((left, right) => Number(left.year) - Number(right.year));
    if (rows.length < 2) return null;
    const first = number(rows[0].sample_n);
    const last = number(rows.at(-1).sample_n);
    const drop = first > 0 ? Math.round((1 - last / first) * 100) : 0;
    return drop >= 20 ? { tag, first, last, drop, year: rows.at(-1).year } : null;
  };
  const items = [inspect(a, "A"), inspect(b, "B")].filter(Boolean);
  if (!items.length) return null;
  const worst = items.sort((x, y) => y.drop - x.drop)[0];
  return {
    kind: "sample",
    side: worst.tag,
    metric: `−${worst.drop}%`,
    caption: "장기 관측 표본 감소폭",
    pair: [
      { tag: "시작", text: `${worst.first.toLocaleString()}명` },
      { tag: `${worst.year}년 차`, text: `${worst.last.toLocaleString()}명` },
    ],
    body: "뒤 연차로 갈수록 추적된 사람이 줄어듭니다.",
    note: "뒤 시점으로 갈수록 결과의 불확실성이 커질 수 있습니다.",
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
      byKey.get(id)[tag] = {
        delta,
        start: number(facet.start),
        latest: number(facet.latest),
        direction: facet.direction,
      };
    });
  };
  collect(a, "A");
  collect(b, "B");
  return [...byKey.values()]
    .filter((row) => facetMagnitude(row) >= 0.05)
    .sort((left, right) => facetMagnitude(right) - facetMagnitude(left));
}

const facetMagnitude = (row) => Math.max(Math.abs(row.A?.delta ?? 0), Math.abs(row.B?.delta ?? 0));

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

      <p className="mt-2.5 text-[10.5px] leading-[1.65] text-sub">{insight.body}</p>
      {insight.note && (
        <p className="mt-2.5 border-t border-white/[.06] pt-2 text-[9px] leading-4 text-mut">{insight.note}</p>
      )}
    </article>
  );
}

const UP = "#69D1AE";
const DOWN = "#E58B94";

// 변화량은 부호가 있는 값이라 **0을 가운데 둔 축**에 그린다 — 오른쪽이 상승,
// 왼쪽이 하락. 축은 이 블록 전체가 공유하므로(scale) 항목끼리도, A와 B끼리도
// 길이를 그대로 비교할 수 있다. 숫자만 있으면 +0.1과 +0.6이 같은 무게로 읽힌다.
function ChangeBar({ side, item, scale }) {
  if (!item) {
    return (
      <div className="grid grid-cols-[0.9rem_minmax(0,1fr)_1px_minmax(0,1fr)_3.4rem] items-center gap-1.5">
        <b className="text-[9px] font-black" style={{ color: SIDE[side].color }}>{side}</b>
        <span className="col-span-4 text-[9px] text-mut">이 항목 관측 없음</span>
      </div>
    );
  }
  const up = item.delta > 0;
  const tone = up ? UP : DOWN;
  const width = scale > 0 ? Math.max(3, (Math.abs(item.delta) / scale) * 100) : 0;
  const title = Number.isFinite(item.start) && Number.isFinite(item.latest)
    ? `${item.start.toFixed(1)} → ${item.latest.toFixed(1)} (1~5점)`
    : undefined;
  return (
    <div className="grid grid-cols-[0.9rem_minmax(0,1fr)_1px_minmax(0,1fr)_3.4rem] items-center gap-1.5" title={title}>
      <b className="text-[9px] font-black" style={{ color: SIDE[side].color }}>{side}</b>
      <div className="flex h-2 items-center justify-end overflow-hidden rounded-l-full bg-white/[.05]" aria-hidden="true">
        {!up && <div className="h-full rounded-l-full transition-[width] duration-500" style={{ width: `${width}%`, background: tone }} />}
      </div>
      <div className="h-3 bg-white/25" aria-hidden="true" />
      <div className="flex h-2 items-center justify-start overflow-hidden rounded-r-full bg-white/[.05]" aria-hidden="true">
        {up && <div className="h-full rounded-r-full transition-[width] duration-500" style={{ width: `${width}%`, background: tone }} />}
      </div>
      <span className="text-right text-[10px] font-bold tabular-nums" style={{ color: tone }}>
        {up ? "+" : "−"}{Math.abs(item.delta).toFixed(1)}
      </span>
    </div>
  );
}

// 같은 항목의 A와 B를 한 블록에 위아래로. 이게 이 섹션의 존재 이유다.
function FacetPair({ row, scale }) {
  const gap = row.A && row.B ? row.A.delta - row.B.delta : null;
  return (
    <div className="rounded-xl border border-white/[.06] bg-white/[.02] px-3 py-2.5">
      <div className="mb-2 flex items-baseline justify-between gap-2">
        <span className="min-w-0 truncate text-[10.5px] font-semibold text-sub">{row.label}</span>
        {gap != null && Math.abs(gap) >= 0.05 && (
          <span className="shrink-0 text-[9px] font-bold tabular-nums" style={{ color: SIDE[gap > 0 ? "A" : "B"].color }}>
            {gap > 0 ? "A" : "B"}가 {Math.abs(gap).toFixed(1)}점 더 올랐음
          </span>
        )}
      </div>
      <div className="space-y-1.5">
        <ChangeBar side="A" item={row.A} scale={scale} />
        <ChangeBar side="B" item={row.B} scale={scale} />
      </div>
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
  const facetScale = Math.max(0, ...facets.map(facetMagnitude));
  const education = [...educationRows(a, "A"), ...educationRows(b, "B")]
    .filter((item, index, rows) => rows.findIndex((candidate) => candidate.tag === item.tag && candidate.indicator === item.indicator) === index);
  const insights = [comparisonInsight(a, b, futureYears), spreadInsight(a, b, futureYears), sampleInsight(a, b)].filter(Boolean);
  const matched = [...new Set([...(a.matched_on || []), ...(b.matched_on || [])])];
  if (!facets.length && !education.length && !insights.length && !matched.length) return null;

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
              title="만족도를 움직인 세부 항목"
              desc="각 선택을 한 유사인 집단의 만족도가 관측 기간 동안 스스로 얼마나 오르내렸는지입니다(1~5점 척도). 두 값의 격차가 아니라 각자의 변화량이며, 같은 항목끼리 위아래로 놓아 비교합니다."
            />
            <div className="mb-2 flex items-center justify-center gap-3 text-[8.5px] text-mut">
              <span>← 하락</span>
              <span className="h-2.5 w-px bg-white/25" />
              <span>상승 →</span>
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
              {facets.map((row) => <FacetPair key={row.id} row={row} scale={facetScale} />)}
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

        {matched.length > 0 && (
          <div className="border-t border-white/[.07] pt-3">
            <p className="text-[9px] text-mut">실제 유사사례 매칭에 반영된 조건</p>
            <div className="mt-1.5 flex flex-wrap gap-1">
              {matched.map((condition) => (
                <span key={condition} className="rounded-md bg-white/[.05] px-2 py-1 text-[9px] text-sub">{condition}</span>
              ))}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
