// 백엔드가 이미 계산해 보내는데 화면이 한 번도 안 쓰던 값들을 모은 카드.
//
// 왜 따로 두는가 — 셋 다 "A와 B 중 무엇이 나은가"에 답하는 값이 아니다.
// 소득 증감률은 같은 축(만원)이 아니라 비율이라 A/B 막대에 섞으면 단위가 꼬이고,
// 건강·직업환경 실측은 선택과 무관한 배경 수치이며, 명목소득 경고는 수치가 아니라
// 위 표 전체를 어떻게 읽어야 하는지에 대한 단서다. 비교표에 밀어넣는 대신
// '이 숫자들을 어떻게 읽을지' 한 자리에 묶었다.

import { labelOf } from "../../data/prediction.js";

const COLORS = { A: "#B79BF5", B: "#F5C86B" };

function closestPoint(rows, targetYear) {
  if (!Array.isArray(rows) || !rows.length) return null;
  return [...rows]
    .filter((point) => Number.isFinite(Number(point?.year)) && point?.available !== false)
    .sort((left, right) => Math.abs(Number(left.year) - targetYear) - Math.abs(Number(right.year) - targetYear))[0] || null;
}

// 출처 문자열에 붙은 경고를 찾는다. 백엔드가 문장으로 주기 때문에 키가 따로 없다.
function nominalNotice(...sides) {
  const sources = sides
    .flatMap((side) => side?.income_series || [])
    .map((point) => String(point?.source || ""));
  return sources.some((text) => text.includes("명목"));
}

function growthOf(side, futureYears) {
  const point = closestPoint(side?.growth_potential, futureYears);
  if (point?.value == null) return null;
  const value = Number(point.value);
  if (!Number.isFinite(value)) return null;
  return { value, year: Number(point.year), sample: point.sample_n ?? null };
}

// 지표마다 관측 천장이 다르다. 소득(KLIPS)은 10년까지 있는데 만족도(YP 청년패널)는
// 패널이 4웨이브뿐이라 3년이 끝이다. 요청 시점이 천장을 넘으면 화면은 가장 가까운
// 연차 값으로 조용히 스냅하는데, 그걸 안 밝히면 3년 관측치가 '10년 뒤 만족도'로 읽힌다.
//
// 천장을 상수로 박지 않고 **응답에 실제로 담긴 연차**를 본다 — 패널이 늘거나
// 백엔드 horizon 이 바뀌면 이 안내도 저절로 따라간다.
//
// 그렇다고 만족도 때문에 5년·10년 선택을 막지는 않는다. 소득·재직기간은 그 시점까지
// 실측이 있어서, 한 지표가 없다고 함께 막으면 있는 데이터까지 못 보게 된다.
const HORIZON_SERIES = [
  { key: "trajectory", label: "월소득 중앙값", source: "KLIPS 종단" },
  { key: "wellbeing_trajectory", label: "삶의 만족", source: "YP 청년패널" },
];

function horizonGaps(a, b, futureYears) {
  return HORIZON_SERIES.map(({ key, label, source }) => {
    const years = [a, b]
      .flatMap((side) => side?.[key] || [])
      .map((point) => Number(point?.year))
      .filter(Number.isFinite);
    if (!years.length) return null;
    const observed = Math.max(...years);
    return observed < futureYears ? { key, label, source, observed } : null;
  }).filter(Boolean);
}

