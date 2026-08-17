import { useMemo, useState } from "react";
import { seedFrom, starShapeFor } from "../data/starShapes.js";
import { MOOD_ALPHA, MOOD_COLORS, MOOD_EMPTY, MOOD_GLOW, MOOD_LABELS, MOOD_RULE_LINE, moodLevel } from "../data/moodColors.js";

// 별자리 = 디자인 뼈대(starShapes) 위에 기록 별을 하나씩 앉힌 것.
// 기분은 별의 색·크기로 읽고, 자리는 모양이 정한다 — 3D 우주에 뜬 그 별자리와 같은 모양이
// 나와야 눌러서 펼쳤을 때 "아까 그 별자리"로 읽힌다.
// (전에는 각도=순번·반지름=기분인 극좌표라, 별이 늘수록 선이 서로 넘나들어 실타래가 됐다.)
// 별 클릭 → onSelect(star).

const W = 200, H = 200, CX = 100, CY = 100;
const R = 74;   // 뼈대(-1~1) → 화면 반지름
// 색·레벨 규칙은 data/moodColors.js 한 곳에 있다(밝기가 1→5 로 오르는 램프).
// 여기서 다시 정의하면 홈 캘린더·기록 아카이브와 또 갈라진다.
const COL = MOOD_COLORS;
const MOOD_LABEL = MOOD_LABELS;
const level = moodLevel;
export const starColor = (s) => COL[level(s) - 1];

function shortNote(star) {
  const note = String(star.note || star.text || "").replace(/\s+/g, " ").trim();
  if (!note) return star.hasDiary ? "일기를 기록했어요" : "기분을 기록했어요";
  return note.length > 34 ? `${note.slice(0, 34)}…` : note;
}

function dateLabel(dateKey) {
  const [, month, day] = String(dateKey || "").split("-");
  return month && day ? `${Number(month)}월 ${Number(day)}일` : dateKey;
}

// 뼈대 좌표(-1~1, y 위쪽이 +) → SVG 좌표(y 아래쪽이 +).
function place([x, y]) {
  return [CX + x * R, CY - y * R];
}

// 뼈대보다 별이 많으면(7개 초과 묶음) 남는 별은 바깥 고리에 둘러 놓는다.
// 자리가 없다고 빼버리면 기록이 조용히 사라진다.
function overflowPoint(i, extra) {
  const a = (i / Math.max(1, extra)) * Math.PI * 2 - Math.PI / 2;
  return [Math.cos(a) * 1.18, Math.sin(a) * 1.18];
}

