import { Card, Caption } from "../ui.jsx";
import { labelOf } from "../../data/prediction.js";

export default function CareerTrajectoryView({ a, b }) {
  // 어느 쪽이 available 인지는 데이터에 달렸다(창업처럼 표본이 얇은 쪽이 빠질 수
  // 있음) — 배열 인덱스가 아니라 **원래 A/B 태그**를 들고 다녀야 라벨이 맞는다.
  // 예전엔 필터 후 남은 배열의 0번째를 무조건 "A"로 칠해서, B만 살아남았을 때도
  // "A · 현재 직장을 유지한다"처럼 라벨과 선택 문구가 어긋났다.
  const sides = [{ tag: "A", side: a }, { tag: "B", side: b }]
    .filter(({ side }) => side.parallel_trajectory?.status === "available");
  if (!sides.length) return null;
  return (
    <div className="mb-4">
      <h2 className="mb-1 text-base font-semibold">1·3·5년 평행 경로</h2>
      <Caption>현재 상태와 유사한 KLIPS 경로에서 각 선택 이후 실제로 관측된 흐름입니다.</Caption>
      <div className="mt-3 grid gap-3 xl:grid-cols-2">
        {sides.map(({ tag, side }) => <TrajectorySide key={tag} side={side} tag={tag} />)}
      </div>
    </div>
  );
}

function TrajectorySide({ side, tag }) {
  const result = side.parallel_trajectory;
  const type = result.trajectory_type;
  const color = tag === "A" ? "#A98BEE" : "#F5C86B";
  return (
    <Card>
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-[11px] font-bold" style={{ color }}>{tag} · {labelOf(side.choice)}</div>
          <div className="mt-1 text-sm font-semibold text-ink">{type.label}</div>
          <div className="mt-0.5 text-[10px] text-mut">현재 상태: {type.current_state_label}</div>
        </div>
        <div className="text-right text-[10px] text-mut">
          유사 사례<br/><b className="text-xs text-ink">{result.matching.people_n.toLocaleString()}명</b>
        </div>
      </div>
      <div className="mt-4 space-y-3">
        {result.timeline.map((point) => {
          const state = point.state_distribution?.[0];
          const wage = point.wage_change_pct;
          return (
            <div key={point.year} className="grid grid-cols-[42px_1fr_auto] items-center gap-2 border-t border-line/70 pt-3">
              <div className="text-xs font-bold" style={{ color }}>{point.year}년</div>
              <div>
                <div className="text-[12px] text-ink">{state?.label || "관측 부족"}</div>
                <div className="text-[10px] text-mut">직종 변경 {point.occupation_change_rate == null ? "—" : `${(point.occupation_change_rate * 100).toFixed(0)}%`} · n={point.sample_n}</div>
              </div>
              <div className="text-right">
                <div className="text-[11px] font-semibold text-ink">{wage?.available ? `${wage.median >= 0 ? "+" : ""}${wage.median}%` : "—"}</div>
                <div className="text-[9px] text-mut">임금변화 중앙값</div>
              </div>
            </div>
          );
        })}
      </div>
      <div className="mt-3 rounded-xl bg-bg/50 px-3 py-2 text-[9px] leading-4 text-mut">
        적용: {result.matching.applied_conditions.join(" · ") || "전체 관측집단"}
        {result.matching.relaxed_conditions.length > 0 && <><br/>표본 확보를 위해 제외: {result.matching.relaxed_conditions.join(" · ")}</>}
      </div>
      <Caption className="mt-2">확정 예측이 아닌 유사 경로의 관측 범위입니다. 장기 임금은 참고값으로만 보세요.</Caption>
    </Card>
  );
}
