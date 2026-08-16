import { Card, Caption } from "../ui.jsx";
import { labelOf } from "../../data/prediction.js";

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

function RatePair({ a, b }) {
  if (!a?.available && !b?.available) return null;
  return (
    <div className="rounded-xl border border-white/[.06] bg-white/[.02] p-3">
      <div className="mb-2 text-center text-[11px] text-sub">{a?.label || b?.label}</div>
      <div className="flex items-center justify-center gap-8">
        <RateRing label="A" item={a} color="#A98BEE" />
        <RateRing label="B" item={b} color="#F5C86B" />
      </div>
    </div>
  );
}

function RateRing({ label, item, color }) {
  const percent = item?.rate == null ? 0 : Math.max(0, Math.min(100, item.rate * 100));
  return (
    <div className="text-center">
      <div className="relative flex h-[72px] w-[72px] items-center justify-center rounded-full" style={{ background: `conic-gradient(${color} ${percent}%, rgba(255,255,255,.08) ${percent}% 100%)` }}>
        <div className="absolute inset-[6px] rounded-full bg-[#0E1424]" />
        <div className="relative"><b className="block text-[9px]" style={{ color }}>{label}</b><span className="text-[11px] font-semibold text-ink">{item?.rate == null ? "—" : `${percent.toFixed(1)}%`}</span></div>
      </div>
      {item?.n ? <span className="mt-1 block text-[8px] text-mut">n={item.n}</span> : null}
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

function QualityPair({ a, b }) {
  if (!a?.available && !b?.available) return null;
  return (
    <div className="rounded-xl border border-white/[.06] bg-white/[.02] p-3">
      <div className="mb-2 text-center text-[11px] text-sub">{a?.label || b?.label}</div>
      <div className="flex items-start justify-center gap-8">
        <QualityRing label="A" item={a} color="#A98BEE" />
        <QualityRing label="B" item={b} color="#F5C86B" />
      </div>
    </div>
  );
}

function QualityRing({ label, item, color }) {
  if (!item?.available) return <div className="flex h-[72px] w-[72px] items-center justify-center rounded-full border border-white/10 text-[9px] text-mut">{label} · 부족</div>;
  const values = [item.improved_rate || 0, item.unchanged_rate || 0, item.worsened_rate || 0].map((v) => v * 100);
  const improvedEnd = values[0];
  const unchangedEnd = values[0] + values[1];
  return (
    <div className="text-center">
      <div
        className="relative flex h-[72px] w-[72px] items-center justify-center rounded-full"
        style={{ background: `conic-gradient(#62C9A7 0 ${improvedEnd}%, #657087 ${improvedEnd}% ${unchangedEnd}%, #D97882 ${unchangedEnd}% 100%)` }}
      >
        <div className="absolute inset-[7px] rounded-full bg-[#0E1424]" />
        <div className="relative"><b className="block text-[9px]" style={{ color }}>{label}</b><span className="text-[10px] font-semibold text-ink">개선 {values[0].toFixed(0)}%</span></div>
      </div>
      <span className="mt-1 block text-[8px] text-mut">유지 {values[1].toFixed(0)} · 악화 {values[2].toFixed(0)}</span>
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
