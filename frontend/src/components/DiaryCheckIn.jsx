import { useState } from "react";
import { Card, Caption } from "./ui.jsx";
import { todayQuestions, CHECKIN, MOODS } from "../data/questions.js";
import { addCheckin, loadUniverse, todayKey } from "../data/myUniverse.js";

// 홈 "오늘 기록" 카드 — jy DiaryToday 포팅본(홈 배치).
//  · 30초 데일리: 기분 5단계(→ 그날 별 밝기) + 에너지·역량·감정 칩
//  · '자세히 답하기' → 오늘의 질문(고정2+랜덤2) → 성향 신호
//  · 저장은 minju 체크인(addCheckin), answers 는 [{q,a}] 배열
//  · 이미 오늘 기록했으면 요약으로 접힘(수정 가능)
export default function DiaryCheckIn({ onSaved }) {
  const today = todayKey();
  const [entry, setEntry] = useState(
    () => loadUniverse().checkins.find((c) => c.date === today) || null,
  );
  const [editing, setEditing] = useState(!entry);

  const [mood, setMood] = useState(entry?.mood ?? null);
  const [energy, setEnergy] = useState(entry?.energy ?? null);
  const [competency, setCompetency] = useState(entry?.skill ?? null);
  const [emotion, setEmotion] = useState(entry?.keyword ?? null);
  const [text, setText] = useState(entry?.text ?? "");
  const [openDetail, setOpenDetail] = useState(Boolean(entry?.answers?.length));

  const questions = todayQuestions();
  const [answers, setAnswers] = useState(() => {
    const init = {};
    (entry?.answers || []).forEach((qa) => {
      const found = questions.find((q) => q.text === qa.q);
      if (found) init[found.id] = qa.a;
    });
    return init;
  });

  const answeredCount = Object.values(answers).filter((v) => (v || "").trim()).length;

  function save() {
    const arr = questions
      .filter((q) => (answers[q.id] || "").trim())
      .map((q) => ({ q: q.text, a: answers[q.id].trim() }));
    const saved = {
      date: today,
      mood,
      text: text.trim(),
      answers: arr.length ? arr : null,
      energy,
      skill: competency,
      keyword: emotion,
    };
    addCheckin(saved);
    setEntry({ ...saved, valence: null });
    setEditing(false);
    onSaved?.();
  }

  // 이미 오늘 기록함 → 요약
  if (entry && !editing) {
    const nAns = Array.isArray(entry.answers) ? entry.answers.length : 0;
    return (
      <Card>
        <div className="flex items-center justify-between">
          <div className="text-xs font-bold text-cyan">오늘 기록 완료 ✦</div>
          <button onClick={() => setEditing(true)} className="tap text-[11px] text-mut">
            수정
          </button>
        </div>
        <div className="mt-2 flex items-center gap-2">
          <span className="text-2xl">{MOODS.find((m) => m.v === entry.mood)?.emoji || "✦"}</span>
          <p className="text-[13px] text-sub">{entry.text || entry.note || "(한 줄 없음)"}</p>
        </div>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {entry.keyword && <Tag>{entry.keyword}</Tag>}
          {entry.skill && <Tag>{entry.skill}</Tag>}
          {nAns > 0 && <Tag>질문 {nAns}개 ✍️</Tag>}
        </div>
        <Caption>오늘 별 하나가 밝혀졌어요.</Caption>
      </Card>
    );
  }

  return (
    <Card>
      <div className="mb-2 text-sm font-bold">
        오늘, 어땠나요? <span className="text-[11px] font-normal text-mut">· 30초</span>
      </div>

      {/* 기분 5단계 — 그날 별의 밝기 */}
      <div className="flex justify-between">
        {MOODS.map((m) => {
          const on = m.v === mood;
          return (
            <button
              key={m.v}
              onClick={() => setMood(m.v)}
              className={`tap flex flex-1 flex-col items-center gap-0.5 rounded-xl py-1.5 transition-colors ${
                on ? "bg-[#1D1730]" : ""
              }`}
            >
              <span className={`text-2xl transition-transform ${on ? "scale-110" : "opacity-60"}`}>
                {m.emoji}
              </span>
              <span className={`text-[9px] ${on ? "text-cyan" : "text-mut"}`}>{m.label}</span>
            </button>
          );
        })}
      </div>

      {/* 데일리 칩 3개 */}
      <div className="mt-3 border-t border-line pt-3">
        <ChipRow label={CHECKIN.energy.q}>
          {CHECKIN.energy.opts.map((o) => (
            <Chip key={o.v} on={energy === o.v} onClick={() => setEnergy(o.v)}>
              {o.emoji}
              <span className="ml-0.5">{o.label}</span>
            </Chip>
          ))}
        </ChipRow>

        <ChipRow label={CHECKIN.competency.q}>
          {CHECKIN.competency.opts.map((c) => (
            <Chip key={c} on={competency === c} onClick={() => setCompetency(c)}>
              {c}
            </Chip>
          ))}
        </ChipRow>

        <ChipRow label={CHECKIN.emotion.q}>
          {CHECKIN.emotion.opts.map((o) => (
            <Chip key={o.key} on={emotion === o.key} onClick={() => setEmotion(o.key)}>
              {o.emoji} {o.key}
            </Chip>
          ))}
        </ChipRow>
      </div>

      <input
        value={text}
        onChange={(e) => setText(e.target.value)}
        maxLength={80}
        placeholder="한 줄로 남겨보세요 (예: 새 팀 적응이 막막함)"
        className="mt-1 w-full rounded-xl border border-line bg-[#0E1424] px-3.5 py-2.5 text-sm text-ink outline-none focus:border-cyan"
      />

      {!openDetail && (
        <button
          onClick={() => setOpenDetail(true)}
          className="tap mt-3 flex w-full items-center justify-center gap-1.5 rounded-2xl border border-cyan bg-[#1D1730] py-3 text-[13px] font-bold text-cyan"
        >
          ✍️ 오늘의 질문에 자세히 답하기
          <span className="text-[11px] font-normal text-sub">· 4문항</span>
        </button>
      )}

      {openDetail && (
        <div className="mt-3 border-t border-line pt-3">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-[12px] font-bold text-cyan">
              ✍️ 자세히 남기기 <span className="font-normal text-mut">· 오늘의 질문 (선택)</span>
            </span>
            <button onClick={() => setOpenDetail(false)} className="tap text-[11px] text-mut">
              접기
            </button>
          </div>
          <div className="flex flex-col gap-2.5">
            {questions.map((q, i) => (
              <div key={q.id}>
                <p className="mb-1 text-[12px] leading-snug text-sub">
                  <b className="mr-1 text-cyan">{i + 1}.</b>
                  {q.text}
                </p>
                <textarea
                  value={answers[q.id] || ""}
                  onChange={(e) => setAnswers((a) => ({ ...a, [q.id]: e.target.value }))}
                  rows={2}
                  placeholder="편하게 적어보세요"
                  className="w-full resize-none rounded-xl border border-line bg-[#0E1424] px-3 py-2 text-[13px] text-ink outline-none focus:border-cyan"
                />
              </div>
            ))}
          </div>
          <Caption>답한 질문일수록 성향을 더 정확히 읽어요.</Caption>
        </div>
      )}

      <button
        disabled={!mood}
        onClick={save}
        className={`tap mt-3 w-full rounded-2xl py-2.5 text-[13px] font-bold transition-colors ${
          mood ? "bg-[#8B6CCF] text-white" : "bg-[#1E2740] text-mut"
        }`}
      >
        기록 저장{answeredCount > 0 ? ` · 질문 ${answeredCount}개` : ""}
      </button>
      <Caption>기분을 고르면 오늘 별 하나가 밝혀집니다.</Caption>
    </Card>
  );
}

function ChipRow({ label, children }) {
  return (
    <div className="mb-2.5">
      <div className="mb-1 text-[11px] text-mut">{label}</div>
      <div className="flex flex-wrap gap-1.5">{children}</div>
    </div>
  );
}

function Chip({ on, onClick, children }) {
  return (
    <button
      onClick={onClick}
      className={`tap !min-h-0 h-[30px] rounded-full border px-2 py-0 text-[12px] leading-none transition-colors ${
        on ? "border-cyan bg-[#1D1730] text-cyan" : "border-line text-sub"
      }`}
    >
      {children}
    </button>
  );
}

function Tag({ children }) {
  return (
    <span className="rounded-full border border-line px-2 py-0.5 text-[10px] text-sub">
      {children}
    </span>
  );
}
