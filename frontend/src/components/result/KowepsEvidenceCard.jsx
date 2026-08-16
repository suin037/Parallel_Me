import { useEffect, useMemo, useState } from "react";
import { Database, Info } from "lucide-react";
import { getKowepsEvidence } from "../../api.js";

const LABELS = {
  disposable_income: "연간 가처분소득",
  bank_deposits: "예금",
  installment_savings: "적금",
  stocks_bonds: "주식·채권",
  financial_loan: "금융기관 대출",
  card_debt: "카드빚",
  living_expenses: "월 생활비",
  medical_expenses: "월 보건의료비",
  medical_visits: "연간 외래진료",
  smoking_amount: "하루 흡연량",
  weekly_work_hours: "주당 근로시간",
  job_satisfaction: "직업 만족도",
  health_satisfaction: "건강 만족도",
  housing_satisfaction: "주거 만족도",
  family_satisfaction: "가족관계 만족도",
  leisure_satisfaction: "여가 만족도",
  overall_satisfaction: "전반적 만족도",
};

function preferredOutcomes(scenario) {
  if (scenario?.startsWith("finance.")) return ["installment_savings", "financial_loan", "living_expenses"];
  if (scenario?.startsWith("lifestyle.")) return ["weekly_work_hours", "leisure_satisfaction", "overall_satisfaction"];
  if (scenario?.startsWith("housing.")) return ["disposable_income", "housing_satisfaction", "overall_satisfaction"];
  if (scenario?.startsWith("relationship.")) return ["disposable_income", "family_satisfaction", "overall_satisfaction"];
  if (scenario?.startsWith("career.")) return ["disposable_income", "job_satisfaction", "overall_satisfaction"];
  if (scenario?.startsWith("education.")) return ["disposable_income", "job_satisfaction", "overall_satisfaction"];
  return ["disposable_income", "health_satisfaction", "overall_satisfaction"];
}

const valueText = (outcome, value) => {
  if (value == null) return "—";
  if (["annual_10k_krw", "10k_krw", "monthly_10k_krw"].includes(outcome.unit)) return `${Math.round(value).toLocaleString()}만원`;
  if (outcome.unit === "hours_per_week") return `${Number(value).toFixed(1)}시간`;
  return `${Number(value).toFixed(1)}점`;
};

function lastObservation(outcome) {
  const point = outcome.trajectory?.at(-1);
  if (typeof point?.event?.mean !== "number" || typeof point?.comparison?.mean !== "number") return null;
  const difference = point.event.mean - point.comparison.mean;
  const money = ["annual_10k_krw", "10k_krw", "monthly_10k_krw"].includes(outcome.unit);
  const noticeable = money
    ? Math.abs(difference) / Math.max(Math.abs(point.comparison.mean), 1) >= 0.05
    : outcome.unit === "hours_per_week"
      ? Math.abs(difference) >= 1
      : Math.abs(difference) >= 0.15;
  return { outcome, point, difference, noticeable };
}

function observationHeadline(observations) {
  const notable = observations
    .filter((item) => item.noticeable)
    .sort((left, right) => Math.abs(right.difference) - Math.abs(left.difference))[0];
  if (!notable) return "관측 집단에서는 눈에 띄는 평균 차이가 크지 않았어요.";
  const label = LABELS[notable.outcome.key] || notable.outcome.key;
  return `${label}에서 사건군 평균이 비교군보다 ${notable.difference > 0 ? "높게" : "낮게"} 관측됐어요.`;
}

