// 아바타 렌더링. UI 와 분리돼 있어서 어떤 화면에서든 쓸 수 있다.
//
// 쓰는 법:
//   import { avatarDataUri, DEFAULT_AVATAR } from ".../renderAvatar.js";
//   <img src={avatarDataUri(config)} width={96} height={96} />
//
// config 는 DEFAULT_AVATAR 모양의 평범한 객체다. 일부만 넘겨도 나머지는 기본값으로 채워진다.
// 선택지 목록(HAIR_STYLES, EYES, ...)이 필요하면 data/avatarOptions.js 에서 가져다 쓰면 된다.

import { createAvatar } from "@dicebear/core";
import { toonHead } from "@dicebear/collection";
import {
  DEFAULT_AVATAR,
  SMALL_EYE,
  hairStyleById,
  toDicebearOptions,
} from "../data/avatarOptions.js";
import {
  fitBeard,
  HAIR_COVERS_EARS,
  overlayCustomHair,
  overlayEars,
  cleanClothes,
  overlayClothesPattern,
  overlayGlasses,
  replaceBrows,
  removeLashes,
  replaceFaceShape,
  scaleEyes,
} from "../data/customParts.js";

export { DEFAULT_AVATAR };

function hairOutlineColor(hex) {
  const clean = String(hex || "").replace("#", "").padEnd(6, "0").slice(0, 6);
  const rgb = [0, 2, 4].map((at) => Number.parseInt(clean.slice(at, at + 2), 16) || 0);
  // 검정 외곽선 대신 현재 머리색을 약 48% 어둡게 한다. 밝은 금발에서도 경계는
  // 남지만 별도 검은 모자처럼 분리되어 보이지 않는다.
  return `#${rgb.map((value) => Math.round(value * .52).toString(16).padStart(2, "0")).join("")}`;
}

function softenBuiltInHairOutline(svg, hairHex) {
  const fill = `#${String(hairHex).replace("#", "")}`;
  const outline = hairOutlineColor(fill);
  return svg.replace(/<(g|path|ellipse|circle|polygon)\b[^>]*>/gi, (tag) => {
    if (!tag.toLowerCase().includes(`fill="${fill.toLowerCase()}"`)) return tag;
    return tag
      .replace(/stroke="(?:black|#000(?:000)?)"/gi, `stroke="${outline}"`)
      .replace(/stroke-width="(?:6|7|8)"/gi, 'stroke-width="4"');
  });
}

/**
 * config → SVG 문자열.
 *
 * @param {object} config  아바타 설정(DEFAULT_AVATAR 참고). 일부만 넘겨도 된다.
 * @param {object} options DiceBear 옵션을 그대로 덧붙인다.
 *                         size / scale / translateX / translateY / flip / radius 등 전부 쓸 수 있고,
 *                         커스텀 파츠도 같이 변환된다(customParts.insertIntoBody 참고).
 */
export function renderAvatarSvg(config, options = {}) {
  const c = { ...DEFAULT_AVATAR, ...(config || {}) };
  const style = hairStyleById(c.hairStyle);

  let svg = createAvatar(toonHead, {
    seed: "me", // 우리가 모든 파츠를 지정하므로 시드는 고정해도 된다
    size: 200,
    ...toDicebearOptions(c),
    ...options,
  }).toString();

  svg = softenBuiltInHairOutline(svg, c.hairColor);

  // 순서가 중요하다.
  //   1) 얼굴형·눈썹은 원본 조각을 '교체'
  //   2) 수염은 바뀐 턱에 맞춰 늘림
  //   3) 커스텀 앞머리 → 그 위에 귀 → 안경 순으로 '덧그림'
  svg = cleanClothes(svg);
  svg = replaceFaceShape(svg, c.face);
  // 속눈썹 제거는 눈 축소보다 먼저다 — 축소가 눈 구간을 transform 으로 감싸고 나면
  // 꼬리 좌표는 그대로 남지만, 굳이 감싼 뒤에 손댈 이유가 없다.
  if (c.lashes === false) svg = removeLashes(svg);
  // 눈 축소는 눈썹 교체보다 먼저다 — 눈 구간의 끝을 '원본 눈썹'으로 찾기 때문이다.
  //
  // eyeScale 은 카메라가 재어 보내는 눈 크기(0.70~1.12). 눈을 '크게 뜬/웃는/작은'
  // 세 칸으로만 두면 카메라가 매번 같은 값에 몰린다(실측 10/10 small). 숫자로 받으면
  // 그 사이 값을 그대로 그릴 수 있다.
  const eyeScale = typeof c.eyeScale === "number" ? Math.max(0.6, Math.min(1.1, c.eyeScale)) : null;
  if (eyeScale && eyeScale !== 1) {
    svg = scaleEyes(svg, eyeScale, c.eyes === "small" ? SMALL_EYE.base : c.eyes, 0);
  } else if (c.eyes === "small") {
    svg = scaleEyes(svg, SMALL_EYE.scale, SMALL_EYE.base, SMALL_EYE.inset);
  }
  svg = replaceBrows(svg, c.eyebrows, c.browThickness, "#" + c.hairColor);
  svg = fitBeard(svg, c.beard, c.eyes, c.face);
  if (style.custom) {
    svg = overlayCustomHair(svg, style.hair, {
      hair: "#" + c.hairColor,
      hairOutline: hairOutlineColor(c.hairColor),
      skin: "#" + c.skinColor,
      clothes: "#" + c.clothesColor,
    });
    // 커스텀 앞머리가 귀를 덮으므로 귀만 다시 위에 그려 앞으로 빼낸다.
    // 다만 리프컷처럼 귀를 덮는 게 디자인인 머리는 예외다 — 귀가 머리를 뚫고 나온다.
    if (!HAIR_COVERS_EARS.has(style.hair)) svg = overlayEars(svg, "#" + c.skinColor);
  }
  // 옷 무늬는 옷 바로 위, 얼굴보다 아래에 들어간다.
  svg = overlayClothesPattern(svg, c.pattern, c.clothes);
  svg = overlayGlasses(svg, c.glasses);
  return svg;
}

/** config → <img src> 에 바로 넣을 수 있는 dataURI. */
export function avatarDataUri(config, options = {}) {
  return "data:image/svg+xml;utf8," + encodeURIComponent(renderAvatarSvg(config, options));
}
