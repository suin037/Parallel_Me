import { useEffect, useMemo, useState } from "react";
import { Database, Info } from "lucide-react";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
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

const scaleText = (outcome) => {
  if (["annual_10k_krw", "10k_krw"].includes(outcome.unit)) return "금액 · 만원";
  if (outcome.unit === "monthly_10k_krw") return "월평균 · 만원";
  if (outcome.unit === "hours_per_week") return "시간/주";
  if (Array.isArray(outcome.scale)) return `${outcome.scale[0]}~${outcome.scale[1]}점 · 높을수록 만족`;
  return "설문 응답값";
};

function OutcomeChart({ outcome }) {
  const rows = outcome.trajectory.map((point) => ({
    year: point.wave,
    selected: point.event.mean,
    maintained: point.comparison.mean,
    selectedN: point.event.n,
    maintainedN: point.comparison.n,
  }));
  const money = ["annual_10k_krw", "10k_krw", "monthly_10k_krw"].includes(outcome.unit);
  return (
    <div className="mt-2 h-[116px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={rows} margin={{ top: 5, right: 7, bottom: 0, left: money ? 6 : -18 }}>
          <XAxis dataKey="year" tickFormatter={(v) => `${v}년`} tick={{ fill: "#8791A8", fontSize: 9 }} axisLine={false} tickLine={false} />
          <YAxis domain={money ? ["auto", "auto"] : [1, 5]} tick={{ fill: "#8791A8", fontSize: 8 }} axisLine={false} tickLine={false} width={money ? 38 : 24} />
          <Tooltip
            contentStyle={{ background: "#0C1424", border: "1px solid rgba(255,255,255,.12)", borderRadius: 10, fontSize: 10 }}
            labelFormatter={(v) => `약 ${v}년 후 평균`}
            formatter={(value, name, item) => [valueText(outcome, value), `${name === "selected" ? "선택 집단" : "유지 집단"} (n=${name === "selected" ? item.payload.selectedN : item.payload.maintainedN})`]}
          />
          <Line type="monotone" dataKey="selected" stroke="#A98AE8" strokeWidth={2.2} dot={{ r: 2.5, fill: "#A98AE8" }} connectNulls />
          <Line type="monotone" dataKey="maintained" stroke="#7B879D" strokeWidth={1.6} strokeDasharray="4 3" dot={{ r: 2, fill: "#7B879D" }} connectNulls />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
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
  if (independent) return null;
  if (state.error || !state.data?.available) return null;
  const data = state.data;
  const matched = data.evidence_level === "personalized_matched_observation";
  const matching = data.personalization || {};
  const wanted = preferredOutcomes(data.scenario);
  const outcomes = wanted.map((key) => data.outcomes.find((item) => item.key === key)).filter(Boolean);

  return (
    <div className="mb-3 rounded-2xl border border-violet-400/30 bg-[#151329] p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-1.5 text-[12px] font-bold text-violet-200"><Database size={14} />{matched ? "내 조건 기반 관측" : "KOWEPS 종단 관측"}</div>
          <p className="mt-1 text-[14px] font-semibold text-ink">{data.label}</p>
          <p className="mt-1 text-[10px] text-mut">{matched ? `가까운 조건: ${(matching.applied_features || []).join(" · ")}` : "선택 당시 25~35세였던 사람들의 이후 관측"}</p>
        </div>
        <span className="shrink-0 rounded-full bg-violet-400/10 px-2 py-1 text-[9px] text-violet-200">25~35세</span>
      </div>
      <p className="mt-2 text-[10px] text-mut">사건군 {Number(matching.event_sample_n || data.event_people).toLocaleString()}명 · 비교군 {Number(matching.comparison_sample_n || data.comparison_people).toLocaleString()}명</p>
      <div className="mt-3 space-y-2">
        {outcomes.map((outcome) => (
          <div key={outcome.key} className="rounded-xl border border-white/[.07] bg-black/15 p-3">
            <div className="flex items-center justify-between gap-2">
              <p className="text-[10px] font-semibold text-sub">{LABELS[outcome.key] || outcome.key}</p>
              <p className="text-[8px] text-mut">{scaleText(outcome)}</p>
            </div>
            <OutcomeChart outcome={outcome} />
            <div className="mt-1 flex items-center gap-4 text-[8px] text-mut"><span><i className="mr-1 inline-block h-0.5 w-3 bg-[#A98AE8] align-middle" />선택 집단</span><span><i className="mr-1 inline-block w-3 border-t border-dashed border-[#7B879D] align-middle" />유지 집단</span><span>선은 집단 평균</span></div>
          </div>
        ))}
      </div>
      <div className="mt-3 flex gap-1.5 text-[9px] leading-relaxed text-mut"><Info size={12} className="mt-0.5 shrink-0" /><span>{matching.score_definition || "관측된 집단 분포이며 선택의 인과효과나 개인별 확정 미래가 아닙니다."} {data.coding_note}</span></div>
    </div>
  );
}
