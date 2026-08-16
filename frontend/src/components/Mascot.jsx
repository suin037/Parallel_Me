const DEF = {
  nova: { light: "#FFE9F0", main: "#FF9EC0", dark: "#F0688F", eye: "#5A2A3E", accent: "stars" },
  lumi: { light: "#FFF7DA", main: "#FFD97A", dark: "#F0AE3A", eye: "#7A5A1E", accent: "topstar" },
  cosmo: { light: "#EAF6FF", main: "#7CC3FF", dark: "#3FA9E0", eye: "#274A66", accent: "ring" },
};

function starPath(cx, cy, outer, inner, points = 5) {
  let p = "";
  const step = Math.PI / points;
  for (let i = 0; i < 2 * points; i++) {
    const r = i % 2 ? inner : outer;
    const a = -Math.PI / 2 + i * step;
    p += `${i ? "L" : "M"}${(cx + r * Math.cos(a)).toFixed(1)},${(cy + r * Math.sin(a)).toFixed(1)}`;
  }
  return `${p}Z`;
}

const spark = (x, y, r) =>
  `M${x},${y-r} L${x+r*.3},${y-r*.3} L${x+r},${y} L${x+r*.3},${y+r*.3} L${x},${y+r} L${x-r*.3},${y+r*.3} L${x-r},${y} L${x-r*.3},${y-r*.3} Z`;

export default function Mascot({ which = "cosmo", size = 48 }) {
  const d = DEF[which] || DEF.cosmo;
  const gid = `masc_${which}`;
  return (
    <svg viewBox="0 0 100 100" width={size} height={size} style={{ display: "block", overflow: "visible" }}>
      <defs><radialGradient id={gid} cx="38%" cy="34%" r="78%">
        <stop offset="0%" stopColor={d.light} /><stop offset="55%" stopColor={d.main} />
        <stop offset="100%" stopColor={d.dark} />
      </radialGradient></defs>
      {d.accent === "ring" && <ellipse cx="50" cy="57" rx="43" ry="12" fill="none" stroke={d.main} strokeWidth="2.4" opacity="0.5" transform="rotate(-18 50 57)" />}
      {d.accent === "topstar" && <path d={starPath(50, 15, 10, 4.4)} fill={d.dark} />}
      <circle cx="50" cy="57" r="30" fill={`url(#${gid})`} />
      {d.accent === "ring" && <><path d="M12,62 Q50,79 88,54" fill="none" stroke={d.dark} strokeWidth="2.4" opacity="0.75" transform="rotate(-18 50 57)" /><circle cx="84" cy="41" r="3" fill={d.light} /></>}
      {d.accent === "stars" && <><path d={spark(80,30,5)} fill="#fff" opacity="0.9" /><path d={spark(23,36,3.4)} fill="#fff" opacity="0.85" /><path d={spark(74,72,2.8)} fill="#fff" opacity="0.8" /></>}
      <ellipse cx="42" cy="55" rx="2.8" ry="3.5" fill={d.eye} /><ellipse cx="58" cy="55" rx="2.8" ry="3.5" fill={d.eye} />
      <circle cx="41" cy="53.4" r="0.9" fill="#fff" /><circle cx="57" cy="53.4" r="0.9" fill="#fff" />
      <path d="M45,62 Q50,67 55,62" fill="none" stroke={d.eye} strokeWidth="2" strokeLinecap="round" />
      <ellipse cx="37" cy="62" rx="3.4" ry="2" fill="#FF7DA0" opacity="0.3" /><ellipse cx="63" cy="62" rx="3.4" ry="2" fill="#FF7DA0" opacity="0.3" />
    </svg>
  );
}
