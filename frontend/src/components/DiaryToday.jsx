import { useEffect, useMemo, useRef, useState } from "react";
import { Caption } from "./ui.jsx";
import { useDiary, MOODS } from "../data/DiaryContext.jsx";
import { CHECKIN } from "../data/questions.js";
import ChatDiary from "./ChatDiary.jsx";
import { composeDiary, analyzeEmotion } from "../data/dispositionApi.js";
import Mascot from "./Mascot.jsx";
import { Clock3, X } from "lucide-react";
import HomeCalendar from "./HomeCalendar.jsx";
import { loadActiveGoal, saveActionResponse } from "../data/actionBridge.js";
import { logExperiment } from "../data/myUniverse.js";

const GUIDES = [
  { key: "daily", mascot: "nova", name: "노바", topic: "오늘의 일상", color: "#FF9EC0", prompt: "오늘 있었던 일, 나와 같이 돌아볼래요?" },
  { key: "disposition", mascot: "cosmo", name: "코스모", topic: "고민과 선택", color: "#8B6CCF", prompt: "고민 중인 갈림길, 같이 비춰볼까요?" },
  { key: "health", mascot: "lumi", name: "루미", topic: "몸과 마음", color: "#FFD97A", prompt: "몸과 마음의 신호를 천천히 살펴봐요." },
];

