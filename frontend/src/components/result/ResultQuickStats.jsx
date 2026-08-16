import { labelOf } from "../../data/prediction.js";

const COLORS = { A: "#B79BF5", B: "#F5C86B" };

function closestPoint(rows, targetYear) {
  if (!Array.isArray(rows) || !rows.length) return null;
  return [...rows]
    .filter((point) => Number.isFinite(Number(point?.year)))
    .sort((left, right) => Math.abs(Number(left.year) - targetYear) - Math.abs(Number(right.year) - targetYear))[0] || null;
}

function metricValue(side, kind, futureYears) {
  if (kind === "income") {
    const point = closestPoint(side.trajectory, futureYears);
    if (point?.income_p50 == null) return null;
    const value = Number(point?.income_p50);
    return Number.isFinite(value) ? { value, unit: "만원", year: Number(point.year) } : null;
  }
  if (kind === "wellbeing") {
    const point = closestPoint(side.wellbeing_trajectory, futureYears);
    if (point?.satis_p50 == null) return null;
    const value = Number(point?.satis_p50);
    return Number.isFinite(value) ? { value, unit: "점", year: Number(point.year) } : null;
  }
  if (kind === "effect") {
    if (side.causal_effect == null) return null;
    const value = Number(side.causal_effect);
    return Number.isFinite(value) ? { value, unit: "%", signed: true } : null;
  }
  if (kind === "tenure") {
    if (side.survival_months == null) return null;
    const value = Number(side.survival_months);
    return Number.isFinite(value) ? { value, unit: "개월" } : null;
  }
  if (kind.startsWith("score:")) {
    const key = kind.slice(6);
    const raw = side.indicator_scores?.[key];
    if (raw == null) return null;
    const value = Number(raw) * 100;
    return Number.isFinite(value) ? { value, unit: "점", percentile: true } : null;
  }
  return null;
}

function formatMetric(metric) {
  if (!metric) return "—";
  const rounded = Math.abs(metric.value) >= 100
    ? Math.round(metric.value)
    : Math.round(metric.value * 10) / 10;
  const sign = metric.signed && rounded > 0 ? "+" : "";
  return `${sign}${rounded.toLocaleString()}${metric.unit}`;
}

function comparisonMeta(left, right) {
  if (!left || !right || left.unit !== right.unit) return null;
  const delta = right.value - left.value;
  const precision = Math.max(Math.abs(delta), Math.abs(left.value), Math.abs(right.value)) >= 100 ? 0 : 1;
  const formatted = Math.abs(delta).toLocaleString(undefined, {
    minimumFractionDigits: precision,
    maximumFractionDigits: precision,
  });
  if (Math.abs(delta) < 0.05) return { label: "거의 같음", color: "#AAB3C5" };
  return {
    label: `${delta > 0 ? "B" : "A"}가 ${formatted}${left.unit} 높음`,
    color: delta > 0 ? COLORS.B : COLORS.A,
  };
}

function barWidth(metric, max) {
  if (!metric || !max) return 0;
  return Math.max(8, Math.min(100, (Math.abs(metric.value) / max) * 100));
}

export default function ResultQuickStats({ a, b, futureYears = 3 }) {
  const rows = [
    { key: "income", label: "월소득 중앙값" },
    { key: "wellbeing", label: "삶의 만족" },
    { key: "effect", label: "선택에 따른 변화 효과" },
    { key: "tenure", label: "예상 재직기간" },
    { key: "score:경제적안정도", label: "경제적 안정도" },
    { key: "score:성장가능성", label: "성장 가능성" },
    { key: "score:삶의질", label: "삶의 질" },
  ].map((row) => ({
    ...row,
    A: metricValue(a, row.key, futureYears),
    B: metricValue(b, row.key, futureYears),
  })).filter((row) => row.A || row.B);
  const comparableRows = rows.filter((row) => row.A && row.B);
  const oneSidedRows = rows.filter((row) => !row.A || !row.B);

  if (!rows.length) return null;

  return (
    <section className="mt-4 overflow-hidden rounded-2xl border border-white/10 bg-[#0B1220]/85" aria-labelledby="quick-stats-title">
      <div className="flex flex-wrap items-end justify-between gap-2 border-b border-white/10 px-4 py-3.5">
        <div>
          <h2 id="quick-stats-title" className="text-[13px] font-bold text-ink">A/B 기본 비교 통계</h2>
          <p className="mt-0.5 text-[9px] text-mut">{futureYears}년 뒤를 기준으로, 연결된 관측값만 표시합니다.</p>
        </div>
        <div className="flex gap-3 text-[10px] font-semibold">
          <span style={{ color: COLORS.A }}>A · {labelOf(a.choice)}</span>
          <span style={{ color: COLORS.B }}>B · {labelOf(b.choice)}</span>
        </div>
      </div>

      {comparableRows.length > 0 && <div className="divide-y divide-white/[.07]">
        {comparableRows.map((row) => <StatRow key={row.key} row={row} futureYears={futureYears} />)}
      </div>}
      {oneSidedRows.length > 0 && (
        <div className="border-t border-white/[.07] px-4 py-3.5">
          <div className="mb-2.5">
            <h3 className="text-[11px] font-semibold text-sub">선택별 모델 참고</h3>
            <p className="mt-0.5 text-[9px] leading-4 text-mut">한 선택에만 정의된 값은 A/B 막대로 비교하지 않습니다.</p>
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            {oneSidedRows.map((row) => <SingleSideMetric key={row.key} row={row} futureYears={futureYears} />)}
          </div>
        </div>
      )}
    </section>
  );
}

