import { useState } from "react";
import { FUTURE_YEAR_OPTIONS } from "../data/futureYears.js";

// 1~10년 전부를 알약 버튼으로 늘어놓으면 좁은 폭에서 두 줄로 꺾여 부산해
// 보였다. 자주 쓰는 값(1·3·5·10)만 기본 노출하고 나머지는 "더보기"로 펼친다.
// 지금 선택된 값이 기본 세트에 없어도(예: 확장해서 7년을 골랐다가 접은 경우)
// 사라지지 않도록 항상 표시 목록에 끼워 넣는다.
const QUICK_YEARS = [1, 3, 5, 10, 15];

export default function FutureYearPicker({
  years, onChange, label, note, ariaLabel = "미래 비교 시점", titleFor, className = "",
}) {
  const [expanded, setExpanded] = useState(false);
  const visible = expanded
    ? FUTURE_YEAR_OPTIONS
    : [...new Set([...QUICK_YEARS, years])].sort((x, y) => x - y);

  return (
    <div className={className}>
      <div data-tour="future-years" className="flex w-full items-start justify-between gap-2 sm:w-auto sm:justify-end" role="radiogroup" aria-label={ariaLabel}>
        {label && <span className="mt-1.5 shrink-0 text-[9px] font-semibold text-mut">{label}</span>}
        <div className="flex flex-wrap items-center justify-end gap-1 rounded-2xl border border-white/10 bg-black/20 p-1">
          {visible.map((y) => {
            const selected = years === y;
            return (
              <button
                key={y}
                type="button"
                role="radio"
                aria-checked={selected}
                title={titleFor ? titleFor(y) : `${y}년 후 비교`}
                onClick={() => onChange(y)}
                className={`tap !min-h-0 rounded-full px-2.5 py-1 text-[10px] font-bold transition-all duration-200 ${
                  selected ? "bg-violet-500/30 text-white shadow-[0_0_12px_rgba(139,108,207,.2)]" : "text-mut hover:bg-white/[.06] hover:text-sub"
                }`}
              >
                {y}년
              </button>
            );
          })}
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            aria-expanded={expanded}
            aria-label={expanded ? "년도 선택 접기" : "1~10년 전체 보기"}
            title={expanded ? "간단히 보기" : "1~10년 전체 보기"}
            className="tap !min-h-0 rounded-full px-2 py-1 text-[10px] font-bold text-mut hover:bg-white/[.06] hover:text-sub"
          >
            {expanded ? "접기" : "더보기"}
          </button>
        </div>
      </div>
      {note}
    </div>
  );
}
