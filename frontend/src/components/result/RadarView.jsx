import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { Card, Caption } from "../ui.jsx";
import { A_COLOR, B_COLOR } from "../../data/result.js";

// 비교: 3지표(경제안정/성장/삶의질)에 A·B 두 계열을 한 차트에 겹쳐서.
export default function RadarView({ result }) {
  const { option_a: a, option_b: b } = result;

  const data = [
    { metric: "경제안정", A: a.scores.경제, B: b.scores.경제 },
    { metric: "성장", A: a.scores.성장, B: b.scores.성장 },
    { metric: "삶의질", A: a.scores.삶의질, B: b.scores.삶의질 },
  ];

  return (
    <Card>
      <div className="h-[260px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart data={data} outerRadius="72%">
            <PolarGrid stroke="#25314D" />
            <PolarAngleAxis
              dataKey="metric"
              tick={{ fill: "#7E8DAB", fontSize: 11 }}
            />
            <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
            <Radar
              name={`${a.label} A (${a.n}명)`}
              dataKey="A"
              stroke={A_COLOR}
              strokeWidth={1.5}
              fill={A_COLOR}
              fillOpacity={0.22}
            />
            <Radar
              name={`${b.label} B (${b.n}명)`}
              dataKey="B"
              stroke={B_COLOR}
              strokeWidth={1.5}
              strokeDasharray="3 2"
              fill={B_COLOR}
              fillOpacity={0.16}
            />
            <Legend
              iconType="circle"
              wrapperStyle={{ fontSize: 11, color: "#8B6CCF" }}
            />
          </RadarChart>
        </ResponsiveContainer>
      </div>
      <Caption className="text-center">
        이직한 사람들은 성장이 높고, 남은 사람들은 삶의 질이 높았습니다. 정답은 없습니다.
      </Caption>
    </Card>
  );
}
