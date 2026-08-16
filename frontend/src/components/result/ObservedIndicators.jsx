import { Card, Caption } from "../ui.jsx";
import { labelOf } from "../../data/prediction.js";
import { SIDE_COLORS } from "./DivergingBar.jsx";

const GROWTH = ["occupation_changed", "employment_improved", "firm_size_up", "wage_band_up"];
const QUALITY = ["satisfaction_overall_change", "satisfaction_family_income_change", "happiness_change", "wellbeing_index_change"];

const metric = (side, domain, key) => side.observed_outcomes?.domains?.[domain]?.find((item) => item.key === key);

export default function ObservedIndicators({ a, b }) {
  if (a.observed_outcomes?.status !== "available" && b.observed_outcomes?.status !== "available") return null;
  return (
    <div className="mb-5">
      <h2 className="mb-1 text-base font-semibold">두 선택에서 관측된 변화</h2>
      <Caption>현재 조건이 비슷한 KLIPS 사례를 이직과 유지로 나눠 비교합니다.</Caption>
      <GrowthCard a={a} b={b} />
      <QualityCard a={a} b={b} />
    </div>
  );
}

function GrowthCard({ a, b }) {
  return (
    <Card>
      <div className="flex items-center justify-between gap-2">
        <div className="text-sm font-semibold">성장 가능성</div>
        <div className="text-[10px] text-mut">A {a.observed_outcomes?.matching?.people_n || 0}명 · B {b.observed_outcomes?.matching?.people_n || 0}명</div>
      </div>
      <Caption>주관적인 성장 점수가 아니라 실제 경력 상태가 바뀐 비율입니다.</Caption>
      <div className="mt-3 space-y-3">
        {GROWTH.map((key) => <RatePair key={key} a={metric(a, "growth", key)} b={metric(b, "growth", key)} />)}
      </div>
    </Card>
  );
}

// 비율(0~100%)은 만점이 실재하는 축이라 축을 자를 이유가 없다. A·B 막대를
// 같은 0~100% 축에 위아래로 붙여 왼쪽 끝을 맞춘다 — 길이 차이가 곧 격차다.
//
// 예전엔 72px 원형 게이지 두 개였다. 원은 길이 비교가 안 돼서 "A 12.4% / B 9.1%"
// 를 두 개의 거의 같은 도넛으로 보여줬고, 지표 4개 × 2 = 도넛 여덟 개가 세로로
// 쌓여 카드 하나가 화면을 다 먹었다.
function RatePair({ a, b }) {
  if (!a?.available && !b?.available) return null;
  const pct = (item) => (item?.rate == null ? null : Math.max(0, Math.min(100, item.rate * 100)));
  const av = pct(a);
  const bv = pct(b);
  const diff = av != null && bv != null ? av - bv : null;
  return (
    <div className="rounded-xl border border-white/[.06] bg-white/[.02] px-3 py-2.5">
      <div className="flex items-baseline justify-between gap-2">
        <span className="min-w-0 truncate text-[11px] text-sub">{a?.label || b?.label}</span>
        {diff != null && Math.abs(diff) >= 0.05 && (
          <span className="shrink-0 text-[9px] font-bold tabular-nums" style={{ color: SIDE_COLORS[diff > 0 ? "A" : "B"] }}>
            {diff > 0 ? "A" : "B"}가 {Math.abs(diff).toFixed(1)}%p 높음
          </span>
        )}
      </div>
      <div className="mt-2 space-y-1.5">
        <RateBar side="A" percent={av} n={a?.n} />
        <RateBar side="B" percent={bv} n={b?.n} />
      </div>
    </div>
  );
}

function RateBar({ side, percent, n }) {
  const color = SIDE_COLORS[side];
  return (
    <div className="grid grid-cols-[0.9rem_minmax(0,1fr)_4.5rem] items-center gap-2">
      <b className="text-[9px] font-black" style={{ color }}>{side}</b>
      <div className="h-2.5 overflow-hidden rounded-full bg-white/[.06]" aria-hidden="true">
        {percent != null && (
          <div
            className="h-full rounded-full transition-[width] duration-500"
            style={{ width: `${Math.max(percent > 0 ? 2 : 0, percent)}%`, background: color }}
          />
        )}
      </div>
      <span className="text-right text-[10px] tabular-nums text-ink">
        {percent == null ? "—" : `${percent.toFixed(1)}%`}
        {n ? <span className="ml-1 text-[8px] text-mut">n={n}</span> : null}
      </span>
    </div>
  );
}

function QualityCard({ a, b }) {
  return (
    <Card>
      <div className="text-sm font-semibold">삶의 질</div>
      <Caption>단일 예측점수 대신 개선·유지·악화가 관측된 비중을 표시합니다.</Caption>
      <div className="mt-3 space-y-4">
        {QUALITY.map((key) => <QualityPair key={key} a={metric(a, "quality_of_life", key)} b={metric(b, "quality_of_life", key)} />)}
      </div>
      <LongTermLevels a={a} b={b} />
      <Caption><span className="text-[#62C9A7]">■</span> 개선 · <span className="text-[#657087]">■</span> 유지 · <span className="text-[#D97882]">■</span> 악화</Caption>
    </Card>
  );
}

