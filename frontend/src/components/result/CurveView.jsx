import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import { Card, Caption } from "../ui.jsx";
import { A_COLOR } from "../../data/result.js";

// 곡선: 재이직 리스크 1·2·3년만. 관찰기간(3년)을 넘는 예측은 만들지 않는다.
export default function CurveView({ result }) {
  const { points } = result.survival;
  const data = points.map((p) => ({ year: `${p.year}년`, risk: Math.round(p.risk * 100) }));
  const last = points[points.length - 1] || { year: 0, risk: 0 };
  const lastPct = Math.round(last.risk * 100);
  const aLabel = result.option_a?.label || "이직";

  return (
    <Card>
      <h2 className="mb-2 flex items-center gap-2 text-base font-semibold">
        이탈·후회 리스크
        <span className="rounded-[10px] border border-line px-1.5 py-0.5 text-[10px] font-normal text-mut">
          관찰 {last.year}년
        </span>
      </h2>
      <div className="h-[170px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 10, right: 12, left: -18, bottom: 0 }}>
            <CartesianGrid stroke="#1E2740" vertical={false} />
            <XAxis
              dataKey="year"
              tick={{ fill: "#7E8DAB", fontSize: 11 }}
              axisLine={{ stroke: "#2A3550" }}
              tickLine={false}
            />
            <YAxis
              domain={[0, 60]}
              tickFormatter={(v) => `${v}%`}
              tick={{ fill: "#7E8DAB", fontSize: 11 }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              formatter={(v) => [`${v}%`, "재이직 비율"]}
              contentStyle={{
                background: "#141B2E",
                border: "1px solid #28324D",
                borderRadius: 10,
                fontSize: 12,
                color: "#EAF0FB",
              }}
            />
            <Line
              type="monotone"
              dataKey="risk"
              stroke={A_COLOR}
              strokeWidth={2}
              dot={{ r: 3, fill: A_COLOR }}
              activeDot={{ r: 5 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <Caption>
        {aLabel}한 사람들의 {last.year}년째 이탈·후회 리스크는 약 {lastPct}%입니다. 데이터가 있는 시점까지만 보여줍니다.
      </Caption>
    </Card>
  );
}
