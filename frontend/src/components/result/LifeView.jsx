import { ChevronDown } from "lucide-react";
import { Caption } from "../ui.jsx";
import ObservedIndicators from "./ObservedIndicators.jsx";
import IndicatorGapChart from "./IndicatorGapChart.jsx";

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

/** 범례용 미니 도트 — 강도 n을 회색 톤으로 보여준다. */
function Dots({ n }) {
  return (
    <span className="flex gap-[2px]">
      {[1, 2, 3].map((i) => (
        <i
          key={i}
          className="h-1 w-2 rounded-full"
          style={{ background: i <= n ? "rgba(255,255,255,.55)" : "rgba(255,255,255,.12)" }}
        />
      ))}
    </span>
  );
}

function StrengthMeter({ level, side }) {
  const color = side === "A" ? "#8B6CCF" : "#F5C86B";
  return (
    <span className="flex shrink-0 gap-[3px]" aria-label={`근거 강도 3단계 중 ${level}단계`}>
      {[1, 2, 3].map((i) => (
        <i
          key={i}
          className="h-1.5 w-4 rounded-full"
          style={{ background: i <= level ? color : "rgba(255,255,255,.09)" }}
        />
      ))}
    </span>
  );
}

/** 영역 근거(domain_stats)의 강도. 항목별 근거(EVIDENCE_STRENGTH)와 같은 3단계로 맞춘다. */
const DOMAIN_STRENGTH = { model: 3, group_stat: 2, rag: 1 };
const domainStrength = (item) =>
  (item?.status === "available" ? DOMAIN_STRENGTH[item.evidence] ?? 1 : 0);

function EvidenceSummary({ a, b, domains }) {
  const defaultOrder = ["경제적안정도", "성장가능성", "삶의질"];
  const preferred = a.personalization?.narrate_order || b.personalization?.narrate_order || [];
  const keys = [...new Set([...preferred, ...defaultOrder])].filter((key) => {
    if (!defaultOrder.includes(key)) return false;
    const statuses = [a.indicator_evidence?.[key]?.status, b.indicator_evidence?.[key]?.status].filter(Boolean);
    return statuses.some((status) => status !== "insufficient_evidence");
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
  const summary = [[3, "개인모델 검증"], [2, "집단통계"], [1, "참고 통계만"]]
    .filter(([level]) => tally[level] > 0)
    .map(([level, label]) => `${label} ${tally[level]}`)
    .join(" · ");

  return (
    <details className="group my-2.5 rounded-[18px] bg-card px-4 py-3.5">
      <summary className="flex cursor-pointer list-none items-center gap-2.5">
        <span className="shrink-0 text-[13px] font-semibold text-ink">이 숫자의 근거</span>
        <span className="min-w-0 flex-1 truncate text-[10.5px] text-mut">{summary || "근거 정보 없음"}</span>
        <ChevronDown size={15} className="shrink-0 text-mut transition-transform group-open:rotate-180" />
      </summary>

      <div className="mt-2 flex flex-wrap items-center gap-x-2.5 gap-y-1 text-[9px] text-mut">
        <span className="flex items-center gap-1"><Dots n={3} /> 개인모델 검증</span>
        <span className="flex items-center gap-1"><Dots n={2} /> 집단통계</span>
        <span className="flex items-center gap-1"><Dots n={1} /> 참고 통계</span>
      </div>
      <Caption>칸이 많이 찰수록 이 숫자를 뒷받침하는 근거가 강합니다.</Caption>
      {preferred.length > 0 && <Caption>중요하게 생각하는 기준부터 A와 B의 차이를 설명해요.</Caption>}

      <div className="mt-3 space-y-2">
        {domainEvidence.map((row) => (
          <div key={`domain-${row.domain}`} className="rounded-xl border border-violet-400/20 bg-violet-500/[.055] px-3 py-2.5">
            <div className="mb-1 text-xs font-semibold text-ink">{row.label} 영역</div>
            <DomainEvidenceSide label="A" item={row.left} />
            <DomainEvidenceSide label="B" item={row.right} />
          </div>
        ))}
        {keys.map((key) => {
          const left = a.indicator_evidence?.[key];
          const right = b.indicator_evidence?.[key];
          if (!left && !right) return null;
          return (
            <div key={key} className="rounded-xl border border-line bg-bg/40 px-3 py-2.5">
              <div className="mb-1 text-xs font-semibold text-ink">{key}</div>
              <EvidenceSide label="A" item={left} />
              <EvidenceSide label="B" item={right} />
            </div>
          );
        })}
      </div>
    </details>
  );
}

function DomainEvidenceSide({ label, item }) {
  if (!item) return null;
  const available = item.status === "available";
  const evidence = item.evidence === "model" ? "개인 조건 모델"
    : item.evidence === "group_stat" ? "유사 조건 집단통계"
      : item.evidence === "rag" ? "기록·논문 해석" : "정량 근거 없음";
  return (
    <div className="mt-1 flex items-start gap-2 text-[11px] leading-5 text-sub">
      <b className={label === "A" ? "text-violet-300" : "text-[#F5C86B]"}>{label}</b>
      <span>{available ? evidence : "현재 연결 가능한 수치 없음"}</span>
      {available && item.indicators?.length > 0 && <span className="ml-auto whitespace-nowrap text-[9px] text-mut">{item.indicators.length}개 지표</span>}
    </div>
  );
}

function EvidenceSide({ label, item }) {
  if (!item || item.status === "insufficient_evidence") return null;
  const effect = typeof item.effect === "number"
    ? ` · 집단 평균 ${item.effect >= 0 ? "+" : ""}${item.effect.toFixed(1)}%p`
    : "";
  const reason = readableReason(item.reason);
  return (
    <div className="mt-1.5 text-[11px] leading-5 text-sub">
      <div className="flex items-center gap-2">
        <b className={`w-3 shrink-0 ${label === "A" ? "text-violet-300" : "text-[#F5C86B]"}`}>{label}</b>
        <StrengthMeter level={EVIDENCE_STRENGTH[item.status] ?? 0} side={label} />
        <span className="min-w-0">{EVIDENCE_LABEL[item.status] || item.status}{effect}</span>
      </div>
      {reason && <div className="mt-0.5 pl-5 text-[10px] leading-4 text-mut">{reason}</div>}
    </div>
  );
}
