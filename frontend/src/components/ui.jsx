// 화면 전반에서 재사용하는 작은 프리미티브들.

export function Eyebrow({ children }) {
  return (
    <div className="mb-2 mt-1 text-[12px] font-semibold text-mut">{children}</div>
  );
}

export function Card({ children, highlight = false, className = "" }) {
  return (
    <div
      className={`my-2.5 rounded-[18px] p-4 ${
        highlight ? "bg-card2" : "bg-card"
      } ${className}`}
    >
      {children}
    </div>
  );
}

// 수치 옆 표본 수 표시 — 데이터 정직성 규칙: 항상 "(n명)"을 붙인다.
export function Sample({ n }) {
  return <span className="text-sub">({n}명)</span>;
}

export function Row({ label, children }) {
  return (
    <div className="mt-2 flex items-center justify-between gap-4 text-[13px] text-sub">
      <span>{label}</span>
      <span className="text-ink">{children}</span>
    </div>
  );
}

export function Caption({ children, className = "" }) {
  return <p className={`mt-1.5 text-[11px] leading-[1.5] text-mut ${className}`}>{children}</p>;
}

// 하단 출처·표본·관찰기간 고지 — 결과/유사 화면에 항상.
export function SourceFootnote({ meta }) {
  return (
    <div className="mt-3.5 text-center text-[10px] leading-relaxed text-mut">
      {meta.source}
      <br />
      소득 궤적 관찰 {meta.observe_years_income}년 · 만족도 {meta.observe_years_wellbeing}년 · 값은
      중앙값이며 표본 수를 함께 표시합니다.
    </div>
  );
}

// 큰 CTA 버튼
export function Button({ children, onClick, variant = "primary", type = "button", className = "" }) {
  const base =
    "tap block w-full rounded-2xl px-4 py-3 text-[15px] font-semibold transition-all active:scale-[.98]";
  const styles =
    variant === "ghost"
      ? "bg-card font-semibold text-sub hover:bg-card2"
      : "border border-[#8B6CCF] bg-[#8B6CCF] text-white shadow-[0_10px_28px_rgba(77,54,126,.34)] hover:brightness-110";
  return (
    <button type={type} onClick={onClick} className={`${base} ${styles} ${className}`}>
      {children}
    </button>
  );
}