// 일기 화면의 기록 작성 영역 — 2층 일기.
//  · 30초 데일리: 기분 5단계(→ 그날 별 밝기) + 에너지·역량·감정키워드 칩
//  · '자세히 답하기' 버튼 → 오늘의 질문(고정2+랜덤2) 펼침 → 성향 신호
export default function DiaryToday() {
  const { entries, saveToday, todayEntry, lastSim, daysSince } = useDiary();
  const [mood, setMood] = useState(todayEntry?.mood ?? null);
  const [energy, setEnergy] = useState(todayEntry?.energy ?? null);
  const [competency, setCompetency] = useState(todayEntry?.competency ?? null);
  const [emotion, setEmotion] = useState(todayEntry?.emotion ?? null);
  const [text, setText] = useState(todayEntry?.text ?? "");
  const [chatMsgs, setChatMsgs] = useState([]); // 챗봇 대화(오늘의 질문·상태) → 저장 시 흡수
  const [activeGuide, setActiveGuide] = useState(null);
  const [checkinOpen, setCheckinOpen] = useState(false);
  const [checkinDone, setCheckinDone] = useState(Boolean(todayEntry?.mood || todayEntry?.energy || todayEntry?.emotion));
  const [activeGoal] = useState(loadActiveGoal);
  const [experimentResult, setExperimentResult] = useState(todayEntry?.experimentResult ?? null);
  const [savedSummary, setSavedSummary] = useState(null);

  const tag = `${lastSim.label} 이후 ${daysSince(lastSim.date)}일째`;

  const chatHasUser = chatMsgs.some((m) => m.role === "user");

  const experimentPrompt = activeGoal ? goalPrompt(activeGoal) : null;
  const changeSummary = useMemo(() => summarizeChange(entries, mood, energy, activeGoal), [entries, mood, energy, activeGoal]);

  async function save(closeAfter = false) {
    // 챗봇 답변을 '질문 → 답변' 그대로 정리해 일기 본문으로(오늘의질문·건강 대체).
    const qaLines = [];
    for (let i = 0; i < chatMsgs.length; i++) {
      if (chatMsgs[i].role !== "user") continue;
      const ans = (chatMsgs[i].text || "").trim();
      if (!ans || ans === "기록 안 함") continue;
      const q = i > 0 && chatMsgs[i - 1].role === "bot" ? chatMsgs[i - 1].text : null;
      qaLines.push(q ? `· ${q} → ${ans}` : `· ${ans}`);
    }
    const line = text.trim();
    const experimentLine = experimentPrompt && experimentResult
      ? `· 진행 중인 선택 점검: ${experimentPrompt} → ${experimentResult}` : "";
    const bodyText = [line, experimentLine, ...qaLines].filter(Boolean).join("\n");
    // 감정/기분을 안 골랐으면 → 내가 만든 감정모델로 일기에서 추론(우선).
    let finalMood = mood;
    let finalEmotion = emotion;
    let composed = null;
    if (chatHasUser) {
      try {
        composed = await composeDiary(chatMsgs);
      } catch {
        composed = null;
      }
    }
    if ((finalMood == null || !finalEmotion) && bodyText) {
      const em = await analyzeEmotion(bodyText);
      if (em) {
        if (!finalEmotion) finalEmotion = em.emotion || finalEmotion;
        if (finalMood == null && em.mood != null) finalMood = em.mood;
      }
    }
    // 감정모델 불가(체크포인트 없음 등)로 기분이 여전히 비었으면 → LLM compose 폴백.
    if (finalMood == null && chatHasUser) {
      finalMood = composed?.mood ?? 3;
      if (!finalEmotion) finalEmotion = composed?.emotion || null;
    }
    saveToday(finalMood, bodyText, null, {
      energy,
      competency,
      emotion: finalEmotion,
      insights: composed?.insights || null,
      chatSummary: composed?.text || null,
    });
    if (activeGoal && experimentResult) {
      const actionId = `checkin:${activeGoal.side || "goal"}:${activeGoal.createdAt || activeGoal.choice}`;
      saveActionResponse(actionId, experimentResult);
      logExperiment({ actionId, prompt: experimentPrompt, text: experimentResult });
    }
    setCheckinDone(true);
    setSavedSummary(changeSummary);
    if (closeAfter) setCheckinOpen(false);
  }

  return (
    <section className="w-full">
      <GuideCarousel onOpen={setActiveGuide} />
      <WeekStrip entries={entries} />

      <div className="mt-6 flex items-center justify-between border-t border-white/[.08] pt-6">
        <div>
          <div className="text-sm font-bold">오늘 기록하기</div>
          <div className="mt-0.5 text-[10px] text-mut">가볍게 한 줄만 남겨도 괜찮아요.</div>
        </div>
        {checkinDone && <span className="rounded-full bg-cyan/10 px-2.5 py-1.5 text-[10px] font-semibold text-cyan">체크인 완료</span>}
      </div>

      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        maxLength={80}
        rows={2}
        placeholder="오늘을 한 줄로 남겨보세요"
        className="mt-3 w-full resize-none rounded-2xl border border-line bg-[#0E1424] px-3.5 py-3 text-sm leading-relaxed text-ink outline-none placeholder:text-mut focus:border-cyan"
      />

      {(mood || energy || emotion) && (
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          {mood && <Tag>{MOODS.find((item) => item.v === mood)?.emoji} {MOODS.find((item) => item.v === mood)?.label}</Tag>}
          {energy && <Tag>에너지 {energy}</Tag>}
          {emotion && <Tag>{emotion}</Tag>}
        </div>
      )}
      {(savedSummary || (checkinDone && changeSummary)) && (
        <div className="mt-3 rounded-2xl border border-violet-400/20 bg-violet-500/[.07] p-3">
          <div className="text-[10px] font-bold text-violet-300">오늘의 변화</div>
          <p className="mt-1 text-[11px] leading-relaxed text-sub">{savedSummary || changeSummary}</p>
          {activeGoal && <p className="mt-1.5 text-[9px] text-mut">진행 중 · {activeGoal.choice}</p>}
        </div>
      )}

      <button
        type="button"
        onClick={() => setCheckinOpen(true)}
        className={`tap mt-4 w-full rounded-2xl py-3 text-[13px] font-bold ${
          checkinDone
            ? "border border-line bg-[#121A2A] text-sub"
            : "bg-gradient-to-r from-[#7652E8] to-[#A783FF] text-white shadow-[0_10px_28px_rgba(118,82,232,.3)]"
        }`}
      >
        <span className="inline-flex items-center justify-center gap-2"><Clock3 size={16} />{checkinDone ? "30초 체크인 수정" : "30초 체크인 하기"}</span>
      </button>

      <button
        disabled={!checkinDone}
        onClick={save}
        className={`tap mt-3 w-full rounded-2xl py-2.5 text-[13px] font-bold transition-colors ${
          checkinDone ? "bg-[#8B6CCF] text-white" : "bg-[#1E2740] text-mut"
        }`}
      >
        기록 저장
      </button>
      {checkinOpen && (
        <div
          className="fixed inset-0 z-50 flex animate-backdrop-in items-end justify-center bg-[#02050C]/70 backdrop-blur-[4px]"
          onClick={() => setCheckinOpen(false)}
        >
          <div
            className="flex max-h-[min(88dvh,760px)] w-full max-w-phone animate-sheet-up flex-col overflow-hidden rounded-t-[36px] border border-b-0 border-[#26324A] bg-[#111A2A] shadow-[0_-22px_60px_rgba(0,0,0,.45)]"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="sticky top-0 z-10 rounded-t-[36px] bg-[#111A2A]/95 px-5 pb-3 pt-3 backdrop-blur">
              <div className="mx-auto mb-3 h-1 w-11 rounded-full bg-[#647087]/65" />
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-[11px] font-bold text-violet-400">30초 체크인</div>
                  <h2 className="mt-1 text-[22px] font-bold tracking-[-.02em]">오늘, 어땠나요?</h2>
                </div>
                <button type="button" onClick={() => setCheckinOpen(false)} className="tap flex h-10 w-10 items-center justify-center rounded-full bg-[#202B3E] text-sub" aria-label="체크인 닫기">
                  <X size={18} />
                </button>
              </div>
            </div>

            <div className="min-h-0 flex-1 space-y-6 overflow-y-auto px-5 pb-8 pt-2">
              <section>
                <div className="mb-3 text-[13px] font-bold text-sub">지금 기분은 어떤가요?</div>
                <div className="grid grid-cols-5 gap-2">
                  {MOODS.map((item) => {
                    const on = item.v === mood;
                    return (
                      <button
                        key={item.v}
                        type="button"
                        onClick={() => setMood(item.v)}
                        className={`tap flex min-w-0 flex-col items-center rounded-[22px] border py-3 ${on ? "border-[#8B6CCF] bg-[#241A3B] shadow-[0_0_0_1px_rgba(139,108,207,.18)]" : "border-[#2A3549] bg-[#182234]"}`}
                      >
                        <span className={`text-[27px] leading-none ${on ? "scale-110" : "opacity-80"}`}>{item.emoji}</span>
                        <span className={`mt-2 text-[10px] ${on ? "font-semibold text-white" : "text-mut"}`}>{item.label}</span>
                      </button>
                    );
                  })}
                </div>
              </section>

              {experimentPrompt && (
                <section className="rounded-[20px] border border-[#8B6CCF]/30 bg-[#8B6CCF]/[.08] p-4">
                  <div className="text-[10px] font-bold text-violet-300">진행 중인 선택 · {activeGoal.choice}</div>
                  <div className="mt-2 text-[13px] font-bold text-ink">{experimentPrompt}</div>
                  <div className="mt-3 grid grid-cols-3 gap-2">
                    {["했어요", "조금 했어요", "못 했어요"].map((value) => <button key={value} type="button" onClick={() => setExperimentResult(value)} className={`tap rounded-xl border px-2 py-2.5 text-[11px] font-semibold ${experimentResult === value ? "border-[#8B6CCF] bg-[#241A3B] text-white" : "border-[#2A3549] bg-[#182234] text-sub"}`}>{value}</button>)}
                  </div>
                </section>
              )}

              <section>
                <div className="mb-3 text-[13px] font-bold text-sub">{CHECKIN.energy.q}</div>
                <div className="flex flex-wrap gap-2">
                  {CHECKIN.energy.opts.map((option) => {
                    const on = energy === option.v;
                    return (
                      <button key={option.v} type="button" onClick={() => setEnergy(option.v)} className={`tap rounded-full border px-5 py-2.5 text-[12px] font-semibold ${on ? "border-[#8B6CCF] bg-[#241A3B] text-white" : "border-[#2A3549] bg-[#182234] text-sub"}`}>
                        {option.label}
                      </button>
                    );
                  })}
                </div>
              </section>

              <section>
                <div className="mb-3 text-[13px] font-bold text-sub">{CHECKIN.competency.q}</div>
                <div className="flex flex-wrap gap-2">
                  {CHECKIN.competency.opts.map((item) => {
                    const on = competency === item;
                    return <button key={item} type="button" onClick={() => setCompetency(item)} className={`tap rounded-full border px-4 py-2.5 text-[12px] font-semibold ${on ? "border-[#8B6CCF] bg-[#241A3B] text-white" : "border-[#2A3549] bg-[#182234] text-sub"}`}>{item}</button>;
                  })}
                </div>
              </section>

              <section>
                <div className="mb-3 text-[13px] font-bold text-sub">{CHECKIN.emotion.q}</div>
                <div className="flex flex-wrap gap-2">
                  {CHECKIN.emotion.opts.map((option) => {
                    const on = emotion === option.key;
                    return <button key={option.key} type="button" onClick={() => setEmotion(option.key)} className={`tap rounded-full border px-4 py-2.5 text-[12px] font-semibold ${on ? "border-[#8B6CCF] bg-[#241A3B] text-white" : "border-[#2A3549] bg-[#182234] text-sub"}`}>{option.emoji} {option.key}</button>;
                  })}
                </div>
              </section>
            </div>

            <div className="relative z-20 shrink-0 border-t border-[#26324A] bg-[#111A2A] px-5 pb-[max(20px,env(safe-area-inset-bottom))] pt-4 shadow-[0_-12px_28px_rgba(3,8,18,.72)]">
              <button
                type="button"
                onClick={() => save(true)}
                className="tap w-full rounded-full bg-[#8B6CCF] py-3.5 text-[14px] font-bold text-white shadow-[0_12px_30px_rgba(77,54,126,.34)]"
              >
                오늘의 변화 저장하기
              </button>
              <p className="mt-2 text-center text-[10px] text-mut">저장하면 다음 미래 비교와 진행 중인 선택 점검에 반영돼요.</p>
            </div>
          </div>
        </div>
      )}

      {activeGuide && (
        <div
          className="fixed inset-0 z-50 bg-[#070B14]/95"
          onClick={() => setActiveGuide(null)}
        >
          <div
            className="mx-auto flex h-full max-w-phone flex-col px-5 pb-6 pt-5"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-center justify-between">
              <button
                type="button"
                onClick={() => setActiveGuide(null)}
                className="tap flex h-10 w-10 items-center justify-center rounded-full bg-card text-sub"
                aria-label="대화 닫기"
              >
                <X size={18} />
              </button>
              <div className="text-center">
                <div className="text-[13px] font-bold" style={{ color: activeGuide.color }}>{activeGuide.name}와 대화</div>
                <div className="text-[10px] text-mut">{activeGuide.topic}</div>
              </div>
              <div className="h-10 w-10" />
            </div>

            <div className="mt-5 flex justify-center">
              <div className="rounded-full bg-white/5 p-3 shadow-[0_0_32px_rgba(124,195,255,.18)]">
                <Mascot which={activeGuide.mascot} size={68} />
              </div>
            </div>

            <div className="mt-5 min-h-0 flex-1 overflow-y-auto rounded-[24px] border border-line bg-card p-4">
              <ChatDiary
                key={activeGuide.key}
                embedded
                initialArea={activeGuide.key}
                showAreas={false}
                onMessagesChange={setChatMsgs}
              />
            </div>

            <button
              type="button"
              onClick={() => setActiveGuide(null)}
              className="tap mt-4 w-full rounded-2xl bg-cyan py-3 text-[13px] font-bold text-[#04203a]"
            >
              대화 반영하고 돌아가기
            </button>
            <p className="mt-2 text-center text-[10px] text-mut">대화는 홈의 ‘기록 저장’을 누르면 오늘 일기에 함께 저장돼요.</p>
          </div>
        </div>
      )}
    </section>
  );
}

