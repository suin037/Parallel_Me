import { Card, Caption } from "../ui.jsx";
import { labelOf } from "../../data/prediction.js";

/**
 * A/B 지표 비교 — 두 종류를 엄격히 분리해서 그린다.
 *
 *  1) 갈림 지표 : A와 B가 실제로 다른 값을 갖는 예측(소득·지속·인과효과 등).
 *                 좌우 마주보는 막대로 격차를 보여준다.
 *  2) 공통 지표 : 프로필 기반 참고 통계. 설계상 선택과 무관해 A와 B가 항상 같다
 *                 (rulebase.query_life_indicators 는 '선택 무관'). 그래서 좌우로
 *                 미러링하지 않고 단일 막대로 그린다 — 같은 값을 양쪽에 그리면
 *                 비교가 된 것처럼 보이는 착시가 생긴다.
 *
 * 갈림 지표가 하나도 없으면(관계처럼 추적 데이터에 대응 사건이 없는 선택)
 * 막대를 지어내지 않고 왜 구분되지 않는지를 설명한다.
 */
export default function IndicatorGapChart({ a, b, domains = { a: [], b: [] } }) {
  const selected = [...new Set([...(domains.a || []), ...(domains.b || [])])];
  const gaps = buildGapRows(a, b);
  const shared = buildSharedRows(a, b, selected);

  if (!gaps.length && !shared.length) return null;

  return (
    <Card className="mb-4">
      <div className="flex items-center justify-between">
        <div className="text-sm font-semibold text-ink">지표별 격차</div>
        <div className="flex items-center gap-3 text-[10px] text-mut">
          <Legend color="#8B6CCF" label="A" />
          <Legend color="#F5C86B" label="B" />
        </div>
      </div>

      {gaps.length > 0 ? (
        <>
          <Caption>두 선택에서 예측값이 갈리는 지표입니다.</Caption>
          <div className="mt-3 space-y-3">
            {gaps.map((row) => <GapRow key={row.name} row={row} />)}
          </div>
          <div className="mt-3 flex flex-wrap gap-1.5">
            {gaps.map((row) => <GapChip key={row.name} row={row} a={a} b={b} />)}
          </div>
        </>
      ) : (
        <NoGapNotice a={a} b={b} />
      )}

      {shared.length > 0 && (
        <div className="mt-5 border-t border-line pt-4">
          <div className="text-[12px] font-semibold text-ink">두 선택 공통 · 참고 기준</div>
          <Caption>
            선택과 무관한 또래 집단 통계입니다. A·B가 같은 값이라 한 줄로 표시합니다.
          </Caption>
          <div className="mt-3 space-y-2.5">
            {shared.map((row) => <SharedRow key={row.name} row={row} />)}
          </div>
        </div>
      )}
    </Card>
  );
}

function Legend({ color, label }) {
  return (
    <span className="flex items-center gap-1">
      <i className="h-2 w-2 rounded-full" style={{ background: color }} />
      {label}
    </span>
  );
}

/** A와 B가 실제로 다른 값을 갖는 예측만 뽑는다. 한쪽만 있는 것도 격차로 본다. */
function buildGapRows(a, b) {
  const last = (rows) => (Array.isArray(rows) && rows.length
    ? Number(rows[rows.length - 1]?.value ?? rows[rows.length - 1]?.median ?? rows[rows.length - 1]?.satis_p50 ?? NaN)
    : NaN);
  const candidates = [
    { name: "예상 월소득", unit: "만원", av: num(a.expected_wage), bv: num(b.expected_wage) },
    { name: "소득 변화 효과", unit: "%", av: num(a.causal_effect), bv: num(b.causal_effect) },
    { name: "예상 지속 기간", unit: "개월", av: num(a.survival_months), bv: num(b.survival_months) },
    { name: "5년 뒤 삶의 만족", unit: "점", av: last(a.wellbeing_trajectory), bv: last(b.wellbeing_trajectory) },
  ];
  return candidates.filter((r) => {
    const hasAny = Number.isFinite(r.av) || Number.isFinite(r.bv);
    const differs = !(Number.isFinite(r.av) && Number.isFinite(r.bv)) || r.av !== r.bv;
    return hasAny && differs;
  });
}

/**
 * 참고 지표. 백엔드 domains 태그로 영역을 거른다(문자열 추측 아님).
 * 한쪽 선택에만 있는 지표(창업 생존율 등)는 side 를 달아 구분한다.
 */
function buildSharedRows(a, b, selected) {
  const inScope = (it) => {
    // 태그를 안 보낸 구버전·데모 응답이면 거르지 않고 통과시킨다.
    const tags = it.domains || [];
    return !selected.length || !tags.length || tags.some((d) => selected.includes(d));
  };
  const bNames = new Set((b.life_indicators || []).map((it) => it.indicator));
  const aNames = new Set((a.life_indicators || []).map((it) => it.indicator));
  const rows = [];
  const seen = new Set();

  const push = (it, side) => {
    if (seen.has(it.indicator) || !inScope(it)) return;
    seen.add(it.indicator);
    rows.push({
      name: it.indicator, value: num(it.value), unit: it.unit,
      source: it.source, lowerIsBetter: it.lower_is_better, side,
    });
  };
  for (const it of a.life_indicators || []) push(it, bNames.has(it.indicator) ? null : "A");
  for (const it of b.life_indicators || []) if (!aNames.has(it.indicator)) push(it, "B");

  // 영역별 실측 집단통계(사회적 고립도 등)도 같은 목록에 얹는다.
  for (const side of ["A", "B"]) {
    const result = side === "A" ? a : b;
    for (const [domain, stat] of Object.entries(result.domain_stats || {})) {
      if (selected.length && !selected.includes(domain)) continue;
      for (const item of stat.indicators || []) {
        if (seen.has(item.name)) continue;
        seen.add(item.name);
        rows.push({
          name: item.name, value: num(item.value), unit: item.unit,
          source: item.source, lowerIsBetter: false, side: null,
        });
      }
    }
  }
  return rows.slice(0, 8);
}

