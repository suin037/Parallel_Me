import { useState, useRef, useEffect } from "react";
import { Card, Caption } from "./ui.jsx";
import { addCheckin, todayKey, loadUniverse, weekStartKey } from "../data/myUniverse.js";
import { tagEntry } from "../data/tagging.js";
import { chatTurn, composeDiary, weeklyComfort, loadSpeech, SPEECH_KEY } from "../data/dispositionApi.js";
import { todayQuestions } from "../data/questions.js";
import { useResult } from "../data/ResultContext.jsx";
import Mascot from "./Mascot.jsx";
import storage from "../data/safeStorage.js";

// 질문 영역별 대화형 일기(jy). 데일리 체크인 아래 '오늘의 질문 + 몸·마음 상태'를 대신한다.
//  · 영역 3개: 일상 / 성향(매일 랜덤 질문) / 건강. 각 영역의 질문 리스트를 하나씩 묻고 사용자가 답한다.
//  · embedded=true: 카드/저장버튼 없이 대화만. onMessagesChange 로 부모(체크인)에 올림 → 부모 '기록 저장'이 흡수.
const AREAS = [
  { key: "daily", name: "오늘 돌아보기", desc: "한 일과 기억에 남은 순간을 기록해요.", mascot: "nova", role: "오늘 하루의 일상 기록을 함께 되짚는 대화다." },
  { key: "disposition", name: "선택 정리", desc: "고민 중인 선택과 중요한 기준을 정리해요.", mascot: "cosmo", role: "가치관·선택을 돌아보는 성향 기록 대화다." },
  { key: "health", name: "몸·마음 체크", desc: "수면·활동·스트레스 상태를 확인해요.", mascot: "lumi", role: "몸과 마음 상태를 살피는 건강 체크 대화다." },
];

const COSMO_PROMPT_KEY = "pm.cosmoDecisionPrompt.v1";
const COSMO_DECISION_Q = [
  { id: "decision_options", kind: "decision", p: "요즘 두고 고민하는 두 가지 선택이 있나요? ‘A를 한다 / B를 한다’처럼 적어주세요.", c: "요즘 고민하는 두 가지 선택이 있어? ‘A를 한다 / B를 한다’처럼 적어줘." },
  { id: "decision_criteria", kind: "decision", p: "두 선택을 비교할 때 가장 중요한 기준과 현실적인 제약은 무엇인가요?", c: "두 선택을 비교할 때 제일 중요한 기준과 현실적인 제약은 뭐야?" },
];

function shouldAskCosmoDecision() {
  // storage(safeStorage) 경유 — iframe·사파리에서 저장소가 막히면 메모리로 대신한다.
  return storage.getItem(COSMO_PROMPT_KEY) !== weekStartKey(todayKey());
}

// 말투(loadSpeech/SPEECH_KEY)는 dispositionApi 에서 온다 — 마스코트가 말하는 화면이
// 여럿이라(대화·주간 위로·N년 뒤) 한 곳에서 정해야 어긋나지 않는다.