export default function ResultDataNotes({ a, b, futureYears = 3 }) {
  // 소득 궤적은 **선택이 아니라 프로필**로 계산된다. 그래서 관계·건강처럼 소득과
  // 상관없는 질문에도 값이 채워져 온다 — '연인과 대화하기 vs 거리 두기'에 소득
  // 증감 −1.9% 가 붙는 식이다. 백엔드는 그런 영역에 quantitative_ok=false 와
  // guard_note 를 보내 "이 질문엔 정량 예측이 없다"고 이미 말하고 있으므로,
  // 값이 있다는 이유로 그리지 않고 그 판단을 따른다.
  const quantitativeOk = [a, b].some((side) => side?.quantitative_ok !== false);
  const growth = { A: growthOf(a, futureYears), B: growthOf(b, futureYears) };
  const nominal = nominalNotice(a, b);
  const hasGrowth = quantitativeOk && (growth.A || growth.B);
  const gaps = quantitativeOk ? horizonGaps(a, b, futureYears) : [];
  // 쉬어가기는 '쉬는 동안 못 번 돈'이 어디에도 안 나온다. KLIPS 로 학습한 효과는
  // **복귀한 뒤의 임금**을 견주기 때문이다(공백 기간의 0원은 결과변수에 안 들어간다).
  // 그래서 화면만 보면 반년을 쉬었는데 1년차 소득이 남는 쪽보다 높게 보인다.
  // 숫자를 고치는 건 재학습이 필요한 일이라, 무엇이 빠졌는지를 밝힌다.
  const breakSide = [a, b].find((side) => side?.kind === "휴식");

  // 그릴 게 하나도 없으면 카드 자체를 내보내지 않는다. 여기에 렌더하지 않는
  // 값(건강 실측 등)을 조건에 남겨두면 제목만 있는 빈 카드가 뜬다.
  if (!hasGrowth && !gaps.length && !breakSide) return null;

  return (
    <section className="mt-4 overflow-hidden rounded-2xl border border-white/10 bg-[#0B1220]/85" aria-labelledby="data-notes-title">
      <div className="border-b border-white/10 px-4 py-3">
        <h2 id="data-notes-title" className="text-[13px] font-bold text-ink">숫자를 읽는 배경</h2>
        <p className="mt-0.5 text-[9px] text-mut">위 비교표의 수치가 어떤 조건에서 나온 값인지 함께 봅니다.</p>
      </div>

      {breakSide && (
        <div className="border-white/[.07] px-4 py-3.5 [&:not(:last-child)]:border-b">
          <h3 className="text-[11px] font-semibold text-sub">쉬는 동안의 소득은 이 비교에 없습니다</h3>
          <p className="mt-0.5 text-[9px] leading-4 text-mut">
            쉬어가기 수치는 <b className="font-semibold text-sub">복귀한 뒤의 임금</b>을 견준 값입니다(KLIPS 공백 스펠).
            쉬는 동안 못 번 소득은 결과변수에 들어가 있지 않아, 소득 줄에는 그 공백이 나타나지 않습니다.
            <b className="font-semibold text-sub"> 쉬는 기간의 생활비는 따로 계산해 보셔야 합니다.</b>
          </p>
        </div>
      )}

      {gaps.length > 0 && (
        <div className="border-white/[.07] px-4 py-3.5 [&:not(:last-child)]:border-b">
          <h3 className="text-[11px] font-semibold text-sub">{futureYears}년까지 관측되지 않은 지표</h3>
          <p className="mt-0.5 text-[9px] leading-4 text-mut">
            표본이 거기까지만 추적돼, 비교표에는 <b className="font-semibold text-sub">관측된 마지막 연차 값</b>이 그대로 표시됩니다.
            {futureYears}년 뒤로 늘려 잡은 값이 아닙니다.
          </p>
          <ul className="mt-2 grid gap-1.5 sm:grid-cols-2">
            {gaps.map((gap) => (
              <li key={gap.key} className="flex items-baseline justify-between gap-2 rounded-lg bg-[#F5C86B]/[.07] px-2.5 py-2">
                <span className="min-w-0">
                  <span className="block truncate text-[10px] text-sub">{gap.label}</span>
                  <span className="block text-[8px] text-mut">{gap.source}</span>
                </span>
                <strong className="shrink-0 text-[11px] font-bold tabular-nums text-[#F5C86B]">{gap.observed}년까지</strong>
              </li>
            ))}
          </ul>
        </div>
      )}

      {hasGrowth && (
        <div className="border-b border-white/[.07] px-4 py-3.5">
          <div className="flex items-baseline justify-between gap-2">
            <h3 className="text-[11px] font-semibold text-sub">지금 대비 소득 증감</h3>
            <span className="text-[8.5px] text-mut">{futureYears}년 뒤 기준</span>
          </div>
          <div className="mt-2 grid gap-2 sm:grid-cols-2">
            {["A", "B"].map((side) => {
              const item = growth[side];
              const choice = side === "A" ? a : b;
              return (
                <article key={side} className="rounded-xl border border-white/[.07] bg-white/[.025] px-3 py-2.5">
                  <div className="flex items-center gap-1.5">
                    <b className="text-[9px] font-black" style={{ color: COLORS[side] }}>{side}</b>
                    <span className="truncate text-[9.5px] text-mut">{labelOf(choice?.choice)}</span>
                  </div>
                  <div className="mt-1 flex items-baseline gap-1.5">
                    <strong className="text-[15px] tabular-nums text-ink">
                      {item ? `${item.value > 0 ? "+" : ""}${item.value.toLocaleString()}%` : "—"}
                    </strong>
                    {item?.sample != null && <span className="text-[8px] text-mut">n={item.sample.toLocaleString()}</span>}
                  </div>
                </article>
              );
            })}
          </div>
          {/* 이 값이 '실질 성장'으로 읽히면 안 된다 — 물가상승분이 들어 있다. */}
          {nominal && (
            <p className="mt-2 text-[8.5px] leading-4 text-[#F5C86B]">
              소득 수치는 <b className="font-semibold">명목</b>입니다 — 물가상승분이 포함돼 있어, 이 증감률이 곧 구매력 변화는 아닙니다.
            </p>
          )}
        </div>
      )}

      {/* 건강·직업환경 실측(KNHANES·KWCS)은 여기 두지 않는다 — '지표별 격차' 카드의
          '두 선택 공통 · 참고 기준'이 같은 값을 이미 다루고, 그쪽은 전체 평균 대비
          격차까지 그린다. 같은 숫자를 두 화면에서 다른 모양으로 보여주면 어느 쪽이
          맞는지 사용자가 판단해야 한다. */}
    </section>
  );
}