function SingleSideMetric({ row, futureYears }) {
  const side = row.A ? "A" : "B";
  const metric = row[side];
  return (
    <article className="rounded-xl border border-white/[.07] bg-white/[.025] px-3 py-3">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[10px] font-semibold text-sub">{row.label}</span>
        <span className="rounded-full px-2 py-0.5 text-[8px] font-bold" style={{ color: COLORS[side], background: `${COLORS[side]}15` }}>{side}에만 연결</span>
      </div>
      <div className="mt-2 flex items-baseline gap-1.5">
        <b className="text-[10px]" style={{ color: COLORS[side] }}>{side}</b>
        <strong className="text-[15px] tabular-nums text-ink">{formatMetric(metric)}</strong>
        {metric?.year != null && metric.year !== futureYears && <span className="text-[8px] text-[#D7B7FF]">{metric.year}년 관측</span>}
      </div>
      <p className="mt-1 text-[8.5px] leading-4 text-mut">반대 선택의 값이 0이라는 뜻이 아니라, 같은 정의의 모델값이 없다는 뜻입니다.</p>
    </article>
  );
}

function StatRow({ row, futureYears }) {
  const values = [row.A?.value, row.B?.value].filter(Number.isFinite).map(Math.abs);
  const max = values.length ? Math.max(...values) : 0;
  const comparison = comparisonMeta(row.A, row.B);
  return (
    <article className="px-4 py-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h3 className="text-[11px] font-semibold text-sub">{row.label}</h3>
        {comparison && (
          <span className="rounded-full border border-white/10 bg-white/[.04] px-2 py-1 text-[9px] font-bold tabular-nums" style={{ color: comparison.color }}>
            {comparison.label}
          </span>
        )}
      </div>
      <div className="space-y-2.5">
        <div className="grid grid-cols-[minmax(4.5rem,auto)_minmax(0,1fr)_1px_minmax(0,1fr)_minmax(4.5rem,auto)] items-center gap-2">
          <MetricValue side="A" metric={row.A} futureYears={futureYears} align="right" />
          <div className="flex h-3 items-center justify-end overflow-hidden rounded-l-full bg-white/[.07]" aria-hidden="true">
            {row.A && (
              <div
                className="h-full rounded-l-full transition-[width] duration-500"
                style={{ width: `${barWidth(row.A, max)}%`, backgroundColor: COLORS.A, boxShadow: `0 0 12px ${COLORS.A}55` }}
              />
            )}
          </div>
          <div className="h-8 bg-white/30" aria-hidden="true" />
          <div className="flex h-3 items-center justify-start overflow-hidden rounded-r-full bg-white/[.07]" aria-hidden="true">
            {row.B && (
              <div
                className="h-full rounded-r-full transition-[width] duration-500"
                style={{ width: `${barWidth(row.B, max)}%`, backgroundColor: COLORS.B, boxShadow: `0 0 12px ${COLORS.B}55` }}
              />
            )}
          </div>
          <MetricValue side="B" metric={row.B} futureYears={futureYears} align="left" />
        </div>
        <div className="grid grid-cols-2 text-[8px] font-bold tracking-[.12em]">
          <span className="pr-2 text-right" style={{ color: COLORS.A }}>A · 왼쪽</span>
          <span className="pl-2 text-left" style={{ color: COLORS.B }}>B · 오른쪽</span>
        </div>
      </div>
    </article>
  );
}

function MetricValue({ side, metric, futureYears, align }) {
  return (
    <div className={align === "right" ? "text-right" : "text-left"}>
      <div className="flex items-baseline gap-1" style={{ justifyContent: align === "right" ? "flex-end" : "flex-start" }}>
        <span className="text-[9px] font-black" style={{ color: COLORS[side] }}>{side}</span>
        <strong className="whitespace-nowrap text-[11px] tabular-nums text-ink">{formatMetric(metric)}</strong>
      </div>
      {metric?.year != null && metric.year !== futureYears && (
        <span className="block text-[8px] text-[#D7B7FF]">{metric.year}년 관측</span>
      )}
    </div>
  );
}
