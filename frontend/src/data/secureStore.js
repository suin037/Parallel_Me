import storage from "./safeStorage.js";
// ─────────────────────────────────────────────────────────────
// 개인정보 암호화 모듈 — 일기·감정·이직조건·회사요건 등 민감정보를 기기에서 암호화.
//
// 진짜 보안: 브라우저 표준 Web Crypto API
//   · 키유도: PBKDF2(SHA-256, 210k회) — 사용자 암호문구에서 파생. 암호 없이는 복호 불가.
//   · 암호화: AES-256-GCM(인증형 암호) — 변조 감지 포함.
//   · 원문·키는 디스크에 저장하지 않는다. localStorage엔 '암호문 + salt + iv'만.
//     (salt/iv는 비밀이 아니어도 됨. 키는 세션 메모리에만 둔다.)
//
// 정직선: 이건 '저장 데이터(at rest)' 보호다. 기기 분실·localStorage 탈취엔 강하지만,
//   암호가 입력된 상태의 감염 기기까지 막지는 못한다(어떤 클라 암호화도 동일).
// ─────────────────────────────────────────────────────────────
const enc = new TextEncoder();
const dec = new TextDecoder();

const PBKDF2_ITERS = 210000; // OWASP 권장선 근처
const SALT_KEY = "pm.sec.salt.v1"; // salt(비밀 아님) 보관
const VERIFY_KEY = "pm.sec.verify.v1"; // 암호문구 검증용 토큰(암호문)

function b64(buf) {
  return btoa(String.fromCharCode(...new Uint8Array(buf)));
}
function unb64(s) {
  return Uint8Array.from(atob(s), (c) => c.charCodeAt(0));
}

export function hasCrypto() {
  return typeof crypto !== "undefined" && !!crypto.subtle;
}

function getSalt() {
  let s = storage.getItem(SALT_KEY);
  if (!s) {
    s = b64(crypto.getRandomValues(new Uint8Array(16)));
    storage.setItem(SALT_KEY, s);
  }
  return s;
}

/** 암호문구 → AES-256-GCM 키 (PBKDF2). 키는 반환만 하고 저장하지 않는다. */
export async function deriveKey(passphrase) {
  const salt = unb64(getSalt());
  const base = await crypto.subtle.importKey("raw", enc.encode(passphrase), "PBKDF2", false, ["deriveKey"]);
  return crypto.subtle.deriveKey(
    { name: "PBKDF2", salt, iterations: PBKDF2_ITERS, hash: "SHA-256" },
    base,
    { name: "AES-GCM", length: 256 },
    false,
    ["encrypt", "decrypt"],
  );
}

/** 객체 → 암호문 블록 { iv, ct, alg, kdf }. */
export async function encryptJSON(obj, key) {
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const ct = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, enc.encode(JSON.stringify(obj)));
  return { v: 1, alg: "AES-256-GCM", kdf: `PBKDF2-SHA256-${PBKDF2_ITERS}`, iv: b64(iv), ct: b64(ct) };
}

/** 암호문 블록 → 원본 객체. 암호 틀리거나 변조되면 throw. */
export async function decryptJSON(blob, key) {
  const pt = await crypto.subtle.decrypt({ name: "AES-GCM", iv: unb64(blob.iv) }, key, unb64(blob.ct));
  return JSON.parse(dec.decode(pt));
}

// ── 암호문구 설정/검증 ────────────────────────────────────────
/** 최초 암호문구 설정 — 검증 토큰을 암호화해 저장. 반환: 세션 키. */
export async function setupPassphrase(passphrase) {
  const key = await deriveKey(passphrase);
  const token = await encryptJSON({ ok: true, t: "pm-verify" }, key);
  storage.setItem(VERIFY_KEY, JSON.stringify(token));
  return key;
}

export function isPassphraseSet() {
  return !!storage.getItem(VERIFY_KEY);
}

/** 입력한 암호문구가 맞는지 검증 토큰 복호로 확인. 맞으면 세션 키 반환, 틀리면 null. */
export async function unlock(passphrase) {
  const raw = storage.getItem(VERIFY_KEY);
  if (!raw) return null;
  try {
    const key = await deriveKey(passphrase);
    const r = await decryptJSON(JSON.parse(raw), key);
    return r?.t === "pm-verify" ? key : null;
  } catch {
    return null; // 복호 실패 = 틀린 암호
  }
}
