import { VALUE_CARDS, topAxes } from "../data/valueCards.js";

// 가치 우선순위 입력 (탭-투-랭크).
//   value    : 카드 id 배열(중요한 순). 이 배열이 그대로 /simulate 의 value_ranking.
//   onChange : 새 배열을 받는 콜백.
//   max      : 최대 선택 수(기본 8 = 전부).
// 온보딩(첫 1회)과 설정(재편집) 양쪽에서 재사용한다.
// 부분 순위 OK — 안 고른 카드는 backend(axis_weights)가 최하위로 처리한다.
export default function ValueRankingInput({ value = [], onChange, max = 8 }) {
  const rankOf = (id) => value.indexOf(id); // -1 = 미선택

  function toggle(id) {
    const i = rankOf(id);
    if (i === -1) {
      if (value.length >= max) return;
      onChange([...value, id]);
    } else {
      onChange(value.filter((x) => x !== id));
    }
  }

  const axes = topAxes(value, 2);

  return (
    <div>
      <p className="mb-2 text-xs text-sub">
        중요한 순서대로 눌러주세요{" "}
        <span className="text-mut">(3순위 이상)</span>
      </p>

      <div className="grid grid-cols-2 gap-2">
        {VALUE_CARDS.map((c) => {
          const i = rankOf(c.id);
          const on = i !== -1;
          return (
            <button
              key={c.id}
              type="button"
              onClick={() => toggle(c.id)}
              className={`tap relative rounded-xl border px-3 py-2.5 text-left transition-colors ${
                on ? "border-cyan bg-[#1D1730]" : "border-line bg-[#0E1424]"
              }`}
            >
              {on && (
                <span className="absolute right-2 top-2 flex h-5 w-5 items-center justify-center rounded-full bg-cyan text-[11px] font-bold text-[#0A0E1A]">
                  {i + 1}
                </span>
              )}
              <div className={`text-[13px] font-semibold ${on ? "text-cyan" : "text-ink"}`}>
                {c.emoji} {c.label}
              </div>
              <div className="mt-0.5 text-[10px] leading-snug text-mut">{c.desc}</div>
            </button>
          );
        })}
      </div>

      {value.length > 0 && (
        <p className="mt-2.5 text-[11px] text-sub">
          네 성향:{" "}
          <span className="font-semibold text-gold">
            {axes.length ? axes.join(" · ") + " 중심" : "—"}
          </span>
          <span className="text-mut"> · {value.length}개 선택</span>
        </p>
      )}
    </div>
  );
}
