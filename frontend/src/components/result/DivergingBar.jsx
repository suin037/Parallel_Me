// A/B 발산 막대 — 결과 화면이 두 선택을 나란히 놓을 때 쓰는 공통 문법.
//
// 원래 ResultQuickStats 안에만 있었는데, 같은 질문("A와 B 중 어느 쪽이 얼마나
// 더 큰가")을 지표별 격차·관측된 변화 카드가 각자 다른 그림(원형 게이지)으로
// 답하고 있었다. 한 화면에서 같은 질문에 세 가지 그림이 나오면 읽는 쪽이 매번
// 읽는 법을 새로 배워야 한다. 여기로 모아 세 카드가 같은 막대를 쓴다.

export const SIDE_COLORS = { A: "#B79BF5", B: "#F5C86B" };

// 축 바닥이 핵심이다. 0 부터 재면 320 vs 340 이 94% vs 100% 라 눈에는 같은
// 길이다 — 이 표에서 알고 싶은 건 "어느 쪽이 얼마나 더 나은가"인데 화면이
// 그 질문에 답하지 못한다. 그래서 **두 막대의 길이 차이가 트랙의 35% 밑으로
// 내려가면 딱 35% 가 되는 지점까지만 축을 잘라 올린다.** 필요한 만큼만 자르므로,
// 이미 충분히 벌어진 행(0 vs 10 같은)은 0 부터 그대로 그린다.
//
// 축을 자른 행은 막대 길이가 '값의 크기'가 아니라 '두 값의 비교'만 뜻하게 되므로
// 0선 자리에 절단 표시를 띄운다(DivergePoint). 정확한 값은 양 끝 숫자가,
// 정확한 차이는 옆 배지가 숫자로 말한다.
//
// 막대 길이 자체는 값의 크기(축을 자른 뒤의 상대 위치)를 담당하고, 색은
// 발산점(중심)에서 멀어질수록 진해지는 그라디언트로 그 위에 겹친다 — 두 값이
// 갈리는 지점을 다시 한번 강조하되, 격차 구간만 원색으로 확 밝히고 나머지는
// 죽이던 예전 방식(뒤진 쪽은 처음부터 끝까지 죽은 색)보다 경계가 부드럽다.
const MIN_LEAD = 0.35;

/**
 * 두 수 → 발산 막대 모양.
 * @returns {{A:{fill,negative}, B:{fill,negative}, clipped:boolean}|null}
 *          fill 은 0~1 (트랙 대비 비율), clipped 면 축을 잘랐다는 뜻.
 */
export function divergingShape(av, bv) {
  if (!Number.isFinite(av) || !Number.isFinite(bv)) return null;
  const lo = Math.min(av, bv);
  const hi = Math.max(av, bv);
  const shape = {
    A: { fill: 0, negative: av < 0 },
    B: { fill: 0, negative: bv < 0 },
    clipped: false,
  };
  if (hi === lo) {
    // 값이 완전히 같다 — 양쪽을 같은 길이로 두고 '거의 같음'은 배지가 말한다.
    shape.A.fill = shape.B.fill = hi === 0 ? 0 : 0.6;
    return shape;
  }
  // 음수가 섞이면 0 이 아니라 더 낮은 값이 자연 바닥이다.
  const natural = Math.min(0, lo);
  let floor = natural;
  if ((hi - lo) / (hi - natural) < MIN_LEAD) {
    // (lo - floor) / (hi - floor) = 1 - MIN_LEAD 을 floor 에 대해 푼 값.
    floor = (lo - (1 - MIN_LEAD) * hi) / MIN_LEAD;
    shape.clipped = true;
  }
  const span = hi - floor;
  shape.A.fill = (av - floor) / span;
  shape.B.fill = (bv - floor) / span;
  return shape;
}

/** 양쪽 막대가 갈라지는 자리. 축을 자른 행에서는 빗금 두 줄(축 절단 기호)로 바꾼다. */
export function DivergePoint({ clipped, height = "h-4" }) {
  if (!clipped) return <div className={`mx-auto w-px bg-white/30 ${height}`} aria-hidden="true" />;
  return (
    <div
      className={`flex items-center justify-center gap-[2px] ${height}`}
      title="두 값의 차이가 보이도록 축을 잘라 확대했습니다 — 막대 길이는 값의 크기가 아니라 두 값의 비교입니다"
      aria-label="축 절단(확대)"
    >
      <span className={`w-[2px] -skew-x-12 bg-white/30 ${height}`} />
      <span className={`w-[2px] -skew-x-12 bg-white/30 ${height}`} />
    </div>
  );
}

/**
 * 0선에서 바깥쪽으로 자라는 반쪽 막대. side 로 방향이 정해진다.
 * 색은 발산점(중심, 안쪽)에서 옅게 시작해 바깥쪽(막대 끝)으로 갈수록
 * 원색에 가까워지는 그라디언트다 — 값이 클수록 더 진하게 읽힌다.
 */
export function HalfBar({ side, shape, height = "h-3" }) {
  const isA = side === "A";
  const color = SIDE_COLORS[side];
  const fill = shape?.fill || 0;
  const soft = `${color}4D`; // 중심 쪽 — 약 30% 불투명도
  const background = shape?.negative
    ? `repeating-linear-gradient(135deg, ${color}66 0 3px, transparent 3px 6px)`
    : `linear-gradient(to ${isA ? "left" : "right"}, ${soft}, ${color})`;
  return (
    <div
      className={`flex items-center overflow-hidden bg-white/[.05] ${height} ${isA ? "justify-end rounded-l-full" : "justify-start rounded-r-full"}`}
      aria-hidden="true"
    >
      {fill > 0 && (
        <div
          className={`h-full transition-[width] duration-500 ${isA ? "rounded-l-full" : "rounded-r-full"}`}
          style={{ width: `${fill * 100}%`, background }}
        />
      )}
    </div>
  );
}

/**
 * A값 · 막대 · 0선 · 막대 · B값 을 한 줄로. 좌우 폭이 대칭 고정이라 0선이 항상
 * 정중앙에 오고, 여러 행을 세로로 쌓아도 발산점이 같은 축에 정렬된다.
 */
export function DivergingRow({ av, bv, format, valueWidth = "6.5rem", suffixA, suffixB }) {
  const shape = divergingShape(av, bv);
  return (
    <div
      className="grid items-center gap-1.5"
      style={{ gridTemplateColumns: `${valueWidth} minmax(0,1fr) 10px minmax(0,1fr) ${valueWidth}` }}
    >
      <SideValue side="A" value={av} format={format} suffix={suffixA} align="right" />
      <HalfBar side="A" shape={shape?.A} />
      <DivergePoint clipped={shape?.clipped} />
      <HalfBar side="B" shape={shape?.B} />
      <SideValue side="B" value={bv} format={format} suffix={suffixB} align="left" />
    </div>
  );
}

function SideValue({ side, value, format, suffix, align }) {
  return (
    <div
      className="flex items-baseline gap-1 whitespace-nowrap"
      style={{ justifyContent: align === "right" ? "flex-end" : "flex-start" }}
    >
      <span className="text-[9px] font-black" style={{ color: SIDE_COLORS[side] }}>{side}</span>
      <strong className="text-[11px] tabular-nums text-ink">
        {Number.isFinite(value) ? (format ? format(value) : value.toLocaleString()) : "—"}
      </strong>
      {suffix && <span className="text-[8px] text-mut">{suffix}</span>}
    </div>
  );
}
