import { useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";
import {
  pendingReminders,
  completeReminder,
  remindersEnabled,
  setRemindersEnabled,
} from "../data/reminders.js";

// 헤더 종 아이콘 + 미완료 배지. 누르면 '결정한 미래'를 향한 오늘 할 일 패널이 열린다.
// 문구는 로컬 큐레이션(actionsFor) 그대로 — API·네트워크 0, iframe 안에서도 안전.
function BellIcon({ size = 18 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.7 21a2 2 0 0 1-3.4 0" />
    </svg>
  );
}

export default function ReminderBell() {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [tick, setTick] = useState(0);
  const [enabled, setEnabled] = useState(remindersEnabled);

  const items = useMemo(
    () => (enabled ? pendingReminders() : []),
    [open, tick, enabled],
  );
  const count = items.length;

  function done(item) {
    completeReminder(item.universeId, item.actionText);
    setTick((t) => t + 1);
  }
  function toggle() {
    const next = !enabled;
    setRemindersEnabled(next);
    setEnabled(next);
    setTick((t) => t + 1);
  }
  function goArchive() {
    setOpen(false);
    navigate("/archive");
  }

  const overlayRoot = typeof document !== "undefined" ? document.getElementById("pm-overlay-root") : null;

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        data-tour="reminder-bell"
        aria-label={`알람${count ? ` ${count}개` : ""}`}
        className="tap relative flex h-10 w-10 items-center justify-center rounded-full text-mut transition-colors hover:bg-white/[.05]"
      >
        <BellIcon />
        {count > 0 && (
          <span className="absolute right-1 top-1 flex h-[18px] min-w-[18px] items-center justify-center rounded-full border border-bg bg-cyan px-1 text-[10px] font-bold leading-none text-white">
            {count > 9 ? "9+" : count}
          </span>
        )}
      </button>

      {open && overlayRoot &&
        createPortal(
          // PC 전체화면 모드에서는 프레임이 화면보다 길어진다. absolute 로 두면 패널이
          // 문서 맨 위에 박혀 스크롤 아래에서는 안 보인다 → 상점(PetShop)과 같이 fixed.
          <div className="fixed inset-0 z-[120]">
            {/* 배경 */}
            <button
              aria-label="닫기"
              onClick={() => setOpen(false)}
              className="absolute inset-0 bg-black/55 animate-backdrop-in"
            />
            {/* 패널 (상단에서 슬라이드) */}
            <div className="absolute inset-x-0 top-0 mx-auto flex max-h-full w-full max-w-phone flex-col animate-fade">
              <div className="mx-3 mt-3 flex max-h-[80vh] flex-col overflow-hidden rounded-[22px] border border-line bg-card shadow-[0_20px_60px_rgba(0,0,0,.5)]">
                {/* 헤더 */}
                <div className="flex items-center justify-between border-b border-line px-4 py-3">
                  <div className="flex items-center gap-2">
                    <span className="text-cyan"><BellIcon size={16} /></span>
                    <span className="text-[14px] font-bold text-ink">내 미래를 향한 알람</span>
                  </div>
                  <button onClick={() => setOpen(false)} aria-label="닫기" className="tap text-[13px] text-mut">
                    닫기
                  </button>
                </div>

                {/* 본문 */}
                <div className="no-scrollbar flex-1 overflow-y-auto px-3 py-3">
                  {!enabled ? (
                    <p className="px-1 py-6 text-center text-[12px] leading-relaxed text-mut">
                      알람이 꺼져 있어요.<br />아래에서 다시 켜면 결정한 미래를 향한 할 일을 알려드려요.
                    </p>
                  ) : count === 0 ? (
                    <div className="px-1 py-6 text-center">
                      <p className="text-[12px] leading-relaxed text-mut">
                        지금은 알려드릴 게 없어요.<br />
                        보관함에서 시나리오를 저장하고 A/B 중 <b className="text-sub">마음이 기운 미래</b>를 고르면,<br />
                        그 미래를 향한 오늘 할 일이 여기 알람으로 떠요.
                      </p>
                      <button
                        onClick={goArchive}
                        className="tap mt-3 rounded-full border border-line px-3 py-1.5 text-[11px] text-cyan"
                      >
                        보관함 열기
                      </button>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {items.map((item, i) => (
                        <div key={`${item.universeId}:${item.actionText}:${i}`} className="rounded-[16px] border border-line bg-[#0E1424] p-3">
                          <div className="mb-1.5 flex items-center gap-1.5">
                            <span className="rounded-full border border-cyan/50 bg-[#12203a] px-2 py-0.5 text-[10px] font-semibold text-cyan">
                              🧭 {item.choice}
                            </span>
                            <span className="truncate text-[10px] text-mut">{item.title}</span>
                          </div>
                          <p className="text-[13px] font-semibold leading-relaxed text-ink">{item.actionText}</p>
                          {item.purpose && (
                            <p className="mt-1 text-[11px] leading-relaxed text-sub">· {item.purpose}</p>
                          )}
                          <div className="mt-2.5 flex gap-2">
                            <button
                              onClick={() => done(item)}
                              className="tap rounded-lg bg-cyan px-3 py-1 text-[11px] font-bold text-white"
                            >
                              ✓ 했어요
                            </button>
                            <button
                              onClick={goArchive}
                              className="tap rounded-lg border border-line px-3 py-1 text-[11px] text-sub"
                            >
                              보관함에서 보기
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* 푸터 — 알람 켜기/끄기 */}
                <div className="flex items-center justify-between border-t border-line px-4 py-2.5">
                  <span className="text-[11px] text-mut">하루 한 번, 앱을 열면 알려드려요</span>
                  <button
                    onClick={toggle}
                    className={`tap rounded-full px-3 py-1 text-[11px] font-semibold ${
                      enabled ? "border border-line text-sub" : "bg-cyan text-white"
                    }`}
                  >
                    {enabled ? "알람 끄기" : "알람 켜기"}
                  </button>
                </div>
              </div>
            </div>
          </div>,
          overlayRoot,
        )}
    </>
  );
}
