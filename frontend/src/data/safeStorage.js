// ─────────────────────────────────────────────────────────────
// 저장소 어댑터 — iframe·사파리에서도 앱이 같은 방식으로 돌게 한다.
//
// 왜 필요한가: 이 앱은 상태를 전부 localStorage 에 넣는다(25개 파일·86곳).
//   그런데 **크로스 오리진 iframe 안에서는 그게 막힌다.**
//     · Chrome / Firefox — 파티션 저장소로 동작(상위 사이트별로 격리)
//     · Safari · iOS 전체 — 차단. Storage Access API 로 권한을 받기 전엔 못 쓴다
//       (iOS 는 크롬을 써도 엔진이 WebKit 이라 같다)
//   온라인 전시는 관람객이 자기 폰으로 들어오므로 아이폰 비중이 크다.
//   막힌 채로 두면 페르소나를 골라도 슬롯이 안 써지고 빈 우주가 뜬다 —
//   에러도 안 나서 원인을 못 찾는다.
//
// 방식: 실제 저장소를 한 번 시험해보고, 안 되면 **메모리 Map** 으로 대신한다.
//   화면 코드 입장에서는 getItem/setItem/removeItem 이 늘 성공한다.
//   되는 환경에서는 예전처럼 localStorage 에 남으므로 동작이 달라지지 않는다.
//
// 한계(의도된 것): 메모리로 떨어지면 **새로고침에 날아간다.**
//   그래서 페르소나 전환이 window.location.assign 같은 전체 새로고침을 쓰면 안 된다
//   — 그 순간 방금 심은 1년치가 사라진다. 라우팅으로만 이동할 것.
// ─────────────────────────────────────────────────────────────

const memory = new Map();

/** localStorage 를 실제로 써볼 수 있는가 — 읽기만으로는 모른다(사파리는 쓰기에서 막힌다). */
function probe() {
  try {
    if (typeof window === "undefined" || !window.localStorage) return null;
    const key = "__pm_probe__";
    window.localStorage.setItem(key, "1");
    window.localStorage.removeItem(key);
    return window.localStorage;
  } catch {
    return null;
  }
}

const real = probe();

/** 실제 저장소를 쓰는 중인가 — 안내 문구·진단에서 쓴다. */
export const isPersistent = real !== null;

/**
 * 왜 메모리로 떨어졌는지 — 화면에 "이 브라우저에서는 기록이 저장되지 않아요" 를
 * 띄울 때 근거로 쓴다. 원인을 정확히 알 방법은 없어 정황으로 적는다.
 */
export function storageNote() {
  if (isPersistent) return null;
  const framed = typeof window !== "undefined" && window.top !== window.self;
  return framed
    ? "다른 사이트에 embed 된 화면이라 브라우저가 저장을 막고 있어요. 새로고침하면 기록이 사라집니다."
    : "이 브라우저에서는 저장이 막혀 있어요(시크릿 모드 등). 새로고침하면 기록이 사라집니다.";
}

export function getItem(key) {
  if (real) {
    try {
      return real.getItem(key);
    } catch {
      /* 중간에 권한이 바뀐 경우 — 메모리로 흘린다 */
    }
  }
  return memory.has(key) ? memory.get(key) : null;
}

export function setItem(key, value) {
  const v = String(value);
  memory.set(key, v); // 항상 메모리에도 둔다 — 저장소가 도중에 막혀도 이번 세션은 이어진다
  if (real) {
    try {
      real.setItem(key, v);
    } catch {
      /* 용량 초과·권한 변경 — 메모리 값으로 계속 간다 */
    }
  }
}

export function removeItem(key) {
  memory.delete(key);
  if (real) {
    try {
      real.removeItem(key);
    } catch {
      /* 무시 */
    }
  }
}

/** localStorage 와 같은 모양 — 기존 코드에서 `localStorage` 를 이걸로 바꾸기만 하면 된다. */
const storage = { getItem, setItem, removeItem, get length() { return memory.size; } };
export default storage;
