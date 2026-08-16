// ─────────────────────────────────────────────────────────────
// 기쁠 때 올라가는 하트 — 돌보미가 나오는 곳이면 어디든 같은 모션을 쓴다.
//
// 일기 화면의 미리보기(PetPeek)와 설정의 돌보미 카드(PetMascot)는 같은 친구다.
// 한쪽만 하트를 날리면 다른 앤가 싶다. 그래서 여기 한 곳에 두고 둘 다 부른다.
//
// 셋을 시차·방향·크기를 달리해 띄운다 — 같은 걸 반복하면 기계처럼 보인다.
// ─────────────────────────────────────────────────────────────
const CSS = `
@keyframes pet-heart {
  0%   { opacity: 0; transform: translate(0, 4px) scale(.6) }
  15%  { opacity: 1 }
  70%  { opacity: .9 }
  100% { opacity: 0; transform: translate(var(--dx, 6px), calc(var(--rise, 26px) * -1)) scale(1.05) }
}
.pet-heart { animation: pet-heart 2.4s ease-out infinite }
@media (prefers-reduced-motion: reduce) {
  .pet-heart { animation: none; opacity: .9 }
}
`;

const HEARTS = [
  { delay: "0s", dx: "-7px", left: "12%", scale: 1 },
  { delay: ".8s", dx: "5px", left: "46%", scale: 1.22 },
  { delay: "1.6s", dx: "9px", left: "74%", scale: .9 },
];

/**
 * @param on    기쁨일 때만 true
 * @param size  기준 크기(하트 크기·올라가는 높이가 여기서 나온다)
 */
export default function PetHearts({ on, size = 62 }) {
  if (!on) return null;
  const base = Math.max(8, Math.round(size * 0.15));
  const rise = Math.round(size * 0.42);

  return (
    <span
      className="pointer-events-none absolute inset-x-0 -top-1 block"
      style={{ height: rise }}
      aria-hidden="true"
    >
      <style>{CSS}</style>
      {HEARTS.map((h) => (
        <svg
          key={h.left}
          viewBox="0 0 24 24"
          width={Math.round(base * h.scale)}
          height={Math.round(base * h.scale)}
          className="pet-heart absolute bottom-0"
          style={{ left: h.left, animationDelay: h.delay, "--dx": h.dx, "--rise": `${rise}px` }}
        >
          <path
            d="M12 21s-7.5-4.7-9.4-9A5.2 5.2 0 0 1 12 6.6 5.2 5.2 0 0 1 21.4 12c-1.9 4.3-9.4 9-9.4 9Z"
            fill="#FF8FB1"
          />
        </svg>
      ))}
    </span>
  );
}
