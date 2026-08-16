import { avatarDataUri } from "../lib/renderAvatar.js";
import { normalizeAvatar } from "../data/avatarOptions.js";

// 기존 화면들이 쓰던 그대로의 API: <Avatar config={...} size={96} ring />
// 속을 react-nice-avatar 에서 toonHead 로 갈아끼운 것뿐이라 호출부는 손댈 필요가 없다.
//
// toonHead SVG 는 배경이 투명하다. 앱이 어두운 테마라 머리카락·윤곽선이 배경에 묻혀
// 아바타가 잘 안 보인다. 그래서 원 안을 밝게 깔아 프로필 사진처럼 띄운다.
// 색은 AI 참조용 PNG(data/avatarImage.js)의 배경과 같은 값이라 미리보기와 결과물이 일치한다.
const AVATAR_BG = "#F3F0EA";

export default function Avatar({ config, size = 96, ring = true, bg = AVATAR_BG }) {
  const c = normalizeAvatar(config);
  return (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: "50%",
        overflow: "hidden",
        flexShrink: 0,
        background: bg, // bg={null} 로 끄면 투명하게 쓸 수 있다
        boxShadow: ring ? "0 0 0 2px rgba(139,108,207,0.45)" : "none",
      }}
    >
      <img
        src={avatarDataUri(c, { size })}
        alt=""
        width={size}
        height={size}
        style={{ display: "block", width: "100%", height: "100%" }}
      />
    </div>
  );
}
