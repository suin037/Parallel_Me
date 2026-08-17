import { ChevronDown } from "lucide-react";
import { Caption } from "../ui.jsx";
import ObservedIndicators from "./ObservedIndicators.jsx";
import IndicatorGapChart from "./IndicatorGapChart.jsx";
import { SIDE_COLORS } from "./DivergingBar.jsx";
import { AXES } from "../../api.js";

// 숫자가 먼저, 근거는 그 다음. 전에는 '예측 근거 신뢰도'가 맨 위에 있어서
// 첫 화면이 통째로 "이 숫자를 믿어도 되는가"였고, 정작 A와 B가 뭐가 다른지는
// 스크롤 아래에 있었다. 근거를 없애지는 않는다 — 강도 요약 한 줄은 항상 보이고
// 항목별 내역만 접어 둔다.
export default function LifeView({ a, b, domains = { a: [], b: [] } }) {
  return (
    <div>
      <IndicatorGapChart a={a} b={b} domains={domains} />
      <ObservedIndicators a={a} b={b} />
      <EvidenceSummary a={a} b={b} domains={domains} />
    </div>
  );
}

const EVIDENCE_LABEL = {
  directional_evidence: "방향 근거 있음",
  matched_observation: "유사 사례 관측 근거",
  insufficient_evidence: "근거 부족",
  reference_only: "참고 통계만",
  user_provided_state: "현재 상태 입력",
  observed_group: "종단 집단 관측",
  proxy_observation: "부분 관측 근거",
};

// 근거 강도 3단계. 채워진 칸 수가 곧 "이 숫자를 얼마나 믿어도 되는가"다.
//   3 = 개인 조건 인과모델까지 검증  2 = 유사 조건 집단의 실제 관측  1 = 참고 통계(선택 효과 아님)
const EVIDENCE_STRENGTH = {
  directional_evidence: 3,
  matched_observation: 2,
  observed_group: 2,
  proxy_observation: 2,
  user_provided_state: 1,
  reference_only: 1,
  insufficient_evidence: 0,
};

/** 근거 설명에서 내부 컬럼명 나열("· 직접 결과: disposable_income, …")을 잘라낸다. */
function readableReason(reason) {
  if (!reason) return "";
  const cut = reason.split(/\s*·\s*(?:직접 결과|일부 대리지표|미측정)\s*:/)[0];
  return cut.length > 120 ? `${cut.slice(0, 120)}…` : cut;
}

// 근거 강도를 나타내는 모양은 **하나뿐**이어야 한다.
// 예전엔 범례가 도트(h-1 w-2), 항목 행이 막대(h-1.5 w-4)로 서로 다른 그림이었고,
// 영역 근거 행에는 아예 강도 표시가 없었다(같은 3단계 척도인데도). 그래서 같은
// 카드 안에서 강도를 세 가지 방식으로 읽어야 했다. 이제 전부 이 Meter 를 쓴다.
const LEVEL_TONE = { 3: "rgba(255,255,255,.72)", 2: "rgba(255,255,255,.4)", 1: "rgba(255,255,255,.17)" };

function Meter({ level, side }) {
  // 색은 A/B 를 가리키고, 채워진 칸 수가 강도를 가리킨다. 범례처럼 쪽이 없는
  // 자리에서는 회색 톤을 쓴다.
  const color = side ? SIDE_COLORS[side] : "rgba(255,255,255,.6)";
  return (
    <span className="flex shrink-0 gap-[3px]" aria-label={`근거 강도 3단계 중 ${level}단계`}>
      {[1, 2, 3].map((i) => (
        <i
          key={i}
          className="h-1.5 w-3.5 rounded-full"
          style={{ background: i <= level ? color : "rgba(255,255,255,.09)" }}
        />
      ))}
    </span>
  );
}

// 접힌 상태에서 보이는 한 줄 요약. 숫자를 나열하는 대신 강도 구성비를 막대로
// 그린다 — 펴보지 않아도 "대부분 참고 통계"인지 "개인모델이 절반"인지 보인다.
function StrengthMix({ tally, total }) {
  if (!total) return null;
  return (
    <span className="flex h-1.5 w-16 shrink-0 overflow-hidden rounded-full bg-white/[.08]" aria-hidden="true">
      {[3, 2, 1].map((level) => (tally[level] > 0 ? (
        <i key={level} style={{ flex: tally[level], background: LEVEL_TONE[level] }} />
      ) : null))}
    </span>
  );
}

