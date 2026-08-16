import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Check, ChevronRight, Compass, Lock, Orbit, Plus, RotateCcw, Sparkles, Trash2 } from "lucide-react";
import { useResult } from "../data/ResultContext.jsx";
import {
  listUniverses,
  saveUniverse,
  updateUniverse,
  decideUniverse,
  removeUniverse,
  universeFromResult,
} from "../data/savedUniverses.js";
import { actionsForGoal, chosenChoice } from "../data/actionBridge.js";
import { computeDiarySignals } from "../data/diarySignals.js";
import { LIFE_DOMAINS, domainColor, domainLabel, labelOf } from "../data/choices.js";

// 보관함 = 항해일지. 저장한 결과의 목록이 아니라 '결정 → 실행 → 회고'의 진행을 추적하는 곳.
// 카드는 접힌 상태가 기본이고, 상세는 나의 우주와 같은 바텀시트로 연다.

// 선택 A/B 색은 입력·로딩 화면과 반드시 같아야 한다(A=파랑, B=주황).
const SIDE = {
  A: { color: "#9B82E8", soft: "rgba(139,108,207,.16)", edge: "rgba(155,130,232,.48)" },
  B: { color: "#FF9F32", soft: "rgba(255,159,50,.13)", edge: "rgba(255,159,50,.45)" },
};
const REFLECT_AFTER_DAYS = 7; // 결정 후 이만큼 지나야 회고를 묻는다
const DAY = 86400000;

// 0개인 필터도 들어갈 수 있게 한다 — 비어 있다는 사실 자체가 정보다("보류가 하나도 없구나").
const FILTER_EMPTY = {
  going: {
    title: "아직 탐험 중인 갈림길이 없어요",
    hint: "카드를 열어 마음이 기운 쪽을 고르면 여기에 모여요.",
  },
  pending: {
    title: "회고를 기다리는 기록이 없어요",
    hint: `결정하고 ${REFLECT_AFTER_DAYS}일이 지나면 그때의 선택을 돌아볼 때가 됐다고 알려드릴게요.`,
  },
  hold: {
    title: "보류 중인 갈림길이 없어요",
    hint: "미뤄둔 고민이 없다는 뜻이에요. 마음을 정하지 못한 갈림길은 여기 남습니다.",
  },
  done: {
    title: "회고까지 마친 기록이 없어요",
    hint: "선택하고 시간이 지난 뒤 남긴 회고가 여기 쌓여요.",
  },
};

function daysSince(value) {
  if (!value) return null;
  const iso = String(value);
  const time = new Date(iso.length <= 10 ? `${iso}T00:00:00` : iso).getTime();
  if (Number.isNaN(time)) return null;
  return Math.max(0, Math.floor((Date.now() - time) / DAY));
}

function relDate(dateStr) {
  const d = daysSince(dateStr);
  if (d == null) return dateStr || "";
  if (d === 0) return "오늘";
  if (d === 1) return "어제";
  if (d < 7) return `${d}일 전`;
  if (d < 28) return `${Math.floor(d / 7)}주 전`;
  return String(dateStr).slice(5).replace("-", "/");
}

// hold(보류) → going(탐험 중) → done(회고까지 마침)
function statusOf(u) {
  if (u.reflection?.trim()) return "done";
  if (u.decision === "A" || u.decision === "B") return "going";
  return "hold";
}

// 결정한 지 7일이 지났는데 아직 회고가 비어 있는 것 = 지금 손댈 거리
function isReflectPending(u) {
  if (statusOf(u) !== "going") return false;
  const d = daysSince(u.decidedAt);
  return d != null && d >= REFLECT_AFTER_DAYS;
}

// 결과 화면·알람과 같은 진입점을 써야 문구가 같아진다(doneActions 는 텍스트로 대조).
function actionsOf(u, signals) {
  const chosen = chosenChoice(u);
  return chosen ? actionsForGoal(chosen, u.domains, signals) : [];
}

