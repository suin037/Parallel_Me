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
  const max = Math.max(a?.rate || 0, b?.rate || 0, .01);
  return (
    <div>
      <div className="mb-1 text-[11px] text-sub">{a?.label || b?.label}</div>
      <RateLine label="A" item={a} max={max} color="#A98BEE" />
      <RateLine label="B" item={b} max={max} color="#F5C86B" />
    </div>
  );
}

function RateLine({ label, item, max, color }) {
  return (
    <div className="mt-1 grid grid-cols-[18px_1fr_92px] items-center gap-2 text-[10px]">
      <b style={{ color }}>{label}</b>
      <div className="h-1.5 overflow-hidden rounded-full bg-[#080D19]"><div className="h-full rounded-full" style={{ width: `${item?.rate == null ? 0 : item.rate / max * 100}%`, backgroundColor: color }} /></div>
      <span className="text-right text-sub">{item?.rate == null ? "—" : `${(item.rate * 100).toFixed(1)}%`} {item?.n ? `· n=${item.n}` : ""}</span>
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
    <div>
      <div className="mb-1 text-[11px] text-sub">{a?.label || b?.label}</div>
      <QualityLine label="A" item={a} color="#A98BEE" />
      <QualityLine label="B" item={b} color="#F5C86B" />
    </div>
  );
}

function QualityLine({ label, item, color }) {
  if (!item?.available) return <div className="text-[10px] text-mut">{label} · 관측 부족</div>;
  const values = [item.improved_rate || 0, item.unchanged_rate || 0, item.worsened_rate || 0].map((v) => v * 100);
  return (
    <div className="mt-1 grid grid-cols-[18px_1fr_116px] items-center gap-2 text-[9px]">
      <b style={{ color }}>{label}</b>
      <div className="flex h-2 overflow-hidden rounded-full bg-[#080D19]">
        <div className="bg-[#62C9A7]" style={{ width: `${values[0]}%` }} />
        <div className="bg-[#657087]" style={{ width: `${values[1]}%` }} />
        <div className="bg-[#D97882]" style={{ width: `${values[2]}%` }} />
      </div>
      <span className="text-right text-mut">개선 {values[0].toFixed(0)} · 유지 {values[1].toFixed(0)} · 악화 {values[2].toFixed(0)}</span>
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