export default function KowepsEvidenceCard({ a, b, domains }) {
  const independent = a.koweps_evidence?.available && b.koweps_evidence?.available
    && a.koweps_evidence.scenario !== b.koweps_evidence.scenario;
  const embedded = a.koweps_evidence || b.koweps_evidence || null;
  const [state, setState] = useState({ loading: !embedded, data: embedded, error: null });
  const payload = useMemo(() => ({
    choice_a: a.choice, choice_b: b.choice,
    choice_a_detail: a.detail || "", choice_b_detail: b.detail || "",
    choice_a_domains: domains?.a || [], choice_b_domains: domains?.b || [],
  }), [a.choice, b.choice, a.detail, b.detail, domains]);

  useEffect(() => {
    if (embedded?.available) {
      setState({ loading: false, data: embedded, error: null });
      return undefined;
    }
    let alive = true;
    setState({ loading: true, data: null, error: null });
    getKowepsEvidence(payload)
      .then((data) => alive && setState({ loading: false, data, error: null }))
      .catch((error) => alive && setState({ loading: false, data: null, error: error.message }));
    return () => { alive = false; };
  }, [payload, embedded]);

  if (state.loading) return <div className="mb-3 rounded-2xl border border-white/10 bg-card p-4 text-[11px] text-mut">KOWEPS 관측 근거 확인 중…</div>;
  if (independent) {
    return (
      <div className="space-y-3">
        <CompactObservation data={a.koweps_evidence} tag="A" choice={a.choice} independent />
        <CompactObservation data={b.koweps_evidence} tag="B" choice={b.choice} independent />
      </div>
    );
  }
  if (state.error || !state.data?.available) return null;
  return <CompactObservation data={state.data} />;
}

function CompactObservation({ data, tag, choice, independent = false }) {
  const matched = data.evidence_level === "personalized_matched_observation";
  const matching = data.personalization || {};
  const wanted = preferredOutcomes(data.scenario);
  const outcomes = wanted.map((key) => data.outcomes?.find((item) => item.key === key)).filter(Boolean);
  const observations = outcomes.map(lastObservation).filter(Boolean);
  const eventCount = Number(matching.event_sample_n || data.event_people || 0);
  const comparisonCount = Number(matching.comparison_sample_n || data.comparison_people || 0);

  return (
    <div className="rounded-2xl border border-violet-400/30 bg-[#151329] p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-1.5 text-[12px] font-bold text-violet-200">
            <Database size={14} />{tag ? `${tag} · ${choice}` : matched ? "내 조건 기반 집단 관측" : "KOWEPS 집단 관측"}
          </div>
          <p className="mt-1 text-[12px] text-sub">{data.label}</p>
        </div>
        <span className="shrink-0 rounded-full bg-violet-400/10 px-2 py-1 text-[9px] text-violet-200">25~35세</span>
      </div>
      <div className="mt-3 rounded-xl border border-white/[.07] bg-black/15 px-3.5 py-3">
        <p className="text-[13px] font-semibold leading-relaxed text-ink">{observationHeadline(observations)}</p>
        <p className="mt-1.5 text-[10px] text-mut">
          사건군 {eventCount.toLocaleString()}명 · 비교군 {comparisonCount.toLocaleString()}명
        </p>
      </div>

      <details className="group mt-3 rounded-xl border border-white/[.07] bg-white/[.025] px-3 py-2.5">
        <summary className="cursor-pointer list-none text-[11px] font-semibold text-violet-200">
          관측값과 비교 기준 자세히 보기
        </summary>
        {observations.length > 0 && (
          <div className="mt-3 space-y-2">
            {observations.map(({ outcome, point }) => (
              <div key={outcome.key} className="flex items-center justify-between gap-3 border-t border-white/[.06] pt-2 text-[10px]">
                <span className="text-sub">{point.wave}년 뒤 · {LABELS[outcome.key] || outcome.key}</span>
                <span className="shrink-0 text-right text-mut">
                  사건군 <b className="text-ink">{valueText(outcome, point.event.mean)}</b>
                  <span className="mx-1">·</span>
                  비교군 <b className="text-ink">{valueText(outcome, point.comparison.mean)}</b>
                </span>
              </div>
            ))}
          </div>
        )}
        {matching.applied_features?.length > 0 && (
          <p className="mt-3 text-[9px] leading-relaxed text-mut">가까운 조건 · {matching.applied_features.join(" · ")}</p>
        )}
      </details>

      <div className="mt-3 flex gap-1.5 text-[9px] leading-relaxed text-mut">
        <Info size={12} className="mt-0.5 shrink-0" />
        <span>
          {independent && "A와 B를 직접 비교한 결과가 아니라, 이 선택의 사건군과 미발생 집단을 비교했습니다. "}
          {matching.score_definition || data.claim_limit || "집단 평균 관측이며 개인의 확정 미래나 선택의 인과효과가 아닙니다."}
        </span>
      </div>
    </div>
  );
}