// 개선/유지/악화 세 조각은 합이 100% 인 구성비다. 도넛 두 개로 그리면 두 원의
// 같은 조각을 눈으로 이어 붙여야 비교가 되는데, 그건 사람이 잘 못하는 일이다.
// 100% 누적 막대를 위아래로 겹쳐 놓으면 각 조각의 경계선이 세로로 정렬돼
// "A의 개선이 B보다 여기까지 더 길다"가 바로 보인다.
const QUALITY_BANDS = [
  { key: "improved_rate", label: "개선", color: "#62C9A7" },
  { key: "unchanged_rate", label: "유지", color: "#657087" },
  { key: "worsened_rate", label: "악화", color: "#D97882" },
];

function QualityPair({ a, b }) {
  if (!a?.available && !b?.available) return null;
  const improved = (item) => (item?.available ? (item.improved_rate || 0) * 100 : null);
  const diff = improved(a) != null && improved(b) != null ? improved(a) - improved(b) : null;
  return (
    <div className="rounded-xl border border-white/[.06] bg-white/[.02] px-3 py-2.5">
      <div className="flex items-baseline justify-between gap-2">
        <span className="min-w-0 truncate text-[11px] text-sub">{a?.label || b?.label}</span>
        {diff != null && Math.abs(diff) >= 0.5 && (
          <span className="shrink-0 text-[9px] font-bold tabular-nums" style={{ color: SIDE_COLORS[diff > 0 ? "A" : "B"] }}>
            개선 {diff > 0 ? "A" : "B"}가 {Math.abs(diff).toFixed(0)}%p 높음
          </span>
        )}
      </div>
      <div className="mt-2 space-y-1.5">
        <QualityBar side="A" item={a} />
        <QualityBar side="B" item={b} />
      </div>
    </div>
  );
}

function QualityBar({ side, item }) {
  const color = SIDE_COLORS[side];
  if (!item?.available) {
    return (
      <div className="grid grid-cols-[0.9rem_minmax(0,1fr)] items-center gap-2">
        <b className="text-[9px] font-black" style={{ color }}>{side}</b>
        <span className="text-[9px] text-mut">표본 부족</span>
      </div>
    );
  }
  const bands = QUALITY_BANDS.map((band) => ({ ...band, value: (item[band.key] || 0) * 100 }));
  return (
    <div className="grid grid-cols-[0.9rem_minmax(0,1fr)_4.5rem] items-center gap-2">
      <b className="text-[9px] font-black" style={{ color }}>{side}</b>
      <div className="flex h-2.5 overflow-hidden rounded-full bg-white/[.06]">
        {bands.map((band) => (
          <div
            key={band.key}
            className="h-full transition-[width] duration-500"
            style={{ width: `${band.value}%`, background: band.color }}
            title={`${band.label} ${band.value.toFixed(0)}%`}
          />
        ))}
      </div>
      <span className="text-right text-[10px] tabular-nums text-ink">
        개선 {bands[0].value.toFixed(0)}%
      </span>
    </div>
  );
}

function LongTermLevels({ a, b }) {
  const ta = a.parallel_trajectory?.timeline || [];
  const tb = b.parallel_trajectory?.timeline || [];
  if (!ta.length && !tb.length) return null;
  return (
    <div className="mt-4 border-t border-line pt-3">
      <div className="mb-2 text-[11px] font-semibold">1·3·5년 행복·웰빙 관측 수준</div>
      <div className="grid grid-cols-[34px_repeat(2,minmax(0,1fr))] gap-2 text-center text-[10px]">
        <span/><span className="text-[#A98BEE]">A · {labelOf(a.choice)}</span><span className="text-[#F5C86B]">B · {labelOf(b.choice)}</span>
        {[1, 3, 5].flatMap((year) => {
          const pa = ta.find((point) => point.year === year);
          const pb = tb.find((point) => point.year === year);
          return [<b key={`${year}y`} className="self-center text-sub">{year}년</b>, <Level key={`${year}a`} point={pa}/>, <Level key={`${year}b`} point={pb}/>];
        })}
      </div>
      <Caption>장기 값은 개인 점수 예측이 아니라 유사 사례의 관측 중앙값입니다.</Caption>
    </div>
  );
}

function Level({ point }) {
  if (!point) return <span className="rounded-lg bg-bg/50 p-2 text-mut">—</span>;
  const happy = point.happiness_level?.available ? point.happiness_level.median : "—";
  const wellbeing = point.wellbeing_level?.available ? point.wellbeing_level.median : "—";
  return <span className="rounded-lg bg-bg/50 p-2 text-sub">행복 {happy}<br/>웰빙 {wellbeing}<br/><small>n={point.sample_n}</small></span>;
}
