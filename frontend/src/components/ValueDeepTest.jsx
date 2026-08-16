import { useEffect, useState } from "react";
import { fetchValueTest, submitValueTest } from "../data/careerNet.js";

// 직업가치관검사(커리어넷 · 대학/일반) — 28문항, 두 가치 중 하나 고르기.
// 온보딩에 넣으면 부담이라, 진로 질문을 한 '직후'에 세부 분석으로 권한다.
// 28문항 = 8개 가치의 모든 쌍이라 응답만 세면 순위가 나온다(서버가 집계).
export default function ValueDeepTest({ onDone, onClose }) {
  const [items, setItems] = useState(null);
  const [at, setAt] = useState(0);
  const [answers, setAnswers] = useState({});
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  useEffect(() => {
    let alive = true;
    fetchValueTest()
      .then((data) => {
        if (!alive) return;
        if (data.ok) setItems(data.items);
        else setErr(data.reason === "no_careernet_key" ? "검사 서버에 커리어넷 키가 없어요" : "문항을 불러오지 못했어요");
      })
      .catch(() => alive && setErr("검사 서버에 연결하지 못했어요"));
    return () => { alive = false; };
  }, []);

  async function pick(side) {
    const q = items[at];
    const next = { ...answers, [q.no]: side };
    setAnswers(next);
    if (at + 1 < items.length) { setAt(at + 1); return; }
    setBusy(true);
    try {
      const data = await submitValueTest(next);
      if (data.ok) onDone?.(data);
      else setErr("결과를 만들지 못했어요");
    } catch {
      setErr("결과 요청에 실패했어요");
    } finally {
      setBusy(false);
    }
  }

  if (err) {
    return (
      <div className="rounded-xl border border-white/10 bg-black/20 px-3 py-3">
        <p className="text-[11px] leading-relaxed text-[#F0736F]">{err}</p>
        <button onClick={onClose} className="tap mt-2 text-[11px] text-sub">닫기</button>
      </div>
    );
  }
  if (!items) return <p className="px-1 py-3 text-[11px] text-mut">문항을 불러오는 중…</p>;
  if (busy) return <p className="px-1 py-3 text-[11px] text-mut">응답을 정리하는 중…</p>;

  const q = items[at];
  const pct = Math.round(((at) / items.length) * 100);

  return (
    <div className="rounded-xl border border-white/10 bg-black/20 px-3 py-3">
      <div className="flex items-center justify-between">
        <span className="text-[10px] text-mut">{at + 1} / {items.length}</span>
        <button onClick={onClose} className="tap text-[10px] text-mut">그만두기</button>
      </div>
      <div className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-white/10">
        <div className="h-full rounded-full bg-[#8B6CCF] transition-all" style={{ width: `${pct}%` }} />
      </div>

      <p className="mt-3 text-[11px] font-semibold text-sub">두 가치 중 더 중요한 쪽을 골라주세요</p>
      <div className="mt-2 grid gap-2">
        {[["1", q.a], ["2", q.b]].map(([side, v]) => (
          <button
            key={side}
            onClick={() => pick(side)}
            className="tap rounded-xl border border-white/10 bg-[#0E1424] px-3 py-2.5 text-left transition-colors hover:border-[#8B6CCF]"
          >
            <b className="text-[12px] text-ink">{v.name}</b>
            <span className="mt-0.5 block text-[10px] leading-relaxed text-mut">{v.desc}</span>
          </button>
        ))}
      </div>
      <p className="mt-2 text-[9px] leading-relaxed text-mut">
        커리어넷(한국직업능력연구원) 직업가치관검사 · 대학/일반용
      </p>
    </div>
  );
}
