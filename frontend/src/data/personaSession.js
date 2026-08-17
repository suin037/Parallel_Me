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
 * 이미 만들어진 슬롯의 프로필을 그 페르소나에 맞춘다.
 *
 * 왜 필요한가: enterPersona 는 슬롯을 **처음 만들 때만** writeProfile 을 부른다.
 *   그래서 한 번이라도 들어가 본 인물은, 나중에 페르소나 프로필에 새로 생긴 값이
 *   그 슬롯에 영영 안 들어간다.
 *
 * 아바타는 '없을 때만 채우기'로는 안 된다 — 저장소에는 avatarConfig 가 **언제나** 있다.
 *   ResultContext 의 DEFAULT_PROFILE 이 avatarConfig: DEFAULT_AVATAR 를 들고 있고,
 *   프로필이 바뀔 때마다 통째로 저장하기 때문이다(그쪽 useEffect). 그래서 빈 자리를
 *   찾는 방식으로는 페르소나 얼굴이 영영 안 들어가고, 카드에는 얼굴이 뜨는데
 *   프로필·시뮬레이션 화면은 기본 아바타인 상태가 된다.
 *
 *   대신 **사용자가 직접 고른 적이 있는가**(avatarChosen)로 가린다. 값이 있는지가 아니라
 *   사람이 골랐는지를 보는 것으로, sex 를 sexConfirmed 로 가리는 것과 같은 방식이다.
 *   설정·온보딩의 아바타 빌더만 그 표시를 남긴다.
 */
// 모델이 실제로 읽는 '그 인물의 사실' — 취향 설정이 아니라 신원이다.
//
// 이 값들은 '없으면 채운다' 로는 안 된다. 다른 인물을 체험하다 넘어오면 앞사람의
// 값이 그대로 남아 있어서, 화면에는 지금 인물이 뜨는데 직종·근속은 앞사람 것이
// 붙는다(실제로 '전문가·관련 종사자 · 근속 4년' 이 인물을 바꿔도 계속 따라다녔다).
//
// 페르소나가 정의한 값은 **덮어쓰고**, 정의하지 않은 값은 **지운다.**
// 지우는 쪽이 중요하다 — 고용형태·회사규모는 어떤 인물도 정하지 않아서,
// 비우지 않으면 앞사람 값이 영영 남는다. 빈 값은 백엔드가 전체 표본으로
// 떨어뜨리므로(api.js 의 sex 주석과 같은 방식) 근거 없는 매칭보다 낫다.
const PERSONA_FACTS = [
  "age", "sex", "sexConfirmed", "major", "occupation", "occupation_group",
  "income", "edu_level", "tenure_years", "employment_status", "firm_size",
  "mbti", "value_ranking",
];

function syncPersonaProfile(profile) {
  try {
    const prev = JSON.parse(storage.getItem(PROFILE_KEY) || "{}");
    const next = { ...prev };
    let changed = false;

    for (const key of PERSONA_FACTS) {
      const value = Object.prototype.hasOwnProperty.call(profile, key) ? profile[key] : null;
      // value_ranking 은 배열이라 === 로는 늘 다르게 나온다 — 값으로 견준다.
      const same = typeof value === "object" || typeof prev[key] === "object"
        ? JSON.stringify(prev[key] ?? null) === JSON.stringify(value ?? null)
        : prev[key] === value;
      if (!same) { next[key] = value; changed = true; }
    }

    // 나머지(아직 없는 값)는 채운다 — 나중에 프로필에 필드가 추가돼도 예전 슬롯이 따라온다.
    for (const [key, value] of Object.entries(profile)) {
      if (prev[key] === undefined) { next[key] = value; changed = true; }
    }

    // 얼굴은 그 인물의 정체다. 시뮬레이션 결과 이미지까지 이 값을 쓰므로
    // (ResultContext 의 avatarToPngBlob) 카드에서 본 얼굴과 어긋나면 안 된다.
    if (!prev.avatarChosen && profile.avatarConfig
        && JSON.stringify(prev.avatarConfig) !== JSON.stringify(profile.avatarConfig)) {
      next.avatarConfig = profile.avatarConfig;
      changed = true;
    }

    if (changed) storage.setItem(PROFILE_KEY, JSON.stringify(next));
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
  // 이미 있던 슬롯이면 위를 건너뛰므로, 그 뒤에 프로필에 새로 생긴 값은 빠진 채로 남는다.
  // 예전에 만든 슬롯도 최신 프로필과 어긋나지 않게 맞춘다.
  syncPersonaProfile(persona.profile);

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