export default function Constellation({ stars = [], onSelect, selectedDate = null, todayDate = null, size = 210, seed = null }) {
  const [hovered, setHovered] = useState(null);
  const shape = useMemo(
    () => starShapeFor(stars.length, seedFrom(seed ?? stars[0]?.date ?? "")),
    [stars.length, seed, stars[0]?.date],
  );
  if (!stars.length) return null;
  const nodes = shape.points.length;
  const pts = stars.map((s, i) => {
    const filled = !s.empty && (s.mood != null || s.valence != null);
    const [x, y] = place(i < nodes ? shape.points[i] : overflowPoint(i - nodes, stars.length - nodes));
    return { ...s, x, y, filled, lvl: level(s) };
  });
  // 7일 다 기록해 별자리가 완성되면 은은하게 빛난다.
  const complete = pts.length >= 7 && pts.every((p) => p.filled);

  return (
    <div className="relative">
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img"
      aria-label={`기록 ${pts.filter((p) => p.filled).length}개로 그린 ${shape.name} 모양 별자리`}
      style={{ maxHeight: size, height: size, display: "block" }}>
      {/* 뼈대가 정한 선만 긋는다 — 순서대로 전부 이으면 선이 서로 넘나들어 실타래가 된다. */}
      {shape.edges.map(([a, b]) => {
        const p = pts[a], q = pts[b];
        if (!p || !q) return null;
        const solid = p.filled && q.filled;
        return (
          <line key={`ln${a}-${b}`} x1={p.x} y1={p.y} x2={q.x} y2={q.y}
            stroke="#B8C4DD" strokeWidth={0.55}
            strokeOpacity={solid ? 0.22 : 0.08}
            strokeDasharray={solid ? undefined : "1.5 5"} />
        );
      })}
      {/* 별 */}
      {pts.map((p, i) => {
        const isSel = selectedDate && p.date === selectedDate;
        const isToday = todayDate && p.date === todayDate;
        if (!p.filled) {
          return <circle key={i} cx={p.x} cy={p.y} r={1.25} fill={MOOD_EMPTY} opacity={0.28} />;
        }
        // 밝기 차이가 한눈에 들어와야 한다 — 색·크기·헤일로를 같은 레벨로 함께 키운다.
        // (전에는 크기 폭이 3.1~4.5 라 사실상 같은 크기였고, 헤일로는 레벨과 무관하게 고정이었다.)
        const r = 2.1 + (p.lvl - 1) * 0.68;
        const col = COL[p.lvl - 1];
        const alpha = MOOD_ALPHA[p.lvl - 1];
        const glow = MOOD_GLOW[p.lvl - 1];
        const starPath = `M ${p.x} ${p.y-r} L ${p.x+r*.28} ${p.y-r*.28} L ${p.x+r} ${p.y} L ${p.x+r*.28} ${p.y+r*.28} L ${p.x} ${p.y+r} L ${p.x-r*.28} ${p.y+r*.28} L ${p.x-r} ${p.y} L ${p.x-r*.28} ${p.y-r*.28} Z`;
        return (
          <g
            key={i}
            role={onSelect ? "button" : undefined}
            tabIndex={onSelect ? 0 : undefined}
            aria-label={`${dateLabel(p.date)}, 기분 ${MOOD_LABEL[p.lvl - 1]}`}
            onMouseEnter={() => setHovered(p)}
            onMouseLeave={() => setHovered(null)}
            onFocus={() => setHovered(p)}
            onBlur={() => setHovered(null)}
            onClick={() => onSelect?.(p)}
            onKeyDown={(e) => {
              if ((e.key === "Enter" || e.key === " ") && onSelect) {
                e.preventDefault();
                onSelect(p);
              }
            }}
            style={{ cursor: onSelect ? "pointer" : "default", outline: "none" }}
          >
            <circle cx={p.x} cy={p.y} r={r + (isSel ? 6 : 2.2 + p.lvl * 0.5)} fill={col} opacity={isSel ? 0.3 : glow} />
            <path d={starPath} fill={col} fillOpacity={alpha} stroke="#FFFFFF" strokeOpacity={isToday ? 0.9 : 0.22} strokeWidth={isToday ? 0.9 : 0.3} />
            {/* 별이 작아서 탭 영역 별도 */}
            <circle cx={p.x} cy={p.y} r={13} fill="transparent" />
          </g>
        );
      })}
      {/* 완성 시 각 별 옆에서 작은 반짝이가 빤짝빤짝 */}
      {complete &&
        pts
          .filter((p) => p.filled)
          .flatMap((p, i) => {
            const off = [
              [6, -5],
              [-5, 5],
            ];
            return off.map(([dx, dy], j) => (
              <Sparkle
                key={`spk${i}-${j}`}
                x={p.x + dx}
                y={p.y + dy}
                size={1.4 + j * 0.8}
                delay={(((i * 2 + j) * 0.26) % 1.8).toFixed(2)}
              />
            ));
          })}
    </svg>
    {hovered && (
      <div
        className="pointer-events-none absolute z-10 w-max max-w-[180px] -translate-x-1/2 -translate-y-[calc(100%+8px)] rounded-xl border border-line bg-[#0B1220]/95 px-2.5 py-2 text-left shadow-xl backdrop-blur"
        style={{
          left: `${Math.max(16, Math.min(84, (hovered.x / W) * 100))}%`,
          top: `${(hovered.y / H) * 100}%`,
        }}
        role="tooltip"
      >
        <div className="flex items-center gap-1.5 text-[10px] font-semibold text-ink">
          <span className="h-2 w-2 rounded-full" style={{ backgroundColor: COL[hovered.lvl - 1] }} />
          {dateLabel(hovered.date)} · {MOOD_LABEL[hovered.lvl - 1]}
        </div>
        <p className="mt-1 line-clamp-2 text-[10px] leading-[1.45] text-sub">{shortNote(hovered)}</p>
      </div>
    )}
    </div>
  );
}

/**
 * 별빛 범례 — 색 규칙을 사용자에게 한 번은 말해 준다.
 *
 * 규칙을 정해 놓고 화면 어디에도 안 적으면 사용자 입장에선 그냥 알록달록한 점이다.
 * 다섯 점을 실제 램프 순서대로 놓고(밝기가 오르는 게 눈에 보인다) 한 줄로 설명한다.
 * 문구는 moodColors.MOOD_RULE_LINE 하나를 공유한다 — 화면마다 다르게 적으면 규칙이 아니게 된다.
 */
export function MoodLegend({ className = "" }) {
  return (
    <div className={`flex flex-wrap items-center gap-x-2 gap-y-1 ${className}`}>
      <span className="flex items-center gap-[3px]" aria-hidden="true">
        {COL.map((c, i) => (
          // 별자리와 같은 규칙 — 좋은 날일수록 밝고 커진다(색·투명도·크기 셋 다).
          <span
            key={c}
            className="block rounded-full"
            style={{ background: c, opacity: MOOD_ALPHA[i], width: 3.5 + i * 1.4, height: 3.5 + i * 1.4 }}
          />
        ))}
      </span>
      <span className="text-[9px] leading-[1.5] text-mut">{MOOD_RULE_LINE}</span>
    </div>
  );
}

// 작은 4갈래 반짝이 별 — 완성 별자리에서 빤짝거린다.
function Sparkle({ x, y, size = 3, delay = "0" }) {
  const r = size,
    s = size * 0.32;
  const d = `M${x},${y - r} L${x + s},${y - s} L${x + r},${y} L${x + s},${y + s} L${x},${y + r} L${x - s},${y + s} L${x - r},${y} L${x - s},${y - s} Z`;
  return (
    <path d={d} fill="#F4F0FF">
      <animate attributeName="opacity" values="0;1;0.3;1;0" dur="1.8s" begin={`${delay}s`} repeatCount="indefinite" />
    </path>
  );
}