export default function Archive() {
  const navigate = useNavigate();
  const { result, profile, choices, scenarioDomains, setResult, setChoices } = useResult();
  const [items, setItems] = useState(listUniverses);
  const [filter, setFilter] = useState("all");
  const [sort, setSort] = useState("recent"); // recent | domain
  const [openId, setOpenId] = useState(null);
  // 일기 신호는 카드마다 같으니 화면에서 한 번만 계산해 내려준다.
  const signals = useMemo(() => computeDiarySignals({ windowDays: 28 }), []);

  const refresh = () => setItems(listUniverses());
  const open = openId ? items.find((u) => u.id === openId) || null : null;

  // 기본 결과(목업)를 그대로 저장하지 않도록, 실제로 시뮬레이션을 돌린 결과일 때만 저장을 연다.
  const hasRealResult = Boolean(
    result &&
      (result.dataMode === "model" || result.domains || result.narrative || result.narrativeError),
  );
  // 제목 기준을 결과 화면과 맞춘다(화면에 보이는 A/B) — 중복 저장 판정이 두 화면에서 어긋나지 않게.
  const pair = { a: result?.a?.choice || choices.a, b: result?.b?.choice || choices.b };
  const currentTitle = `${pair.a} vs ${pair.b}`;
  const today = new Date().toISOString().slice(0, 10);
  const savedToday = items.some((u) => u.title === currentTitle && u.savedAt === today);

  function saveCurrent() {
    saveUniverse(universeFromResult(result, profile, pair, result?.domains || scenarioDomains));
    refresh();
  }

  const counts = useMemo(
    () => ({
      all: items.length,
      going: items.filter((u) => statusOf(u) === "going").length,
      hold: items.filter((u) => statusOf(u) === "hold").length,
      done: items.filter((u) => statusOf(u) === "done").length,
      pending: items.filter(isReflectPending).length,
    }),
    [items],
  );

  const visible = useMemo(() => {
    const picked =
      filter === "all"
        ? items
        : filter === "pending"
          ? items.filter(isReflectPending)
          : items.filter((u) => statusOf(u) === filter);
    if (sort !== "domain") return picked;
    const order = LIFE_DOMAINS.map((d) => d.key);
    return [...picked].sort((a, b) => order.indexOf(a.domains[0]) - order.indexOf(b.domains[0]));
  }, [items, filter, sort]);

  return (
    <div className="relative isolate min-h-full w-full overflow-hidden pb-5 lg:px-4 lg:pb-12 xl:px-8">
      <div className="pointer-events-none absolute inset-x-[-140px] top-[-220px] -z-10 h-[520px] rounded-full bg-[radial-gradient(circle,rgba(139,108,207,.22)_0%,rgba(74,83,170,.08)_44%,transparent_70%)]" />
      <div className="pointer-events-none absolute inset-0 -z-10 opacity-45 [background-image:radial-gradient(circle,rgba(255,255,255,.55)_0_1px,transparent_1.2px),radial-gradient(circle,rgba(139,108,207,.42)_0_1px,transparent_1.3px)] [background-position:8px_17px,35px_49px] [background-size:79px_79px,113px_113px]" />

      <div className="mb-5 mt-1 flex items-start justify-between gap-3 lg:mb-8">
        <div className="min-w-0">
          <div className="flex items-center gap-1.5 text-[11px] font-semibold tracking-[.12em] text-[#A98DF1]">
            <Orbit size={14} /> PARALLEL LOG
          </div>
          <h1 className="mt-0.5 text-[24px] font-bold leading-[1.2] tracking-[-.02em] lg:text-[34px]">
            선택의 항해일지
          </h1>
          <p className="mt-1 text-[13px] text-sub">
            비교했던 미래와 선택 이후의 발자국을 한곳에 모아요.
          </p>
        </div>
        {/* 새 카드는 시뮬레이션을 거쳐서만 생긴다 → 목록이 길어져도 진입점은 항상 여기 있다. */}
        <button
          type="button"
          onClick={() => navigate("/input")}
          className="tap mt-0.5 flex shrink-0 items-center gap-1 rounded-full border border-[#9B82E8]/45 bg-[#8B6CCF]/15 px-3 py-2 text-[12px] font-semibold text-[#B8A4F2] transition-colors hover:bg-[#8B6CCF]/25"
        >
          <Plus size={14} strokeWidth={2.4} />새 갈림길
        </button>
      </div>

      {hasRealResult && (
        <button
          type="button"
          onClick={saveCurrent}
          disabled={savedToday}
          className={`tap mb-3 flex w-full items-center justify-center gap-2 rounded-[18px] border py-3 text-[13px] font-semibold transition-colors ${
            savedToday
              ? "border-white/10 bg-white/[.04] text-mut"
              : "border-[#9B82E8]/45 bg-[linear-gradient(110deg,rgba(87,112,226,.18),rgba(139,108,207,.2))] text-[#C3B3F5] hover:bg-[#8B6CCF]/25"
          }`}
        >
          <Sparkles size={15} strokeWidth={2.1} />
          {savedToday ? "오늘 저장한 결과예요" : `지금 결과 저장 · ${labelOf(pair.a)} vs ${labelOf(pair.b)}`}
        </button>
      )}

      {items.length === 0 ? (
        <EmptyState onStart={() => navigate("/input")} />
      ) : (
        <>
          <div className="mb-5 grid grid-cols-3 gap-2 rounded-[22px] border border-white/[.08] bg-[#0C1627]/70 p-3 shadow-[0_18px_55px_rgba(0,0,0,.22)] backdrop-blur-xl lg:max-w-[760px] lg:p-4">
            <ArchiveStat label="저장한 우주" value={counts.all} />
            <ArchiveStat label="탐험 중" value={counts.going} accent />
            <ArchiveStat label="회고 완료" value={counts.done} />
          </div>

          <div className="no-scrollbar -mx-1 flex items-center gap-1.5 overflow-x-auto px-1 pb-0.5">
            <Chip active={filter === "all"} onClick={() => setFilter("all")} count={counts.all}>
              전체
            </Chip>
            <Chip active={filter === "going"} onClick={() => setFilter("going")} count={counts.going}>
              탐험 중
            </Chip>
            {/* 회고 대기는 '지금 할 거리'라 대상이 있을 때만 뜬다. 단, 보고 있는 중이면 남긴다. */}
            {(counts.pending > 0 || filter === "pending") && (
              <Chip
                active={filter === "pending"}
                onClick={() => setFilter("pending")}
                count={counts.pending}
                accent="#FF9F32"
              >
                회고 대기
              </Chip>
            )}
            <Chip active={filter === "hold"} onClick={() => setFilter("hold")} count={counts.hold}>
              보류
            </Chip>
            <Chip active={filter === "done"} onClick={() => setFilter("done")} count={counts.done}>
              완료
            </Chip>
          </div>

          <div className="mb-2 mt-2 flex items-center justify-between px-1">
            <span className="text-[11px] text-mut">{visible.length}개</span>
            <button
              type="button"
              onClick={() => setSort((s) => (s === "recent" ? "domain" : "recent"))}
              className="tap text-[11px] text-sub"
            >
              {sort === "recent" ? "최신순" : "영역별"} ⇅
            </button>
          </div>

          {visible.length === 0 ? (
            <FilterEmpty filter={filter} onShowAll={() => setFilter("all")} />
          ) : (
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {visible.map((u) => (
                <UniverseCard key={u.id} u={u} signals={signals} onOpen={() => setOpenId(u.id)} />
              ))}
            </div>
          )}
        </>
      )}

      {open && (
        <DetailSheet
          key={open.id}
          u={open}
          signals={signals}
          onClose={() => setOpenId(null)}
          onDecide={(d) => {
            decideUniverse(open.id, d);
            refresh();
          }}
          onToggleAction={(text) => {
            const done = open.doneActions || [];
            updateUniverse(open.id, {
              doneActions: done.includes(text) ? done.filter((x) => x !== text) : [...done, text],
            });
            refresh();
          }}
          onSaveNote={(text) => {
            updateUniverse(open.id, { reflection: text });
            refresh();
          }}
          onReopen={() => {
            if (open.result) setResult(open.result);
            navigate("/result");
          }}
          onResim={() => {
            if (open.choiceA && open.choiceB) setChoices({ a: open.choiceA, b: open.choiceB });
            navigate("/input");
          }}
          onDelete={() => {
            removeUniverse(open.id);
            setOpenId(null);
            refresh();
          }}
        />
      )}
    </div>
  );
}