function goalPrompt(goal) {
  const domains = goal.domains || [];
  const choice = String(goal.choice || "이 선택");
  if (domains.includes("relationship")) return /거리/.test(choice) ? "거리를 둔 뒤 내 마음을 살펴봤나요?" : "상대에게 내 마음이나 경계를 표현했나요?";
  if (domains.includes("career")) return "오늘 이 선택을 확인하기 위한 행동을 하나 했나요?";
  if (domains.includes("health")) return "오늘 계획한 회복·건강 행동을 실천했나요?";
  if (domains.includes("education")) return "오늘 배우거나 정보를 확인하는 행동을 했나요?";
  return "오늘 이 선택에 가까워지는 작은 행동을 했나요?";
}

function summarizeChange(entries, mood, energy, goal) {
  const previous = (entries || []).filter((entry) => entry.mood != null).slice(-7);
  if (mood == null && energy == null) return goal ? "상태를 기록하면 이 선택을 실행한 날의 변화를 비교할 수 있어요." : "상태를 기록하면 최근 흐름과 비교해드려요.";
  if (previous.length < 2) return `오늘의 기준선을 저장했어요. ${3 - Math.min(previous.length, 2)}번 더 기록하면 최근 흐름과 비교할 수 있어요.`;
  const avg = previous.reduce((sum, entry) => sum + Number(entry.mood || 0), 0) / previous.length;
  const diff = mood == null ? 0 : mood - avg;
  const moodText = Math.abs(diff) < .35 ? "최근과 비슷한 기분이에요" : diff > 0 ? "최근 평균보다 기분이 나아요" : "최근 평균보다 기분이 낮아요";
  return `${moodText}${energy != null ? ` · 에너지 ${energy}/5` : ""}. ${goal ? "진행 중인 선택과 함께 변화를 이어서 볼게요." : "이 기록은 다음 비교의 현재 상태로 사용돼요."}`;
}

