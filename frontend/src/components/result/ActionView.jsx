import { useEffect, useMemo, useState } from "react";
import { Card, Caption } from "../ui.jsx";
import { actionsForGoal, clearActiveGoal, loadActiveGoal, saveActionResponse, saveActiveGoal } from "../../data/actionBridge.js";
import { computeDiarySignals } from "../../data/diarySignals.js";
import { logExperiment } from "../../data/myUniverse.js";
import { domainLabel, labelOf } from "../../data/choices.js";

export default function ActionView({ a, b, domains = { a: [], b: [] } }) {
  const [goal, setGoal] = useState(loadActiveGoal);
  const [resp, setResp] = useState({}); // actionId → 적는 중인 텍스트
  const [savedIds, setSavedIds] = useState(() => new Set());
  const sig = useMemo(() => computeDiarySignals({ windowDays: 28 }), []);
  const selected = goal?.side === "A" && goal.choice === a.choice ? { side: "A", result: a, domains: domains.a || [] }
    : goal?.side === "B" && goal.choice === b.choice ? { side: "B", result: b, domains: domains.b || [] } : null;
  // 신호 게이팅(진로 계열에만 주입)은 actionsForGoal 안에 있다 — 보관함·알람과 같은 규칙.
  const actions = useMemo(
    () => selected ? actionsForGoal(selected.result.choice, selected.domains, sig) : [],
    [selected?.result.choice, selected?.domains.join("|"), sig],
  );
  // 다음 단계에 반영된 일기 신호(로컬 계산) — "화면용 아님"을 보여주는 근거.
  const reflected = actions.filter((x) => x.domain === "signal");

  // 이미 적어둔 답이 있으면 입력칸에 채운다(목표의 completedActions).
  useEffect(() => {
    const done = goal?.completedActions || [];
    setResp(Object.fromEntries(done.map((d) => [d.id, d.text])));
    setSavedIds(new Set(done.map((d) => d.id)));
  }, [goal?.side, goal?.choice]);

  function choose(side, result, selectedDomains) {
    setGoal(saveActiveGoal({ side, choice: result.choice, domains: selectedDomains || [] }));
  }

  // 적은 답 저장 — 둘 다: 목표 완료 기록 + 그날 일기에 반영(다음 신호 분석에 들어감).
  function saveResp(action) {
    const text = (resp[action.id] || "").trim();
    const g = saveActionResponse(action.id, text);
    if (g) setGoal(g);
    logExperiment({ actionId: action.id, prompt: action.text, text });
    setSavedIds((prev) => {
      const n = new Set(prev);
      if (text) n.add(action.id);
      else n.delete(action.id);
      return n;
    });
  }

  if (!selected) {
    return (
      <div>
        <h2 className="mb-1 text-base font-semibold">어느 방향을 더 알아볼까요?</h2>
        <Caption>결정을 대신하지 않아요. 선택한 방향의 불확실성을 줄이는 작은 실험을 제안합니다.</Caption>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <GoalButton side="A" result={a} onClick={() => choose("A", a, domains.a)} />
          <GoalButton side="B" result={b} onClick={() => choose("B", b, domains.b)} />
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold">{selected.side}를 위한 작은 실험</h2>
          <Caption>{labelOf(selected.result.choice)} 방향을 목표로 저장했어요. 정답 추천이 아니라 확인 행동입니다.</Caption>
        </div>
        <button onClick={() => { clearActiveGoal(); setGoal(null); }} className="shrink-0 text-[10px] text-cyan">다시 선택</button>
      </div>
      {selected.domains.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">{selected.domains.map((d) => <span key={d} className="rounded-full border border-line px-2 py-1 text-[10px] text-mut">{domainLabel(d)}</span>)}</div>
      )}
      {reflected.length > 0 && (
        <p className="mt-2 rounded-lg border border-cyan/25 bg-[#1D1730] px-2.5 py-1.5 text-[10px] leading-relaxed text-sub">
          🗒 최근 일기 반영: {reflected.map((r) => `${r.signal} ${r.days}일`).join(" · ")} — 이 상태에 맞춰 아래 실험을 골랐어요.
        </p>
      )}
      <div className="mt-3 space-y-2.5">
        {actions.map((action, index) => (
          <Card key={action.id}>
            <div className="text-[10px] font-bold text-cyan">
              작은 실험 {index + 1}
              {action.domain === "signal" && <span className="ml-1.5 rounded-full bg-cyan/15 px-1.5 py-0.5 text-[9px] text-cyan">내 기록 기반</span>}
              {action.tailored && <span className="ml-1.5 rounded-full bg-violet-500/15 px-1.5 py-0.5 text-[9px] text-violet-300">질문 맞춤</span>}
            </div>
            <p className="mt-1 text-[13px] font-semibold leading-relaxed text-ink">{action.text}</p>
            <p className="mt-2 text-[11px] leading-relaxed text-sub"><b>추천 이유</b> · {action.purpose}</p>
            <p className="mt-1 text-[9px] leading-4 text-violet-300/80">행동설계 근거 · {action.source}</p>

            {/* 여기 적으면 → 완료 기록 + 그날 일기에 반영되어 다음 분석에 들어감 */}
            <div className="mt-2.5">
              <textarea
                value={resp[action.id] || ""}
                onChange={(e) => setResp((r) => ({ ...r, [action.id]: e.target.value }))}
                rows={2}
                placeholder="여기에 적어보세요 — 적으면 오늘 기록에 반영돼요"
                className="w-full resize-none rounded-xl border border-line bg-[#0E1424] px-3 py-2 text-[12px] leading-relaxed text-ink outline-none focus:border-cyan"
              />
              <div className="mt-1.5 flex items-center gap-2">
                <button
                  onClick={() => saveResp(action)}
                  disabled={!(resp[action.id] || "").trim() && !savedIds.has(action.id)}
                  className="tap rounded-lg bg-cyan px-3 py-1 text-[11px] font-bold text-[#04203a] disabled:opacity-50"
                >
                  {savedIds.has(action.id) ? "다시 저장" : "저장"}
                </button>
                {savedIds.has(action.id) && (
                  <span className="text-[10px] text-[#5DCAA5]">✓ 완료 · 오늘 일기에 반영됨</span>
                )}
              </div>
            </div>

            <details className="mt-2 text-[10px] leading-relaxed text-mut">
              <summary className="cursor-pointer text-sub">행동설계 근거 보기</summary>
              <p className="mt-1">{action.basis}</p><p className="mt-1">출처: {action.source}</p>
            </details>
          </Card>
        ))}
      </div>
    </div>
  );
}

function GoalButton({ side, result, onClick }) {
  const color = side === "A" ? "text-cyan border-cyan/50 bg-[#1D1730]" : "text-gold border-gold/50 bg-[#241d10]";
  return <button onClick={onClick} className={`tap rounded-xl border p-3 text-left ${color}`}><span className="text-[10px] font-bold">UNIVERSE {side}</span><span className="mt-1 block text-[12px] font-semibold">{labelOf(result.choice)}를 목표로</span></button>;
}
