import { createPortal } from "react-dom";

// 앱 프레임 안의 공통 오버레이 레이어.
// 페이지 컴포넌트의 높이나 스크롤 위치와 무관하게 헤더 아래~탭바 위를 채운다.
export default function AppOverlay({ children, className = "", onClick, aboveTabs = true }) {
  const host = typeof document !== "undefined" ? document.getElementById("app-shell") : null;
  if (!host) return null;
  const bounds = aboveTabs
    ? "top-14 bottom-[72px] lg:top-[72px] lg:bottom-[76px]"
    : "inset-0";
  return createPortal(
    <div className={`absolute left-0 right-0 ${bounds} ${className}`} onClick={onClick}>
      {children}
    </div>,
    host,
  );
}
