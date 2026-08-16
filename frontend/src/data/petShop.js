// ─────────────────────────────────────────────────────────────
// 펫 상점/인벤토리 — 소품·간식·배경·가구를 코인으로 사서 꾸민다.
// 코인 = floor(총XP / 100) − 사용량.  (100 XP당 1코인, 대부분 아이템 1~2코인)
// 전부 로컬(localStorage). XP는 활동에서 파생되므로 코인도 자동 적립된다.
// MVP: 배경·소품 중심 + 간식/가구는 뼈대 몇 개. 렌더는 이모지(추후 SVG 교체 가능).
// ─────────────────────────────────────────────────────────────
import { totalXp } from "./myUniverse.js";
import storage from "./safeStorage.js";

const KEY = "pm.petShop.v1";
// 가구(furniture)는 배열 — 여러 개 동시 배치. 배경·소품·행성스킨은 단일.
const DEF = { spent: 0, owned: [], equipped: { background: null, accessory: null, furniture: [], planet: null } };

export const COIN_PER_XP = 100; // 100 XP = 1 coin

export const CAT_LABELS = { background: "배경", accessory: "소품", snack: "간식", planet: "행성" };
export const CATS = ["background", "accessory", "snack", "planet"];

// 아이템 카탈로그. render: 배경=CSS background 문자열 / 그 외=이모지.
export const CATALOG = [
  // 배경 — 하늘+땅 씬(지평선). 펫은 땅 위에 선다.
  { id: "bg_night", cat: "background", name: "밤 초원", price: 1, render: "radial-gradient(1.6px 1.6px at 18% 16%, #fff9, transparent), radial-gradient(1.3px 1.3px at 66% 22%, #fff8, transparent), radial-gradient(1.2px 1.2px at 40% 34%, #ffffffcc, transparent), radial-gradient(1.5px 1.5px at 82% 28%, #fff9, transparent), radial-gradient(1.2px 1.2px at 54% 12%, #fff7, transparent), radial-gradient(ellipse 120% 30% at 50% 62%, rgba(120,150,220,.35), transparent 60%), linear-gradient(180deg, #0a1436 0%, #26406f 60%, #1c3b26 60%, #0e2416 100%)" },
  { id: "bg_dawn", cat: "background", name: "노을 언덕", price: 2, render: "radial-gradient(circle at 50% 58%, rgba(255,216,150,.6), transparent 40%), linear-gradient(180deg, #f2a15c 0%, #d07f9a 38%, #8a5688 60%, #3f5e42 60%, #274522 100%)" },
  { id: "bg_aurora", cat: "background", name: "오로라 설원", price: 2, render: "radial-gradient(ellipse 95% 40% at 34% 28%, rgba(78,235,168,.5), transparent 62%), radial-gradient(ellipse 85% 42% at 72% 36%, rgba(128,116,238,.44), transparent 62%), radial-gradient(1.4px 1.4px at 24% 16%, #fff9, transparent), radial-gradient(1.2px 1.2px at 78% 22%, #fff8, transparent), linear-gradient(180deg, #051226 0%, #0e2c48 58%, #d3e8f4 58%, #a8ccdf 100%)" },
  { id: "bg_nebula", cat: "background", name: "성운 지대", price: 2, render: "radial-gradient(ellipse 85% 45% at 30% 32%, rgba(196,92,206,.5), transparent 60%), radial-gradient(ellipse 78% 45% at 72% 38%, rgba(96,116,236,.46), transparent 60%), radial-gradient(1.5px 1.5px at 20% 18%, #fff9, transparent), radial-gradient(1.2px 1.2px at 66% 20%, #fff8, transparent), linear-gradient(180deg, #0a0820 0%, #291452 58%, #3c2c4e 58%, #241a30 100%)" },
  { id: "bg_galaxy", cat: "background", name: "은하 언덕", price: 3, render: "radial-gradient(ellipse 150% 26% at 50% 40%, rgba(160,180,255,.42), transparent 55%), radial-gradient(1.6px 1.6px at 20% 20%, #fff9, transparent), radial-gradient(1.2px 1.2px at 70% 30%, #fff8, transparent), radial-gradient(1.6px 1.6px at 85% 24%, #fff9, transparent), radial-gradient(1.3px 1.3px at 44% 34%, #fff7, transparent), linear-gradient(180deg, #06091f 0%, #1e2858 58%, #2a2a48 58%, #16182c 100%)" },
  { id: "bg_sakura", cat: "background", name: "벚꽃 들판", price: 3, render: "radial-gradient(ellipse 100% 40% at 50% 22%, rgba(255,190,216,.5), transparent 65%), linear-gradient(180deg, #f6c3d6 0%, #eca4b8 40%, #e29ab0 60%, #6fa85e 60%, #4d8340 100%)" },
  // 소품 (착용 위치 pos): 왕관=머리 위 얹기 / 리본=몸통 입 아래 / 꽃=오른쪽 귀
  { id: "acc_crown",  cat: "accessory", name: "작은 왕관",   price: 2, render: "👑", pos: { top: 26, left: "50%", size: 20 } },
  { id: "acc_ribbon", cat: "accessory", name: "나비 리본",   price: 1, render: "🎀", pos: { top: 90, left: "50%", size: 19 } },
  { id: "acc_flower", cat: "accessory", name: "꽃 한 송이",  price: 2, render: "🌸", pos: { top: 42, left: "73%", size: 19, rotate: 14 } },
  // 간식 (소비형 — 먹이면 호감도↑, 코인 소모)
  { id: "snack_carrot", cat: "snack", name: "당근",       price: 1, render: "🥕", bond: 5 },
  { id: "snack_fish",   cat: "snack", name: "생선",       price: 1, render: "🐟", bond: 7 },
  { id: "snack_cake",   cat: "snack", name: "케이크",     price: 2, render: "🍰", bond: 10 },
  { id: "snack_star",   cat: "snack", name: "특별간식 별", price: 4, render: "⭐", bond: 15 },
  // 행성 스킨 (나의 우주 지도) — 미장착 = 기본 민무늬 행성. skin 값은 UniverseMap이 읽는다.
  { id: "planet_glow",   cat: "planet", name: "빛나는 구체",     price: 10, render: "🪐", skin: "glow" },
];