function GuideCarousel({ onOpen }) {
  const [index, setIndex] = useState(1);
  const trackRef = useRef(null);
  const dragRef = useRef({ active: false, x: 0, left: 0, moved: false });
  const guide = GUIDES[index];

  function centerItem(nextIndex, smooth = true) {
    const track = trackRef.current;
    const item = track?.querySelectorAll("[data-guide]")?.[nextIndex];
    if (!track || !item) return;
    const left = item.offsetLeft - (track.clientWidth - item.clientWidth) / 2;
    track.scrollTo({ left, behavior: smooth ? "smooth" : "auto" });
    setIndex(nextIndex);
    if (!smooth) requestAnimationFrame(updateOrbit);
  }

  useEffect(() => {
    const timer = requestAnimationFrame(() => centerItem(1, false));
    return () => cancelAnimationFrame(timer);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  function nearestIndex() {
    const track = trackRef.current;
    if (!track) return index;
    const center = track.scrollLeft + track.clientWidth / 2;
    let nearest = 0;
    let distance = Infinity;
    Array.from(track.querySelectorAll("[data-guide]")).forEach((item, itemIndex) => {
      const gap = Math.abs(item.offsetLeft + item.clientWidth / 2 - center);
      if (gap < distance) {
        nearest = itemIndex;
        distance = gap;
      }
    });
    return nearest;
  }

  function updateOrbit() {
    const track = trackRef.current;
    if (!track) return;
    const center = track.scrollLeft + track.clientWidth / 2;

    Array.from(track.querySelectorAll("[data-guide]")).forEach((item) => {
      const itemCenter = item.offsetLeft + item.clientWidth / 2;
      const distancePx = Math.abs(itemCenter - center);
      const distance = Math.min(1, distancePx / (item.clientWidth * 0.92));
      // A quadratic curve makes the guides follow a rounded hill instead of a V-shaped path.
      const lift = -18 + (distance * distance) * 46;
      const scale = 1 - distance * 0.22;
      const opacity = 1 - distance * 0.55;
      item.style.transform = `translateY(${lift}px) scale(${scale})`;
      item.style.opacity = String(opacity);
    });

  }

  function finishDrag(event) {
    if (!dragRef.current.active) return;
    dragRef.current.active = false;
    event.currentTarget.releasePointerCapture?.(event.pointerId);
    centerItem(nearestIndex());
  }

  return (
    <div className="mb-5 border-b border-line pb-5">
      <button
        type="button"
        onClick={() => onOpen(guide)}
        className="tap relative mx-auto mb-2 block max-w-[280px] rounded-[20px] border border-line bg-[#1B2438] px-4 py-2.5 text-center text-[12px] font-semibold text-ink"
      >
        {guide.prompt}
        <span className="absolute -bottom-1.5 left-1/2 h-3 w-3 -translate-x-1/2 rotate-45 border-b border-r border-line bg-[#1B2438]" />
      </button>

      <div className="relative overflow-hidden pb-3 pt-2">
        <div className="pointer-events-none absolute -bottom-[74px] left-1/2 h-[138px] w-[118%] -translate-x-1/2 rounded-[50%] border-t border-[#2A3850] bg-[radial-gradient(ellipse_at_top,rgba(57,86,130,.20),rgba(17,27,43,.05)_55%,transparent_72%)]" />
        <div
        ref={trackRef}
        onScroll={updateOrbit}
        onPointerDown={(event) => {
          dragRef.current = {
            active: true,
            x: event.clientX,
            left: event.currentTarget.scrollLeft,
            moved: false,
          };
          event.currentTarget.setPointerCapture?.(event.pointerId);
        }}
        onPointerMove={(event) => {
          if (!dragRef.current.active) return;
          const distance = event.clientX - dragRef.current.x;
          if (Math.abs(distance) > 6) dragRef.current.moved = true;
          event.currentTarget.scrollLeft = dragRef.current.left - distance;
          updateOrbit();
        }}
        onPointerUp={finishDrag}
        onPointerCancel={finishDrag}
        className="no-scrollbar relative z-10 flex cursor-grab snap-x snap-proximity scroll-smooth overflow-x-auto pb-3 pt-2 active:cursor-grabbing"
        style={{ touchAction: "pan-y" }}
      >
        <span aria-hidden="true" className="w-[34%] shrink-0" />
        {GUIDES.map((item) => {
          return (
            <button
              type="button"
              key={item.key}
              data-guide
              onClick={() => {
                if (dragRef.current.moved) {
                  dragRef.current.moved = false;
                  return;
                }
                onOpen(item);
              }}
              aria-label={`${item.name}와 대화하기`}
              className="tap flex w-[32%] shrink-0 snap-center flex-col items-center justify-center py-3 will-change-transform transition-[transform,opacity] duration-300 ease-out"
            >
              <span
                className="flex h-32 w-32 items-center justify-center rounded-full"
                style={{ background: `radial-gradient(circle, ${item.color}35 0%, ${item.color}18 45%, transparent 70%)` }}
              >
                <Mascot which={item.mascot} size={112} />
              </span>
              <span className="mt-2 text-[14px] font-bold" style={{ color: item.color }}>{item.name}</span>
              <span className="text-[10px] text-mut">{item.topic}</span>
            </button>
          );
        })}
        <span aria-hidden="true" className="w-[34%] shrink-0" />
        </div>
      </div>

      <div className="mt-1 flex justify-center gap-1.5">
        {GUIDES.map((item, itemIndex) => (
          <button
            type="button"
            key={item.key}
            onClick={() => centerItem(itemIndex)}
            aria-label={`${item.name} 선택`}
            className={`h-1.5 rounded-full ${itemIndex === index ? "w-5 bg-cyan" : "w-1.5 bg-[#3A4358]"}`}
          />
        ))}
      </div>
    </div>
  );
}

function WeekStrip({ entries }) {
  const [calendarOpen, setCalendarOpen] = useState(false);
  const today = new Date();
  const days = Array.from({ length: 7 }, (_, index) => {
    const date = new Date(today);
    date.setDate(today.getDate() - (6 - index));
    const offset = date.getTimezoneOffset() * 60000;
    const key = new Date(date.getTime() - offset).toISOString().slice(0, 10);
    return { date, key, entry: entries.find((item) => item.date === key) };
  });
  const moodEmoji = ["", "😞", "😕", "😐", "🙂", "😄"];

  return (
    <div className="mb-5 border-b border-line pb-4">
      <div className="mb-2 flex items-center justify-between"><span className="text-[11px] font-semibold text-sub">최근 7일</span><button type="button" onClick={()=>setCalendarOpen(true)} className="tap rounded-full border border-white/10 px-3 py-1.5 text-[10px] text-[#BBA4ED]">전체 캘린더 보기</button></div>
      <div className="grid grid-cols-7 gap-1">
        {days.map(({ date, key, entry }, index) => {
          const isToday = index === days.length - 1;
          return (
            <div key={key} className={`flex min-w-0 flex-col items-center rounded-2xl py-2 ${isToday ? "border border-cyan/35 bg-cyan/10" : ""}`}>
              <span className={`text-[9px] ${isToday ? "font-semibold text-cyan" : "text-mut"}`}>
                {new Intl.DateTimeFormat("ko-KR", { weekday: "short" }).format(date)}
              </span>
              <span className={`mt-0.5 text-[12px] font-bold ${isToday ? "text-cyan" : "text-sub"}`}>{date.getDate()}</span>
              <span className="mt-1 flex h-4 items-center justify-center text-[12px]">
                {entry ? moodEmoji[entry.mood] || "✦" : <i className="h-1 w-1 rounded-full bg-line" />}
              </span>
            </div>
          );
        })}
      </div>
      {calendarOpen&&<div className="fixed inset-0 z-[90] flex items-end justify-center bg-[#02040B]/75 p-4 backdrop-blur-sm md:items-center" onClick={()=>setCalendarOpen(false)}><div className="max-h-[92dvh] w-full max-w-[820px] overflow-y-auto rounded-[26px]" onClick={(e)=>e.stopPropagation()}><div className="sticky top-2 z-10 flex justify-end px-2"><button type="button" onClick={()=>setCalendarOpen(false)} className="tap flex h-10 w-10 items-center justify-center rounded-full border border-white/10 bg-[#0B1322] text-sub"><X size={17}/></button></div><div className="-mt-12"><HomeCalendar /></div></div></div>}
    </div>
  );
}

function ChipRow({ label, hint, children }) {
  return (
    <div className="mb-3.5 last:mb-0">
      <div className="mb-2 text-[12.5px] font-medium text-ink/90">
        {label}
        {hint && <span className="ml-1 text-[10px] text-mut">{hint}</span>}
      </div>
      <div className="flex flex-wrap gap-2">{children}</div>
    </div>
  );
}

function Chip({ on, onClick, children, dense = false, full = false }) {
  return (
    <button
      onClick={onClick}
      className={`tap !min-h-0 h-[30px] whitespace-nowrap rounded-full border px-2 py-0 text-[12px] font-medium leading-none transition-colors ${
        full ? "flex w-full items-center justify-center" : ""
      } ${
        on ? "border-cyan bg-cyan/15 text-cyan" : "border-line bg-card2 text-sub hover:text-ink"
      }`}
    >
      {children}
    </button>
  );
}

function Tag({ children }) {
  return (
    <span className="rounded-md border border-line bg-[#0E1424] px-2 py-0.5 text-[10px] text-mut">
      {children}
    </span>
  );
}
