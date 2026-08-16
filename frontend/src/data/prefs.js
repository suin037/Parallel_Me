import storage from "./safeStorage.js";
// 로컬 환경설정(알림·아바타) — localStorage 지속. 설정 화면(수인) 소관.
const KEY = "pm.prefs.v1";

const DEFAULTS = {
  notifications: { checkin: true, actionBridge: true, weekly: false },
  avatar: "rocket",
};

export function loadPrefs() {
  try {
    return { ...DEFAULTS, ...JSON.parse(storage.getItem(KEY) || "{}") };
  } catch {
    return { ...DEFAULTS };
  }
}

export function savePrefs(prefs) {
  try {
    storage.setItem(KEY, JSON.stringify(prefs));
  } catch {
    /* localStorage 불가 환경 무시 */
  }
}

// 아바타 프리셋(가벼운 이모지형). 나중에 일러스트로 교체 가능.
export const AVATARS = [
  { id: "rocket", emoji: "🚀", label: "코멧" },
  { id: "star", emoji: "⭐", label: "스타" },
  { id: "planet", emoji: "🪐", label: "플래닛" },
  { id: "moon", emoji: "🌙", label: "루나" },
  { id: "comet", emoji: "☄️", label: "혜성" },
  { id: "sparkle", emoji: "✨", label: "스파클" },
];
