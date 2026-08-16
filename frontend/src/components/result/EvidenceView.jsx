import { Card, Caption } from "../ui.jsx";
import PeopleView from "./PeopleView.jsx";
import CausalView from "./CausalView.jsx";
import RiskView from "./RiskView.jsx";
import ReturnView from "./ReturnView.jsx";
import { KowepsDetailView } from "./KowepsEvidenceView.jsx";

/**
 * 이 탭에 실제로 채울 내용이 있는지. 결과 화면의 탭 목록이 같은 기준을 써서
 * "현재 추가로 보여드릴 상세 분석이 없습니다" 한 줄짜리 빈 탭을 만들지 않게 한다.
 * 데모 모드는 예외 — 아래 데모 경고는 어떤 경우에도 닿을 수 있어야 한다.
 */
export function hasEvidenceDetail(a, b, dataMode) {
  if (dataMode === "demo") return true;
  return [a, b].some((s) => (
    s.neighbors?.length
    || s.causal_effect != null
    || Object.keys(s.risk_timeline || {}).length
    || Object.keys(s.return_timeline || {}).length
    || s.koweps_evidence?.available
    || Object.keys(s.domain_stats || {}).length
  ));
}

export default function EvidenceView({ a, b, dataMode }) {
  const hasPeople = [a, b].some((s) => s.neighbors?.length);
  const hasCausal = [a, b].some((s) => s.causal_effect != null);
  const hasRisk = [a, b].some((s) => Object.keys(s.risk_timeline || {}).length);
  const hasReturn = [a, b].some((s) => Object.keys(s.return_timeline || {}).length);
  const hasKoweps = [a, b].some((s) => s.koweps_evidence?.available);
  const hasDomain = [a, b].some((s) => Object.keys(s.domain_stats || {}).length);
  // 쉬어가기에서 소득 효과는 '복귀한 사람만' 보고 잰 값이라 단독으로 읽으면 안 된다.
  // 접는 제목에서부터 그 짝을 붙여 둔다.
  const causalTitle = hasReturn
    ? "쉬어갈 때의 소득 효과 보기 (복귀한 사람 기준)"
    : "이직의 소득 효과 추정 보기";
  return (
    <div>
      <h2 className="mb-1 text-base font-semibold">분석 상세</h2>
      <Caption>원하면 비슷한 사례와 효과 추정을 더 자세히 볼 수 있어요.</Caption>
      {dataMode === "demo" && <Card className="border-danger/40"><p className="text-[12px] font-semibold text-danger">현재 숫자와 그래프는 데모 데이터입니다.</p><Caption>로컬 예측모델 파일이 연결되기 전에는 실제 개인 예측으로 해석하면 안 됩니다.</Caption></Card>}
      <DomainStats a={a} b={b} />
      {hasKoweps && <KowepsDetailView a={a} b={b} />}
      {/* 복귀 곡선은 접지 않는다 — 쉬어갈지 판단할 때 먼저 봐야 하는 수치다.
          "얼마나 쉬게 되나" 를 모른 채 소득 효과부터 보면 순서가 뒤집힌다. */}
      {hasReturn && <ReturnView a={a} b={b} />}
      {hasPeople && <Disclosure title="비슷한 사례 보기"><PeopleView a={a} b={b} /></Disclosure>}
      {hasCausal && <Disclosure title={causalTitle}><CausalView a={a} b={b} /></Disclosure>}
      {hasRisk && <Disclosure title="지속 가능성·이탈 가능성 보기"><RiskView a={a} b={b} /></Disclosure>}
      {!hasPeople && !hasCausal && !hasRisk && !hasReturn && !hasKoweps && !hasDomain && <Card><Caption>현재 추가로 보여드릴 상세 분석이 없습니다.</Caption></Card>}
    </div>
  );
}

function Disclosure({ title, children }) {
  return <details className="my-2 rounded-xl border border-line bg-[#0E1424] px-3 py-2.5"><summary className="cursor-pointer text-[12px] font-semibold text-sub">{title}</summary><div className="mt-2">{children}</div></details>;
}

// 삶의 영역 참고지표(항목3) — 각 선택이 건드리는 영역의 실측 집단통계.
function DomainStats({ a, b }) {
  const sides = [["A", a], ["B", b]];
  const rows = [];
  for (const [tag, s] of sides) {
    for (const dom of Object.values(s.domain_stats || {})) {
      rows.push({ tag, ...dom });
    }
  }
  if (!rows.length) return null;
  return (
    <Card>
      <p className="text-[11px] font-bold text-cyan">9가지 삶의 영역 분석 <span className="text-mut">(근거가 있는 범위만 표시)</span></p>
      <div className="mt-2 space-y-2.5">
        {rows.map((r, i) => (
          <div key={i}>
            <div className="flex items-center gap-1.5 text-[11px] font-semibold text-ink">{r.tag} · {r.label}
              <span className={`rounded-full px-1.5 py-0.5 text-[8px] ${r.status === "available" ? "bg-cyan/10 text-cyan" : "bg-white/5 text-mut"}`}>
                {r.status === "available" ? evidenceLabel(r.evidence) : "근거 부족"}
              </span>
            </div>
            {r.indicators?.length ? <div className="mt-1 flex flex-wrap gap-1.5">
              {r.indicators.map((ind, j) => (
                <span key={j} className="rounded-lg border border-line bg-[#0E1424] px-2 py-1 text-[11px] text-sub">
                  {ind.name} <span className="font-bold text-ink">{ind.value}{ind.unit}</span>
                </span>
              ))}
            </div> : <p className="mt-1 text-[10px] text-mut">{r.source_note || r.limitation || "현재 연결된 수치 데이터가 없습니다."}</p>}
            {r.indicators?.length > 0 && r.limitation && <p className="mt-1 text-[9px] text-mut">{r.limitation}</p>}
            {r.source_note && <p className="mt-1 text-[9px] leading-4 text-violet-300/80">사용 근거 · {r.source_note}</p>}
            {r.outcome_contract?.length > 0 && <p className="mt-1 text-[9px] leading-4 text-mut">확인 대상 · {r.outcome_contract.join(" · ")}</p>}
          </div>
        ))}
      </div>
      <Caption>비슷한 조건의 사람들 집단 수치입니다. 이 선택의 개인 예측이 아니라 참고 맥락입니다.</Caption>
    </Card>
  );
}

function evidenceLabel(evidence) {
  return ({ model: "모델·관측", group_stat: "집단통계", rag: "기록 해석" })[evidence] || evidence;
}
