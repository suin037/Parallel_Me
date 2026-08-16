import { useEffect, useState } from "react";
import { Compass } from "lucide-react";
import {
  activeExpeditions, completeExpedition, doneExpeditions, dropExpedition,
} from "../data/expeditions.js";

// 진행 중인 작은 탐험 — 떠난 길을 잊지 않게 홈에 걸어둔다.
// 돌아와 적은 한 줄이 회고 자리를 대신하고, 그 영역의 'N년 뒤'를 쓸 때 재료가 된다.
export default function ExpeditionBoard() {
  const [going, setGoing] = useState(activeExpeditions);
  const [done, setDone] = useState(() => doneExpeditions());
  const [writing, setWriting] = useState(null);   // 기록 중인 탐험 id
  const [note, setNote] = useState("");

  useEffect(() => {
    const refresh = () => { setGoing(activeExpeditions()); setDone(doneExpeditions()); };
    window.addEventListener("pm:expedition", refresh);
    return () => window.removeEventListener("pm:expedition", refresh);
  }, []);

  if (!going.length && !done.length) return null;

  function finish(id) {
    completeExpedition(id, note);
    setWriting(null);
    setNote("");
  }

  return (
    <div className="mt-4 rounded-[18px] border border-[#3E9C7F]/30 bg-[#0F1E1A] p-4">
      <div className="mb-2 flex items-center gap-1.5">
        <Compass size={14} className="text-[#5DCAA5]" />
        <span className="text-[12.5px] font-semibold text-ink">떠나 있는 작은 탐험</span>
        {done.length > 0 && (
          <span className="ml-auto text-[9.5px] text-mut">다녀온 곳 {done.length}</span>
        )}
      </div>

      <div className="space-y-2">
        {going.map((e) => (
          <div key={e.id} className="rounded-xl border border-white/[.06] bg-black/25 p-3">
            <div className="flex items-start justify-between gap-2">
              <p className="text-[11.5px] font-semibold text-ink">{e.title}</p>
              {e.planetLabel && (
                <span className="shrink-0 rounded-full bg-white/[.06] px-2 py-0.5 text-[8.5px] text-mut">
                  {e.planetLabel}
                </span>
              )}
            </div>
            {e.step && <p className="mt-1 text-[10px] leading-relaxed text-sub">첫 걸음 · {e.step}</p>}

            {writing === e.id ? (
              <div className="mt-2">
                <textarea
                  value={note}
                  autoFocus
                  onChange={(ev) => setNote(ev.target.value)}
                  rows={2}
                  placeholder="가서 뭘 알게 됐나요? 한 줄이면 충분해요."
                  className="w-full rounded-lg border border-line bg-[#0E1424] px-2.5 py-2 text-[11px] text-ink outline-none focus:border-[#5DCAA5]"
                />
                <div className="mt-1.5 flex gap-1.5">
                  <button
                    onClick={() => finish(e.id)}
                    disabled={!note.trim()}
                    className={`tap flex-1 rounded-lg py-1.5 text-[10px] font-bold ${
                      note.trim() ? "bg-[#3E9C7F] text-white" : "bg-[#1E2740] text-mut"
                    }`}
                  >
                    기록하고 마치기
                  </button>
                  <button
                    onClick={() => { setWriting(null); setNote(""); }}
                    className="tap rounded-lg border border-white/[.09] px-2.5 text-[10px] text-mut"
                  >
                    취소
                  </button>
                </div>
              </div>
            ) : (
              <div className="mt-2 flex gap-1.5">
                <button
                  onClick={() => { setWriting(e.id); setNote(""); }}
                  className="tap flex-1 rounded-lg bg-[#3E9C7F] py-1.5 text-[10px] font-bold text-white"
                >
                  다녀왔어요
                </button>
                <button
                  onClick={() => dropExpedition(e.id)}
                  className="tap rounded-lg border border-white/[.09] px-2.5 py-1.5 text-[10px] text-mut"
                >
                  접기
                </button>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* 다녀온 길 — 지나온 게 눈에 보여야 다음 탐험이 가볍다. */}
      {done.length > 0 && (
        <div className={`${going.length ? "mt-2.5 border-t border-white/[.06] pt-2.5" : ""}`}>
          {done.slice(-2).reverse().map((e) => (
            <div key={e.id} className="mb-1 last:mb-0">
              <p className="text-[10px] text-[#7FD9BB]">✓ {e.title}</p>
              {e.note && <p className="mt-0.5 text-[9.5px] leading-relaxed text-mut">“{e.note}”</p>}
            </div>
          ))}
        </div>
      )}

      <p className="mt-2 text-[9px] leading-relaxed text-mut">
        다녀와서 적은 한 줄은 그 영역의 ‘N년 뒤’를 쓸 때 가장 단단한 재료가 돼요.
      </p>
    </div>
  );
}
