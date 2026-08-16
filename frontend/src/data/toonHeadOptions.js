// toonHead(DiceBear) 부위별 빌더 옵션.
// 값(id)은 DiceBear 스키마의 enum 을 그대로 쓰고, 라벨만 한국어로 붙였다.
// 스키마에 없는 값을 넣으면 조용히 무시되므로 id 를 임의로 바꾸지 말 것.
//
// 출처 표기 의무: ToonHead by Johan Melin, CC BY 4.0
// https://creativecommons.org/licenses/by/4.0/

import {
  BROW_SHAPE_ITEMS,
  BROW_THICKNESS,
  FACE_SHAPES,
  GLASSES_OPTIONS,
} from "./customParts.js";

export { BROW_SHAPE_ITEMS, BROW_THICKNESS, GLASSES_OPTIONS };

export const TOONHEAD_CREDIT = {
  title: "ToonHead",
  creator: "Johan Melin",
  creatorUrl: "https://www.johanmelin.com",
  license: "CC BY 4.0",
  licenseUrl: "https://creativecommons.org/licenses/by/4.0/",
};

// 헤어스타일 = 앞머리 + 뒷머리 조합 프리셋.
// 앞·뒤를 따로 고르게 하면 어울리지 않는 조합이 나오고 고를 게 두 배로 늘어난다.
// 그래서 완성된 스타일 하나씩만 고르게 한다. 긴머리는 '앞머리 있음/없음'으로 갈린다.
//   hair = 앞머리 (null 이면 없음), rear = 뒷머리 (null 이면 없음)
//   custom: true 면 customParts.js 의 CUSTOM_HAIR 에서 온 것
// '앞머리 없음'은 민머리가 아니라 '이마가 드러나는 가르마'를 뜻한다(윗머리는 있다).
// '앞머리 있음'은 이마를 덮는 뱅. 빌트인 앞머리 4종은 전부 이마가 드러나는 쪽이라
// 뱅은 customParts.CUSTOM_HAIR.bangs 로 따로 그려서 쓴다.
export const HAIR_STYLES = [
  { id: "bald", label: "민머리", hair: null, rear: null },
  { id: "sideComed", label: "옆가르마", hair: "sideComed", rear: null },
  { id: "undercut", label: "언더컷", hair: "undercut", rear: null },
  { id: "spiky", label: "뾰족머리", hair: "spiky", rear: null },
  { id: "bun", label: "번머리", hair: "bun", rear: null },
  { id: "bobShort", label: "단발(짧게) · 앞머리", hair: "bangs", rear: "neckHigh", custom: true },
  { id: "bobLong", label: "단발(어깨) · 앞머리", hair: "bangs", rear: "shoulderHigh", custom: true },
  { id: "longParted", label: "긴 생머리 · 가르마", hair: "sideComed", rear: "longStraight" },
  { id: "longBangs", label: "긴 생머리 · 앞머리", hair: "bangs", rear: "longStraight", custom: true },
  { id: "wavyParted", label: "긴 웨이브 · 가르마", hair: "sideComed", rear: "longWavy" },
  { id: "wavyBangs", label: "긴 웨이브 · 앞머리", hair: "bangs", rear: "longWavy", custom: true },
];

export function hairStyleById(id) {
  return HAIR_STYLES.find((h) => h.id === id) || HAIR_STYLES[0];
}

export const BEARD = [
  { id: "moustacheTwirl", label: "콧수염" },
  { id: "chin", label: "턱수염" },
  { id: "chinMoustache", label: "턱+콧수염" },
  { id: "fullBeard", label: "풀비어드" },
  { id: "longBeard", label: "긴 수염" },
];

// 직접 그린 무쌍/유쌍은 화풍이 안 맞아 기각됐다. 빌트인만 쓴다.
// 눈매를 손보려면 손으로 그리지 말고 Figma 원본에서 그려 재수출하는 쪽이 맞다.
export const EYES = [
  { id: "wide", label: "크게 뜬" },
  { id: "happy", label: "웃는" },
  { id: "humble", label: "수줍은" },
  { id: "bow", label: "활 모양" },
  { id: "wink", label: "윙크" },
];

