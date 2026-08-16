import { Card, Caption } from "../ui.jsx";
import { labelOf } from "../../data/prediction.js";

// 요약 — A/B 각각의 한 줄 결론 + coverage + 서사. 관찰형·표본 병기·단정 금지.
export default function SummaryView({ a, b }) {
  const bothChange = a.choice !== "유지" && b.choice !== "유지";

  return (
    <div>
      <SideLine result={a} accent="cyan" />
      <SideLine result={b} accent="gold" />

      {bothChange && (
        <Caption className="mt-1">
          두 갈래 모두 ‘변화’라, 각각을 데이터로 비춘 <b>두 개의 거울</b>입니다. 어느 쪽이 인과적으로
          낫다는 비교가 아닙니다.
        </Caption>
      )}

      <Card>
        <div className="mb-1 text-xs font-bold text-mut">각 선택지에서 볼 수 있는 데이터</div>
        <p className="text-[12px] leading-relaxed text-cyan">A · {a.coverage}</p>
        <p className="mt-1 text-[12px] leading-relaxed text-gold">B · {b.coverage}</p>
      </Card>

      <Card highlight>
        <div className="mb-1.5 text-xs font-bold text-cyan">Claude의 해석</div>
        <p className="text-[13px] leading-relaxed text-sub">
          {a.narrative ||
            "(심리 RAG 서사가 들어갈 자리) — 비슷한 사람들의 실제 기록을 바탕으로 상승과 하락을 함께 짚어드립니다. 판단은 당신의 몫입니다."}
        </p>
      </Card>
    </div>
  );
}

function SideLine({ result, accent }) {
  const c = accent === "cyan" ? "text-cyan" : "text-gold";
  return (
    <div className="mb-3">
      <div className={`text-[11px] font-bold ${c}`}>
        {accent === "cyan" ? "A" : "B"} · {labelOf(result.choice)}
      </div>
      <p className="mt-0.5 text-[14px] leading-relaxed">{headline(result)}</p>
    </div>
  );
}

function headline(result) {
  const { choice } = result;
  const nSim = result.trajectory?.[0]?.sample_n;
  if (choice === "이직") {
    const down = Math.round((result.down_ratio || 0) * 100);
    return (
      <>
        비슷한 약 {nSim}명 중 이직한 이들은 소득 순수효과{" "}
        <b className="text-cyan">{result.causal_effect > 0 ? "+" : ""}{result.causal_effect}만원</b>, 다만{" "}
        <b className="text-danger">{down}%</b>는 오히려 줄었습니다.
      </>
    );
  }
  if (choice === "창업") {
    const s1 = result.life_indicators.find((l) => l.indicator.includes("1년"))?.value;
    const s5 = result.life_indicators.find((l) => l.indicator.includes("5년"))?.value;
    return (
      <>
        창업 1년 생존율 <b className="text-cyan">{s1}%</b>, 5년 뒤엔{" "}
        <b className="text-danger">{s5}%</b>만 남았습니다.
      </>
    );
  }
  if (choice === "진학") {
    const emp = result.life_indicators.find((l) => l.indicator.includes("취업률"))?.value;
    const adv = result.life_indicators.find((l) => l.indicator.includes("진학률"))?.value;
    return (
      <>
        같은 계열 졸업자 취업률 <b className="text-cyan">{emp}%</b> · 진학률{" "}
        <b className="text-gold">{adv}%</b>.
      </>
    );
  }
  // 유지
  const wage = result.trajectory?.[0]?.income_p50;
  return (
    <>
      유지 시 또래 소득 중앙값은 현재 <b>{wage}만원</b>에서 완만히 움직였습니다(기준선).
    </>
  );
}
