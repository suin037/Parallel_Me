import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { Card, Caption } from "../ui.jsx";
import { A_COLOR, B_COLOR } from "../../data/result.js";
import { labelOf } from "../../data/prediction.js";

// 변화 흐름 — A/B 두 갈래의 소득 중앙값 궤적을 한 차트에 겹침.
// 근거 수준 라벨 → 뱃지 색. (항목4)
const EV_STYLE = {
  모델예측: { bg: "#211832", fg: "#8B6CCF", bd: "#6F55A7" },
  집단통계: { bg: "#123a2e", fg: "#5FE0B0", bd: "#1f5a45" },
  RAG설명: { bg: "#2a2340", fg: "#8B6CCF", bd: "#463a6a" },
  데이터부족: { bg: "#3a1220", fg: "#FF9EC0", bd: "#5a2436" },
};
function EvBadge({ label }) {
  if (!label) return null;
  const s = EV_STYLE[label] || EV_STYLE.데이터부족;
  return (
    <span style={{ background: s.bg, color: s.fg, border: `1px solid ${s.bd}` }}
      className="rounded-full px-2 py-0.5 text-[10px] font-semibold">{label}</span>
  );
}

export default function ParallelView({ a, b }) {
  const la = labelOf(a.choice);
  const lb = labelOf(b.choice);
  const bothBaseline = a.trajectory_is_baseline && b.trajectory_is_baseline;

  // 근거 가드(항목4) — 정량 데이터 없는 삶의 영역이면 오해 소지 있는 수치 그래프 대신 안내.
  const guarded = a.quantitative_ok === false || b.quantitative_ok === false;
  if (guarded) {
    const guardNote = a.graph_guard_note || b.graph_guard_note ||
      "이 질문의 삶의 영역은 정량 예측 데이터가 없어요 — 수치 그래프 대신 통계·설명 근거로만 답합니다.";
    return (
      <Card>
        <h2 className="mb-1 text-base font-semibold">A/B 소득 변화 흐름</h2>
        <div className="mt-2 rounded-xl border border-line bg-[#0E1424] px-4 py-7 text-center">
          <div className="text-[13px] font-semibold text-gold">📊 수치 그래프 없음</div>
          <p className="mx-auto mt-2 max-w-[300px] text-[12.5px] leading-relaxed text-sub">{guardNote}</p>
        </div>
      </Card>
    );
  }

  const data = a.trajectory.map((p, i) => ({
    year: `${p.year}년`,
    A: p.income_p50,
    B: b.trajectory[i]?.income_p50,
    baseline: p.income_p50,
    sample_n: p.sample_n,
  }));
  const bothChange = a.choice !== "유지" && b.choice !== "유지";
  // 창업·진학은 갈래별 소득 추적 데이터가 없어 양쪽이 같은 기준선을 쓴다.
  // 두 선이 겹쳐 보이는 이유를 밝히지 않으면 '갈래별 예측'으로 오해된다.
  const baselineSides = [a, b].filter((s) => s.trajectory_is_baseline).map((s) => labelOf(s.choice));

  return (
    <Card>
      <div className="mb-1 flex items-center gap-2">
        <h2 className="text-base font-semibold">{bothBaseline ? "공통 소득 참고선" : "A/B 소득 변화 흐름"}</h2>
        {!bothBaseline && (
          <span className="ml-auto flex items-center gap-1">
            <span className="text-[10px] text-mut">{la}</span><EvBadge label={a.evidence_label} />
            <span className="ml-1 text-[10px] text-mut">{lb}</span><EvBadge label={b.evidence_label} />
          </span>
        )}
      </div>
      {bothBaseline && (
        <p className="mt-1 text-[11px] leading-relaxed text-sub">
          현재 조건이 비슷한 사람들의 일반적인 변화입니다. 두 선택의 소득 차이를 예측한 값은 아닙니다.
        </p>
      )}
      <div className="mt-2 h-[220px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 12, left: -14, bottom: 0 }}>
            <CartesianGrid stroke="#1E2740" vertical={false} />
            <XAxis dataKey="year" tick={{ fill: "#7E8DAB", fontSize: 11 }} axisLine={{ stroke: "#2A3550" }} tickLine={false} />
            <YAxis tick={{ fill: "#7E8DAB", fontSize: 11 }} axisLine={false} tickLine={false} />
            <Tooltip
              contentStyle={{ background: "#141B2E", border: "1px solid #28324D", borderRadius: 10, fontSize: 12, color: "#EAF0FB" }}
              formatter={(v) => [`${v}만원`, ""]}
              labelFormatter={(l, p) => `${l} · 추적 ${p?.[0]?.payload?.sample_n}명`}
            />
            {!bothBaseline && <Legend wrapperStyle={{ fontSize: 11, color: "#8B6CCF" }} iconType="plainline" formatter={(key) => key === "A" ? la : lb} />}
            {bothBaseline ? (
              <Line type="monotone" dataKey="baseline" name="공통 참고선" stroke="#8791A8" strokeWidth={2} dot={{ r: 2.5 }} />
            ) : (
              <>
                <Line type="monotone" dataKey="A" name={la} stroke={A_COLOR} strokeWidth={2} dot={{ r: 2.5 }} />
                <Line type="monotone" dataKey="B" name={lb} stroke={B_COLOR} strokeWidth={2} strokeDasharray="4 3" dot={{ r: 2.5 }} />
              </>
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>
      <Caption>
        {bothBaseline
          ? "비슷한 사람들의 소득 중앙값(만원)이며, 선택별 효과가 아닙니다. 뒤 연차일수록 추적 표본이 줄어 불확실합니다."
          : "비슷한 사람들이 각 갈래에서 걸어간 소득 중앙값(만원). 예측이 아니라 관찰된 분포이며, 뒤 연차일수록 추적 표본이 줄어 불확실합니다."}
        {!bothBaseline && bothChange && " 두 갈래 모두 변화라, 직접 인과비교가 아닌 각각의 거울입니다."}
        {!bothBaseline && baselineSides.length > 0 && (
          <>
            {" "}
            <span className="text-gold">
              {baselineSides.join("·")}는 선택별 소득선이 아니라 공통 참고선입니다.
            </span>
          </>
        )}
      </Caption>
    </Card>
  );
}
