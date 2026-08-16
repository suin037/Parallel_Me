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
  { id: "menFringe", label: "남자 앞머리", hair: "menFringe", rear: null, custom: true },
  { id: "menPerm", label: "남자 펌", hair: "menPerm", rear: null, custom: true },
  { id: "menPermFringe", label: "남자 펌 · 앞머리", hair: "menPermFringe", rear: null, custom: true },
  { id: "menPermPart", label: "남자 펌 · 5대5 가르마", hair: "menPermPart", rear: null, custom: true },
  { id: "menBowl", label: "남자 바가지컷", hair: "menBowl", rear: null, custom: true },
  { id: "menCrop", label: "남자 크롭컷", hair: "menCrop", rear: null, custom: true },
  // 단발도 긴머리처럼 가르마/앞머리 두 갈래로 둔다. 가르마 쪽은 빌트인 파츠 조합이라
  // 새로 그린 게 없다(sideComed + 짧은 뒷머리).
  { id: "bobShortParted", label: "단발(짧게) · 가르마", hair: "sideComed", rear: "neckHigh" },
  { id: "bobShort", label: "단발(짧게) · 앞머리", hair: "bangs", rear: "neckHigh", custom: true },
  { id: "bobLongParted", label: "단발(어깨) · 가르마", hair: "sideComed", rear: "shoulderHigh" },
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
// 감은 눈(수줍은·활 모양·윙크)은 뺐다. 눈이 작은 사람을 표현할 방법이 없다 보니
// 사진 분석이 '작은 눈' 대신 '감은 눈'을 계속 골랐다.
// 'small' 은 새 그림이 아니라 'wide' 를 각 눈 중심 기준으로 줄인 것이다(customParts.scaleEyes).
export const EYES = [
  { id: "wide", label: "크게 뜬" },
  { id: "happy", label: "웃는" },
  { id: "small", label: "작은 눈" },
];

// 'small' 이 실제로 쓰는 빌트인 눈과 축소 배율.
export const SMALL_EYE = { base: "happy", scale: 0.82, inset: 0 };

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

export const DEFAULT_AVATAR = {
  face: "original", // 얼굴형은 customParts.js 의 FACE_SHAPES 에서 온다
  hairStyle: "longParted", // 앞·뒤 조합 프리셋 id
  beard: null, // null = 수염 없음
  eyes: "wide",
  // 속눈썹. 빌트인 눈에는 항상 붙어 있어서 남자 아바타가 여성적으로 보였다.
  lashes: true,
  eyebrows: "neutral", // customParts.BROW_SHAPES 의 id
  browThickness: "normal",
  glasses: "none",
  mouth: "smile",
  clothes: "tShirt",
  skinColor: SKIN_COLORS[1],
  hairColor: HAIR_COLORS[0],
  clothesColor: CLOTHES_COLORS[0],
  // 옷 무늬. 목록에서 고르는 게 아니라 카메라 분석이 즉석에서 채운다.
  // { kind: "none"|"stripe"|"dot"|"check", color: "hex", size: 8~120, angle: 도 }
  pattern: { kind: "none" },
};

/**
 * 빌더 config → DiceBear createAvatar 옵션.
 * 배열로 넘겨야 그 값이 확정되고, *Probability 로 유무를 통제한다.
 */
export function toDicebearOptions(config) {
  const c = { ...DEFAULT_AVATAR, ...(config || {}) };
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
    eyes: [c.eyes === "small" ? SMALL_EYE.base : c.eyes],
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

// 기존 UI 가 기대하는 이름들. 화면 코드를 안 고치고 갈아끼우려고 유지한다.
//   Avatar / AvatarBuilder / avatarImage 가 이 두 개를 쓴다.
export { DEFAULT_AVATAR as DEFAULT_TOONHEAD };

/** 저장된 config 를 항상 완전한 형태로. 예전(react-nice-avatar) 설정이 와도 기본값으로 되돌린다. */
export function normalizeAvatar(config) {
  const isToonHead =
    config &&
    typeof config.face === "string" &&
    typeof config.hairStyle === "string" &&
    HAIR_STYLES.some((style) => style.id === config.hairStyle);
  if (!isToonHead) return { ...DEFAULT_AVATAR };
  return { ...DEFAULT_AVATAR, ...config };
}

// 개인화 이미지 생성 API가 사용하는 설명 규격. 화면용 아바타와 같은 설정을
// 전달해 A/B 이미지에서도 동일 인물의 특징이 유지되도록 한다.
export function avatarGenerationSpec(config, sex = "") {
  const c = normalizeAvatar(config);
  const hair = hairStyleById(c.hairStyle);
  const labelOf = (items, id) => items.find((item) => item.id === id)?.label || id;
  return {
    characterType: sex === "1" ? "male illustrated avatar" : sex === "2" ? "female illustrated avatar" : "gender-neutral illustrated avatar",
    gender: sex === "1" ? "male" : sex === "2" ? "female" : "unspecified",
    faceShape: FACE_SHAPES[c.face]?.label || c.face,
    hairStyle: hair.label,
    hairColor: `#${c.hairColor}`,
    skinTone: `#${c.skinColor}`,
    eyeStyle: labelOf(EYES, c.eyes),
    eyelashes: c.lashes === false ? "none" : "visible",
    eyebrowStyle: labelOf(BROW_SHAPE_ITEMS, c.eyebrows),
    eyebrowThickness: labelOf(BROW_THICKNESS, c.browThickness),
    mouthStyle: labelOf(MOUTH, c.mouth),
    glassesStyle: labelOf(GLASSES_OPTIONS, c.glasses),
    facialHair: c.beard ? labelOf(BEARD, c.beard) : "none",
    outfitStyle: labelOf(CLOTHES, c.clothes),
    outfitColor: `#${c.clothesColor}`,
  };
}
