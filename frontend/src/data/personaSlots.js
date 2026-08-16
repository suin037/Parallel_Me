import storage from "./safeStorage.js";
// ─────────────────────────────────────────────────────────────
// 프로필 슬롯 — 넷플릭스식 프로필 전환의 저장소 레이어.
//
// 문제: 앱의 저장소 키가 전부 단일 슬롯이다(pm.myuniverse.v1 하나, pm.profile.v1 하나).
//   페르소나 7명이 각자 데이터를 들고 공존하려면 키를 나눠야 하는데, 키 이름을 바꾸면
//   그 키를 읽는 화면·모듈을 전부 고쳐야 한다(15개 파일이 넘는다).
//
// 방식: 키를 나누지 않고 **스냅샷을 통째로 교체**한다.
//   전환할 때 지금 살아 있는 키들을 현재 슬롯에 담아두고, 대상 슬롯의 내용을 같은 키에
//   되돌려 쓴다. 화면 코드는 늘 pm.myuniverse.v1 하나만 보면 되므로 한 줄도 안 고친다.
//
//   pm.slots.v1 = { active: "dohyun", slots: { dohyun: { "pm.myuniverse.v1": …, … }, … } }
//
// 주의: 전환은 저장소만 바꾼다. React 컨텍스트(ResultContext)는 마운트 시점에
//   프로필을 읽으므로, 전환 뒤에 화면을 갱신해줘야 한다.
//   **새로고침으로 하지 말 것** — iframe·사파리에서는 저장소가 메모리라
//   (safeStorage.js) 새로고침이 세션을 통째로 날린다.
//   대신 호출측에서 ResultContext 의 reloadProfile() 을 부른다(Personas.jsx 참조).
//   기록은 restoreLive 가 쏘는 'pm:universe' 이벤트로 각 화면이 스스로 다시 읽는다.
// ─────────────────────────────────────────────────────────────

const SLOTS_KEY = "pm.slots.v1";

// 프로필에 딸린 키 — 슬롯마다 따로 보관한다.
// (pm.guide.seen.v1·pm.prefs.v1·pm.sec.* 는 기기/앱 전역 설정이라 공유한다.)
export const PROFILE_KEYS = [
  "pm.myuniverse.v1",   // 나의 우주 — 체크인·별·행성
  "pm.profile.v1",      // 온보딩 프로필 — 나이·성별·직종·소득·가치순위·MBTI·아바타
  "pm.universes.v1",    // 보관함 — 시뮬 결과 스냅샷
  "pm.softCompare.v1",  // 두 길의 하루 결과
  "pm.future.v1",
  "pm.comfort.v1",
  "pm.suggest.v1",
  "pm.tracks.v1",
  "pm.activeGoal.v1",
  "pm.opportunity.v1",
  "pm.expedition.v1",
  "pm.petCare.v1",
  "pm.petShop.v1",
  "pm.highestLevel.v1",
  "pm.reminders.v1",
  "pm.chatDraft.v1",
  "pm.speech.v1",
  "pm.contribConsent.v1",
  "pm.anonId.v1",
];

// 직접 만든 계정(체험용 페르소나가 아닌 '나')의 슬롯 id.
export const MY_SLOT = "__me__";

function readSlots() {
  try {
    const raw = JSON.parse(storage.getItem(SLOTS_KEY) || "null");
    if (!raw || typeof raw !== "object") return { active: null, slots: {} };
    return { active: raw.active ?? null, slots: raw.slots && typeof raw.slots === "object" ? raw.slots : {} };
  } catch {
    return { active: null, slots: {} };
  }
}

function writeSlots(next) {
  try {
    storage.setItem(SLOTS_KEY, JSON.stringify(next));
  } catch { /* 저장 실패는 무시 — 이번 세션은 메모리로만 동작 */ }
  return next;
}

/** 지금 살아 있는 프로필 키들을 한 덩어리로 뜬다. */
function snapshotLive() {
  const snap = {};
  for (const k of PROFILE_KEYS) {
    try {
      const v = storage.getItem(k);
      if (v != null) snap[k] = v;
    } catch { /* 무시 */ }
  }
  return snap;
}

/** 스냅샷을 살아 있는 키에 되돌려 쓴다. 스냅샷에 없는 키는 지운다(이전 프로필 잔상 방지). */
function restoreLive(snap = {}) {
  for (const k of PROFILE_KEYS) {
    try {
      if (Object.prototype.hasOwnProperty.call(snap, k)) storage.setItem(k, snap[k]);
      else storage.removeItem(k);
    } catch { /* 무시 */ }
  }
  if (typeof window !== "undefined") window.dispatchEvent(new Event("pm:universe"));
}

export function activeSlotId() {
  return readSlots().active;
}

/** 슬롯 목록 — [{ id, hasData, savedAt }] */
export function listSlots() {
  const { slots } = readSlots();
  return Object.entries(slots).map(([id, s]) => ({
    id,
    hasData: Boolean(s?.["pm.myuniverse.v1"]),
    savedAt: s?.__savedAt ?? null,
  }));
}

export function hasSlot(id) {
  return Boolean(readSlots().slots[id]);
}

/** 현재 화면 상태를 활성 슬롯에 담아둔다. 전환·이탈 직전에 부른다. */
export function saveActiveSlot(nowIso = null) {
  const st = readSlots();
  if (!st.active) return st;
  const snap = snapshotLive();
  if (nowIso) snap.__savedAt = nowIso;
  st.slots[st.active] = snap;
  return writeSlots(st);
}

/**
 * 슬롯을 활성화한다.
 *  · 현재 슬롯이 있으면 먼저 담아둔다(작업 내용 보존).
 *  · 대상 슬롯이 이미 있으면 그 내용을 복원한다.
 *  · 없으면 빈 상태로 만들고 `seeded:false` 를 돌려준다 → 호출측이 초기 데이터를 심는다.
 *
 * @returns {{restored: boolean}} restored=false 면 새 슬롯이라 심을 게 필요하다는 뜻.
 */
export function activateSlot(id, opts = {}) {
  const { reload = false, nowIso = null } = opts;
  const st = readSlots();

  if (st.active && st.active !== id) {
    const snap = snapshotLive();
    if (nowIso) snap.__savedAt = nowIso;
    st.slots[st.active] = snap;
  }

  const target = st.slots[id];
  const restored = Boolean(target);
  restoreLive(target || {});

  st.active = id;
  if (!restored) st.slots[id] = {}; // 자리를 잡아둔다 — 목록에 뜨게
  writeSlots(st);

  if (reload && typeof window !== "undefined") window.location.reload();
  return { restored };
}

/** 슬롯 하나를 비운다(전시에서 관람객이 남긴 흔적 정리용). 활성 슬롯이면 화면도 비운다. */
export function clearSlot(id) {
  const st = readSlots();
  delete st.slots[id];
  if (st.active === id) {
    restoreLive({});
    st.active = null;
  }
  return writeSlots(st);
}

/** 모든 슬롯을 비운다 — 전시 리셋 버튼용. */
export function clearAllSlots() {
  restoreLive({});
  return writeSlots({ active: null, slots: {} });
}
