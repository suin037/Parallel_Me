import { useState } from "react";
import Avatar from "../Avatar.jsx";
import { labelOf } from "../../data/prediction.js";

export default function AvatarComparison({ avatar, a, b, visuals, narrative, narrativeLoading, loading, error, onRetry }) {
  const [expanded, setExpanded] = useState(null);
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

      {expanded && (
        <StoryDetail side={expanded} story={expanded === "A" ? narrative?.a : narrative?.b} />
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
  return (
    <article className="overflow-hidden rounded-2xl border border-line bg-card">
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
        {hasDetail && (
          <button
            type="button"
            aria-expanded={open}
            onClick={onToggle}
            className="tap mt-2 w-full rounded-lg border border-line px-2 py-1.5 text-[10px] font-semibold text-sub"
          >
            {open ? "구체적인 설명 접기 ▲" : "구체적인 설명 보기 ▼"}
          </button>
        )}
      </div>
    </article>
  );
}

function StoryDetail({ side, story }) {
  if (!story || typeof story !== "object") return null;
  const detail = story.detail || {};
  const color = side === "A" ? "text-cyan" : "text-gold";
  return (
    <div className="mt-2.5 rounded-xl border border-line bg-card p-3.5 text-[12px] leading-relaxed">
      <p className={`mb-2 text-[11px] font-bold ${color}`}>UNIVERSE {side} · 상세 이야기</p>
      <div className="space-y-3">
        <StoryBeat label="지금" text={detail.present} />
        <StoryBeat label="변화 과정" text={detail.transition} />
        <StoryBeat label="그 이후" text={detail.future} />
        <StoryBeat label="불확실한 점" text={story.uncertainty} />
        {(story.gain || story.cost) && (
          <div className="grid grid-cols-2 gap-2 rounded-lg bg-[#0E1424] p-2.5 text-[11px]">
            {story.gain && <p><b className="text-cyan">얻게 될 수 있는 것</b><br /><span className="text-sub">{story.gain}</span></p>}
            {story.cost && <p><b className="text-gold">감수할 수 있는 것</b><br /><span className="text-sub">{story.cost}</span></p>}
          </div>
        )}
      </div>
    </div>
  );
}

function StoryBeat({ label, text }) {
  if (!text) return null;
  return <p><b className="text-ink">{label}</b><br /><span className="text-sub">{text}</span></p>;
}

function Comparison({ story }) {
  const structured = typeof story === "object";
  const summary = structured ? story.summary : story;
  if (!summary) return null;
  return (
    <div className="rounded-xl border border-violet-400/20 bg-violet-500/[.06] p-3">
      <div className="flex items-center justify-between gap-2">
        <p className="text-[10px] font-bold tracking-wide text-violet-200">두 선택을 가르는 핵심 차이</p>
        <span className="shrink-0 text-[9px] text-mut">AI 비교 요약</span>
      </div>
      <p className="mt-1 text-[11px] leading-relaxed text-sub">{summary}</p>
      {structured && story.question && (
        <p className="mt-2 border-t border-line pt-2 text-[11px] leading-relaxed text-ink">{story.question}</p>
      )}
    </div>
  );
}
