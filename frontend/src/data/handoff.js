import storage from "./safeStorage.js";
// ─────────────────────────────────────────────────────────────
// 기기 옮기기 — 폰에서 하던 체험을 노트북에서 이어서 한다. 서버 없이.
//
// 왜 서버가 없나: 전시용으로 필요한 건 '보관'이 아니라 '옮기기'다. 계정도,
//   DB도, 만료 정책도 필요 없다. 서버가 없으면 콜드스타트·다운·트래픽 걱정도
//   같이 사라진다(출품 요강의 트래픽 조건).
//
// 어떻게: 이 앱의 상태는 전부 localStorage 의 "pm.*" 키에 있다. 그걸 모아
//   gzip 으로 줄이고 base64url 로 바꿔 링크의 '#' 뒤(fragment)에 싣는다.
//
// 왜 '#' 뒤인가: fragment 는 브라우저가 서버로 보내지 않는다. Vercel 접속
//   로그에도, 우리 백엔드에도 기록이 남지 않는다. 쿼리(?d=)로 하면 남는다.
//
// 정직선: 링크 자체가 열쇠다. 링크를 받은 사람은 그 기록을 본다. 그래서
//   화면에서 "남에게 보내지 말라"고 명시한다. 또 카톡으로 보내면 카톡 서버엔
//   남는다 — 우리 서버에 안 남는다는 것과 별개다.
// ─────────────────────────────────────────────────────────────

const PREFIX = "pm.";

// 옮기면 안 되는 키.
//  · sec.*   : 이 기기에서만 의미 있는 암호 재료(salt·검증토큰). 옮기면 오히려 꼬인다.
//  · anonId  : 기기별 익명 식별자. 복사하면 같은 ID가 두 기기에 생겨 집계가 틀어진다.
//  · chatDraft: 쓰다 만 초안. 옮길 값이 없다.
//  · guide.seen: 새 기기에선 가이드를 한 번 보는 게 맞다.
const SKIP = new Set([
  "pm.sec.salt.v1",
  "pm.sec.verify.v1",
  "pm.anonId.v1",
  "pm.chatDraft.v1",
  "pm.guide.seen.v1",
]);

// QR 은 데이터가 커지면 화면에서 못 읽는다(칸이 촘촘해져 카메라가 못 잡음).
// 이 길이를 넘으면 QR 대신 링크 공유·복사만 안내한다.
export const QR_MAX = 1200;
// 브라우저·메신저가 주소를 자르기 시작하는 대략의 한계. 넘으면 경고만 띄운다.
export const LINK_WARN = 30000;

