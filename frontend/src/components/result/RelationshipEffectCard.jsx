// 관계 영역 개인단위 인과효과(ATE + 95% CI).
//
// 왜 KowepsEvidenceCard 와 따로 두는가 — 그 카드는 '사건군과 비교군의 관측 평균차'다.
// 여기 값은 처치효과(LinearDML, 직전 같은 문항 통제)라 근거 강도가 한 단계 위고,
// 같이 그리면 두 성격이 뭉개진다. 기획안의 근거 강도 3단계를 화면에서 유지한다.
//
// 표시 규칙 (기획안 4장 "화면에 박아둔 규칙들"):
//  · 신뢰구간이 0을 포함하면 막대를 그리지 않는다. 견줄 데 없는 숫자에 길이를 주면
//    그 길이가 곧 판단으로 읽힌다. 대신 "구분되지 않음"으로 적는다.
//  · 5점 척도는 점 단위로 크기 감이 안 잡히므로 대조군 SD 대비(ate_sd)를 함께 쓴다.
//  · 단순 평균차(naive_diff)를 같이 보여준다. ATE 와 벌어진 폭이 곧 "그냥 평균
//    비교로 냈으면 얼마나 틀렸는가"다.

import { Info, TrendingUp, TrendingDown, Minus } from "lucide-react";

const COLORS = { A: "#B79BF5", B: "#F5C86B" };

// 막대 길이는 SD 기준. 0.4SD 를 가득 찬 막대로 두면 관계 효과(0.02~0.38SD)가
// 한 화면에서 서로 비교된다. 상한을 넘으면 잘리되 값은 그대로 적는다.
const SD_FULL = 0.4;

function barWidth(sd) {
  const ratio = Math.min(Math.abs(Number(sd) || 0) / SD_FULL, 1);
  return `${Math.max(ratio * 100, 2)}%`;
}

function EffectRow({ effect, color }) {
  const { label, ate, ci_low, ci_high, ate_sd, naive_diff, significant, n_treated } = effect;
  const up = Number(ate) > 0;
  const Icon = !significant ? Minus : up ? TrendingUp : TrendingDown;

  return (
    <div className="border-t border-white/[.06] py-2.5 first:border-t-0">
      <div className="flex items-center justify-between gap-3">
        <span className="flex items-center gap-1.5 text-[11px] text-sub">
          <Icon size={12} className={significant ? "" : "text-mut"} />
          {label}
        </span>
        <span className="shrink-0 text-right text-[11px]">
          {significant ? (
            <b className="text-ink">{ate > 0 ? "+" : ""}{Number(ate).toFixed(3)}점</b>
          ) : (
            <span className="text-mut">구분되지 않음</span>
          )}
        </span>
      </div>

      {/* 유의할 때만 막대. 비유의는 길이를 주지 않는다. */}
      {significant && (
        <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-white/[.06]">
          <div className="h-full rounded-full"
               style={{ width: barWidth(ate_sd), background: color, opacity: up ? 1 : 0.55 }} />
        </div>
      )}

      <div className="mt-1 text-[9px] leading-relaxed text-mut">
        95% CI {Number(ci_low).toFixed(3)} ~ {Number(ci_high).toFixed(3)}
        {ate_sd != null && <> · 대조군 SD 대비 {Number(ate_sd) > 0 ? "+" : ""}{Number(ate_sd).toFixed(2)}SD</>}
        {n_treated != null && <> · 처치 {Number(n_treated).toLocaleString()}명</>}
        {naive_diff != null && (
          <> · 단순 평균차라면 {Number(naive_diff) > 0 ? "+" : ""}{Number(naive_diff).toFixed(3)}</>
        )}
      </div>
    </div>
  );
}

function SideBlock({ side, tag, choice }) {
  const data = side?.relationship_effects;
  const color = COLORS[tag];

  // 값이 없으면 카드를 지우지 않고 왜 없는지를 남긴다 — "켤 수 없는 레이어는
  // 켜지 않았다는 사실을 화면에 표시" 원칙.
  if (!data) {
    const reason = side?.relationship_effects_reason;
    if (!reason) return null;
    return (
      <div className="rounded-xl border border-dashed border-white/10 bg-white/[.02] px-3.5 py-3">
        <div className="text-[11px] font-semibold" style={{ color }}>{tag} · {choice}</div>
        <p className="mt-1 text-[10px] leading-relaxed text-mut">{reason}</p>
      </div>
    );
  }

  const effects = data.effects || [];
  const hit = effects.filter((e) => e.significant);

  return (
    <div className="rounded-xl border border-white/[.08] bg-black/15 px-3.5 py-3">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[11px] font-semibold" style={{ color }}>{tag} · {choice}</span>
        <span className="shrink-0 text-[9px] text-mut">{data.source}</span>
      </div>
      <p className="mt-1 text-[10px] text-mut">
        {hit.length === 0
          ? "이 선택은 관계 만족을 통계적으로 구분할 만큼 바꾸지 않았어요."
          : `관계 ${hit.length}개 축에서 효과가 확인됐어요.`}
      </p>
      <div className="mt-2">
        {effects.map((effect) => (
          <EffectRow key={effect.key} effect={effect} color={color} />
        ))}
      </div>
    </div>
  );
}

export default function RelationshipEffectCard({ a, b }) {
  const any = a?.relationship_effects || b?.relationship_effects
    || a?.relationship_effects_reason || b?.relationship_effects_reason;
  if (!any) return null;

  const estimator = a?.relationship_effects?.estimator || b?.relationship_effects?.estimator;

  return (
    <div className="mb-3 rounded-2xl border border-emerald-400/25 bg-[#101f1b] p-4">
      <div className="flex items-center gap-1.5 text-[12px] font-bold text-emerald-200">
        <TrendingUp size={14} /> 이 선택이 관계에 남기는 것
      </div>
      <p className="mt-1 text-[11px] leading-relaxed text-sub">
        선택 자체의 순효과입니다. 선택한 사람과 안 한 사람의 평균을 그냥 뺀 값이 아니라,
        나이·소득·직종과 <b className="text-ink">직전 같은 문항의 값</b>까지 맞춘 뒤 남은 차이예요.
      </p>

      <div className="mt-3 space-y-2.5">
        <SideBlock side={a} tag="A" choice={a?.choice} />
        <SideBlock side={b} tag="B" choice={b?.choice} />
      </div>

      <div className="mt-3 flex gap-1.5 text-[9px] leading-relaxed text-mut">
        <Info size={12} className="mt-0.5 shrink-0" />
        <span>
          {estimator || "LinearDML"} · 신뢰구간이 0을 포함하면 두 선택이 그 축에서 구분되지 않는다는
          뜻이며, 격차를 지어내지 않고 그대로 비워 둡니다. 자기보고 5점 척도라 점 단위보다
          대조군 표준편차 대비(SD)로 읽는 편이 정확합니다.
        </span>
      </div>
    </div>
  );
}
