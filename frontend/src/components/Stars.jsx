import { useMemo } from "react";

// 배경 별. 주인공은 숫자이므로 은은하게(opacity 낮게). 한 번만 생성.
// twinkle: 반짝임 애니메이션. glow: 일부 별에 halo를 씌워 "빛나는" 느낌을 준다.
export default function Stars({ count = 26, twinkle = false, glow = false }) {
  const stars = useMemo(
    () =>
      Array.from({ length: count }, () => ({
        left: Math.random() * 100,
        top: Math.random() * 100,
        opacity: Math.random() * 0.45 + 0.12,
        scale: Math.random() * 1.3 + 0.5,
        // 같은 주기로 깜빡이면 기계적으로 보여서 별마다 흩뜨린다.
        duration: Math.random() * 2.6 + 2.2,
        delay: Math.random() * 4,
        // 큰 별에만 halo — 전부 빛나면 배경이 시끄러워진다.
        halo: glow && Math.random() < 0.22,
      })),
    [count, glow],
  );

  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
      {stars.map((s, i) => (
        // 바깥 span = 위치·기본 밝기, 안쪽 span = 반짝임.
        // 밝기를 나눠 두면 별마다 다른 기본 밝기를 유지한 채 깜빡일 수 있다.
        <span
          key={i}
          className="absolute block"
          style={{ left: `${s.left}%`, top: `${s.top}%`, opacity: s.opacity, transform: `scale(${s.scale})` }}
        >
          <span
            className={`block h-[2px] w-[2px] rounded-full bg-white ${twinkle ? "animate-twinkle" : ""} ${
              s.halo ? "shadow-[0_0_6px_2px_rgba(255,255,255,.55)]" : ""
            }`}
            style={twinkle ? { animationDuration: `${s.duration}s`, animationDelay: `${s.delay}s` } : undefined}
          />
        </span>
      ))}
    </div>
  );
}
