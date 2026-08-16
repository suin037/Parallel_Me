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
// 친밀도 단계(성장 느낌) — 나중에 진화/스킨 해금 트리거로.
export function bondTier(bond) {
  return bond >= 80 ? 3 : bond >= 45 ? 2 : 1;
}