/**
 * 근거 한 줄. 영역 근거와 지표 근거가 같은 격자를 쓴다 —
 * [쪽] [강도 미터] [근거 이름] [부가]. 한쪽 데이터가 없어도 행은 남겨서
 * A와 B가 항상 같은 자리에 오게 한다(예전엔 없는 쪽 행이 통째로 사라져
 * 'B는 근거가 약함'과 'B는 표시 안 됨'이 구분되지 않았다).
 */
function EvidenceRow({ side, level, label, meta, reason }) {
  const empty = !level;
  return (
    <div className="mt-1.5 grid grid-cols-[0.75rem_3.1rem_minmax(0,1fr)_auto] items-center gap-2">
      <b className="text-[10px] font-black" style={{ color: SIDE_COLORS[side] }}>{side}</b>
      <Meter level={level} side={empty ? null : side} />
      <span className={`min-w-0 truncate text-[11px] ${empty ? "text-mut" : "text-sub"}`} title={reason || label}>
        {label}
      </span>
      {meta && <span className="shrink-0 whitespace-nowrap text-[9px] text-mut">{meta}</span>}
    </div>
  );
}

/** 강도 3단계의 이름. 범례·요약·행이 전부 이 표현을 쓴다. */
const STRENGTH_NAME = { 3: "개인모델 검증", 2: "집단통계", 1: "참고 통계", 0: "근거 부족" };

/** 영역 근거(domain_stats)의 강도. 항목별 근거(EVIDENCE_STRENGTH)와 같은 3단계로 맞춘다. */
const DOMAIN_STRENGTH = { model: 3, group_stat: 2, rag: 1 };
const DOMAIN_EVIDENCE_LABEL = {
  model: "개인 조건 모델",
  group_stat: "유사 조건 집단통계",
  rag: "기록·논문 해석",
};
const domainStrength = (item) =>
  (item?.status === "available" ? DOMAIN_STRENGTH[item.evidence] ?? 1 : 0);

