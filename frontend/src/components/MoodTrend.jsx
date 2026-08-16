import { LineChart, Line, YAxis, XAxis, Tooltip, ResponsiveContainer } from "recharts";
import { Card, Caption } from "./ui.jsx";
import { useDiary, moodEmoji } from "../data/DiaryContext.jsx";

// 최근 1주 감정 흐름 (짧게). '내 주관적 기록'이지 실측 데이터 아님.
export default function MoodTrend({ days = 7 }) {
  const { entries } = useDiary();
  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - days);
  const cutoffStr = cutoff.toISOString().slice(0, 10);

  const data = entries
    .filter((e) => e.date >= cutoffStr)
    .sort((a, b) => (a.date < b.date ? -1 : 1))
    .map((e) => ({ date: e.date.slice(5), mood: e.mood }));

  if (data.length < 2) {
    return (
      <Card>
        <div className="mb-1 text-xs font-bold text-mut">최근 감정 흐름</div>
        <Caption>기록이 2개 이상 쌓이면 흐름이 보여요.</Caption>
      </Card>
    );
  }

  return (
    <Card>
      <div className="mb-1 flex items-center justify-between">
        <div className="text-xs font-bold text-mut">최근 1주 감정 흐름</div>
        <div className="text-[10px] text-mut">{data.length}개 기록</div>
      </div>
      <div className="h-[90px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 8, left: -28, bottom: 0 }}>
            <YAxis domain={[1, 5]} ticks={[1, 3, 5]} tick={false} axisLine={false} tickLine={false} width={0} />
            <XAxis dataKey="date" tick={{ fill: "#8B6CCF", fontSize: 9 }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
            <Tooltip
              contentStyle={{ background: "#141B2E", border: "1px solid #28324D", borderRadius: 10, fontSize: 12, color: "#EAF0FB" }}
              formatter={(v) => [`${moodEmoji(v)} ${v}/5`, "기분"]}
            />
            <Line type="monotone" dataKey="mood" stroke="#7FE0D4" strokeWidth={2} dot={{ r: 2.5, fill: "#7FE0D4" }} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <Caption>당신의 주관적 기록입니다(1~5). 비슷한 사람들의 실측 데이터와는 다른 층이에요.</Caption>
    </Card>
  );
}
