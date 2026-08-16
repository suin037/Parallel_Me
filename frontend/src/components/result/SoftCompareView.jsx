import { useEffect, useState } from "react";
import { Card, Caption } from "../ui.jsx";
import { fetchSoftCompare, getCachedSoft } from "../../data/softCompare.js";
import { loadSpeech } from "../../data/dispositionApi.js";
import { useResult } from "../../data/ResultContext.jsx";

// 수치가 없는 영역(관계·건강·일상·성장)의 두 길 비교.
// 여기선 숫자를 만들지 않는다 — 두 길이 각각 어떤 하루가 되는지 장면으로 보여준다.
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

  const Side = ({ side, name, box, tint }) => (
    <div className="rounded-[18px] border p-4" style={{ borderColor: `${tint}40`, background: `${tint}0F` }}>
      <div className="flex items-center gap-1.5">
        <span className="rounded-full px-2 py-0.5 text-[9.5px] font-bold" style={{ color: tint, background: `${tint}22` }}>{side}</span>
        <b className="text-[13px]">{name}</b>
      </div>
      <p className="mt-2 text-[12px] leading-relaxed text-sub">{box.scene}</p>
      {box.gain && (
        <p className="mt-2.5 text-[11px] leading-relaxed text-[#7FD9BB]">얻는 것 · {box.gain}</p>
      )}
      {box.cost && (
        <p className="mt-1 text-[11px] leading-relaxed text-[#F0A08D]">치르는 것 · {box.cost}</p>
      )}
    </div>
  );

  return (
    <div>
      <h2 className="mb-1 text-base font-semibold">두 길의 하루</h2>
      <p className="mb-3 text-[11px] leading-relaxed text-mut">
        {planetLabel} 영역은 소득·고용 통계로 답할 수 있는 자리가 아니라, 숫자 대신
        내 기록에서 두 길이 각각 어떤 하루가 되는지를 그렸어요.
      </p>

      <div className="space-y-2.5">
        <Side side="A" name={nameA} box={data.a} tint="#8B6CCF" />
        <Side side="B" name={nameB} box={data.b} tint="#4E7FD9" />
      </div>

      {data.hinge && (
        <div className="mt-3 rounded-[18px] bg-[#EDA100]/[.08] p-4">
          <p className="text-[10px] text-[#EDA100]">두 길을 가르는 지점</p>
          <p className="mt-1 text-[12px] leading-relaxed text-sub">{data.hinge}</p>
        </div>
      )}

      {data.basis?.length > 0 && (
        <div className="mt-3 border-t border-white/[.06] pt-3">
          <p className="text-[10px] text-mut">이 비교를 끌어온 기록</p>
          <ul className="mt-1 space-y-0.5">
            {data.basis.map((x, i) => (
              <li key={i} className="text-[10.5px] leading-relaxed text-mut">· {x}</li>
            ))}
          </ul>
        </div>
      )}

      <Caption>
        예측이 아니라 내 기록에서 끌어온 이야기예요. 확률·점수를 만들지 않았습니다.
      </Caption>
    </div>
  );
}
