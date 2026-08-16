import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine,
} from "recharts";
import { Card, Caption } from "../ui.jsx";
import { labelOf } from "../../data/prediction.js";

// 복귀 곡선 — 휴식(쉬어가기) 전용. return_timeline = {개월: 복귀 누적확률}.
//
// 다른 갈래의 생존 곡선(RiskView)은 '그 상태에서 이탈' 이 나쁜 쪽이라 빨간 선으로
// 그린다. 여기서는 이탈이 곧 **복귀**라 좋은 쪽이고, 단위도 연이 아니라 개월이다.
// "3개월만 쉬려 했는데 실제로는 얼마나 걸리나" 가 이 화면이 답하는 질문이다.
export default function ReturnView({ a, b }) {
  const sides = [a, b].filter((s) => Object.keys(s?.return_timeline || {}).length > 0);
  if (!sides.length) return null;
  return <div>{sides.map((s, i) => <SideReturn key={i} result={s} />)}</div>;
}

function SideReturn({ result }) {
  const data = Object.entries(result.return_timeline)
    .map(([m, p]) => ({ m: Number(m), month: `${m}개월`, pct: Math.round(p * 100) }))
    .sort((x, y) => x.m - y.m);

  const median = result.survival_months;
  // 이 사람 기준으로 '절반이 아직 안 돌아와 있는' 구간을 문장으로 집어준다.
  // 곡선만 두면 50% 선을 각자 눈으로 찾아야 한다.
  const half = data.find((d) => d.pct >= 50);

  return (
    <Card>
      <h2 className="mb-1 flex items-center gap-2 text-base font-semibold">
        {labelOf(result.choice)} · 일로 돌아오기까지
      </h2>
      {median != null && (
        <p className="mb-2 text-[13px] text-sub">
          비슷한 조건에서 쉰 사람의 절반이 돌아오기까지{" "}
          <strong className="text-ink">{Math.round(median)}개월</strong>이 걸렸습니다.
        </p>
      )}
      <div className="mt-2 h-[170px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 8, right: 12, left: -14, bottom: 0 }}>
            <defs>
              <linearGradient id="returnFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#6FD3C7" stopOpacity={0.45} />
                <stop offset="100%" stopColor="#6FD3C7" stopOpacity={0.03} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="#1E2740" vertical={false} />
            <XAxis dataKey="month" tick={{ fill: "#7E8DAB", fontSize: 11 }} axisLine={{ stroke: "#2A3550" }} tickLine={false} />
            <YAxis domain={[0, 100]} tickFormatter={(v) => `${v}%`} tick={{ fill: "#7E8DAB", fontSize: 11 }} axisLine={false} tickLine={false} />
            {/* 절반이 돌아온 지점 — 중앙값을 눈으로 찾게 두지 않는다 */}
            <ReferenceLine y={50} stroke="#3C4869" strokeDasharray="3 3" />
            <Tooltip
              contentStyle={{ background: "#141B2E", border: "1px solid #28324D", borderRadius: 10, fontSize: 12, color: "#EAF0FB" }}
              formatter={(v) => [`${v}%`, "복귀한 비율"]}
            />
            <Area type="monotone" dataKey="pct" stroke="#6FD3C7" strokeWidth={2} fill="url(#returnFill)" dot={{ r: 3, fill: "#6FD3C7" }} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <Caption>
        KLIPS 직업력에서 자발적으로 그만두고 2개월 이상 비운 구간을 모아, 다음 일자리를
        시작한 시점까지를 잰 것입니다(공백 스펠 5,209건). 아직 안 돌아온 사람은 &lsquo;복귀
        안 함&rsquo;이 아니라 관측이 끊긴 것으로 처리했습니다.
        {half && ` 이 조건에선 ${half.month}쯤 절반이 돌아옵니다.`} 개인의 확정된 미래가 아니라
        비슷한 사람들이 실제로 걸린 시간입니다.
      </Caption>
    </Card>
  );
}