function Chip({ children, active, onClick, count, accent }) {
  const color = accent || "#9B82E8";
  return (
    <button
      type="button"
      onClick={onClick}
      className={`tap flex shrink-0 items-center gap-1.5 rounded-full border px-3 py-1.5 text-[12px] transition-colors ${
        active ? "font-semibold" : "border-white/10 bg-white/[.04] text-sub"
      }`}
      style={active ? { borderColor: color, color, background: `${color}1F` } : undefined}
    >
      {children}
      <span className={`text-[10px] tabular-nums ${active ? "" : "text-mut"}`}>{count}</span>
    </button>
  );
}

function ArchiveStat({ label, value, accent = false }) {
  return (
    <div className="relative overflow-hidden rounded-2xl border border-white/[.07] bg-white/[.025] px-3 py-3">
      {accent && <span className="absolute -right-3 -top-4 h-12 w-12 rounded-full bg-[#8B6CCF]/25 blur-xl" />}
      <div className="text-[10px] text-mut">{label}</div>
      <div className={`mt-1 text-[20px] font-bold tabular-nums ${accent ? "text-[#B8A4F2]" : "text-ink"}`}>
        {value}<span className="ml-0.5 text-[10px] font-medium text-mut">개</span>
      </div>
    </div>
  );
}

