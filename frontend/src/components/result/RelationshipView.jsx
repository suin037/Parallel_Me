import { useState } from "react";
import { useResult } from "../../data/ResultContext.jsx";

// 관계 분석 탭 — 담아둔 대화에서 읽은 신호 + 성향과 엮은 선택지형 서사.
// 예측 수치가 '비슷한 사람들'을 말한다면, 이 탭은 '지금 이 관계에서 오가는 것'을 말한다.
// 상대를 진단하지 않고, 내가 고를 수 있는 길을 보여주는 게 원칙.
export default function RelationshipView() {
  const { relResults, relBusy, talks } = useResult();
  const [at, setAt] = useState(0);
  const list = relResults || [];

  if (relBusy && !list.length) {
    return <p className="px-1 py-6 text-center text-[12px] text-mut">공유해 주신 대화 {talks?.length || 0}개를 읽고 있어요…</p>;
  }
  if (!list.length) {
    return (
      <div className="rounded-2xl border border-dashed border-white/10 px-3.5 py-6 text-center">
        <p className="text-[12px] text-sub">아직 공유된 대화가 없어요.</p>
        <p className="mt-1 text-[10px] leading-relaxed text-mut">
          시뮬레이션 입력에서 대화·연락 내역을 공유하면 여기서 관계 신호를 볼 수 있어요.
        </p>
      </div>
    );
  }

  const r = list[Math.min(at, list.length - 1)];

  // 위기 신호가 잡히면 분석 대신 도움받을 곳을 안내한다(설계상 최우선).
  if (r?.blocked) {
    return (
      <div className="rounded-2xl border border-[#F0736F]/30 bg-[#F0736F]/[.08] px-3.5 py-4">
        <p className="text-[12px] font-bold text-[#F0736F]">지금은 분석보다 먼저 전할 말이 있어요</p>
        <p className="mt-2 whitespace-pre-line text-[12px] leading-relaxed text-sub">{r.support}</p>
      </div>
    );
  }
  if (r?.error) {
    return <p className="px-1 py-6 text-center text-[12px] text-[#F0736F]">대화를 분석하지 못했어요. 잠시 후 다시 시도해 주세요.</p>;
  }

  const sig = r?.signals || {};
  const narr = r?.narrative || {};

  return (
    <div className="space-y-2.5">
      {list.length > 1 && (
        <div className="flex flex-wrap gap-1.5">
          {list.map((item, i) => (
            <button
              key={i}
              type="button"
              onClick={() => setAt(i)}
              className={`tap rounded-full border px-3 py-1.5 text-[11px] transition-colors ${
                i === at ? "border-[#8B6CCF] bg-[#8B6CCF]/20 text-[#C7B5F2]" : "border-white/10 text-sub"
              }`}
            >
              {item.tag || item.label || `대화 ${i + 1}`}
            </button>
          ))}
        </div>
      )}

      <div className="rounded-2xl border border-[#8B6CCF]/25 bg-[#8B6CCF]/[.07] px-3.5 py-3">
        <p className="text-[10px] tracking-[.12em] text-[#9F85DD]">RELATIONSHIP</p>
        <b className="mt-1 block text-[15px] text-ink">{r.tag || "이 관계"}</b>
        {r.mode === "track" && r.history_count > 1 && (
          <p className="mt-1 text-[10px] text-mut">기록 {r.history_count}번째 — 지난 대화와 견줘 변화도 함께 봤어요.</p>
        )}
      </div>

      {/* 대화에서 읽은 것 — 오간 패턴과 각자의 행동. 상대를 진단하는 말은 싣지 않는다
          (애착 유형 같은 라벨은 서사의 근거로만 쓰고 화면엔 띄우지 않음). */}
      {sig.interaction_pattern && (
        <div className="rounded-2xl border border-white/[.07] bg-black/15 px-3.5 py-3">
          <p className="text-[11px] font-bold text-[#8B6CCF]">오간 흐름</p>
          <p className="mt-1.5 text-[12px] leading-relaxed text-sub">{sig.interaction_pattern}</p>
          {sig.emotional_tone && <p className="mt-1.5 text-[11px] text-mut">분위기 — {sig.emotional_tone}</p>}
        </div>
      )}

      {(sig.my_behavior?.length > 0 || sig.other_behavior?.length > 0) && (
        <div className="grid gap-2.5 sm:grid-cols-2">
          {sig.my_behavior?.length > 0 && (
            <Block title="내가 한 말·행동" tone="#A8CDF5">
              {sig.my_behavior.slice(0, 4).map((b, i) => (
                <li key={i} className="text-[12px] leading-relaxed text-sub">· {b}</li>
              ))}
            </Block>
          )}
          {sig.other_behavior?.length > 0 && (
            <Block title="상대에게서 보인 것" tone="#C7B5F2">
              {sig.other_behavior.slice(0, 4).map((b, i) => (
                <li key={i} className="text-[12px] leading-relaxed text-sub">· {b}</li>
              ))}
            </Block>
          )}
        </div>
      )}

      {sig.recurring_themes?.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {sig.recurring_themes.map((t) => (
            <span key={t} className="rounded-full border border-[#8B6CCF]/30 bg-[#8B6CCF]/[.1] px-2.5 py-1 text-[10px] text-[#C7B5F2]">
              반복되는 주제 · {t}
            </span>
          ))}
        </div>
      )}

      {narr.reading && (
        <div className="rounded-2xl border border-[#8B6CCF]/25 bg-[#8B6CCF]/[.07] px-3.5 py-3">
          <p className="text-[11px] font-bold text-[#C7B5F2]">지금 이 관계에서 일어나는 일</p>
          <p className="mt-2 whitespace-pre-line text-[12px] leading-relaxed text-sub">{narr.reading}</p>
        </div>
      )}

      {/* 선택지형 — 정답을 주지 않고, 고를 수 있는 길과 그 길의 결과를 나란히 둔다. */}
      {Array.isArray(narr.branches) && narr.branches.length > 0 && (
        <div className="space-y-2">
          <p className="text-[11px] font-bold text-[#5DCAA5]">고를 수 있는 길</p>
          {narr.branches.map((o, i) => (
            <div key={i} className="rounded-2xl border border-white/[.07] bg-black/15 px-3.5 py-3">
              <b className="text-[12.5px] text-ink">{o.label || `선택 ${i + 1}`}</b>
              {o.outcome && <p className="mt-1.5 text-[12px] leading-relaxed text-sub">{o.outcome}</p>}
              {o.basis && <p className="mt-1.5 text-[9.5px] text-mut">근거 — {o.basis}</p>}
            </div>
          ))}
        </div>
      )}

      {narr.next_step && (
        <div className="rounded-2xl border border-[#5DCAA5]/20 bg-[#5DCAA5]/[.06] px-3.5 py-3">
          <p className="text-[11px] font-bold text-[#5DCAA5]">오늘 해볼 만한 것</p>
          <p className="mt-1.5 text-[12px] leading-relaxed text-sub">{narr.next_step}</p>
        </div>
      )}

      {narr.change_note && (
        <div className="rounded-2xl border border-[#F0A45E]/20 bg-[#F0A45E]/[.06] px-3.5 py-3">
          <p className="text-[11px] font-bold text-[#F0A45E]">지난 대화와 견주면</p>
          <p className="mt-1.5 text-[12px] leading-relaxed text-sub">{narr.change_note}</p>
        </div>
      )}

      <p className="text-[10px] leading-relaxed text-mut">
        대화는 이름·연락처를 가린 뒤 보내고, 서버에는 암호화해 보관합니다. 상대를 진단하거나
        관계의 옳고 그름을 판단하지 않아요.
      </p>
    </div>
  );
}

function Block({ title, tone = "#8B6CCF", children }) {
  return (
    <div className="rounded-2xl border border-white/[.07] bg-black/15 px-3.5 py-3">
      <p className="text-[11px] font-bold" style={{ color: tone }}>{title}</p>
      <ul className="mt-2 space-y-1.5">{children}</ul>
    </div>
  );
}