// 질문 ={ p(존댓말), c(반말), options? type? unit? skip? id? }.
// options 있으면 선택창(칩)으로, type:"number"면 숫자 입력, 없으면 자유서술.
// 일상 = 구체적 하루 활동 로그. 성향(todayQuestions=가치·성찰 질문)과 겹치지 않게 '한 일/사람/먹은 것'.
const DAILY_Q = [
  { p: "오늘 하루, 주로 뭘 하면서 보냈어요?", c: "오늘 하루, 주로 뭘 하면서 보냈어?" },
  { p: "오늘 누구와 함께한 시간이 있었나요?", c: "오늘 누구랑 같이 보낸 시간 있었어?" },
  // 고민을 직접 물어야 이직·관계 등 신호를 잡을 수 있다(diarySignals 입력원).
  { p: "요즘 마음에 걸리는 고민 있어요? 일·관계·건강 뭐든 좋아요. (없으면 넘겨도 돼요)",
    c: "요즘 마음에 걸리는 고민 있어? 일·관계·건강 뭐든 좋아. (없으면 넘겨도 돼)", skip: true },
  { p: "오늘 먹은 것 중에 맛있었던 게 있어요?", c: "오늘 먹은 것 중에 맛있었던 거 있어?" },
];
// 건강 = 고정 질문(매일 안 바뀜). 선택형(옵션) + 정량 수치(number). 수치는 후에 삼성헬스 자동수신 자리.
// field 는 이 답을 어느 칸에 넣을지다. 여태 답이 대화 글로만 남아서, 수면 점수를
// 적어도 건강 점수 계산에는 쓰이지 못했다(domainScore.js 가 이 칸들을 읽는다).
const HEALTH_Q = [
  { p: "요즘 밤잠은 어떠세요?", c: "요즘 밤잠은 어땠어?", options: ["잘 잠", "뒤척임", "못 잠"], field: "sleepQual" },
  { p: "어젯밤 수면 점수는요? (알면 숫자로)", c: "어젯밤 수면 점수는? (알면 숫자로)",
    type: "number", unit: "점", skip: true, field: "sleepScore" },
  { p: "어제 몇 시간쯤 주무셨어요?", c: "어제 몇 시간쯤 잤어?", type: "number", unit: "시간", skip: true, field: "sleepHours" },
  { p: "오늘 걸음수는 얼마였어요?", c: "오늘 걸음수는 얼마였어?", type: "number", unit: "걸음", skip: true, field: "steps" },
  { p: "오늘 운동은 얼마나 하셨어요?", c: "오늘 운동은 얼마나 했어?", type: "number", unit: "분", skip: true, field: "exerciseMin" },
  { p: "요즘 스트레스는 얼마나 느끼세요?", c: "요즘 스트레스는 얼마나 느껴?",
    options: ["거의 없음", "보통", "심함"], field: "stress" },
];

// 답 한 줄 → 숫자. "7시간쯤", "약 80점" 처럼 적어도 건진다. 못 건지면 null(0 아님).
const SCALE_3 = { "잘 잠": 5, "뒤척임": 3, "못 잠": 1, "거의 없음": 1, "보통": 3, "심함": 5 };
function healthValue(field, raw) {
  const v = (raw || "").trim();
  if (!v || /^(모름|건너뛰|없|스킵)/.test(v)) return null;
  if (field === "sleepQual" || field === "stress") return SCALE_3[v] ?? null;
  const n = Number((v.match(/-?\d+(\.\d+)?/) || [])[0]);
  return Number.isFinite(n) ? n : null;
}

// 질문 텍스트 — 고른 말투로. 성향 질문(questions.js)은 원문 하나뿐이라 그대로 쓴다.
function qText(q, speech) {
  if (!q) return "";
  if (q.text) return q.text;
  return speech === "casual" ? q.c : q.p;
}

function areaQuestions(key) {
  if (key === "disposition") {
    try {
      const qs = todayQuestions().map((q) => ({ text: q.text, id: q.id })).filter((q) => q.text);
      if (qs.length) return shouldAskCosmoDecision() ? [...qs, ...COSMO_DECISION_Q] : qs;
    } catch {
      /* 로드 실패 시 기본 */
    }
    return [{ p: "오늘 어떤 선택을 하셨고, 왜 그렇게 하셨어요?", c: "오늘 어떤 선택을 했고, 왜 그렇게 했어?" }];
  }
  if (key === "health") return HEALTH_Q;
  return DAILY_Q;
}

// ── 주간 위로 — 답마다 반응하면 말이 많아지니, 한 주치를 읽고 한 번만 건넨다.
// 리포트(분석·수치·할 거리)와는 별개. 여기는 위로만 한다.
const COMFORT_KEY = "pm.comfort.v1";

// 지난 주 기록 [{date, text, mood, emotion}] — 이번 주가 아니라 '완결된 저번 주'.
function lastWeekEntries() {
  try {
    const thisWeek = weekStartKey(todayKey());
    const rows = (loadUniverse().checkins || [])
      .filter((c) => (c.text || c.note || "").trim() && weekStartKey(c.date) < thisWeek);
    if (!rows.length) return { week: null, entries: [] };
    const week = weekStartKey(rows[rows.length - 1].date); // 가장 최근에 끝난 주
    return {
      week,
      entries: rows.filter((c) => weekStartKey(c.date) === week).map((c) => ({
        date: c.date, text: (c.text || c.note || "").slice(0, 200),
        mood: c.mood ?? null, emotion: c.keyword || "",
      })),
    };
  } catch {
    return { week: null, entries: [] };
  }
}

