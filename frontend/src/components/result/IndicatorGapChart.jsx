import { Card, Caption } from "../ui.jsx";
import { labelOf } from "../../data/prediction.js";
import { DivergePoint, HalfBar, SIDE_COLORS, divergingShape } from "./DivergingBar.jsx";

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
  // 공유 축 — 가장 크게 벗어난 지표가 트랙을 채운다. 바닥값 1은 확대경 방지용이다
  // (전부 0.2%p 차이인 표에서 최대값에 맞춰 늘리면 미미한 차이가 압도적으로 보인다).
  const sharedDomain = Math.max(1, ...shared.map((row) => (
    Number.isFinite(row.baseline) && Number.isFinite(row.value)
      ? Math.abs(row.value - row.baseline) : 0
  )));

  if (!gaps.length && !shared.length) return null;

  return (
    <Card className="mb-4">
      <div className="flex items-center justify-between">
        <div className="text-sm font-semibold text-ink">지표별 격차</div>
        <div className="flex items-center gap-3 text-[10px] text-mut">
          <Legend color={SIDE_COLORS.A} label="A" />
          <Legend color={SIDE_COLORS.B} label="B" />
        </div>
      </div>

      {gaps.length > 0 ? (
        <>
          <Caption>두 선택에서 예측값이 갈리는 지표입니다.</Caption>
          {/* 예전엔 지표 하나당 68px 원형 게이지 두 개(최대 8개)를 그리고, 그
              아래 같은 내용을 알약으로 한 번 더 썼다. 원은 길이 비교가 안 되는
              데다 게이지 최댓값이 max(|A|,|B|) 라 이긴 쪽은 항상 꽉 찬 원이었다
              — 격차가 1이든 100이든 그림이 똑같았다는 뜻이다. 이제 다른 카드와
              같은 발산 막대를 쓰고, 중복이던 알약 줄은 없앴다. */}
          <div className="mt-3 divide-y divide-white/[.06]">
            {gaps.map((row) => <GapRow key={row.name} row={row} a={a} b={b} />)}
          </div>
        </>
      ) : (
        <NoGapNotice a={a} b={b} />
      )}

      {shared.length > 0 && (
        <div className="mt-5 border-t border-line pt-4">
          <div className="text-[12px] font-semibold text-ink">두 선택 공통 · 참고 기준</div>
          <Caption>
            선택과 무관한 또래 집단 통계입니다. A·B가 같은 값이라 한 줄로 표시하며,
            막대는 <b className="font-semibold text-sub">전체 평균 대비 차이</b>입니다 — 가운데가 전체 평균.
          </Caption>
          <div className="mt-3 space-y-2.5">
            {shared.map((row) => <SharedRow key={row.name} row={row} domain={sharedDomain} />)}
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
      baseline: num(it.baseline),
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
          baseline: num(item.baseline),
        });
      }
    }
  }
  return rows.slice(0, 8);
}

const num = (v) => (v === null || v === undefined || v === "" ? NaN : Number(v));

/**
 * 지표 한 줄 = [이름] [A값 ◀막대│막대▶ B값] [격차 배지].
 * 결과 화면 어디서나 같은 발산 막대를 쓴다(DivergingBar).
 */
function GapRow({ row, a, b }) {
  const bothKnown = Number.isFinite(row.av) && Number.isFinite(row.bv);
  const shape = bothKnown ? divergingShape(row.av, row.bv) : null;
  return (
    <article className="grid items-center gap-x-3 gap-y-1 py-2.5 sm:grid-cols-[7.5rem_minmax(0,1fr)_7.5rem]">
      <h4 className="truncate text-[11px] font-semibold text-sub">
        {row.name}
        {row.unit ? <span className="ml-1 text-[9px] font-normal text-mut">({row.unit})</span> : null}
      </h4>

      <div className="grid grid-cols-[5rem_minmax(0,1fr)_10px_minmax(0,1fr)_5rem] items-center gap-1.5">
        <SideValue side="A" value={row.av} align="right" />
        <HalfBar side="A" shape={shape?.A} />
        <DivergePoint clipped={shape?.clipped} />
        <HalfBar side="B" shape={shape?.B} />
        <SideValue side="B" value={row.bv} align="left" />
      </div>

      <GapBadge row={row} a={a} b={b} />
    </article>
  );
}

function SideValue({ side, value, align }) {
  return (
    <div
      className="flex items-baseline gap-1 whitespace-nowrap"
      style={{ justifyContent: align === "right" ? "flex-end" : "flex-start" }}
    >
      <span className="text-[9px] font-black" style={{ color: SIDE_COLORS[side] }}>{side}</span>
      <strong className="text-[11px] tabular-nums text-ink">{fmt(value)}</strong>
    </div>
  );
}

