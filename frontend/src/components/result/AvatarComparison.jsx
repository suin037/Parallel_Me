import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import Avatar from "../Avatar.jsx";
import { labelOf } from "../../data/prediction.js";

export default function AvatarComparison({ avatar, a, b, visuals, narrative, narrativeLoading, loading, error, onRetry }) {
  const [expanded, setExpanded] = useState(null);
  useEffect(() => {
    if (!expanded) return undefined;
    const previousOverflow = document.body.style.overflow;
    const closeOnEscape = (event) => {
      if (event.key === "Escape") setExpanded(null);
    };
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [expanded]);
  return (
    <section className="mt-4" aria-labelledby="visual-story-title">
      <div className="mb-2 flex items-end justify-between gap-3">
        <div>
          <p className="text-[10px] font-bold tracking-[.16em] text-mut">VISUAL STORY</p>
          <h2 id="visual-story-title" className="mt-0.5 text-base font-semibold">두 갈림길 속의 나</h2>
        </div>
      </div>

      {narrative?.comparison && (
        <Comparison story={narrative.comparison} />
      )}

      <div className={`${narrative?.comparison ? "mt-3" : ""} grid gap-3 sm:grid-cols-2 lg:gap-5`}>
        <StoryCard side="A" result={a} image={visuals?.a} story={narrative?.a} storyLoading={narrativeLoading} avatar={avatar} open={expanded === "A"} onToggle={() => setExpanded((v) => v === "A" ? null : "A")} />
        <StoryCard side="B" result={b} image={visuals?.b} story={narrative?.b} storyLoading={narrativeLoading} avatar={avatar} open={expanded === "B"} onToggle={() => setExpanded((v) => v === "B" ? null : "B")} />
      </div>

      {expanded && createPortal(
        <div
          className="fixed inset-0 z-[160] flex animate-backdrop-in items-end justify-center bg-[#02050C]/75 backdrop-blur-[5px] sm:items-center sm:p-6"
          role="dialog"
          aria-modal="true"
          aria-label={`UNIVERSE ${expanded} 상세 이야기`}
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) setExpanded(null);
          }}
        >
          <div className="max-h-[90dvh] w-full max-w-[760px] animate-sheet-up overflow-y-auto rounded-t-[30px] border border-white/10 bg-[#09111F] shadow-[0_-28px_90px_rgba(0,0,0,.68)] sm:animate-fade sm:rounded-[30px]">
            <StoryDetail
              side={expanded}
              story={expanded === "A" ? narrative?.a : narrative?.b}
              image={expanded === "A" ? visuals?.a : visuals?.b}
              choice={expanded === "A" ? a?.choice : b?.choice}
              onClose={() => setExpanded(null)}
            />
          </div>
        </div>,
        document.body,
      )}

      {error && (
        <div className="mt-2 rounded-lg border border-danger/30 bg-danger/10 px-2.5 py-2 text-[10px] leading-relaxed text-danger">
          <p>일부 AI 결과를 표시하지 못했어요. 가능한 내용만 보여드립니다: {error}</p>
          {onRetry && (
            <button type="button" disabled={loading} onClick={onRetry}
              className="mt-2 rounded-lg border border-danger/40 px-2.5 py-1.5 font-semibold disabled:opacity-50">
              {loading ? "이미지 생성 중…" : "이미지만 다시 생성"}
            </button>
          )}
        </div>
      )}
    </section>
  );
}

