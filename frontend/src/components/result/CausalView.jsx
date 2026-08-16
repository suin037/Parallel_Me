import { Card, Caption } from "../ui.jsx";
import { labelOf } from "../../data/prediction.js";

// 인과(L3) — 개인단위(이직)만. A/B 중 해당 쪽 렌더.
export default function CausalView({ a, b }) {
  const sides = [a, b].filter((s) => s.causal_effect != null);
  if (!sides.length) {
    return <Card><Caption>선택한 두 갈래 모두 인과효과(EconML) 데이터가 없습니다.</Caption></Card>;
  }
  return <div>{sides.map((s, i) => <SideCausal key={i} result={s} />)}</div>;
}

// 실데이터는 음수도 나온다(이직이 소득을 낮추는 추정). 부호를 직접 붙이고 자릿수를 줄인다.
const signed = (v) => `${v > 0 ? "+" : ""}${Number(v).toFixed(1)}`;

// 막대는 '크기'만 표현하고 방향은 색으로 구분한다(음수 폭은 그릴 수 없다).
function Bar({ value, scale, tone }) {
  const pct = scale > 0 ? Math.min(100, (Math.abs(value) / scale) * 100) : 0;
  return (
    <div className="relative my-1.5 h-3.5 rounded-[7px] bg-[#16203A]">
      <span
        className={`absolute inset-y-0 left-0 rounded-[7px] ${tone}`}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

function SideCausal({ result }) {
  const effect = result.causal_effect;
  const descriptive = result.descriptive_effect;
  const ci = result.causal_ci || result.confidence?.causal_effect_ci;
  // 겉보기 효과는 백엔드가 주지 않으면 표시하지 않는다(같은 값을 두 번 그리지 않음).
  const hasDescriptive = descriptive != null && descriptive !== effect;
  const scale = Math.max(Math.abs(effect), Math.abs(descriptive ?? 0)) * 1.14;
  const tone = effect >= 0 ? "bg-cyan" : "bg-[#EE8888]";
  const spansZero =
    ci && ci.ci95_low != null && ci.ci95_high != null && ci.ci95_low <= 0 && ci.ci95_high >= 0;

  return (
    <>
      <Card highlight>
        <div className="text-[11px] font-bold tracking-[2px] text-cyan">
          {labelOf(result.choice)} · 조건 보정 소득효과 (만원)
        </div>
        {hasDescriptive && (
          <>
            <div className="mt-2.5 text-xs text-sub">겉보기 (그냥 비교)</div>
            <Bar value={descriptive} scale={scale} tone="bg-[#8B6CCF] opacity-60" />
            <div className="flex justify-end text-xs font-bold text-ink">{signed(descriptive)}만원</div>
          </>
        )}

        <div className="mt-2.5 text-xs text-sub">조건을 보정한 추정치</div>
        <Bar value={effect} scale={scale} tone={tone} />
        <div className="flex justify-end text-xs font-bold text-ink">{signed(effect)}만원</div>

        {ci && ci.ci95_low != null && (
          <div className="mt-2.5 rounded-xl border border-line bg-[#0E1424] px-3 py-2">
            <div className="text-[11px] text-sub">
              95% 신뢰구간 · {signed(ci.ci95_low)} ~ {signed(ci.ci95_high)}
              {ci.unit ? ci.unit : "만원"}
              {ci.ate != null && <span className="text-mut"> (점추정 {signed(ci.ate)})</span>}
            </div>
            {spansZero && (
              <div className="mt-1 text-[11px] font-semibold text-gold">
                구간이 0을 포함합니다 — 효과가 없을 가능성을 배제하지 못합니다.
              </div>
            )}
            {(ci.method || ci.source) && (
              <div className="mt-1 text-[10px] text-mut">
                {[ci.method, ci.source].filter(Boolean).join(" · ")}
              </div>
            )}
          </div>
        )}

        {hasDescriptive && (
          <Caption className="mt-2.5">
            두 값의 차이는 이직자와 비이직자의 원래 조건 차이를 일부 보정한 결과입니다.
          </Caption>
        )}
      </Card>
      <Caption>
        나이·소득·학력 등 관측 가능한 조건을 보정한 추정치이며, 측정되지 않은 차이까지 제거한 확정
        효과는 아닙니다.
      </Caption>
    </>
  );
}
