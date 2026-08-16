import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";
import { shouldAutoShowToday, markAutoShown, todaysReminder } from "../data/reminders.js";

// 하루 한 번 자동 토스트 — 그날 첫 접속 시 '오늘의 한 걸음' 1개를 상단에 띄운다.
// markAutoShown() 으로 그날 다시는 안 뜨게 하고, 12초 뒤/닫기로 사라진다. (Type A, iframe 안전)
export default function ReminderToast() {
  const navigate = useNavigate();
  const [item, setItem] = useState(null);

  useEffect(() => {
    if (shouldAutoShowToday()) {
      const r = todaysReminder();
      if (r) {
        setItem(r);
        markAutoShown();
      }
    }
  }, []);

  useEffect(() => {
    if (!item) return undefined;
    const t = setTimeout(() => setItem(null), 12000);
    return () => clearTimeout(t);
  }, [item]);

  if (!item) return null;
  const root = typeof document !== "undefined" ? document.getElementById("pm-overlay-root") : null;
  if (!root) return null;

  return createPortal(
    // PC 전체화면 모드에서도 화면 위쪽에 보이도록 fixed (프레임이 뷰포트보다 길어진다).
    <div className="pointer-events-none fixed inset-x-0 top-0 z-[110] mx-auto w-full max-w-phone animate-fade">
      <div className="pointer-events-auto mx-3 mt-3 flex items-start gap-3 rounded-[18px] border border-cyan/40 bg-[#12203a] p-3.5 shadow-[0_16px_44px_rgba(0,0,0,.45)]">
        <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-cyan/15 text-cyan">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
            <path d="M13.7 21a2 2 0 0 1-3.4 0" />
          </svg>
        </span>
        <div className="min-w-0 flex-1">
          <div className="mb-0.5 flex items-center gap-1.5">
            <span className="text-[11px] font-bold text-cyan">🌱 오늘의 한 걸음</span>
            <span className="truncate text-[10px] text-mut">「{item.choice}」을(를) 향해</span>
          </div>
          <p className="text-[12.5px] font-semibold leading-relaxed text-ink">{item.actionText}</p>
          <div className="mt-2 flex gap-2">
            <button
              onClick={() => {
                setItem(null);
                navigate("/archive");
              }}
              className="tap rounded-lg bg-cyan px-3 py-1 text-[11px] font-bold text-white"
            >
              보러 가기
            </button>
            <button
              onClick={() => setItem(null)}
              className="tap rounded-lg border border-line px-3 py-1 text-[11px] text-sub"
            >
              나중에
            </button>
          </div>
        </div>
        <button onClick={() => setItem(null)} aria-label="닫기" className="tap -mr-1 -mt-1 shrink-0 text-mut">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <path d="M18 6 6 18M6 6l12 12" />
          </svg>
        </button>
      </div>
    </div>,
    root,
  );
}