// 접힌 카드 — 영역 색 / 대비된 A·B / 진행 상태까지 훑기만 해도 읽힌다.
function UniverseCard({ u, signals, onOpen }) {
  const status = statusOf(u);
  const chosen = chosenChoice(u);
  const actions = actionsOf(u, signals);
  const doneCount = actions.filter((a) => (u.doneActions || []).includes(a.text)).length;
  const pending = isReflectPending(u);

  const colors = u.domains.slice(0, 2).map(domainColor);
  const stripe =
    colors.length > 1 ? `linear-gradient(180deg, ${colors[0]}, ${colors[1]})` : colors[0] || "#4A90E2";

  return (
    <button
      type="button"
      onClick={onOpen}
      className="tap group relative block w-full overflow-hidden rounded-[24px] border border-white/10 bg-[linear-gradient(145deg,rgba(18,29,49,.92),rgba(13,20,36,.82))] py-4 pl-5 pr-4 text-left shadow-[0_18px_45px_rgba(0,0,0,.25)] backdrop-blur-xl transition-all hover:-translate-y-0.5 hover:border-[#9B82E8]/35"
    >
      <span className="absolute left-0 top-0 h-full w-[4px]" style={{ background: stripe }} />
      <span className="pointer-events-none absolute -right-10 -top-12 h-28 w-28 rounded-full border border-white/[.05] bg-[#8B6CCF]/[.06] transition-transform group-hover:scale-110" />

      <div className="flex items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-1.5">
          {u.domains.slice(0, 2).map((key) => (
            <span
              key={key}
              className="shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium"
              style={{ color: domainColor(key), background: `${domainColor(key)}1A` }}
            >
              {domainLabel(key)}
            </span>
          ))}
          {u.domains.length > 2 && (
            <span className="text-[10px] text-mut">+{u.domains.length - 2}</span>
          )}
        </div>
        <span className="shrink-0 text-[10px] text-mut">{relDate(u.savedAt)}</span>
      </div>

      <div className="mt-2 flex items-baseline gap-2 text-[16px] font-bold tracking-[-.02em]">
        <ChoiceLabel side="A" text={u.choiceA} dim={u.decision === "B"} />
        <span className="shrink-0 text-[11px] font-medium text-mut">vs</span>
        <ChoiceLabel side="B" text={u.choiceB} dim={u.decision === "A"} />
      </div>

      <div className="mt-2.5 flex items-center gap-2">
        <StatusBadge status={status} chosen={chosen} side={u.decision} pending={pending} />
        {actions.length > 0 && (
          <span className="flex items-center gap-1.5 text-[10px] text-mut">
            할 일 {doneCount}/{actions.length}
            <span className="flex gap-[3px]">
              {actions.map((a, i) => (
                <i
                  key={a.id || i}
                  className={`h-[5px] w-[5px] rounded-full ${
                    i < doneCount ? "bg-cyan" : "bg-white/20"
                  }`}
                />
              ))}
            </span>
          </span>
        )}
        <ChevronRight size={16} className="ml-auto shrink-0 text-mut transition-transform group-hover:translate-x-0.5" />
      </div>
    </button>
  );
}