const num = (v) => (v === null || v === undefined || v === "" ? NaN : Number(v));

/** A/B 원형 게이지. 단위가 지표마다 달라 각 항목의 최댓값 기준으로 채움 정도를 비교한다. */
function GapRow({ row }) {
  const max = Math.max(Number.isFinite(row.av) ? Math.abs(row.av) : 0, Number.isFinite(row.bv) ? Math.abs(row.bv) : 0, 1);
  return (
    <div className="rounded-xl border border-white/[.06] bg-white/[.02] px-3 py-3">
      <div className="mb-2 text-center text-[11px] text-sub">{row.name}{row.unit ? <span className="ml-1 text-[9px] text-mut">({row.unit})</span> : null}</div>
      <div className="flex items-center justify-center gap-8">
        <GapRing side="A" value={row.av} max={max} color="#8B6CCF" />
        <GapRing side="B" value={row.bv} max={max} color="#F5C86B" />
      </div>
    </div>
  );
}

function GapRing({ side, value, max, color }) {
  const fill = Number.isFinite(value) ? Math.max(4, Math.min(100, Math.abs(value) / max * 100)) : 0;
  return (
    <div
      className="relative flex h-[68px] w-[68px] items-center justify-center rounded-full"
      style={{ background: `conic-gradient(${color} ${fill}%, rgba(255,255,255,.08) ${fill}% 100%)` }}
      aria-label={`${side} ${fmt(value)}`}
    >
      <div className="absolute inset-[6px] rounded-full bg-[#0E1424]" />
      <div className="relative text-center">
        <div className="text-[9px] font-bold" style={{ color }}>{side}</div>
        <div className="text-[11px] font-semibold tabular-nums text-ink">{fmt(value)}</div>
      </div>
    </div>
  );
}

function GapChip({ row, a, b }) {
  if (!Number.isFinite(row.av) || !Number.isFinite(row.bv)) {
    const only = Number.isFinite(row.av) ? "A" : "B";
    const other = only === "A" ? "B" : "A";
    return (
      <span className="rounded-full bg-white/[.05] px-2.5 py-1 text-[10px] text-mut">
        {row.name} · {other}는 예측 데이터 없음
      </span>
    );
  }
  const diff = row.av - row.bv;
  const win = diff > 0 ? "A" : "B";
  const label = win === "A" ? labelOf(a.choice) : labelOf(b.choice);
  return (
    <span
      className="rounded-full px-2.5 py-1 text-[10px] font-semibold"
      style={win === "A"
        ? { background: "rgba(139,108,207,.16)", color: "#B79BF5" }
        : { background: "rgba(245,200,107,.16)", color: "#F5C86B" }}
    >
      {row.name} {win}({label}) +{fmt(Math.abs(diff))}
    </span>
  );
}

/** 갈림 지표가 없을 때 — 막대를 지어내지 않고 이유를 설명한다. */
function NoGapNotice({ a, b }) {
  return (
    <div className="mt-3 rounded-xl border border-violet-400/20 bg-violet-500/[.055] px-3 py-3">
      <div className="text-[12px] font-semibold text-ink">
        이 두 선택은 수치로는 구분되지 않습니다
      </div>
      <p className="mt-1.5 text-[11px] leading-5 text-sub">
        «{labelOf(a.choice)}»와 «{labelOf(b.choice)}»는 장기 추적조사가 기록하는 사건
        (이직·창업·결혼·가구 변화처럼 날짜가 남는 일)에 해당하지 않습니다. 그래서 두 선택을
        가른 집단을 만들 수 없고, 억지로 격차를 만들지 않았습니다.
      </p>
      <p className="mt-1.5 text-[11px] leading-5 text-mut">
        아래 참고 기준과 기록 기반 해석으로 비교해 보세요.
      </p>
    </div>
  );
}

function SharedRow({ row }) {
  const scaleMax = row.unit === "%" ? 100
    : String(row.unit).includes("10") ? 10
      : String(row.unit).includes("점") ? 5
        : Math.max(row.value, 1);
  const width = Number.isFinite(row.value)
    ? Math.max(4, Math.min(100, (row.value / scaleMax) * 100)) : 0;
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3">
        <span className="min-w-0 text-[12px] text-ink">
          {row.side && (
            <b
              className="mr-1.5 rounded px-1 py-px text-[9px]"
              style={row.side === "A"
                ? { background: "rgba(139,108,207,.18)", color: "#B79BF5" }
                : { background: "rgba(245,200,107,.18)", color: "#F5C86B" }}
            >
              {row.side}만
            </b>
          )}
          {row.name}
        </span>
        <span className="whitespace-nowrap">
          <b className="text-[13px] tabular-nums text-ink">{fmt(row.value)}</b>
          <span className="ml-1 text-[9px] text-sub">{row.unit}</span>
        </span>
      </div>
      <div className="mt-1 h-2 overflow-hidden rounded-full bg-[#080D19]">
        <div
          className="h-full rounded-full bg-gradient-to-r from-[#7455C5] to-[#B093F0]"
          style={{ width: `${width}%` }}
        />
      </div>
      <div className="mt-1 text-[9px] text-mut">
        {row.source}{row.lowerIsBetter ? " · 낮을수록 좋음" : ""}
      </div>
    </div>
  );
}

const fmt = (v) => (Number.isFinite(v)
  ? (Math.abs(v) >= 100 ? Math.round(v) : Math.round(v * 10) / 10).toLocaleString()
  : "—");
