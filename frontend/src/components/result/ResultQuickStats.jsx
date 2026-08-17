import { labelOf } from "../../data/prediction.js";
import { DivergePoint, HalfBar, SIDE_COLORS, divergingShape } from "./DivergingBar.jsx";

const COLORS = SIDE_COLORS;

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
    // 단위는 만원이다(EconML ATE = ate_manwon). 예전엔 여기만 "%"로 찍혀
    // 같은 값을 만원으로 쓰는 인과 탭·요약과 화면끼리 어긋났다.
    return Number.isFinite(value) ? { value, unit: "만원", signed: true } : null;
  }
  if (kind === "tenure") {
    if (side.survival_months == null) return null;
    const value = Number(side.survival_months);
    return Number.isFinite(value) ? { value, unit: "개월" } : null;
  }
  if (kind.startsWith("score:")) {
    const key = kind.slice(6);
    // 근거가 없어 중립값(0.5)만 채워진 축은 값을 내지 않는다 — 0.5 를 '50점'으로
    // 그리면 재지 않은 축이 '중간 정도'라는 측정 결과처럼 보인다.
    if (side.indicator_unmeasured?.includes(key)) return null;
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

// 인과효과(L3)는 '그 선택을 안 했을 때' 대비로 추정된 값이다. 그래서 유지 쪽에
// 모델값이 없는 건 "못 쟀다"가 아니라 **그쪽이 0 기준선**이라는 뜻이다.
// 예전엔 이 행이 통째로 '한쪽에만 연결' 카드로 빠지면서 화면이
// "반대 선택의 값이 0이라는 뜻이 아닙니다"라고 사실과 정반대로 안내했다.
// 반대편이 유지일 때만 채운다 — 이직 vs 창업처럼 둘 다 처치인 쌍에서는
// 어느 쪽도 0 기준이 아니라서 채우면 거짓말이 된다.
function withCausalBaseline(row, a, b) {
  if (row.key !== "effect" || (row.A && row.B) || (!row.A && !row.B)) return row;
  const emptySide = row.A ? "B" : "A";
  const emptyKind = (emptySide === "A" ? a : b)?.kind;
  if (emptyKind !== "유지") return row;
  return {
    ...row,
    [emptySide]: { value: 0, unit: (row.A || row.B).unit, signed: true, baseline: true },
  };
}

// 발산 막대 자체는 DivergingBar.jsx 로 옮겼다 — 지표별 격차·관측된 변화 카드도
// 같은 막대를 쓴다. 여기서는 단위가 같을 때만 비교한다는 규칙만 지킨다.
function barShape(a, b) {
  if (!a || !b || a.unit !== b.unit) return null;
  return divergingShape(a.value, b.value);
}

// survival_months 는 선택 유형마다 **무엇의 기간인지가 다르다**(backend/schemas.py):
//   이직·유지 = 재직 / 창업 = 자영 유지 / 쉬어가기 = 일에서 떠나 있는 기간(복귀까지)
// 라벨을 "예상 재직기간" 하나로 고정해두는 바람에, 쉬어가기에서는 **쉬는 기간**을
// '재직기간' 이라고 말하고 있었다. 일하지 않는 기간을 재직이라 부르는 셈이다.
const TENURE_LABEL = {
  이직: "예상 재직기간",
  유지: "예상 재직기간",
  창업: "예상 자영 유지기간",
  휴식: "복귀까지 걸리는 기간",
};

function tenureLabel(a, b) {
  // 한쪽에만 붙는 값이라(유지는 처치가 아니라 기준선이라 L4 가 없다) 값이 있는 쪽의
  // 유형으로 라벨을 정한다.
  const side = a?.survival_months != null ? a : b?.survival_months != null ? b : null;
  return TENURE_LABEL[side?.kind] || "예상 지속기간";
}

export default function ResultQuickStats({ a, b, futureYears = 3 }) {
  const rows = [
    { key: "income", label: "월소득 중앙값" },
    { key: "wellbeing", label: "삶의 만족" },
    { key: "effect", label: "선택에 따른 변화 효과" },
    { key: "tenure", label: tenureLabel(a, b) },
    // 5축 — 온보딩에서 사용자가 정렬한 가치축과 같은 이름·같은 순서다.
    { key: "score:경제", label: "경제적 안정" },
    { key: "score:성장", label: "성장 가능성" },
    { key: "score:관계", label: "관계" },
    { key: "score:자기실현", label: "자기실현" },
    { key: "score:안정", label: "건강·안정" },
  ].map((row) => ({
    ...row,
    A: metricValue(a, row.key, futureYears),
    B: metricValue(b, row.key, futureYears),
  })).map((row) => withCausalBaseline(row, a, b)).filter((row) => row.A || row.B);

  // 관계·건강처럼 선택별 모델이 없는 영역에서는 A와 B가 **같은 기준선**을 받는다.
  // 소득 궤적은 프로필로만 계산되고(scenario_trajectories 가 빈 배열), 만족도는
  // wellbeing_branch.branched=false 로 갈리지 않으며, 지표 3종은 그 둘을 섞어
  // 만들어지므로 결국 A=B 가 된다. 그걸 A/B 비교표에 나란히 그리면 사용자는
  // "두 선택의 차이가 없다"로 읽지만, 진실은 "이 질문은 이 수치로 구분되지
  // 않는다"다. 백엔드는 quantitative_ok=false 로 이미 그렇게 말하고 있다.
  const comparable = [a, b].some((side) => side?.quantitative_ok !== false);
  const guardNote = a?.graph_guard_note || b?.graph_guard_note || null;

  const comparableRows = comparable
    ? rows.filter((row) => row.A && row.B).map((row) => ({ ...row, shape: barShape(row.A, row.B) }))
    : [];
  const oneSidedRows = comparable ? rows.filter((row) => !row.A || !row.B) : [];
  // 비교가 성립하지 않을 때도 값 자체는 유효한 정보다(비슷한 사람들의 관측값).
  // 버리지 않고 '두 선택 공통' 자리로 내려 단일 값으로 보여준다.
  const sharedRows = comparable ? [] : rows.filter((row) => row.A || row.B);

  // 잰 적 없는 축은 막대로 그릴 수 없다(막대는 '모름'을 표현하지 못한다). 대신
  // 어떤 축이 왜 비었는지 각주로 말한다 — 조용히 빼면 없는 축은 화면에서 사라져
  // 사용자가 온보딩에서 고른 가치가 무시된 것처럼 보인다.
  const unmeasuredAxes = [...new Set([
    ...(a?.indicator_unmeasured || []), ...(b?.indicator_unmeasured || []),
  ])];

  if (!rows.length && !unmeasuredAxes.length) return null;

  return (
    <section className="mt-4 overflow-hidden rounded-2xl border border-white/10 bg-[#0B1220]/85" aria-labelledby="quick-stats-title">
      <div className="flex flex-wrap items-end justify-between gap-2 border-b border-white/10 px-4 py-3">
        <div>
          <h2 id="quick-stats-title" className="text-[13px] font-bold text-ink">
            {comparable ? "A/B 기본 비교 통계" : "기본 통계 · 두 선택 공통"}
          </h2>
          <p className="mt-0.5 text-[9px] text-mut">{futureYears}년 뒤를 기준으로, 연결된 관측값만 표시합니다.</p>
        </div>
        {comparable && (
          <div className="flex gap-3 text-[10px] font-semibold">
            <span style={{ color: COLORS.A }}>A · {labelOf(a.choice)}</span>
            <span style={{ color: COLORS.B }}>B · {labelOf(b.choice)}</span>
          </div>
        )}
      </div>

      {sharedRows.length > 0 && (
        <div className="px-4 py-3.5">
          <p className="mb-2.5 rounded-lg bg-[#F5C86B]/[.07] px-3 py-2 text-[9.5px] leading-4 text-sub">
            이 질문은 <b className="font-semibold">두 선택이 이 수치로 구분되지 않습니다.</b> 아래 값은 A·B 공통으로,
            비슷한 조건인 사람들의 관측값입니다 — 어느 쪽을 골랐을 때의 예측이 아닙니다.
            {guardNote && <span className="mt-1 block text-mut">{guardNote}</span>}
          </p>
          <div className="grid gap-2 sm:grid-cols-2">
            {sharedRows.map((row) => (
              <article key={row.key} className="flex items-baseline justify-between gap-2 rounded-xl border border-white/[.07] bg-white/[.025] px-3 py-2.5">
                <span className="min-w-0 truncate text-[10px] text-sub">{row.label}</span>
                <strong className="shrink-0 text-[13px] tabular-nums text-ink">{formatMetric(row.A || row.B)}</strong>
              </article>
            ))}
          </div>
          <p className="mt-2.5 text-[9px] leading-4 text-mut">
            두 선택의 차이는 <b className="font-semibold text-sub">집단 관측</b>과 <b className="font-semibold text-sub">기록 근거</b> 탭에서 확인하세요.
          </p>
        </div>
      )}

      {comparableRows.length > 0 && <div className="divide-y divide-white/[.07]">
        {comparableRows.map((row) => <StatRow key={row.key} row={row} futureYears={futureYears} />)}
      </div>}
      {oneSidedRows.length > 0 && (
        <div className="border-t border-white/[.07] px-4 py-3.5">
          <div className="mb-2.5">
            <h3 className="text-[11px] font-semibold text-sub">선택별 모델 참고</h3>          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            {oneSidedRows.map((row) => <SingleSideMetric key={row.key} row={row} futureYears={futureYears} />)}
          </div>
        </div>
      )}
      {unmeasuredAxes.length > 0 && (
        <p className="border-t border-white/[.07] px-4 py-2.5 text-[9px] leading-4 text-mut">
          <b className="font-semibold text-sub">{unmeasuredAxes.join(" · ")}</b>
          {" "}축은 이 선택을 측정한 검증 결과가 없어 비워 두었습니다 — 값이 낮다는 뜻이 아닙니다.
        </p>
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
    </article>
  );
}

// 한 행 = 한 줄. 항목명·막대·배지를 같은 높이에 두고, 값에 붙는 관측연도도
// 아랫줄로 흘리지 않고 숫자 옆에 붙인다. 예전엔 항목명 줄 + 막대 줄 +
// "← A가 높음" 줄로 세 줄이라, 막대끼리 간격이 실제 막대 높이의 네 배였다.
//
// 좌우 폭은 **대칭 고정**이다 — 항목명 7rem = 배지 7rem, A값 6rem = B값 6rem.
// 값 칸을 auto 로 두면 "340만원 2028년"과 "3.9점"의 글자 수 차이만큼 0선이
// 옆으로 밀려서, 행마다 발산점이 다른 자리에 찍혔다. 고정폭이라야 0선이
// 카드 정중앙에 오고 모든 행의 막대가 같은 축에서 갈라진다.
function StatRow({ row, futureYears }) {
  const comparison = comparisonMeta(row.A, row.B);
  return (
    <article className="grid items-center gap-x-3 gap-y-1 px-4 py-2 sm:grid-cols-[7rem_minmax(0,1fr)_7rem]">
      <h3 className="truncate text-[11px] font-semibold text-sub">{row.label}</h3>
      <div className="grid grid-cols-[6.5rem_minmax(0,1fr)_10px_minmax(0,1fr)_6.5rem] items-center gap-1.5">
        <MetricValue side="A" metric={row.A} futureYears={futureYears} align="right" />
        <HalfBar side="A" shape={row.shape?.A} />
        <DivergePoint clipped={row.shape?.clipped} />
        <HalfBar side="B" shape={row.shape?.B} />
        <MetricValue side="B" metric={row.B} futureYears={futureYears} align="left" />
      </div>
      {comparison && (
        <span
          className="justify-self-start truncate rounded-full border border-white/10 bg-white/[.04] px-2 py-0.5 text-[9px] font-bold tabular-nums sm:justify-self-end"
          style={{ color: comparison.color }}
        >
          {comparison.label}
        </span>
      )}
    </article>
  );
}

function MetricValue({ side, metric, futureYears, align }) {
  // 관측연도·기준 표시는 아랫줄로 내리지 않고 숫자 뒤에 붙인다(줄바꿈 방지).
  const suffix = metric?.baseline
    ? "기준"
    : metric?.year != null && metric.year !== futureYears
      ? `${metric.year}년`
      : null;
  return (
    <div
      className="flex items-baseline gap-1 whitespace-nowrap"
      style={{ justifyContent: align === "right" ? "flex-end" : "flex-start" }}
    >
      <span className="text-[9px] font-black" style={{ color: COLORS[side] }}>{side}</span>
      <strong className="text-[11px] tabular-nums text-ink">{formatMetric(metric)}</strong>
      {suffix && <span className="text-[8px] text-[#D7B7FF]">{suffix}</span>}
    </div>
  );
}