function ChoiceLabel({ side, text, dim }) {
  return (
    <span
      className={`min-w-0 truncate transition-opacity ${dim ? "opacity-35" : ""}`}
      style={{ color: SIDE[side].color }}
    >
      {labelOf(text)}
    </span>
  );
}

function StatusBadge({ status, chosen, side, pending }) {
  if (pending) {
    return (
      <span className="rounded-full px-2 py-1 text-[10px] font-semibold" style={{ color: SIDE.B.color, background: SIDE.B.soft }}>
        회고를 남길 때예요
      </span>
    );
  }
  if (status === "going") {
    const tone = SIDE[side] || SIDE.A;
    return (
      <span className="max-w-[52%] truncate rounded-full px-2 py-1 text-[10px] font-semibold" style={{ color: tone.color, background: tone.soft }}>
        → {labelOf(chosen)} 탐험 중
      </span>
    );
  }
  if (status === "done") {
    return (
      <span className="rounded-full bg-white/[.07] px-2 py-1 text-[10px] font-semibold text-sub">
        회고까지 완료
      </span>
    );
  }
  return (
    <span className="rounded-full bg-white/[.07] px-2 py-1 text-[10px] font-semibold text-mut">
      아직 보류
    </span>
  );
}

// 상세 — 나의 우주 별자리 시트와 같은 패턴. 단계가 오지 않은 섹션은 잠근다.
function DetailSheet({ u, signals, onClose, onDecide, onToggleAction, onSaveNote, onReopen, onResim, onDelete }) {
  const [note, setNote] = useState(u.reflection || "");
  const [unlockedNote, setUnlockedNote] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  // Esc·백드롭으로 닫으면 textarea blur 가 보장되지 않는다 → 사라질 때 마지막 회고를 저장한다.
  const noteRef = useRef(note);
  noteRef.current = note;
  const initialNote = useRef(u.reflection || "");
  useEffect(
    () => () => {
      if (noteRef.current !== initialNote.current) onSaveNote(noteRef.current);
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

  const chosen = chosenChoice(u);
  const actions = actionsOf(u, signals);
  const done = u.doneActions || [];
  const decided = u.decision === "A" || u.decision === "B";
  const sinceDecision = daysSince(u.decidedAt);
  const noteReady =
    unlockedNote || Boolean(u.reflection?.trim()) || (decided && (sinceDecision ?? 0) >= REFLECT_AFTER_DAYS);

  return (
    <div
      className="fixed inset-0 z-[70] flex animate-backdrop-in items-end justify-center overflow-hidden bg-[#02050C]/75 backdrop-blur-[5px] md:items-center md:px-8 md:py-[88px]"
      onClick={onClose}
    >
      <div
        className="mb-[76px] flex h-[min(780px,calc(100dvh-96px))] min-h-0 w-full max-w-phone animate-sheet-up flex-col overflow-hidden rounded-t-[34px] border border-white/10 bg-[radial-gradient(circle_at_85%_0%,rgba(139,108,207,.16),transparent_34%),#0D1727] shadow-[0_-24px_70px_rgba(0,0,0,.55)] md:mb-0 md:h-[min(720px,calc(100dvh-176px))] md:max-w-[820px] md:rounded-[30px]"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="shrink-0 px-5 pb-3 pt-3">
          <div className="mx-auto mb-3 h-1 w-11 rounded-full bg-white/25" />
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-1.5">
                {u.domains.map((key) => (
                  <span
                    key={key}
                    className="rounded-full px-2 py-0.5 text-[10px] font-medium"
                    style={{ color: domainColor(key), background: `${domainColor(key)}1A` }}
                  >
                    {domainLabel(key)}
                  </span>
                ))}
              </div>
              <h2 className="mt-2 flex flex-wrap items-baseline gap-x-2 gap-y-1 text-[19px] font-bold tracking-[-.02em]">
                <ChoiceLabel side="A" text={u.choiceA} dim={u.decision === "B"} />
                <span className="shrink-0 text-[12px] font-medium text-mut">vs</span>
                <ChoiceLabel side="B" text={u.choiceB} dim={u.decision === "A"} />
              </h2>
              <div className="mt-1 text-[11px] text-mut">{u.savedAt} 저장 · {relDate(u.savedAt)}</div>
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label="닫기"
              className="tap flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-white/[.07] text-[22px] text-sub"
            >
              ×
            </button>
          </div>
        </div>

        <div className="no-scrollbar min-h-0 flex-1 space-y-3 overflow-y-auto overscroll-contain px-5 pb-8 md:grid md:grid-cols-2 md:content-start md:gap-3 md:space-y-0 md:px-6">
          {u.headline && (
            <p className="rounded-2xl border border-white/[.07] bg-white/[.03] px-3.5 py-3 text-[13px] leading-relaxed text-sub">
              {u.headline}
            </p>
          )}

          <Step n={1} title="이 갈림길, 지금 마음은?">
            <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-3">
              <DecisionBtn on={u.decision === "A"} tone={SIDE.A} onClick={() => onDecide("A")}>
                {labelOf(u.choiceA)}
              </DecisionBtn>
              <DecisionBtn on={!decided} tone={null} onClick={() => onDecide("none")}>
                아직 보류
              </DecisionBtn>
              <DecisionBtn on={u.decision === "B"} tone={SIDE.B} onClick={() => onDecide("B")}>
                {labelOf(u.choiceB)}
              </DecisionBtn>
            </div>
          </Step>

          <Step
            n={2}
            title={chosen ? `"${labelOf(chosen)}" 탐험 · 오늘 할 일` : "탐험 · 오늘 할 일"}
            locked={!decided}
            lockedText="탐험을 시작하려면 먼저 마음이 기운 쪽을 골라주세요. 그 선택에 맞는 행동을 꺼내드릴게요."
          >
            <div className="space-y-1">
              {actions.map((action) => {
                const ok = done.includes(action.text);
                return (
                  <button
                    key={action.id || action.text}
                    type="button"
                    onClick={() => onToggleAction(action.text)}
                    className="tap flex w-full items-start gap-2.5 rounded-xl px-2 py-2 text-left transition-colors hover:bg-white/[.04]"
                  >
                    <span
                      className={`mt-[2px] flex h-[18px] w-[18px] shrink-0 items-center justify-center rounded-md border transition-colors ${
                        ok ? "border-cyan bg-cyan text-[#04203a]" : "border-white/20 text-transparent"
                      }`}
                    >
                      <Check size={12} strokeWidth={3} />
                    </span>
                    <span className="min-w-0">
                      <span className={`block text-[13px] leading-snug ${ok ? "text-mut line-through" : "text-ink"}`}>
                        {action.text}
                      </span>
                      {action.purpose && !ok && (
                        <span className="mt-0.5 block text-[11px] leading-snug text-mut">{action.purpose}</span>
                      )}
                    </span>
                  </button>
                );
              })}
            </div>
            <p className="mt-2 text-[11px] text-mut">완료 체크는 저장돼요. 매일 하나씩이면 충분해요.</p>
          </Step>

          <Step
            n={3}
            title="그 후 어떻게 됐나요?"
            locked={!noteReady}
            lockedText={
              !decided
                ? "결정을 내린 뒤, 시간이 조금 지나면 여기서 돌아볼게요."
                : `결정한 지 ${sinceDecision ?? 0}일 됐어요. ${Math.max(1, REFLECT_AFTER_DAYS - (sinceDecision ?? 0))}일 뒤에 다시 물어볼게요.`
            }
            lockedAction={decided ? { label: "지금 바로 쓰기", onClick: () => setUnlockedNote(true) } : null}
          >
            <textarea
              value={note}
              rows={4}
              onChange={(e) => setNote(e.target.value)}
              onBlur={() => onSaveNote(note)}
              placeholder="그때의 선택을 지금 돌아보면… (회고·감정 기록)"
              className="w-full resize-none rounded-xl border border-white/10 bg-[#0A1322] px-3 py-2.5 text-[13px] leading-relaxed text-ink outline-none transition-colors focus:border-cyan"
            />
          </Step>

          <div className="flex flex-wrap gap-2 pt-1 md:col-span-2">
            <button
              type="button"
              onClick={onReopen}
              className="tap flex-1 rounded-2xl border border-white/12 bg-white/[.04] py-3 text-[12px] font-semibold text-sub transition-colors hover:bg-white/[.08]"
            >
              결과 다시 보기
            </button>
            <button
              type="button"
              onClick={onResim}
              className="tap flex flex-1 items-center justify-center gap-1.5 rounded-2xl border border-cyan/40 bg-cyan/[.10] py-3 text-[12px] font-semibold text-cyan transition-colors hover:bg-cyan/[.16]"
            >
              <RotateCcw size={14} strokeWidth={2.1} />
              다시 시뮬레이션
            </button>
          </div>

          <div className="mt-1 rounded-2xl border border-white/[.07] px-3.5 py-3 md:col-span-2">
            {confirmDelete ? (
              <div className="flex items-center justify-between gap-3">
                <span className="text-[12px] text-sub">이 기록을 삭제할까요? 되돌릴 수 없어요.</span>
                <div className="flex shrink-0 gap-1.5">
                  <button
                    type="button"
                    onClick={() => setConfirmDelete(false)}
                    className="tap rounded-lg border border-white/12 px-2.5 py-1.5 text-[11px] text-sub"
                  >
                    취소
                  </button>
                  <button
                    type="button"
                    onClick={onDelete}
                    className="tap rounded-lg bg-danger/15 px-2.5 py-1.5 text-[11px] font-semibold text-danger"
                  >
                    삭제
                  </button>
                </div>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => setConfirmDelete(true)}
                className="tap flex items-center gap-1.5 text-[11px] text-mut transition-colors hover:text-danger"
              >
                <Trash2 size={13} />이 기록 삭제
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function Step({ n, title, children, locked = false, lockedText, lockedAction }) {
  return (
    <section
      className={`rounded-[22px] border px-4 py-3.5 transition-colors ${
        locked ? "border-white/[.06] bg-white/[.015]" : "border-white/10 bg-white/[.035]"
      }`}
    >
      <div className="flex items-center gap-2">
        <span
          className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[10px] font-bold ${
            locked ? "bg-white/[.07] text-mut" : "bg-[#8B6CCF]/20 text-[#B8A4F2]"
          }`}
        >
          {n}
        </span>
        <h3 className={`min-w-0 flex-1 truncate text-[13px] font-bold ${locked ? "text-mut" : "text-ink"}`}>
          {title}
        </h3>
        {locked && <Lock size={13} className="shrink-0 text-mut" />}
      </div>

      {locked ? (
        <div className="mt-2">
          <p className="text-[11px] leading-relaxed text-mut">{lockedText}</p>
          {lockedAction && (
            <button
              type="button"
              onClick={lockedAction.onClick}
              className="tap mt-2 rounded-lg border border-white/12 px-2.5 py-1.5 text-[11px] text-sub transition-colors hover:text-ink"
            >
              {lockedAction.label}
            </button>
          )}
        </div>
      ) : (
        <div className="mt-3">{children}</div>
      )}
    </section>
  );
}

function DecisionBtn({ on, tone, onClick, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`tap min-w-0 flex-1 truncate rounded-xl border px-2 py-2.5 text-[12px] font-semibold transition-colors ${
        on ? "" : "border-white/10 bg-white/[.03] text-mut hover:text-sub"
      }`}
      style={
        on
          ? tone
            ? { borderColor: tone.edge, color: tone.color, background: tone.soft }
            : { borderColor: "rgba(255,255,255,.28)", color: "#F6F8FC", background: "rgba(255,255,255,.07)" }
          : undefined
      }
    >
      {children}
    </button>
  );
}

// 필터는 걸려 있는데 그 안이 빈 경우 — 목록을 지우지 않고 '왜 비었는지'를 그 자리에 말해준다.
function FilterEmpty({ filter, onShowAll }) {
  const copy = FILTER_EMPTY[filter] || { title: "아직 아무것도 없어요", hint: "" };
  return (
    <div className="rounded-[20px] border border-dashed border-white/12 bg-white/[.02] px-5 py-8 text-center">
      <div className="mx-auto flex h-9 w-9 items-center justify-center rounded-full bg-white/[.05]">
        <Compass size={17} className="text-mut" strokeWidth={1.8} />
      </div>
      <p className="mt-2.5 text-[13px] font-semibold text-sub">{copy.title}</p>
      {copy.hint && (
        <p className="mx-auto mt-1.5 max-w-[280px] text-[11px] leading-relaxed text-mut">{copy.hint}</p>
      )}
      <button
        type="button"
        onClick={onShowAll}
        className="tap mt-4 rounded-full border border-white/12 px-4 py-2 text-[11px] font-semibold text-sub transition-colors hover:text-ink"
      >
        전체 보기
      </button>
    </div>
  );
}

function EmptyState({ onStart }) {
  return (
    <div className="rounded-[28px] border border-white/10 bg-[radial-gradient(circle_at_50%_25%,rgba(139,108,207,.16),transparent_40%),rgba(16,26,42,.78)] px-5 py-9 text-center shadow-[0_22px_65px_rgba(0,0,0,.28)] backdrop-blur-xl">
      <svg viewBox="0 0 120 120" className="mx-auto h-[112px] w-[112px]" aria-hidden="true">
        <ellipse cx="60" cy="60" rx="52" ry="20" fill="none" stroke="rgba(255,255,255,.10)" strokeDasharray="3 5" />
        <ellipse cx="60" cy="60" rx="38" ry="46" fill="none" stroke="rgba(76,145,255,.22)" strokeDasharray="3 5" />
        <circle cx="60" cy="60" r="12" fill="rgba(76,145,255,.14)" stroke="rgba(76,145,255,.45)" />
        <circle cx="112" cy="60" r="3.5" fill="#4C91FF" />
        <circle cx="60" cy="14" r="3" fill="#FF9F32" />
      </svg>
      <p className="mt-3 text-[14px] font-semibold text-ink">아직 궤도에 올린 결정이 없어요</p>
      <p className="mx-auto mt-1.5 max-w-[280px] text-[12px] leading-relaxed text-mut">
        두 미래를 비교한 뒤 결과를 저장하면, 여기에서 마음을 정하고 그 후까지 따라갈 수 있어요.
      </p>
      <button
        type="button"
        onClick={onStart}
        className="tap mt-5 inline-flex items-center gap-1.5 rounded-full border border-[#9B82E8]/45 bg-[#8B6CCF]/20 px-5 py-2.5 text-[13px] font-semibold text-[#C3B3F5] transition-colors hover:bg-[#8B6CCF]/30"
      >
        <Sparkles size={15} strokeWidth={2.1} />첫 갈림길 비교하기
      </button>
    </div>
  );
}
