import { Card, Caption } from "../ui.jsx";
import ParallelView from "./ParallelView.jsx";
import RiskView from "./RiskView.jsx";
import CareerTrajectoryView from "./CareerTrajectoryView.jsx";
import KowepsTrajectoryView from "./KowepsEvidenceView.jsx";

export default function ChangeView({ a, b, domains = { a: [], b: [] }, dataMode = "demo" }) {
  const selected = new Set([...(domains.a || []), ...(domains.b || [])]);
  const incomeRelevant = selected.has("career") || selected.has("finance");
  const businessRelevant = selected.has("business");
  // 길이(숫자)를 그대로 두면 0일 때 React 가 "0" 을 화면에 찍는다.
  const hasIncome = Boolean(incomeRelevant && a.trajectory?.length && b.trajectory?.length);
  const hasBusinessRisk = businessRelevant && [a, b].some((s) => Object.keys(s.risk_timeline || {}).length);
  const hasCareerTrajectory = [a, b].some((s) => s.parallel_trajectory?.status === "available");
  const hasKowepsTrajectory = [a, b].some((s) => s.koweps_evidence?.available);
  const relationshipRelevant = selected.has("relationship");
  const isJobComparison = [a.choice, b.choice].some((choice) => ["이직", "유지"].includes(choice));

  // API/모델 연결 실패 시 만들어지는 고정 데모 궤적을 실제 분석처럼 그리지 않는다.
  if (dataMode !== "model") {
    return (
      <Card>
        <h2 className="text-base font-semibold">변화 흐름</h2>
        <div className="mt-3 rounded-xl border border-[#D97882]/35 bg-[#2A1420] px-4 py-5 text-center">
          <div className="text-[12px] font-semibold text-[#FF9EAC]">실제 모델 결과를 불러오지 못했어요</div>
          <Caption className="mx-auto max-w-[320px] text-center">
            고정 데모값으로 소득선을 대신 그리지 않았습니다. 백엔드와 모델 파일이 연결되면 유사 집단의 1·3·5년 관측 경로가 표시됩니다.
          </Caption>
        </div>
      </Card>
    );
  }

  if (!hasIncome && !hasBusinessRisk && !hasCareerTrajectory && !hasKowepsTrajectory && !relationshipRelevant) {
    return <Card><h2 className="text-base font-semibold">변화 흐름</h2><Caption>이 선택에 대해 시간에 따른 변화를 계산할 수 있는 데이터가 아직 없습니다. 관련 없는 소득 그래프는 표시하지 않았어요.</Caption></Card>;
  }
  return (
    <div>
      {relationshipRelevant && !hasKowepsTrajectory && <RelationshipPathView a={a} b={b} />}
      {hasKowepsTrajectory && <KowepsTrajectoryView a={a} b={b} />}
      {hasCareerTrajectory && <CareerTrajectoryView a={a} b={b} />}
      {isJobComparison && !hasCareerTrajectory && (
        <Card>
          <h2 className="text-base font-semibold">1·3·5년 평행 경로</h2>
          <Caption>현재 조건에 맞는 유사 집단 관측 경로를 만들 수 없어 소득 그래프를 표시하지 않았어요.</Caption>
        </Card>
      )}
      {/* 이직·유지는 새 유사집단 경로를 정본으로 사용한다. 구 인과효과 가산 그래프는 숨긴다. */}
      {!isJobComparison && hasIncome && <ParallelView a={a} b={b} />}
      {hasBusinessRisk && <RiskView a={a} b={b} />}
    </div>
  );
}

function RelationshipPathView({ a, b }) {
  return (
    <Card>
      <h2 className="text-base font-semibold">관계 변화 흐름</h2>
      <Caption>데이터가 없는 미래 점수 대신, 두 선택이 실제로 거치는 행동과 확인 지점을 비교합니다.</Caption>
      <div className="mt-4 grid grid-cols-2 gap-3">
        <RelationshipLane side="A" choice={a.choice} steps={["대화 준비", "감정·요구 표현", "상대 반응 관찰"]} color="#9B72F2" />
        <RelationshipLane side="B" choice={b.choice} steps={["거리 확보", "내 감정 기록", "재접촉 기준 점검"]} color="#F39A4A" />
      </div>
      <Caption>각 단계의 기록이 쌓이면 다음 시뮬레이션에서 관계 성향 서사와 행동 제안에 반영됩니다.</Caption>
    </Card>
  );
}

function RelationshipLane({ side, choice, steps, color }) {
  return (
    <div className="min-w-0 rounded-2xl border border-line bg-bg/40 p-3">
      <div className="text-[10px] font-bold" style={{ color }}>선택 {side}</div>
      <div className="mt-1 line-clamp-2 min-h-9 text-[11px] font-semibold text-ink">{choice}</div>
      <div className="mt-3 space-y-2">
        {steps.map((step, index) => <div key={step} className="flex items-center gap-2 text-[10px] text-sub"><span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[9px] font-bold text-white" style={{ backgroundColor: color }}>{index + 1}</span><span>{step}</span></div>)}
      </div>
    </div>
  );
}