// ── base64url ────────────────────────────────────────────────
// btoa 는 문자열만 받는다. 큰 배열을 한 번에 String.fromCharCode(...arr) 로
// 펼치면 인자 개수 한계로 스택이 터지므로 조각내서 붙인다.
function toB64Url(bytes) {
  let bin = "";
  const CHUNK = 0x8000;
  for (let i = 0; i < bytes.length; i += CHUNK) {
    bin += String.fromCharCode.apply(null, bytes.subarray(i, i + CHUNK));
  }
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function fromB64Url(text) {
  const b64 = text.replace(/-/g, "+").replace(/_/g, "/");
  const padded = b64 + "=".repeat((4 - (b64.length % 4)) % 4);
  const bin = atob(padded);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

// ── 압축 ─────────────────────────────────────────────────────
// CompressionStream 은 Safari 16.4 미만·구형 브라우저에 없다. 없으면 압축을
// 건너뛰고 원본을 싣는다(링크가 길어질 뿐 동작은 같다). 어느 쪽인지는 맨 앞
// 한 글자로 표시한다 — z=압축, r=원본.
function canCompress() {
  return typeof CompressionStream !== "undefined" && typeof DecompressionStream !== "undefined";
}

async function gzip(bytes) {
  const stream = new Blob([bytes]).stream().pipeThrough(new CompressionStream("gzip"));
  return new Uint8Array(await new Response(stream).arrayBuffer());
}

async function gunzip(bytes) {
  const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"));
  return new Uint8Array(await new Response(stream).arrayBuffer());
}

// ── 상태 모으기 / 심기 ───────────────────────────────────────
/** localStorage 의 pm.* 를 모은다. 값은 문자열 그대로 둔다(파싱하지 않는다). */
export function collectState() {
  const out = {};
  try {
    for (let i = 0; i < storage.length; i++) {
      const key = storage.key(i);
      if (!key || !key.startsWith(PREFIX) || SKIP.has(key)) continue;
      const value = storage.getItem(key);
      if (value != null) out[key] = value;
    }
  } catch {
    /* localStorage 불가 환경(사파리 프라이빗 등) — 빈 상태로 취급 */
  }
  return out;
}

/** 받은 상태를 이 기기에 심는다. 같은 키는 덮어쓰고, 없던 키는 그대로 둔다. */
export function applyState(state) {
  let written = 0;
  for (const [key, value] of Object.entries(state || {})) {
    // 신뢰하지 않는 링크에서 온 값이므로 우리 네임스페이스 밖은 절대 쓰지 않는다.
    if (!key.startsWith(PREFIX) || SKIP.has(key)) continue;
    try {
      storage.setItem(key, String(value));
      written++;
    } catch {
      /* 용량 초과 등 — 나머지 키는 계속 시도한다 */
    }
  }
  return written;
}

// ── 싣기 / 풀기 ──────────────────────────────────────────────
/** 지금 이 기기의 상태 → 링크에 실을 문자열. */
export async function packState(state = collectState()) {
  const raw = new TextEncoder().encode(JSON.stringify({ v: 1, t: Date.now(), s: state }));
  if (!canCompress()) return "r" + toB64Url(raw);
  return "z" + toB64Url(await gzip(raw));
}

/** 링크에서 받은 문자열 → 상태. 형식이 깨졌으면 throw. */
export async function unpackState(payload) {
  const flag = payload[0];
  const body = fromB64Url(payload.slice(1));
  const raw = flag === "z" ? await gunzip(body) : body;
  const parsed = JSON.parse(new TextDecoder().decode(raw));
  if (!parsed || typeof parsed.s !== "object") throw new Error("형식이 올바르지 않아요");
  return { state: parsed.s, at: parsed.t || null };
}

// ── 링크 ─────────────────────────────────────────────────────
export function buildResumeLink(payload) {
  return `${window.location.origin}/resume#d=${payload}`;
}

/** 주소창의 '#d=' 를 읽는다. 없으면 null. */
export function readIncoming() {
  const hash = window.location.hash || "";
  const match = hash.match(/[#&]d=([A-Za-z0-9_-]+)/);
  return match ? match[1] : null;
}

/** 불러온 뒤 주소창에서 데이터를 지운다 — 뒤로가기·재공유로 새어나가지 않게. */
export function clearIncoming() {
  try {
    window.history.replaceState(null, "", window.location.pathname);
  } catch {
    /* 무시 */
  }
}

// ── 미리보기용 요약 ──────────────────────────────────────────
// "무엇이 옮겨지는지" 를 사용자에게 보여주기 위한 것. 실패해도 옮기기 자체는
// 되어야 하므로 파싱은 전부 try 로 감싼다.
export function describeState(state) {
  const read = (key) => {
    try {
      return JSON.parse(state[key] || "null");
    } catch {
      return null;
    }
  };
  const universe = read("pm.myuniverse.v1") || {};
  const profile = read("pm.profile.v1") || {};
  const universes = read("pm.universes.v1");
  const checkins = Array.isArray(universe.checkins) ? universe.checkins.filter((c) => !c.empty) : [];

  return {
    name: (profile.name || "").trim(),
    checkins: checkins.length,
    scenarios: Array.isArray(universe.scenarios) ? universe.scenarios.length : 0,
    universes: Array.isArray(universes) ? universes.length : 0,
    demo: !!universe.demo,
    keys: Object.keys(state).length,
  };
}
