import { labelOf } from "../../data/prediction.js";

const SIDE = {
  A: { color: "#B79BF5", bg: "rgba(139,108,207,.10)" },
  B: { color: "#F5C86B", bg: "rgba(245,200,107,.09)" },
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
      title: `${first.year}년 차부터 ${item.label} 격차가 관측됩니다`,
      body: `${target.year}년 시점에는 ${winner}(${labelOf(winner === "A" ? a.choice : b.choice)})가 약 ${Math.abs(target.delta).toFixed(item.type === "income" ? 0 : 1)}${item.unit} 높습니다.`,
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
    title: `${wider}의 소득 결과 범위가 더 넓습니다`,
    body: `${Math.min(left.year, right.year)}년 관측에서 중간 50% 범위는 A ${Math.round(left.width)}만원, B ${Math.round(right.width)}만원입니다. ${narrow}가 상대적으로 좁은 분포를 보입니다.`,
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
    title: `장기 관측 표본이 ${worst.drop}% 줄어듭니다`,
    body: `${worst.tag}는 초기 ${worst.first.toLocaleString()}명에서 ${worst.year}년 차 ${worst.last.toLocaleString()}명으로 감소합니다.`,
    note: "뒤 시점으로 갈수록 결과의 불확실성이 커질 수 있습니다.",
  };
}

function facetRows(side, tag) {
  return (Array.isArray(side.satisfaction_facets) ? side.satisfaction_facets : [])
    .filter((facet) => number(facet.delta) != null && Math.abs(number(facet.delta)) >= 0.05)
    .sort((left, right) => Math.abs(number(right.delta)) - Math.abs(number(left.delta)))
    .slice(0, 3)
    .map((facet) => ({ tag, label: facet.label, delta: number(facet.delta), direction: facet.direction }));
}

function educationRows(side, tag) {
  const context = side.choice_context?.length
    ? side.choice_context
    : (side.life_indicators || []).filter((item) => ["진학·취업", "진학/취업"].includes(item.dimension));
  return context.map((item) => ({ tag, ...item }));
}

function InsightCard({ insight }) {
  return (
    <article className="rounded-2xl border border-white/[.07] bg-white/[.025] p-3.5">
      <h3 className="text-[12px] font-semibold leading-5 text-ink">{insight.title}</h3>
      <p className="mt-1 text-[10.5px] leading-[1.65] text-sub">{insight.body}</p>
      {insight.note && <p className="mt-2 text-[9px] leading-4 text-mut">{insight.note}</p>}
    </article>
  );
}

export default function DetailedInsights({ a, b, futureYears = 3 }) {
  const facets = [...facetRows(a, "A"), ...facetRows(b, "B")];
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
        {insights.length > 0 && <div className="grid gap-2.5 sm:grid-cols-2">{insights.map((insight) => <InsightCard key={insight.title} insight={insight} />)}</div>}

        {facets.length > 0 && (
          <div>
            <h3 className="text-[12px] font-semibold text-ink">만족도를 움직인 세부 항목</h3>
            <p className="mt-0.5 text-[9px] text-mut">종합점수 뒤에 있는 직무·성장·소득·안정·미래 만족의 관측 변화입니다.</p>
            <div className="mt-2 grid gap-2 sm:grid-cols-2">
              {facets.map((row) => (
                <div key={`${row.tag}-${row.label}`} className="flex items-center justify-between rounded-xl border border-white/[.06] px-3 py-2.5" style={{ background: SIDE[row.tag].bg }}>
                  <span className="text-[10.5px] text-sub"><b style={{ color: SIDE[row.tag].color }}>{row.tag}</b> · {row.label}</span>
                  <span className="text-[11px] font-bold tabular-nums" style={{ color: row.delta > 0 ? "#69D1AE" : "#E58B94" }}>{row.delta > 0 ? "+" : ""}{row.delta.toFixed(1)}점</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {education.length > 0 && (
          <div className="border-t border-white/[.07] pt-4">
            <h3 className="text-[12px] font-semibold text-ink">진학 이후 참고 경로</h3>
            <p className="mt-0.5 text-[9px] text-mut">해당 계열 졸업자 집단 통계이며 개인 취업 확률이 아닙니다.</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {education.map((item) => <span key={`${item.tag}-${item.indicator}`} className="rounded-xl border border-white/[.07] bg-white/[.03] px-3 py-2 text-[10.5px] text-sub"><b style={{ color: SIDE[item.tag].color }}>{item.tag}</b> · {item.indicator} <strong className="ml-1 text-ink">{number(item.value)?.toLocaleString()}{item.unit}</strong></span>)}
            </div>
          </div>
        )}

        {matched.length > 0 && (
          <div className="border-t border-white/[.07] pt-3 text-[9px] leading-4 text-mut">
            실제 유사사례 매칭에 반영된 조건 · <span className="text-sub">{matched.join(" · ")}</span>
          </div>
        )}
      </div>
    </section>
  );
}