function loadComfort() {
  try { return JSON.parse(storage.getItem(COMFORT_KEY) || "null"); } catch { return null; }
}

// 하루 단위 대화 드래프트 — 챗봇을 닫아도 그날 대화가 유지되고, 날이 바뀌면 새로 시작.
const DRAFT_KEY = "pm.chatDraft.v1";
function loadDraft() {
  try {
    const d = JSON.parse(storage.getItem(DRAFT_KEY) || "null");
    if (d && d.date === todayKey()) return d; // 오늘 것만 유효 → 다음날 자동 새 기록
  } catch { /* 무시 */ }
  return { date: todayKey(), d: {} };
}
function draftFor(area) {
  return loadDraft().d[area] || null;
}
function saveDraftArea(area, msgs, qi) {
  const d = loadDraft();
  d.d[area] = { msgs, qi };
  try { storage.setItem(DRAFT_KEY, JSON.stringify(d)); } catch { /* 무시 */ }
}

function recentChatContext() {
  try {
    const rows = (loadUniverse().checkins || [])
      .filter((item) => (item.text || item.note || "").trim())
      .slice(-7);
    let hardStreak = 0;
    for (let i = rows.length - 1; i >= 0; i -= 1) {
      if (Number(rows[i].mood) > 2) break;
      hardStreak += 1;
    }
    return {
      recent: rows.map((item) => ({
        date: item.date,
        emotion: item.keyword || item.emotion || "",
        text: (item.text || item.note || "").slice(0, 240),
      })),
      hardStreak,
    };
  } catch {
    return { recent: [], hardStreak: 0 };
  }
}

