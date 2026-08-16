import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import { Card, Caption } from "../ui.jsx";
import { labelOf } from "../../data/prediction.js";

// 리스크 — risk_timeline. 이직=재이직 확률 / 창업=폐업 확률 / 진학=없음.
export default function RiskView({ a, b }) {
  const sides = [a, b].filter((s) => Object.keys(s.risk_timeline || {}).length > 0);
  if (!sides.length) {
    return <Card><Caption>선택한 두 갈래 모두 리스크 타임라인 데이터가 없습니다.</Caption></Card>;
  }
  return <div>{sides.map((s, i) => <SideRisk key={i} result={s} />)}</div>;
}

function SideRisk({ result }) {
  const data = Object.entries(result.risk_timeline)
    .map(([y, p]) => ({ year: `${y}년`, pct: Math.round(p * 100) }))
    .sort((x, y) => parseInt(x.year) - parseInt(y.year));

  return (
    <Card>
      <h2 className="mb-1 flex items-center gap-2 text-base font-semibold">
        {labelOf(result.choice)} · {result.risk_label}
      </h2>
      <div className="mt-2 h-[160px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 12, left: -14, bottom: 0 }}>
            <CartesianGrid stroke="#1E2740" vertical={false} />
            <XAxis dataKey="year" tick={{ fill: "#7E8DAB", fontSize: 11 }} axisLine={{ stroke: "#2A3550" }} tickLine={false} />
            {/* 실데이터는 10년차 이탈확률이 80%를 넘는다(KLIPS 기준 84.7%) → 0~100 고정 */}
            <YAxis domain={[0, 100]} tickFormatter={(v) => `${v}%`} tick={{ fill: "#7E8DAB", fontSize: 11 }} axisLine={false} tickLine={false} />
            <Tooltip contentStyle={{ background: "#141B2E", border: "1px solid #28324D", borderRadius: 10, fontSize: 12, color: "#EAF0FB" }} formatter={(v) => [`${v}%`, result.risk_label]} />
            <Line type="monotone" dataKey="pct" stroke="#EE8888" strokeWidth={2} dot={{ r: 3, fill: "#EE8888" }} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <Caption>
        {result.choice === "이직"
          ? "개인 패널을 학습한 생존모델이 추정한 해당 연차까지의 재이동 가능성입니다."
          : result.choice === "휴식"
            ? "쉬기 시작한 뒤 그 시점에도 아직 일로 돌아오지 못했을 확률입니다. 다른 갈래와 달리 시간이 갈수록 내려갑니다(대부분 결국 돌아오기 때문)."
            : "창업한 사업체 중 해당 연차까지 폐업한 비율(1−생존율)입니다."}{" "}
        개인의 확정적인 미래가 아니라 참고 가능한 집단 수준 정보입니다.
      </Caption>
    </Card>
  );
}