function StoryCard({ side, result, image, story, storyLoading, avatar, open, onToggle }) {
  const color = side === "A" ? "#8B6CCF" : "#F5C86B";
  const structured = story && typeof story === "object";
  const summary = structured ? story.summary : story;
  const detail = structured ? story.detail || {} : {};
  const hasDetail = structured && Boolean(
    detail.present || detail.transition || detail.future || story.gain || story.cost || story.uncertainty
  );
  const toggleOnKey = (event) => {
    if (!hasDetail || (event.key !== "Enter" && event.key !== " ")) return;
    event.preventDefault();
    onToggle();
  };
  return (
    <article
      role={hasDetail ? "button" : undefined}
      tabIndex={hasDetail ? 0 : undefined}
      aria-expanded={hasDetail ? open : undefined}
      aria-haspopup={hasDetail ? "dialog" : undefined}
      aria-label={hasDetail ? `${labelOf(result.choice)} 상세 설명 팝업 보기` : undefined}
      onClick={hasDetail ? onToggle : undefined}
      onKeyDown={toggleOnKey}
      className={`overflow-hidden rounded-2xl border bg-card transition-all ${
        hasDetail ? "cursor-pointer focus:outline-none focus:ring-2 focus:ring-violet-400/50" : ""
      } ${
        open
          ? side === "A"
            ? "border-violet-400/70 shadow-[0_0_24px_rgba(139,108,207,.16)]"
            : "border-orange-300/60 shadow-[0_0_24px_rgba(243,154,74,.13)]"
          : "border-line hover:border-white/20 hover:bg-white/[.025]"
      }`}
    >
      <div className="relative aspect-[4/5] overflow-hidden bg-[#0E1424] sm:aspect-video">
        {image ? (
          <>
            <img src={image} alt={`${labelOf(result.choice)} 시나리오 상상도`} className="h-full w-full object-cover" />
            <div className="pointer-events-none absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/95 via-black/65 to-transparent px-3 pb-3 pt-12 text-white lg:px-4 lg:pb-4 lg:pt-16">
              <p className="text-[9px] font-bold uppercase tracking-[.14em] text-white/70">{side} Universe · {labelOf(result.choice)}</p>
              {structured && story.title && <h3 className="mt-1 text-[13px] font-bold leading-snug drop-shadow lg:text-[15px]">{story.title}</h3>}
              {summary && <p className="mt-1 overflow-hidden text-[10px] leading-[1.45] text-white/85 drop-shadow lg:text-[11px]" style={{ display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical" }}>{summary}</p>}
            </div>
          </>
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-3 px-3 text-center">
            <Avatar config={avatar} size={92} />
            <span className="text-[10px] leading-relaxed text-mut">시뮬레이션을 실행하면<br />서사 기반 장면이 생성됩니다.</span>
          </div>
        )}
        <span className="absolute left-2 top-2 rounded-full border bg-[#0B0F1CDD] px-2 py-1 text-[9px] font-bold" style={{ color, borderColor: `${color}66` }}>UNIVERSE {side}</span>
      </div>
      <div className="p-2.5">
        <p className="text-xs font-bold" style={{ color }}>{labelOf(result.choice)}</p>
        {!image && structured && story.title && <h3 className="mt-1 text-[12px] font-semibold leading-snug text-ink">{story.title}</h3>}
        {!image && <p className="mt-1 text-[11px] leading-relaxed text-sub">{summary || (storyLoading ? "RAG 서사를 생성하고 있어요…" : "RAG 서사를 아직 생성하지 못했어요.")}</p>}
        {image && !summary && <p className="mt-1 text-[11px] leading-relaxed text-sub">{storyLoading ? "서사를 생성하고 있어요…" : "서사를 아직 생성하지 못했어요."}</p>}
        {hasDetail && <p className="mt-2 text-[9px] font-semibold text-mut">카드를 눌러 상세 설명 보기 ↗</p>}
      </div>
    </article>
  );
}

function StoryDetail({ side, story, image, choice, onClose }) {
  if (!story || typeof story !== "object") return null;
  const detail = story.detail || {};
  const isA = side === "A";
  const color = isA ? "text-violet-200" : "text-orange-200";
  const accent = isA ? "#9B72F2" : "#F39A4A";
  return (
    <div className="relative text-[12px] leading-relaxed">
      <div className="relative h-[220px] overflow-hidden sm:h-[290px]">
        {image && <img src={image} alt="" className="h-full w-full object-cover" />}
        <div className="absolute inset-0 bg-gradient-to-t from-[#09111F] via-[#09111F]/25 to-black/15" />
        <div className="absolute inset-0 opacity-40" style={{ background: `radial-gradient(circle at 20% 15%, ${accent}88, transparent 42%)` }} />
        <button type="button" onClick={onClose} aria-label="상세 설명 닫기" className="absolute right-4 top-4 flex h-9 w-9 items-center justify-center rounded-full border border-white/20 bg-black/35 text-xl text-white/80 backdrop-blur-md transition hover:bg-black/55 hover:text-white">×</button>
        <div className="absolute inset-x-0 bottom-0 px-5 pb-5 sm:px-7 sm:pb-7">
          <p className={`text-[10px] font-bold tracking-[.18em] ${color}`}>UNIVERSE {side} · {labelOf(choice)}</p>
          <h3 className="mt-1 max-w-[560px] text-[22px] font-bold leading-tight tracking-[-.035em] text-white sm:text-[28px]">{story.title || "상세 이야기"}</h3>
        </div>
      </div>

      <div className="relative -mt-1 px-4 pb-6 sm:px-7 sm:pb-8">
        {story.summary && <p className="rounded-2xl border border-white/10 bg-white/[.055] px-4 py-3.5 text-[12px] leading-6 text-white/80 shadow-[0_14px_40px_rgba(0,0,0,.22)] backdrop-blur-xl sm:px-5">{story.summary}</p>}
        <div className="relative mt-5 space-y-2.5 before:absolute before:bottom-4 before:left-[15px] before:top-4 before:w-px before:bg-gradient-to-b before:from-violet-400/55 before:via-white/15 before:to-transparent">
          <StoryBeat index="01" label="지금" text={detail.present} accent={accent} />
          <StoryBeat index="02" label="변화 과정" text={detail.transition} accent={accent} />
          <StoryBeat index="03" label="그 이후" text={detail.future} accent={accent} />
          <StoryBeat index="?" label="불확실한 점" text={story.uncertainty} accent={accent} />
        </div>
        {(story.gain || story.cost) && (
          <div className="mt-5 grid gap-2.5 sm:grid-cols-2">
            {story.gain && <p className="rounded-2xl border border-violet-400/20 bg-violet-500/[.07] p-4"><b className="text-violet-200">＋ 얻게 될 수 있는 것</b><br /><span className="mt-1.5 block text-sub">{story.gain}</span></p>}
            {story.cost && <p className="rounded-2xl border border-orange-300/20 bg-orange-400/[.06] p-4"><b className="text-orange-200">− 감수할 수 있는 것</b><br /><span className="mt-1.5 block text-sub">{story.cost}</span></p>}
          </div>
        )}
      </div>
    </div>
  );
}

function StoryBeat({ index, label, text, accent }) {
  if (!text) return null;
  return (
    <div className="relative grid grid-cols-[32px_1fr] gap-3 rounded-2xl border border-white/[.07] bg-[#0E192A]/80 p-3.5 shadow-[0_10px_28px_rgba(0,0,0,.16)]">
      <span className="relative z-10 flex h-8 w-8 items-center justify-center rounded-full border bg-[#0A1322] text-[9px] font-bold" style={{ color: accent, borderColor: `${accent}66`, boxShadow: `0 0 18px ${accent}22` }}>{index}</span>
      <p className="pt-0.5"><b className="text-[11px] tracking-[.04em] text-ink">{label}</b><br /><span className="mt-1 block leading-5 text-sub">{text}</span></p>
    </div>
  );
}

function Comparison({ story }) {
  const structured = typeof story === "object";
  const summary = structured ? story.summary : story;
  if (!summary) return null;
  return (
    <div className="relative overflow-hidden rounded-[20px] border border-white/10 bg-[#091321]/95 p-4 shadow-[0_18px_50px_rgba(0,0,0,.18)] lg:p-5">
      <div className="pointer-events-none absolute -left-16 -top-20 h-44 w-44 rounded-full bg-violet-500/10 blur-[55px]" />
      <div className="pointer-events-none absolute -bottom-24 -right-14 h-48 w-48 rounded-full bg-orange-400/[.07] blur-[60px]" />

      <div className="relative text-center">
        <span className="text-[9px] font-bold tracking-[.18em] text-violet-300/70">CORE INSIGHT</span>
        <h3 className="mt-1 text-[15px] font-bold tracking-[-.02em] text-ink lg:text-[17px]">두 선택의 핵심 차이</h3>
        <p className="mx-auto mt-2 max-w-[760px] text-[11px] leading-[1.65] text-sub lg:text-[12px]">{summary}</p>
      </div>

    </div>
  );
}