function EvidenceSummary({ a, b, domains }) {
  const defaultOrder = AXES;
  const preferred = a.personalization?.narrate_order || b.personalization?.narrate_order || [];
  const keys = [...new Set([...preferred, ...defaultOrder])].filter((key) => {
    if (!defaultOrder.includes(key)) return false;
    const statuses = [a.indicator_evidence?.[key]?.status, b.indicator_evidence?.[key]?.status].filter(Boolean);
    // 근거가 없는 축은 여기서 뺀다. 'unmeasured'(자기실현처럼 아예 측정 문항이
    // 없는 축)도 같이 빠진다 — 없는 근거를 근거 요약에 올릴 수는 없다.
    return statuses.some((status) => status !== "insufficient_evidence" && status !== "unmeasured");
  });
  const selectedDomains = [...new Set([...(domains?.a || []), ...(domains?.b || [])])];
  const domainEvidence = selectedDomains.map((domain) => {
    const left = a.domain_stats?.[domain];
    const right = b.domain_stats?.[domain];
    if (!left && !right) return null;
    return { domain, label: left?.label || right?.label || domain, left, right };
  }).filter(Boolean);
  if (!keys.length && !domainEvidence.length) return null;

  // 접힌 상태에서도 "무엇이 몇 개나 뒷받침되는가"는 보이게 한다. 가장 강한 근거만
  // 골라 한 줄로 쓰면 실제보다 단단해 보인다 — 강도별 개수를 그대로 센다.
  const tally = [0, 0, 0, 0];
  for (const row of domainEvidence) {
    for (const item of [row.left, row.right]) if (item) tally[domainStrength(item)] += 1;
  }
  for (const key of keys) {
    for (const item of [a.indicator_evidence?.[key], b.indicator_evidence?.[key]]) {
      if (!item || item.status === "insufficient_evidence") continue;
      tally[EVIDENCE_STRENGTH[item.status] ?? 0] += 1;
    }
  }
  const total = tally[1] + tally[2] + tally[3];
  const strongest = tally[3] > 0 ? 3 : tally[2] > 0 ? 2 : tally[1] > 0 ? 1 : 0;

  return (
    <details className="group my-2.5 rounded-[18px] bg-card px-4 py-3.5">
      {/* 접힌 줄에는 딱 두 가지만 — 강도 구성비 막대와 "N개 항목 중 가장 강한 근거".
          예전엔 "개인모델 검증 2 · 집단통계 3 · 참고 통계만 1" 이라는 숫자 나열이라
          한눈에 강한지 약한지 판단이 안 됐다. */}
      <summary className="flex cursor-pointer list-none items-center gap-2.5">
        <span className="shrink-0 text-[13px] font-semibold text-ink">이 숫자의 근거</span>
        {total > 0 ? (
          <span className="flex min-w-0 flex-1 items-center gap-2">
            <StrengthMix tally={tally} total={total} />
            <span className="truncate text-[10.5px] text-mut">
              {total}개 항목 · 최고 {STRENGTH_NAME[strongest]}
            </span>
          </span>
        ) : (
          <span className="min-w-0 flex-1 truncate text-[10.5px] text-mut">근거 정보 없음</span>
        )}
        <ChevronDown size={15} className="shrink-0 text-mut transition-transform group-open:rotate-180" />
      </summary>

      {/* 범례도 본문 행과 똑같은 미터 모양을 쓴다 — 모양이 다르면 범례가 아니다. */}
      <div className="mt-2.5 flex flex-wrap items-center gap-x-3 gap-y-1.5 rounded-xl bg-white/[.03] px-3 py-2 text-[9px] text-mut">
        {[3, 2, 1].map((level) => (
          <span key={level} className="flex items-center gap-1.5"><Meter level={level} /> {STRENGTH_NAME[level]}</span>
        ))}
        <span className="text-[8.5px]">칸이 많이 찰수록 강한 근거</span>
      </div>
      {preferred.length > 0 && <Caption>중요하게 생각하는 기준부터 A와 B의 차이를 설명해요.</Caption>}

      <div className="mt-3 space-y-2">
        {domainEvidence.map((row) => (
          <EvidenceCard key={`domain-${row.domain}`} kind="영역" title={row.label} accent>
            {["A", "B"].map((side) => {
              const item = side === "A" ? row.left : row.right;
              const available = item?.status === "available";
              return (
                <EvidenceRow
                  key={side}
                  side={side}
                  level={domainStrength(item)}
                  label={available ? DOMAIN_EVIDENCE_LABEL[item.evidence] || "정량 근거 없음" : "연결 가능한 수치 없음"}
                  meta={available && item.indicators?.length ? `지표 ${item.indicators.length}개` : null}
                />
              );
            })}
          </EvidenceCard>
        ))}
        {keys.map((key) => {
          const left = a.indicator_evidence?.[key];
          const right = b.indicator_evidence?.[key];
          if (!left && !right) return null;
          return (
            <EvidenceCard key={key} kind="지표" title={key}>
              {["A", "B"].map((side) => {
                const item = side === "A" ? left : right;
                const usable = item && item.status !== "insufficient_evidence";
                // 집단 평균 효과는 있을 때만 이름 뒤에 붙인다.
                const effect = usable && typeof item.effect === "number"
                  ? `${item.effect >= 0 ? "+" : ""}${item.effect.toFixed(1)}%p`
                  : null;
                return (
                  <EvidenceRow
                    key={side}
                    side={side}
                    level={usable ? EVIDENCE_STRENGTH[item.status] ?? 0 : 0}
                    label={usable ? EVIDENCE_LABEL[item.status] || item.status : "근거 부족"}
                    meta={effect}
                    // 사유는 한 줄로 접고 전문은 툴팁에 둔다 — 120자 문단이 항목마다
                    // 깔리면 카드가 근거표가 아니라 설명문이 된다.
                    reason={usable ? readableReason(item.reason) : null}
                  />
                );
              })}
            </EvidenceCard>
          );
        })}
      </div>
    </details>
  );
}

function EvidenceCard({ kind, title, accent, children }) {
  return (
    <div className={`rounded-xl border px-3 py-2.5 ${accent ? "border-violet-400/20 bg-violet-500/[.055]" : "border-line bg-bg/40"}`}>
      <div className="flex items-center gap-1.5">
        <span className="rounded bg-white/[.06] px-1.5 py-px text-[8.5px] font-bold text-mut">{kind}</span>
        <span className="min-w-0 truncate text-xs font-semibold text-ink">{title}</span>
      </div>
      {children}
    </div>
  );
}
