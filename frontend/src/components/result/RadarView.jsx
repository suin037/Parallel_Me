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
import { AXES } from "../../api.js";

// 비교: 5축(경제·성장·관계·자기실현·안정)에 A·B 두 계열을 한 차트에 겹쳐서.
//
// 근거가 없어 중립값만 채워진 축(unmeasured)은 **꼭짓점을 그리지 않는다**. 0.5를
// 그대로 그리면 '중간쯤 된다'는 측정 결과처럼 보이는데, 실제로는 잰 적이 없다.
// A·B 중 한쪽이라도 미측정이면 그 축은 비교가 성립하지 않으므로 둘 다 비운다.
export default function RadarView({ result }) {
  const { option_a: a, option_b: b } = result;

  const unmeasured = new Set([...(a.unmeasured || []), ...(b.unmeasured || [])]);
  const data = AXES.map((ax) => ({
    metric: ax,
    A: unmeasured.has(ax) ? null : a.scores[ax],
    B: unmeasured.has(ax) ? null : b.scores[ax],
  }));

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
        축마다 재는 데이터가 다릅니다. 정답은 없습니다.
        {unmeasured.size > 0 && (
          <> · <span className="opacity-70">
            {[...unmeasured].join("·")}은 측정 근거가 없어 비워 두었습니다
          </span></>
        )}
      </Caption>
    </Card>
  );
}
