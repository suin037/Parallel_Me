import { useEffect, useState } from "react";
import { Card, Caption } from "../ui.jsx";
import { fetchSoftCompare, getCachedSoft } from "../../data/softCompare.js";
import { loadSpeech } from "../../data/dispositionApi.js";
import { useResult } from "../../data/ResultContext.jsx";

// 수치가 없는 영역(관계·건강·일상·성장)의 기록 근거.
// 미래 장면·얻는 것·치르는 것은 1단계 상세 이야기에서 이미 보여준다.
// 여기서는 그 이야기를 반복하지 않고, 해석에 사용한 기록과 결정 기준만 보여준다.
export default function SoftCompareView({ a, b, planet, planetLabel }) {
  const { profile } = useResult();
  const nameA = a?.choice || "A";
  const nameB = b?.choice || "B";
  const [data, setData] = useState(() => getCachedSoft(planet, nameA, nameB));
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (data) return;
    let alive = true;
    setBusy(true);
    fetchSoftCompare(planet, nameA, nameB, { speech: loadSpeech(), profile })
      .then((r) => { if (alive) setData(r); })
      .finally(() => { if (alive) setBusy(false); });
    return () => { alive = false; };
  }, [planet, nameA, nameB]); // eslint-disable-line react-hooks/exhaustive-deps

  if (busy && !data) {
    return <Card><Caption>내 기록을 읽고 두 길을 그려보는 중…</Caption></Card>;
  }
  if (!data?.ok) {
    return <Card><Caption>{data?.reason || "비교를 준비하지 못했어요."}</Caption></Card>;
  }

  return (
    <div>
      <h2 className="mb-1 text-base font-semibold">이 해석에 사용한 기록</h2>
      <p className="mb-3 text-[11px] leading-relaxed text-mut">
        1단계의 미래 이야기를 반복하지 않고, {planetLabel} 영역에서 어떤 기록과
        판단 기준을 참고했는지 보여드려요.
      </p>

      {data.hinge && (
        <div className="rounded-[18px] border border-[#EDA100]/20 bg-[#EDA100]/[.08] p-4">
          <p className="text-[10px] font-semibold text-[#EDA100]">결정을 가르는 핵심 기준</p>
          <p className="mt-1 text-[12px] leading-relaxed text-sub">{data.hinge}</p>
        </div>
      )}

      {data.basis?.length > 0 && (
        <div className="mt-3">
          <p className="text-[10px] font-semibold text-mut">참고한 내 기록</p>
          <ul className="mt-2 space-y-2">
            {data.basis.map((x, i) => (
              <li key={i} className="rounded-xl border border-white/[.07] bg-white/[.025] px-3 py-2.5 text-[10.5px] leading-relaxed text-sub">
                <span className="mr-1.5 font-bold text-violet-300">{i + 1}</span>{x}
              </li>
            ))}
          </ul>
        </div>
      )}

      <Caption>
        기록에서 확인할 수 있는 판단 근거이며, 개인의 미래를 확정하거나 점수화한 결과가 아닙니다.
      </Caption>
    </div>
  );
}