// 눈썹은 두께를 조절하려고 전부 직접 그린 것으로 대체했다(customParts.BROW_SHAPES).
// 모양 목록은 BROW_SHAPE_ITEMS, 두께는 BROW_THICKNESS 를 쓴다.

export const MOUTH = [
  { id: "smile", label: "미소" },
  { id: "laugh", label: "활짝" },
  { id: "agape", label: "벌린" },
  { id: "sad", label: "슬픔" },
  { id: "angry", label: "화남" },
];

export const CLOTHES = [
  { id: "tShirt", label: "티셔츠" },
  { id: "shirt", label: "셔츠" },
  { id: "turtleNeck", label: "터틀넥" },
  { id: "openJacket", label: "오픈자켓" },
  { id: "dress", label: "드레스" },
];

// DiceBear 색 파라미터는 '#' 없는 hex 문자열을 받는다. UI 표시할 때만 '#'을 붙인다.
export const SKIN_COLORS = ["f2d3b1", "edb98a", "d08b5b", "ae5d29", "8d5524", "614335"];
export const HAIR_COLORS = ["2c1b18", "0e0e0e", "724133", "a55728", "b58143", "c93305", "d6b370", "e8e1e1"];
export const CLOTHES_COLORS = ["3c4f5c", "5199e4", "25557c", "929598", "a7ffc4", "ff5c5c", "ffafb9", "ffffb1"];

export const DEFAULT_TOONHEAD = {
  face: "original", // 얼굴형은 customParts.js 의 FACE_SHAPES 에서 온다
  hairStyle: "longParted", // 앞·뒤 조합 프리셋 id
  beard: null, // null = 수염 없음
  eyes: "wide",
  eyebrows: "neutral", // customParts.BROW_SHAPES 의 id
  browThickness: "normal",
  glasses: "none",
  mouth: "smile",
  clothes: "tShirt",
  skinColor: SKIN_COLORS[1],
  hairColor: HAIR_COLORS[0],
  clothesColor: CLOTHES_COLORS[0],
};

/**
 * 빌더 config → DiceBear createAvatar 옵션.
 * 배열로 넘겨야 그 값이 확정되고, *Probability 로 유무를 통제한다.
 */
export function toDicebearOptions(config) {
  const c = { ...DEFAULT_TOONHEAD, ...(config || {}) };
  const style = hairStyleById(c.hairStyle);
  // 커스텀 앞머리(비니 등)는 DiceBear 가 모르므로 빌트인 앞머리를 끄고 나중에 덧그린다.
  const frontHair = style.custom ? null : style.hair;
  return {
    hair: frontHair ? [frontHair] : undefined,
    hairProbability: frontHair ? 100 : 0,
    rearHair: style.rear ? [style.rear] : undefined,
    rearHairProbability: style.rear ? 100 : 0,
    beard: c.beard ? [c.beard] : undefined,
    beardProbability: c.beard ? 100 : 0,
    eyes: [c.eyes],
    // 눈썹은 항상 neutral 로 그려두고 customParts.replaceBrows 가 그 자리를 바꾼다.
    eyebrows: ["neutral"],
    mouth: [c.mouth],
    clothes: [c.clothes],
    skinColor: [c.skinColor],
    hairColor: [c.hairColor],
    clothesColor: [c.clothesColor],
  };
}

/** 무작위 조합 하나. "다시 뽑기"용. */
export function randomToonHead() {
  const pick = (arr) => arr[Math.floor(Math.random() * arr.length)];
  return {
    face: pick(Object.keys(FACE_SHAPES)),
    hairStyle: pick(HAIR_STYLES).id,
    beard: Math.random() < 0.3 ? pick(BEARD).id : null,
    eyes: pick(EYES).id,
    eyebrows: pick(BROW_SHAPE_ITEMS).id,
    browThickness: pick(BROW_THICKNESS).id,
    glasses: Math.random() < 0.35 ? pick(GLASSES_OPTIONS.slice(1)).id : "none",
    mouth: pick(MOUTH).id,
    clothes: pick(CLOTHES).id,
    skinColor: pick(SKIN_COLORS),
    hairColor: pick(HAIR_COLORS),
    clothesColor: pick(CLOTHES_COLORS),
  };
}
