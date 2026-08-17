// ─────────────────────────────────────────────────────────────
// 페르소나 레지스트리 — 체험하기(넷플릭스식 프로필 선택) 화면의 데이터 원천.
//
// 카드에 필요한 정보(이름·나이·직업·MBTI)는 각 페르소나 파일의 `profile` 에서 온다.
// 1년치 기록은 무겁기 때문에(파일당 100KB 남짓) 카드를 그릴 때는 안 읽고,
// 실제로 고른 순간에만 동적 import 로 가져온다.
//
// dataStatus
//   "ready"   1년치 기록 있음 — 고르면 바로 체험 가능
//   "pending" 프로필만 있고 기록은 아직 없음 — 카드는 뜨되 '준비 중'으로 표시
// ─────────────────────────────────────────────────────────────

// ⚠ 기록 파일(dohyun.js 등)이 아니라 **프로필 파일**에서 가져와야 한다.
//   기록 파일을 정적 import 하면 ES 모듈은 파일 단위라 1년치가 통째로 첫 화면
//   번들에 딸려 들어오고, 아래 load() 의 동적 import 가 무효가 된다
//   (vite 경고: "dynamic import will not move module into another chunk").
import { profile as jiwon } from "./jiwon.profile.js";
import { profile as dohyun } from "./dohyun.profile.js";
import { profile as seongmin } from "./seongmin.profile.js";
import { profile as jiho } from "./jiho.profile.js";
import { profile as eunwoo } from "./eunwoo.profile.js";
import { profile as rin } from "./rin.profile.js";
import { profile as daun } from "./daun.profile.js";

// 카드가 놓이는 순서. 기록이 있는 인물을 앞에 둔다.
//
// dilemma / tags 는 **카드 전용 메타**라 profile 이 아니라 여기에 둔다.
//   profile 은 슬롯에 심겨 그대로 백엔드 요청에 실리므로(personaSession → schemas.py)
//   화면 문구를 거기 얹으면 보낼 일 없는 값이 요청에 섞인다.
//   dilemma  카드에서 가장 크게 읽히는 문장 — "이 사람이 지금 무엇을 정해야 하는가".
//            줄바꿈(\n)은 카드에서 그대로 두 줄로 그린다.
//   tags     필터 알약이 쓰는 축. 첫 값은 kind 와 같게 두고 부가 축만 덧붙인다
//            (린은 이직이면서 '해외' 결정이다). 알약 목록은 이 값에서 만들어지므로
//            여기 없는 축은 화면에도 안 뜬다 — 눌러도 0명인 필터를 만들지 않기 위함.
export const PERSONAS = [
  { id: "jiwon", profile: jiwon, dataStatus: "ready", kind: "이직", tags: ["이직"],
    dilemma: "합격한 그 회사로 옮길까,\n지금 자리에 남을까?",
    load: () => import("../demoYear.js") },
  { id: "dohyun", profile: dohyun, dataStatus: "ready", kind: "휴식", tags: ["휴식"],
    dilemma: "번아웃 앞에서 반년 쉴까,\n버티며 계속 갈까?",
    load: () => import("./dohyun.js") },
  { id: "seongmin", profile: seongmin, dataStatus: "ready", kind: "창업", tags: ["창업"],
    dilemma: "8년 다닌 회사를 나와\n카페를 차려도 될까?",
    load: () => import("./seongmin.js") },
  { id: "jiho", profile: jiho, dataStatus: "ready", kind: "이직", tags: ["이직"],
    dilemma: "조건 좋은 곳으로 또 옮길까,\n이번엔 버텨볼까?",
    load: () => import("./jiho.js") },
  { id: "eunwoo", profile: eunwoo, dataStatus: "ready", kind: "이직", tags: ["이직"],
    dilemma: "워라밸을 찾아 떠날까,\n지금 커리어를 이어갈까?",
    load: () => import("./eunwoo.js") },
  { id: "rin", profile: rin, dataStatus: "ready", kind: "이직", tags: ["이직", "해외"],
    dilemma: "석사를 마치고 돌아갈까,\n런던에 남아볼까?",
    load: () => import("./rin.js") },
  { id: "daun", profile: daun, dataStatus: "ready", kind: "창업", tags: ["창업"],
    dilemma: "겸업을 접고 독립할까,\n회사를 붙잡고 갈까?",
    load: () => import("./daun.js") },
];

/** 필터 알약 목록 — 실제로 사람이 있는 축만. 순서는 카드 순서를 따른다. */
export function personaTags() {
  const seen = [];
  for (const p of PERSONAS) for (const t of p.tags || []) if (!seen.includes(t)) seen.push(t);
  return seen;
}

export function getPersona(id) {
  return PERSONAS.find((p) => p.id === id) || null;
}

/**
 * 그 인물이 지금 고민 중인 두 갈래 — 시뮬레이션 입력 화면의 추천용.
 *
 * 페르소나마다 choices 를 들고 있는데 화면이 한 번도 읽지 않아서, 인물로 들어와도
 * 기본값("이직" vs "유지")부터 다시 타이핑해야 했다. 그 사람의 1년 기록은 이 두
 * 갈림길로 수렴하도록 쓰였으므로, 기록과 비교 대상이 같아야 결과가 말이 된다.
 *
 * conditionHints 는 '조건 더 알려주기' 칸의 추천값이다(키는 scenarioIntake 의 질문 key).
 */
export function personaCompare(id) {
  const persona = getPersona(id);
  const choices = persona?.profile?.choices;
  if (!choices?.a || !choices?.b) return null;
  return {
    id: persona.id,
    name: persona.profile.name,
    tagline: persona.profile.tagline,
    a: choices.a,
    b: choices.b,
    hints: persona.profile.conditionHints || null,
  };
}

/** 카드 한 장에 필요한 만큼만 — 1년치를 안 읽는다. */
export function personaCards() {
  return PERSONAS.map((p) => ({
    id: p.id,
    name: p.profile.name,
    age: p.profile.age,
    sex: p.profile.sex,
    job: p.profile.occupation,
    mbti: p.profile.mbti,
    tagline: p.profile.tagline,
    // 카드 얼굴. 참조를 그대로 넘긴다 — 화면이 이 값으로 렌더를 메모하므로
    // 여기서 새 객체를 만들면 매 렌더마다 아바타 7장을 다시 그리게 된다.
    avatar: p.profile.avatarConfig || null,
    kind: p.kind,
    tags: p.tags || [p.kind],
    dilemma: p.dilemma || p.profile.tagline,
    ready: p.dataStatus === "ready",
  }));
}