export default function ChatDiary({ onSaved, embedded = false, onMessagesChange, initialArea = "daily", showAreas = true }) {
  const { setProfile } = useResult(); // 성향 답변을 프로필에 반영(모든 시나리오 개인화 재료)
  const [speech, setSpeech] = useState(loadSpeech);
  const [area, setArea] = useState(initialArea);
  const [qs, setQs] = useState(() => areaQuestions(initialArea));
  // 오늘 저장된 드래프트가 있으면 이어서(챗봇 닫았다 열어도 유지).
  const _init = draftFor(initialArea);
  const [qi, setQi] = useState(() => _init?.qi ?? 0);
  // 루미의 몸·마음 체크에서 건진 수치({sleepScore, sleepHours, ...}). 저장 때 함께 넘긴다.
  const [healthVals, setHealthVals] = useState({});
  const [msgs, setMsgs] = useState(() =>
    _init?.msgs?.length
      ? _init.msgs
      : [{ role: "bot", text: qText(areaQuestions(initialArea)[0], loadSpeech()) }],
  );
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [thinking, setThinking] = useState(false); // 마스코트가 위로를 만드는 중
  const [chatBusy, setChatBusy] = useState(false);
  const [comfort, setComfort] = useState(() => loadComfort()); // {week, speech, text}
  const [suggestCompose, setSuggestCompose] = useState(false);
  const [saved, setSaved] = useState(null);
  const [editIdx, setEditIdx] = useState(null); // 수정 중인 답변 인덱스
  const [editText, setEditText] = useState("");
  const threadRef = useRef(null);

  const mascot = AREAS.find((a) => a.key === area)?.mascot || "nova";
  const hasUser = msgs.some((m) => m.role === "user");
  const done = qi >= qs.length;

  useEffect(() => {
    if (threadRef.current) threadRef.current.scrollTop = threadRef.current.scrollHeight;
    onMessagesChange?.(msgs);
    saveDraftArea(area, msgs, qi); // 하루 단위 드래프트로 저장(닫아도 유지)
  }, [msgs, qi, area]); // eslint-disable-line react-hooks/exhaustive-deps

  // 주간 위로 — 저번 주가 끝나면 한 번만 만든다. 같은 주엔 저장본을 그대로 쓴다.
  useEffect(() => {
    const { week, entries } = lastWeekEntries();
    if (!week || entries.length < 2) return;
    if (comfort?.week === week && comfort?.speech === speech) return;
    let alive = true;
    setThinking(true);
    weeklyComfort(entries, { persona: mascot, speech })
      .then((text) => {
        if (!alive || !text) return;
        const next = { week, speech, text };
        setComfort(next);
        try { storage.setItem(COMFORT_KEY, JSON.stringify(next)); } catch { /* 무시 */ }
      })
      .finally(() => { if (alive) setThinking(false); });
    return () => { alive = false; };
  }, [speech, mascot]); // eslint-disable-line react-hooks/exhaustive-deps

  function switchArea(key) {
    const list = areaQuestions(key);
    const dr = draftFor(key);
    setArea(key);
    setQs(list);
    setQi(dr?.qi ?? 0);
    setMsgs(dr?.msgs?.length ? dr.msgs : [{ role: "bot", text: qText(list[0], speech) }]);
    setSaved(null);
    setSuggestCompose(false);
    setEditIdx(null);
  }

  // 말투 전환 — 아직 답을 안 했으면 지금 떠 있는 질문도 그 말투로 바꿔 단다.
  function toggleSpeech() {
    const next = speech === "casual" ? "polite" : "casual";
    setSpeech(next);
    try { storage.setItem(SPEECH_KEY, next); } catch { /* 무시 */ }
    if (!msgs.some((m) => m.role === "user")) {
      setMsgs([{ role: "bot", text: qText(qs[0], next) }]);
    }
  }

  // 답변 수정 — 답변 옆 '수정' 버튼 → 인라인 편집 → 반영.
  function startEdit(i) {
    setEditIdx(i);
    setEditText(msgs[i]?.text || "");
  }
  function commitEdit() {
    if (editIdx == null) return;
    const v = editText.trim();
    if (v) setMsgs((m) => m.map((msg, idx) => (idx === editIdx ? { ...msg, text: v } : msg)));
    setEditIdx(null);
    setEditText("");
  }

  const CLOSING = {
    polite: "다 답해주셔서 고마워요! 아래 ‘기록 저장’을 누르면 오늘 일기로 정리할게요.",
    casual: "다 답해줘서 고마워! 아래 ‘기록 저장’을 누르면 오늘 일기로 정리할게.",
  };

  async function answer(raw) {
    const v = (raw ?? input).trim();
    if (!v || chatBusy) return;
    // 성향 질문(D2/D1/D4 등 id 있는 것)에 답하면 프로필 psych_answers에 저장
    // → buildDisposition → 모든 시뮬 시나리오 개인화에 반영.
    const cur = qs[qi];
    if (cur?.kind === "decision") {
      storage.setItem(COSMO_PROMPT_KEY, weekStartKey(todayKey()));
    }
    if (cur?.id && setProfile) {
      setProfile((p) => ({ ...p, psych_answers: { ...(p.psych_answers || {}), [cur.id]: v } }));
    }
    // 루미의 몸·마음 체크 — 답을 숫자로도 붙잡아 둔다. 대화 글로만 남기면
    // 수면 점수를 적어도 건강 지표 계산에는 못 쓴다.
    if (cur?.field) {
      const num = healthValue(cur.field, v);
      if (num != null) setHealthVals((h) => ({ ...h, [cur.field]: num }));
    }
    const next = qi + 1;
    const conversation = [...msgs, { role: "user", text: v }];
    setMsgs(conversation);
    setInput("");
    setChatBusy(true);
    try {
      const active = AREAS.find((item) => item.key === area);
      const result = await chatTurn(conversation, {
        persona: active?.mascot || mascot,
        context: recentChatContext(),
        speech,
        role: active?.role || null,
      });
      const nextQuestion = next < qs.length ? qText(qs[next], speech) : CLOSING[speech];
      setMsgs([...conversation, { role: "bot", text: nextQuestion }]);
      setSuggestCompose(next >= qs.length || Boolean(result?.suggest_compose && next >= qs.length));
      setQi(next);
    } catch {
      const fallback = next < qs.length ? qText(qs[next], speech) : CLOSING[speech];
      setMsgs([...conversation, { role: "bot", text: fallback }]);
      setQi(next);
    } finally {
      setChatBusy(false);
    }
  }

  // 단독 모드 전용 저장(임베드 때는 부모의 '기록 저장'이 대신한다).
  async function save() {
    if (busy || !hasUser) return;
    setBusy(true);
    try {
      const c = await composeDiary(msgs);
      const today = todayKey();
      // 키워드만 쓰면 절반쯤 놓친다 — 서버 분류까지 합치는 공용 경로를 쓴다.
      const verifiedDomains = tagEntry(today, c.text);
      addCheckin({ date: today, text: c.text, mood: c.mood, keyword: c.emotion,
        domains: verifiedDomains, insights: c.insights || null, chatSummary: c.text,
        health: Object.keys(healthVals).length ? healthVals : null });
      setSaved(c);
      onSaved?.();
    } finally {
      setBusy(false);
    }
  }

  const inner = (
    <>
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-1.5 text-[13px] font-semibold text-cyan">
          💬 질문에 답하며 기록
          <button
            onClick={toggleSpeech}
            className="tap rounded-full border border-line px-2 py-0.5 text-[10px] font-normal text-mut hover:border-cyan hover:text-cyan"
            title="마스코트 말투 바꾸기"
          >
            {speech === "casual" ? "반말" : "존댓말"}
          </button>
        </div>
        {showAreas && <div className="flex gap-1">
          {AREAS.map((a) => (
            <button
              key={a.key}
              onClick={() => switchArea(a.key)}
              className={`tap flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] ${
                area === a.key ? "border-cyan text-cyan" : "border-line text-mut"
              }`}
            >
              <Mascot which={a.mascot} size={20} />
              {a.name}
            </button>
          ))}
        </div>}
      </div>
      {showAreas && (
        <div className="mb-2 text-[11px] text-mut">{AREAS.find((item) => item.key === area)?.desc}</div>
      )}

      {/* 지난 한 주를 읽고 건네는 말 — 주 1회. 분석·할 거리는 주간 리포트가 따로 한다. */}
      {comfort?.text && (
        <div className="mb-2 rounded-2xl border border-[#3A2F55] bg-[#161029] px-3 py-2">
          <div className="mb-1 flex items-center gap-1.5">
            <Mascot which={mascot} size={20} />
            <span className="text-[11px] font-semibold text-[#B79BF0]">지난 한 주를 보고</span>
          </div>
          <p className="text-[12.5px] leading-relaxed text-sub">{comfort.text}</p>
        </div>
      )}
      {thinking && !comfort?.text && (
        <div className="mb-2 text-[11px] text-mut">지난 한 주를 읽고 있어요…</div>
      )}
      {chatBusy && (
        <div className="mb-2 text-[11px] text-mut">마스코트가 답변을 생각하고 있어요…</div>
      )}

      <div ref={threadRef} className="flex flex-col gap-2 overflow-y-auto" style={{ maxHeight: 220 }}>
        {msgs.map((m, i) =>
          m.role === "bot" ? (
            <div key={i} className="flex items-start gap-2 self-start" style={{ maxWidth: "82%" }}>
              <Mascot which={mascot} size={26} />
              <span className="rounded-2xl border border-line bg-[#141b2e] px-3 py-1.5 text-[13px] text-ink">{m.text}</span>
            </div>
          ) : editIdx === i ? (
            <div key={i} className="flex items-center gap-1 self-end" style={{ maxWidth: "90%" }}>
              <input
                value={editText}
                autoFocus
                onChange={(e) => setEditText(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && commitEdit()}
                onBlur={commitEdit}
                className="rounded-2xl border border-cyan bg-[#1D1730] px-3 py-1.5 text-[13px] text-ink outline-none"
              />
              <button onMouseDown={(e) => e.preventDefault()} onClick={commitEdit} className="tap text-[10px] text-cyan">완료</button>
            </div>
          ) : (
            <div key={i} className="group flex items-center gap-1 self-end" style={{ maxWidth: "90%" }}>
              <button
                onClick={() => startEdit(i)}
                className="tap shrink-0 rounded-md px-1 text-[10px] text-mut hover:text-cyan"
                aria-label="답변 수정"
              >
                ✎
              </button>
              <span className="rounded-2xl bg-[#1D1730] px-3 py-1.5 text-[13px]" style={{ color: "#E9E1FA" }}>
                {m.text}
              </span>
            </div>
          ),
        )}
      </div>

      {!done &&
        (qs[qi]?.type === "number" ? (
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <input
              type="number"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && input.trim() && answer(`${input.trim()}${qs[qi].unit || ""}`)}
              placeholder={qs[qi].unit || "숫자"}
              className="w-24 rounded-xl border border-line bg-[#0E1424] px-3 py-2 text-sm text-ink outline-none focus:border-cyan"
            />
            <span className="text-[12px] text-mut">{qs[qi].unit}</span>
            <button
              onClick={() => input.trim() && answer(`${input.trim()}${qs[qi].unit || ""}`)}
              disabled={!input.trim()}
              className="tap rounded-xl border border-line px-3 text-[13px] text-sub"
            >
              확인
            </button>
            {qs[qi].skip && (
              <button onClick={() => answer("기록 안 함")} className="tap px-2 text-[12px] text-mut">
                건너뛰기
              </button>
            )}
          </div>
        ) : qs[qi]?.options ? (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {qs[qi].options.map((opt) => (
              <button
                key={opt}
                onClick={() => answer(opt)}
                className="tap rounded-full border border-line px-3 py-1.5 text-[12px] text-sub focus:border-cyan"
              >
                {opt}
              </button>
            ))}
            <div className="flex items-center gap-1">
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && input.trim() && answer()}
                placeholder="직접 +"
                className="rounded-full border border-line bg-transparent px-2.5 py-1.5 text-[12px] text-sub outline-none focus:border-cyan"
                style={{ width: 82 }}
              />
              <button onClick={() => input.trim() && answer()} disabled={!input.trim()} className="tap rounded-full border border-line px-2.5 py-1.5 text-[12px] text-sub disabled:opacity-40">
                확인
              </button>
            </div>
          </div>
        ) : (
          <div className="mt-2 flex items-center gap-2">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && answer()}
              placeholder={speech === "casual" ? "답변을 적어줘" : "답변을 적어주세요"}
              className="flex-1 rounded-xl border border-line bg-[#0E1424] px-3 py-2 text-sm text-ink outline-none focus:border-cyan"
            />
            <button onClick={() => answer()} disabled={!input.trim()} className="tap rounded-xl border border-line px-3 text-[13px] text-sub">
              답변
            </button>
            {qs[qi]?.skip && (
              <button onClick={() => answer("기록 안 함")} className="tap px-2 text-[12px] text-mut">
                넘기기
              </button>
            )}
          </div>
        ))}

      {!embedded && (
        <>
          <button
            onClick={save}
            disabled={busy || !hasUser}
            className={`tap mt-2 w-full rounded-2xl py-2.5 text-[13px] font-bold transition-colors ${
              hasUser ? "bg-[#8B6CCF] text-white" : "bg-[#1E2740] text-mut"
            }`}
          >
            오늘 기록 저장
          </button>
          <Caption>답변을 오늘의 일기로 정리하고, 기분·감정·영역을 자동으로 남겨요.</Caption>
        </>
      )}
      {embedded && (
        <Caption>
          {done ? "답변 완료 — " : ""}답변은 아래 ‘기록 저장’ 시 오늘의 일기·감정·영역으로 함께 정리돼요.
        </Caption>
      )}
    </>
  );

  if (embedded) return <div className="mt-3 border-t border-line pt-3">{inner}</div>;

  if (saved) {
    return (
      <Card>
        <div className="mb-1 text-xs font-bold text-cyan">오늘 기록 완료 ✦</div>
        <p className="text-[13px] text-sub">{saved.text}</p>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {saved.emotion && <span className="rounded-lg border border-line px-2 py-0.5 text-[11px] text-sub">{saved.emotion}</span>}
          {(saved.domains || []).map((d) => (
            <span key={d} className="rounded-lg border border-line px-2 py-0.5 text-[11px] text-mut">🪐 {d}</span>
          ))}
        </div>
        <button onClick={() => switchArea(area)} className="tap mt-3 text-[11px] text-mut">다시 기록하기</button>
      </Card>
    );
  }

  return <Card>{inner}</Card>;
}
