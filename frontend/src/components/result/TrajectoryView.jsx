import {
  ComposedChart, Area, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart,
} from "recharts";
import { Card, Caption } from "../ui.jsx";
import { A_COLOR, B_COLOR } from "../../data/result.js";
import { labelOf } from "../../data/prediction.js";

// 종단 궤적(L5) — 각 갈래의 실제 소득 분포(p25~p75 밴드+중앙값) + 만족도 궤적.
// '예측'이 아니라 '관찰된 분포'. sample_n 감소 = 불확실.
export default function TrajectoryView({ a, b }) {
  const wb = a.wellbeing_trajectory || [];
  const wbData = wb.map((p) => ({ year: `${p.year}년`, 만족도: p.satis_p50 }));

  return (
    <div>
      <IncomeBand result={a} color={A_COLOR} />
      <IncomeBand result={b} color={B_COLOR} />

      {wbData.length > 0 && (
        <Card>
          <h2 className="mb-1 flex items-center gap-2 text-base font-semibold">
            만족도 궤적
            <span className="rounded-[10px] border border-line px-1.5 py-0.5 text-[10px] font-normal text-mut">
              1~5점 · 관찰 {a.meta?.observe_years_wellbeing}년
            </span>
          </h2>
          <div className="mt-2 h-[150px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={wbData} margin={{ top: 8, right: 12, left: -14, bottom: 0 }}>
                <CartesianGrid stroke="#1E2740" vertical={false} />
                <XAxis dataKey="year" tick={{ fill: "#7E8DAB", fontSize: 11 }} axisLine={{ stroke: "#2A3550" }} tickLine={false} />
                <YAxis domain={[1, 5]} tick={{ fill: "#7E8DAB", fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ background: "#141B2E", border: "1px solid #28324D", borderRadius: 10, fontSize: 12, color: "#EAF0FB" }} />
                <Line type="monotone" dataKey="만족도" stroke="#7FE0D4" strokeWidth={2} dot={{ r: 2.5 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <Caption>종합 만족도(1~5)의 시간 변화. 청년패널(YP) 기준이라 청년 범위 밖이면 제공되지 않습니다.</Caption>
        </Card>
      )}
    </div>
  );
}

function IncomeBand({ result, color }) {
  const traj = result.trajectory || [];
  const hasChoiceSpecificTrajectory = !result.trajectory_is_baseline || ["유지", "현상 유지"].includes(result.choice);
  if (!hasChoiceSpecificTrajectory) {
    return (
      <Card>
        <h2 className="text-base font-semibold">{labelOf(result.choice)} · 소득 흐름</h2>
        <p className="mt-2 text-[12px] leading-relaxed text-sub">
          이 선택에 맞는 장기 소득 흐름은 아직 제공하지 않아요.
        </p>
      </Card>
    );
  }
  const data = traj.map((p) => ({
    year: `${p.year}년`,
    lower: p.income_p25,
    band: p.income_p75 - p.income_p25,
    p50: p.income_p50,
    sample_n: p.sample_n,
  }));
  const minN = traj.length ? Math.min(...traj.map((p) => p.sample_n)) : 0;

  return (
    <Card>
      <h2 className="mb-1 flex items-center gap-2 text-base font-semibold">
        {labelOf(result.choice)} · 소득 궤적
        <span className="rounded-[10px] border border-line px-1.5 py-0.5 text-[10px] font-normal text-mut">
          관찰 {result.meta?.observe_years_income}년
        </span>
      </h2>
      <div className="mt-2 h-[190px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 8, right: 12, left: -14, bottom: 0 }}>
            <CartesianGrid stroke="#1E2740" vertical={false} />
            <XAxis dataKey="year" tick={{ fill: "#7E8DAB", fontSize: 11 }} axisLine={{ stroke: "#2A3550" }} tickLine={false} />
            <YAxis tick={{ fill: "#7E8DAB", fontSize: 11 }} axisLine={false} tickLine={false} />
            <Tooltip
              contentStyle={{ background: "#141B2E", border: "1px solid #28324D", borderRadius: 10, fontSize: 12, color: "#EAF0FB" }}
              formatter={(v, name) => (name === "p50" ? [`${v}만원`, "중앙값"] : null)}
              labelFormatter={(l, p) => `${l} · 추적 ${p?.[0]?.payload?.sample_n}명`}
            />
            <Area dataKey="lower" stackId="b" stroke="none" fill="transparent" isAnimationActive={false} />
            <Area dataKey="band" stackId="b" stroke="none" fill={color} fillOpacity={0.15} isAnimationActive={false} />
            <Line type="monotone" dataKey="p50" stroke={color} strokeWidth={2} dot={{ r: 2.5 }} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <Caption>
        가운데 선=중앙값, 옅은 띠=하위25~상위75%. 뒤 연차일수록 추적 인원이 줄어(마지막 {minN}명)
        불확실합니다. 예측이 아니라 관찰된 분포입니다.
      </Caption>
    </Card>
  );
}
