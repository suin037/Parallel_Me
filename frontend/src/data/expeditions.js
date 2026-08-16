import storage from "./safeStorage.js";
// 작은 탐험 — 기회(갈림길)와 결정 사이를 메우는 한 걸음.
//
// 기회 카드는 누르면 바로 시뮬레이션(이직 vs 유지)으로 간다. 인생 결정 크기라
// 문턱이 높고, 아직 아무것도 모르는 채로 저울에 올리는 셈이기도 하다.
// 탐험은 그 사이다 — 결정하지 말고 가서 알아보고 돌아온다.
//
// 돌아와 적은 한 줄은 회고와 같은 무게를 갖는다. 상상이 아니라 실제로 겪은
// 것이라, 그 영역의 'N년 뒤'를 쓸 때 가장 단단한 재료가 된다.
const KEY = "pm.expedition.v1";

function read() {
  try {
    const v = JSON.parse(storage.getItem(KEY) || "null");
    return Array.isArray(v?.items) ? v.items : [];
  } catch {
    return [];
  }
}

function write(items) {
  try { storage.setItem(KEY, JSON.stringify({ items })); } catch { /* 무시 */ }
  if (typeof window !== "undefined") window.dispatchEvent(new Event("pm:expedition"));
  return items;
}

function today() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function listExpeditions() {
  return read();
}

export function expeditionsFor(planetKey) {
  return read().filter((e) => e.planet === planetKey);
}

export function activeExpeditions() {
  return read().filter((e) => !e.doneAt && !e.gaveUpAt);
}

export function doneExpeditions(planetKey = null) {
  return read().filter((e) => e.doneAt && (!planetKey || e.planet === planetKey));
}

// 기회 항목 → 탐험 시작. 같은 제목이 이미 진행 중이면 중복으로 만들지 않는다.
export function startExpedition({ planet, planetLabel, title, step, why, choiceA, choiceB }) {
  const items = read();
  if (items.some((e) => e.planet === planet && e.title === title && !e.doneAt && !e.gaveUpAt)) {
    return items;
  }
  return write([
    ...items,
    {
      id: `x_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`,
      planet,
      planetLabel: planetLabel || "",
      title,
      step: step || "",
      why: why || "",
      choiceA: choiceA || "",
      choiceB: choiceB || "",
      startedAt: today(),
      doneAt: null,
      note: "",
    },
  ]);
}

// 다녀왔다 — 무엇을 알게 됐는지 한 줄. 이게 회고 자리를 대신한다.
export function completeExpedition(id, note) {
  return write(read().map((e) => (
    e.id === id ? { ...e, doneAt: today(), note: (note || "").trim() } : e
  )));
}

export function dropExpedition(id) {
  return write(read().map((e) => (e.id === id ? { ...e, gaveUpAt: today() } : e)));
}

export function removeExpedition(id) {
  return write(read().filter((e) => e.id !== id));
}