// 장착된 행성 스킨 — 없으면 "basic"(민무늬).
export function planetSkin(x = loadShop()) {
  const it = equippedItem("planet", x);
  return (it && it.skin) || "basic";
}

export function itemById(id) {
  return CATALOG.find((it) => it.id === id) || null;
}

export function loadShop() {
  try {
    const s = JSON.parse(storage.getItem(KEY) || "{}");
    const merged = { ...DEF, ...s, equipped: { ...DEF.equipped, ...(s.equipped || {}) } };
    // 구버전(단일 가구) → 배열로 마이그레이션
    const f = merged.equipped.furniture;
    merged.equipped.furniture = Array.isArray(f) ? f : f ? [f] : [];
    return merged;
  } catch {
    return { ...DEF, equipped: { ...DEF.equipped, furniture: [] } };
  }
}
export function saveShop(x) {
  try {
    storage.setItem(KEY, JSON.stringify(x));
  } catch { /* 무시 */ }
  // 같은 탭에선 storage 이벤트가 안 뜬다 — 마스코트·나의 우주가 바로 반영되게 직접 알린다.
  if (typeof window !== "undefined") window.dispatchEvent(new Event("pm:pet-shop"));
  return x;
}

// 획득한 총 코인(누적) — XP에서 파생.
export function coinsEarned() {
  return Math.floor(totalXp() / COIN_PER_XP);
}
// 쓸 수 있는 코인 = 획득 − 사용.
export function coinsAvailable(x = loadShop()) {
  return Math.max(0, coinsEarned() - (x.spent || 0));
}

export function owns(id, x = loadShop()) {
  return (x.owned || []).includes(id);
}

// 구매: 코인 충분 & 미보유일 때만. {ok, reason}
export function buy(id, x = loadShop()) {
  const it = itemById(id);
  if (!it) return { ok: false, reason: "없는 아이템" };
  if (owns(id, x)) return { ok: false, reason: "이미 보유" };
  if (coinsAvailable(x) < it.price) return { ok: false, reason: "코인 부족" };
  const next = saveShop({ ...x, spent: (x.spent || 0) + it.price, owned: [...(x.owned || []), id] });
  return { ok: true, state: next };
}

// 간식 소비(먹이기) — 코인 소모하고 호감도량 반환. owned에 안 쌓임(소비형).
export function consumeSnack(id, x = loadShop()) {
  const it = itemById(id);
  if (!it || it.cat !== "snack") return { ok: false, reason: "간식 아님" };
  if (coinsAvailable(x) < it.price) return { ok: false, reason: "코인 부족" };
  const next = saveShop({ ...x, spent: (x.spent || 0) + it.price });
  return { ok: true, state: next, bond: it.bond || 0 };
}

// 장착/해제 토글. 가구는 다중(배열), 배경·소품은 단일.
export function toggleEquip(id, x = loadShop()) {
  const it = itemById(id);
  if (!it || !owns(id, x)) return x;
  if (it.cat === "furniture") {
    const cur = Array.isArray(x.equipped.furniture) ? x.equipped.furniture : [];
    const next = cur.includes(id) ? cur.filter((f) => f !== id) : [...cur, id];
    return saveShop({ ...x, equipped: { ...x.equipped, furniture: next } });
  }
  const cur = x.equipped[it.cat];
  return saveShop({ ...x, equipped: { ...x.equipped, [it.cat]: cur === id ? null : id } });
}
// 장착 여부(모든 카테고리 공통).
export function isEquipped(id, x = loadShop()) {
  const it = itemById(id);
  if (!it) return false;
  if (it.cat === "furniture") {
    const f = x.equipped.furniture;
    return Array.isArray(f) && f.includes(id);
  }
  return x.equipped[it.cat] === id;
}
export function equippedId(cat, x = loadShop()) {
  const v = x.equipped ? x.equipped[cat] : null;
  return Array.isArray(v) ? null : v || null;
}
export function equippedItem(cat, x = loadShop()) {
  const id = equippedId(cat, x);
  return id ? itemById(id) : null;
}
// 장착된 가구 아이템들(다중).
export function equippedFurnitureItems(x = loadShop()) {
  const f = x.equipped ? x.equipped.furniture : [];
  return (Array.isArray(f) ? f : []).map(itemById).filter(Boolean);
}
