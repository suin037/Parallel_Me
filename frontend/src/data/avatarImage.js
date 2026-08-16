// 아바타를 AI 이미지 생성의 참조 입력(PNG)으로 변환한다.
//
// 예전 구현은 react-nice-avatar DOM 을 html2canvas 로 캡처해야 했다(foreignObject 가
// canvas 를 taint 해서). toonHead 는 순수 SVG 문자열이라 그럴 필요가 없다 —
// SVG 를 그대로 Image 에 실어 canvas 에 그리면 끝이고, html2canvas 의존도 사라진다.
//
// 반환 규격은 예전과 같게 유지한다(480x480, 불투명 배경). 호출부를 고칠 필요가 없다.

import { normalizeAvatar } from "./avatarOptions.js";
import { renderAvatarSvg } from "../lib/renderAvatar.js";

const OUT = 480; // Cloudflare reference input 제한에 맞춰 512 보다 작게 유지
const BG = "#f3f0ea"; // 투명 배경은 생성 모델이 불안정하게 해석해서 불투명으로 깐다

export async function avatarToPngBlob(config) {
  const svg = renderAvatarSvg(normalizeAvatar(config), { size: OUT });
  const img = await loadSvg(svg);

  const canvas = document.createElement("canvas");
  canvas.width = OUT;
  canvas.height = OUT;
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = BG;
  ctx.fillRect(0, 0, OUT, OUT);
  // 얼굴과 머리가 함께 들어오도록 살짝 여백을 두고 그린다. 너무 좁게 자르면
  // 긴 머리·모자·안경이 잘려 생성 모델이 다른 인물로 해석하기 쉽다.
  const pad = 20;
  ctx.drawImage(img, pad, pad, OUT - pad * 2, OUT - pad * 2);

  return await canvasToBlob(canvas);
}

function loadSvg(svg) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error("아바타 SVG 로드 실패"));
    // SVG 문자열을 그대로 실으므로 외부 요청이 없고 canvas 도 taint 되지 않는다.
    img.src = "data:image/svg+xml;utf8," + encodeURIComponent(svg);
  });
}

function canvasToBlob(canvas) {
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => (blob ? resolve(blob) : reject(new Error("아바타 PNG 변환 실패"))),
      "image/png"
    );
  });
}