function GapBadge({ row, a, b }) {
  if (!Number.isFinite(row.av) || !Number.isFinite(row.bv)) {
    const other = Number.isFinite(row.av) ? "B" : "A";
    return (
      <span className="justify-self-start truncate rounded-full bg-white/[.05] px-2 py-0.5 text-[9px] text-mut sm:justify-self-end">
        {other}는 예측 없음
      </span>
    );
  }
  const diff = row.av - row.bv;
  if (Math.abs(diff) < 0.05) {
    return (
      <span className="justify-self-start truncate rounded-full border border-white/10 bg-white/[.04] px-2 py-0.5 text-[9px] font-bold text-mut sm:justify-self-end">
        거의 같음
      </span>
    );
  }
  const win = diff > 0 ? "A" : "B";
  const label = win === "A" ? labelOf(a.choice) : labelOf(b.choice);
  return (
    <span
      className="justify-self-start truncate rounded-full border border-white/10 bg-white/[.04] px-2 py-0.5 text-[9px] font-bold tabular-nums sm:justify-self-end"
      style={{ color: SIDE_COLORS[win] }}
      title={`${win} · ${label}`}
    >
      {win}가 {fmt(Math.abs(diff))}{row.unit} 높음
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

// 전체 평균을 0으로 두고 좌우로 그린다.
//
// 예전엔 0~100% 축에 값 하나를 막대로 그렸는데, 유병률·인지율에는 만점이 없어서
// 그 축이 아무 의미가 없었다. 게다가 이 지표들은 전부 '낮을수록 좋음'이라
// 스트레스인지율 37.5% 가 가장 긴 막대 = 가장 좋아 보이는 그림이 됐다.
// 이제 기준은 전체 집단 값이고, 막대 길이는 거기서 벗어난 정도다. 방향과 색이
// lower_is_better 를 반영하므로 길이가 곧 '나쁨'으로 뒤집히지 않는다.
//
// 축은 이 카드 안의 모든 행이 공유한다(gapDomain) — 행끼리 "어느 지표가 가장
// 크게 벗어났는가"를 비교할 수 있어야 표로서 의미가 있다.
const WORSE = "#F0846B";   // 또래가 더 나쁜 쪽
const BETTER = "#5FC9A6";  // 또래가 더 나은 쪽

function SharedRow({ row, domain }) {
  const hasBaseline = Number.isFinite(row.baseline) && Number.isFinite(row.value);
  const delta = hasBaseline ? row.value - row.baseline : null;
  // 값이 클수록 나쁜 지표면 +가 나쁨, 아니면 +가 좋음.
  const worse = hasBaseline && (row.lowerIsBetter ? delta > 0 : delta < 0);
  const width = hasBaseline && domain
    ? Math.max(3, Math.min(100, (Math.abs(delta) / domain) * 100)) : 0;
  const negligible = hasBaseline && Math.abs(delta) < 0.05;
  const color = negligible ? "#8994A8" : worse ? WORSE : BETTER;

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

      {hasBaseline ? (
        <>
          <div className="mt-1.5 grid grid-cols-[minmax(0,1fr)_1px_minmax(0,1fr)] items-center gap-1">
            <div className="flex h-2 items-center justify-end overflow-hidden rounded-l-full bg-white/[.05]" aria-hidden="true">
              {delta < 0 && !negligible && (
                <div className="h-full rounded-l-full transition-[width] duration-500"
                     style={{ width: `${width}%`, backgroundColor: color }} />
              )}
            </div>
            <div className="h-4 bg-white/25" aria-hidden="true" />
            <div className="flex h-2 items-center justify-start overflow-hidden rounded-r-full bg-white/[.05]" aria-hidden="true">
              {delta > 0 && !negligible && (
                <div className="h-full rounded-r-full transition-[width] duration-500"
                     style={{ width: `${width}%`, backgroundColor: color }} />
              )}
            </div>
          </div>
          <div className="mt-1 flex flex-wrap items-baseline justify-between gap-x-2 text-[9px]">
            <span className="text-mut">전체 {fmt(row.baseline)}{row.unit} 기준</span>
            <span className="font-semibold tabular-nums" style={{ color }}>
              {negligible ? "전체와 거의 같음"
                : `${delta > 0 ? "+" : "−"}${fmt(Math.abs(delta))}${row.unit} · 또래가 ${worse ? "나쁨" : "나음"}`}
            </span>
          </div>
        </>
      ) : (
        /* 기준선이 없으면 막대를 그리지 않는다 — 견줄 데가 없는 값에 길이를 주면
           그 길이가 곧 판단처럼 읽힌다(예전 화면이 그랬다). */
        <div className="mt-1 text-[9px] text-mut">비교할 전체 기준값이 없어 수치만 표시합니다.</div>
      )}

      <div className="mt-1 text-[9px] text-mut">
        {row.source}{row.lowerIsBetter ? " · 낮을수록 좋음" : ""}
      </div>
    </div>
  );
}

const fmt = (v) => (Number.isFinite(v)
  ? (Math.abs(v) >= 100 ? Math.round(v) : Math.round(v * 10) / 10).toLocaleString()
  : "—");
