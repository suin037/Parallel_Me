// ─────────────────────────────────────────────────────────────
// 페르소나 세션 — '체험하기'와 '계정 만들기'의 진입 동작.
//
// personaSlots.js 가 저장소 교체를,  personas/seed.js 가 기록 심기를 맡는다.
// 여기서는 그 둘을 순서대로 엮어 화면이 부를 함수 하나로 만든다.
//
//   체험하기   enterPersona("dohyun")  → 슬롯 전환 → (처음이면) 1년치 심기 + 프로필 주입
//   계정 만들기 startMyAccount()        → 내 슬롯으로 전환. 기록은 온보딩이 끝난 뒤 심는다.
//   가입 직후  seedStarterData()        → 체험용 예시 1년치를 넣고 안내 문구용 정보를 돌려준다
// ─────────────────────────────────────────────────────────────

import { activateSlot, hasSlot, saveActiveSlot, activeSlotId, MY_SLOT } from "./personaSlots.js";
import { getPersona } from "./personas/index.js";
import { seedYear } from "./personas/seed.js";
import storage from "./safeStorage.js";

const PROFILE_KEY = "pm.profile.v1";

// 계정 만들기로 들어온 사람에게 넣어줄 예시 데이터의 출처.
// 지원의 1년치를 빌려 쓴다 — 화면에는 '예시 데이터' 배지와 출처 안내를 함께 띄운다.
export const STARTER_SOURCE = "jiwon";

function writeProfile(profile) {
  try {
    // 기존 값 위에 얹는다 — 아바타처럼 사용자가 이미 고른 게 있으면 지키기 위해.
    const prev = JSON.parse(storage.getItem(PROFILE_KEY) || "{}");
    storage.setItem(PROFILE_KEY, JSON.stringify({ ...prev, ...profile }));
  } catch { /* 무시 */ }
}

/**
 * 페르소나 체험 시작. 이미 체험한 적 있는 인물이면 그때 상태를 그대로 되살린다.
 *
 * @returns {Promise<{ok: boolean, reason?: string, restored?: boolean, planted?: number}>}
 */
export async function enterPersona(id, opts = {}) {
  // 기본값이 false 인 이유: iframe·사파리에서는 저장소가 메모리라(safeStorage)
  // 새로고침이 방금 심은 1년치를 통째로 날린다. 호출측이 reloadProfile() + navigate 로
  // 화면을 갱신한다(Personas.jsx 참조).
  const { reload = false } = opts;
  const persona = getPersona(id);
  if (!persona) return { ok: false, reason: "unknown-persona" };
  if (persona.dataStatus !== "ready" || !persona.load) {
    return { ok: false, reason: "no-data" }; // 카드에서 '준비 중'으로 막아야 할 상태
  }

  const seen = hasSlot(id);
  const { restored } = activateSlot(id, { nowIso: new Date().toISOString() });

  let planted = 0;
  if (!seen || !restored) {
    const mod = await persona.load();
    planted = seedYear(mod.YEAR, mod.FINALE ?? null, { demoKind: "year" });
    writeProfile(persona.profile);
  }

  // 슬롯에 심은 결과를 곧바로 담아둔다 — 새로고침 전에 저장이 끝나 있어야 한다.
  saveActiveSlot(new Date().toISOString());
  if (reload && typeof window !== "undefined") window.location.reload();
  return { ok: true, restored, planted };
}

/** 계정 만들기 — 내 슬롯으로 전환한다. 기록은 아직 안 넣는다(온보딩이 먼저). */
export function startMyAccount(opts = {}) {
  const { reload = false } = opts;
  const { restored } = activateSlot(MY_SLOT, { nowIso: new Date().toISOString() });
  if (reload && typeof window !== "undefined") window.location.reload();
  return { restored };
}

/**
 * 온보딩을 마친 사람에게 체험용 예시 1년치를 넣는다.
 * 화면은 이 결과로 "체험을 위해 예시 데이터 1년치를 넣어뒀다"는 안내를 띄운다.
 *
 * 정직선: 넣는 건 지원(29세, 프로덕트 디자이너)의 합성 기록이다. 방금 입력한 본인
 *   정보와 일기 내용이 어긋나는 게 정상이며, 안내에 출처를 밝힌다. demo 배지도 유지된다.
 */
export async function seedStarterData() {
  const source = getPersona(STARTER_SOURCE);
  if (!source?.load) return { ok: false, reason: "no-source" };
  const mod = await source.load();
  const planted = seedYear(mod.YEAR, mod.FINALE ?? null, { demoKind: "year" });
  saveActiveSlot(new Date().toISOString());
  return {
    ok: true,
    planted,
    sourceName: source.profile.name,
    sourceTagline: source.profile.tagline,
  };
}

/** 지금 보고 있는 게 어떤 프로필인지 — 헤더·배지 표시용. */
export function currentSlot() {
  const id = activeSlotId();
  if (!id) return { id: null, kind: "none" };
  if (id === MY_SLOT) return { id, kind: "me" };
  const p = getPersona(id);
  return { id, kind: "persona", name: p?.profile.name ?? id, tagline: p?.profile.tagline ?? "" };
}
