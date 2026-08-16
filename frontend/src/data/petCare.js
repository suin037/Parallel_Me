// ─────────────────────────────────────────────────────────────
// 마스코트 육성(케어) — 쓰다듬기·간식으로 친밀도를 키우는 가벼운 게임화.
// 핵심 설계: 간식은 '기록'으로 번다 → 게임화가 데이터 축적(진짜 차별점)을 굴린다.
// 로컬(localStorage)만. 추상 XP를 이 육성 재미로 대체한다.
// ─────────────────────────────────────────────────────────────
import { todayKey, hasCheckedInToday } from "./myUniverse.js";
import storage from "./safeStorage.js";

const KEY = "pm.petCare.v1";
const DEF = { which: "cosmo", bond: 15, happiness: 60, snacks: 3, lastClaim: null, lastPat: null };

export function loadPet() {
  try {
    return { ...DEF, ...(JSON.parse(storage.getItem(KEY) || "{}")) };
  } catch {
    return { ...DEF };
  }
}
export function savePet(p) {
  try {
    storage.setItem(KEY, JSON.stringify(p));
  } catch { /* 무시 */ }
  return p;
}

// 오늘 기록했으면 간식 지급(하루 1회). 기록 → 간식 → 육성 루프.
export function claimDaily(p = loadPet()) {
  if (hasCheckedInToday() && p.lastClaim !== todayKey()) {
    return savePet({ ...p, snacks: p.snacks + 2, lastClaim: todayKey() });
  }
  return p;
}
// 쓰다듬기: 하루 1회만. 친밀도 +랜덤(1~10). 이미 했으면 그대로.
export function canPatToday(p = loadPet()) {
  return p.lastPat !== todayKey();
}
export function petMascot(p = loadPet()) {
  if (p.lastPat === todayKey()) return p; // 하루 한 번
  const gain = 1 + Math.floor(Math.random() * 10); // 1~10
  return savePet({
    ...p,
    bond: Math.min(100, p.bond + gain),
    happiness: Math.min(100, p.happiness + 6),
    lastPat: todayKey(),
  });
}
// 간식: 친밀도 +7 고정, 행복 크게.
export function feedMascot(p = loadPet()) {
  if (p.snacks <= 0) return p;
  return savePet({ ...p, snacks: p.snacks - 1, happiness: Math.min(100, p.happiness + 16), bond: Math.min(100, p.bond + 7) });
}
export function setWhich(which, p = loadPet()) {
  return savePet({ ...p, which });
}
export function moodOf(happiness) {
  return happiness >= 66 ? "기쁨" : happiness >= 33 ? "보통" : "시무룩";
}

// ── 돌보지 않으면 시무룩해진다 ────────────────────────────────
// 지금까지 happiness 는 오르기만 했다. 그러면 며칠을 내버려둬도 늘 웃고 있어서
// 돌볼 이유가 없다. 마지막으로 돌본 날부터 하루씩 깎아 '보고 싶어하는' 얼굴이
// 되게 한다.
//
// 저장값은 건드리지 않는다 — 화면에 보일 때만 깎아서 보여준다. 그래야 오랜만에
// 들어와도 한 번 쓰다듬으면 원래 자리로 돌아온다(벌주는 게 목적이 아니다).
const DECAY_PER_DAY = 12;

function daysBetween(a, b) {
  const d = (Date.parse(`${b}T00:00:00`) - Date.parse(`${a}T00:00:00`)) / 86400000;
  return Number.isFinite(d) ? Math.max(0, Math.round(d)) : 0;
}

/** 마지막으로 돌본 뒤 며칠 지났나. 한 번도 안 돌봤으면 0(아직 깎지 않는다). */
export function daysSinceCare(p = loadPet()) {
  const last = p.lastPat || p.lastClaim;
  return last ? daysBetween(last, todayKey()) : 0;
}

/** 지금 보이는 기분 — 저장값에서 방치한 날만큼 깎은 값. */
export function currentHappiness(p = loadPet()) {
  const h = p.happiness - daysSinceCare(p) * DECAY_PER_DAY;
  return Math.max(0, Math.min(100, h));
}

/**
 * 지금 이 친구에게 필요한 것 — 미리보기에서 무슨 얼굴로 무슨 말을 할지 정한다.
 * 급한 것부터 하나만 고른다. 한 번에 여러 개를 조르면 잔소리로 들린다.
 */
export function careNeed(p = loadPet()) {
  const happiness = currentHappiness(p);
  const mood = moodOf(happiness);
  const away = daysSinceCare(p);
  const canPat = canPatToday(p);

  let need = null;
  if (away >= 3) need = { key: "away", line: `${away}일 만이에요...`, cta: "보러 가기" };
  else if (mood === "시무룩") need = { key: "pat", line: "기운이 없어요", cta: "쓰다듬기" };
  else if (canPat && p.snacks > 0) need = { key: "snack", line: "간식 기다리는 중", cta: "간식 주기" };
  else if (canPat) need = { key: "pat", line: "오늘은 아직 못 만났어요", cta: "쓰다듬기" };

  return { happiness, mood, away, canPat, snacks: p.snacks, need };
}
// 친밀도 단계(성장 느낌) — 나중에 진화/스킨 해금 트리거로.
export function bondTier(bond) {
  return bond >= 80 ? 3 : bond >= 45 ? 2 : 1;
}
