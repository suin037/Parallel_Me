// ─────────────────────────────────────────────────────────────
// 알람(리마인더) 로직 — 보관함(pm.universes.v1)에 저장된 시나리오 중
// '결정한 미래(decision A/B)'를 향한 아직 안 한 행동을 모아 알람으로 만든다.
//
// 규칙(로컬 전용, API 0):
//   · 문구는 actionBridge.actionsFor() 의 검증된 큐레이션 텍스트를 그대로 쓴다.
//   · 완료 여부는 각 우주의 doneActions(텍스트 배열)로 판단 → 이미 있는 계약과 100% 호환.
//   · '하루 한 번' 자동 노출: lastAutoDate 로 그날 1회만 토스트를 띄운다.
//
// iframe/스토리지 차단(사파리 ITP 등) 대비: localStorage 접근을 try/catch 로 감싸고
// 실패하면 모듈 메모리(mem)로 폴백한다. 알람이 저장 실패로 앱을 죽이지 않게 한다.
// ─────────────────────────────────────────────────────────────
import { listUniverses, updateUniverse } from "./savedUniverses.js";
import { actionsForGoal, chosenChoice } from "./actionBridge.js";
import { computeDiarySignals } from "./diarySignals.js";
import storage from "./safeStorage.js";

const KEY = "pm.reminders.v1";
const DEFAULT_STATE = { enabled: true, lastAutoDate: null };
let mem = null; // 스토리지 차단 환경용 메모리 폴백

function readState() {
  try {
    const raw = storage.getItem(KEY);
    return raw ? { ...DEFAULT_STATE, ...JSON.parse(raw) } : { ...DEFAULT_STATE };
  } catch {
    return mem ? { ...mem } : { ...DEFAULT_STATE };
  }
}

function writeState(next) {
  mem = { ...next };
  try {
    storage.setItem(KEY, JSON.stringify(next));
  } catch {
    /* iframe/사파리 등 저장 불가 — 메모리에만 유지 */
  }
}

const todayStr = () => {
  // 사용자 로컬 날짜(YYYY-MM-DD). 자정 넘어가면 새 알람일로 취급.
  const d = new Date();
  const off = d.getTimezoneOffset() * 60000;
  return new Date(d.getTime() - off).toISOString().slice(0, 10);
};

// ── 켜기/끄기 ────────────────────────────────────────────────
export function remindersEnabled() {
  return readState().enabled !== false;
}

export function setRemindersEnabled(on) {
  writeState({ ...readState(), enabled: !!on });
}

// ── 미완료 알람 목록 ─────────────────────────────────────────
// 결정한 미래(A/B)를 향한, 아직 doneActions 에 없는 행동들.
export function pendingReminders() {
  if (!remindersEnabled()) return [];
  const out = [];
  // 일기 신호는 우주마다 같으니 루프 밖에서 한 번만 계산한다(매번 일기 전체를 다시 읽는다).
  const sig = computeDiarySignals({ windowDays: 28 });
  for (const u of listUniverses()) {
    const choice = chosenChoice(u);
    if (!choice) continue; // 보류/미결정은 알람 대상 아님
    const done = new Set(u.doneActions || []);
    // 결과 화면·보관함과 반드시 같은 진입점으로 — 인자가 갈리면 문구가 달라져
    // doneActions(텍스트 대조) 계약이 깨지고 '했어요'가 서로 안 맞는다.
    for (const a of actionsForGoal(choice, u.domains, sig)) {
      if (done.has(a.text)) continue;
      out.push({
        universeId: u.id,
        title: u.title,
        choice,
        actionText: a.text,
        purpose: a.purpose,
        savedAt: u.savedAt,
      });
    }
  }
  return out;
}

export function pendingCount() {
  return pendingReminders().length;
}

// ── 하루 한 번 자동 노출 ─────────────────────────────────────
export function shouldAutoShowToday() {
  if (!remindersEnabled()) return false;
  if (readState().lastAutoDate === todayStr()) return false;
  return pendingReminders().length > 0;
}

export function markAutoShown() {
  writeState({ ...readState(), lastAutoDate: todayStr() });
}

// 오늘의 대표 알람 1개 — 날짜 기반 회전으로 매일 다른 걸 보여준다.
export function todaysReminder() {
  const list = pendingReminders();
  if (!list.length) return null;
  const dayNum = Math.floor(Date.parse(todayStr()) / 86400000);
  return list[dayNum % list.length];
}

// ── 완료 처리 ────────────────────────────────────────────────
// 해당 우주의 doneActions 에 행동 텍스트를 추가(보관함 화면과 동일한 계약).
export function completeReminder(universeId, actionText) {
  const u = listUniverses().find((x) => x.id === universeId);
  if (!u) return;
  const done = u.doneActions || [];
  if (!done.includes(actionText)) {
    updateUniverse(universeId, { doneActions: [...done, actionText] });
  }
}
