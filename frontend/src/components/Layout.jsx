import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { ArrowLeft, Bookmark, BookOpen, HelpCircle, LockKeyhole, Orbit, Sparkles } from "lucide-react";
import TabBar from "./TabBar.jsx";
import UserGuide from "./UserGuide.jsx";
import Tour from "./Tour.jsx";
import GuideAdvice from "./GuideAdvice.jsx";
import { startTour, takeGuideAsk } from "../data/tour.js";
import ReminderBell from "./ReminderBell.jsx";
import ReminderToast from "./ReminderToast.jsx";
import { useResult } from "../data/ResultContext.jsx";
import storage from "../data/safeStorage.js";

// 탭바를 숨기는 경로 (랜딩·온보딩·로딩)
// /resume 은 다른 기기 링크로 처음 들어오는 자리다. 아직 이 기기엔 기록이 없으므로
// 탭으로 다른 화면에 가봐야 빈 화면만 보인다 — 불러오기 결정에만 집중시킨다.
// /personas 는 프로필을 고르기 전이라 탭으로 갈 곳이 없다 — 카드 선택에만 집중시킨다.
const NO_TABBAR = ["/", "/personas", "/onboarding", "/simulate", "/resume"];
// 프로필(설정) 아이콘을 숨기는 경로
const NO_PROFILE = ["/simulate", "/personas", "/onboarding", "/settings", "/resume"];
// PC 에서 넓게 쓰는 화면. /company 는 재무표·공시 목록이라 좁으면 읽기 나쁘다.
// (/checkin 은 오늘 하나를 적는 화면이라 일부러 좁게 둔다.)
// /simulate 는 useFullDesktop 인데 여기 빠져 있어 컨테이너가 450px(max-w-phone)로
// 잡혔고, 그 안에서 lg 2단 레이아웃이 겹쳤다.
const WIDE_DESKTOP = ["/home", "/input", "/result", "/my", "/archive", "/settings", "/company", "/simulate", "/personas"];
export default function Layout() {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const { hasSimulationResult } = useResult();
  const simulationTarget = pathname === "/result" ? "/input" : hasSimulationResult ? "/result" : "/input";
  const desktopTabs = [
    ["/my", "홈", Orbit],
    [simulationTarget, "시뮬레이션", Sparkles],
    ["/home", "일기", BookOpen],
    ["/archive", "보관함", Bookmark],
  ];

  const showTabBar = !NO_TABBAR.includes(pathname);
  const showProfile = !NO_PROFILE.includes(pathname);
  // 알람 종·토스트는 메인 화면(탭바 있는 곳)에서만 — 랜딩·온보딩·로딩엔 안 뜬다.
  // 비교 진행 중(isSimulationFlow)에는 종·프로필도 접는다.
  const showReminders = showTabBar;
  const useWideDesktop = WIDE_DESKTOP.includes(pathname);
  const isLanding = pathname === "/";
  const isDesktopWorkspace = ["/home", "/input", "/result", "/my", "/archive", "/settings"].includes(pathname);
  const isUniverseCanvas = pathname === "/my";
  const isOnboarding = pathname === "/onboarding";
  const isPersonas = pathname === "/personas";
  const isSimulationFlow = pathname === "/simulate";
  const useFullDesktop = isDesktopWorkspace || isOnboarding || isPersonas || pathname === "/simulate";
  const [guideOpen, setGuideOpen] = useState(() => {
    try { return storage.getItem("pm.guide.seen.v1") !== "1"; } catch { return true; }
  });
  const closeGuide = () => {
    try { storage.setItem("pm.guide.seen.v1", "1"); } catch { /* 저장 불가 환경 */ }
    setGuideOpen(false);
  };
  // 계정을 막 만들고 들어온 참이면 안내를 받을지 여기서 묻는다.
  // 온보딩이 남긴 표시를 집어 간다(한 번만).
  useEffect(() => {
    if (takeGuideAsk()) setGuideOpen(true);
  }, [pathname]);
  // 설정의 '안내 다시 보기' — 안내 첫 화면(소개)부터 다시 연다.
  useEffect(() => {
    const open = () => setGuideOpen(true);
    window.addEventListener("pm:guide-open", open);
    return () => window.removeEventListener("pm:guide-open", open);
  }, []);
  // /resume 은 링크로 곧장 들어오는 자리라 돌아갈 이전 화면이 없다.
  const showBack = !["/", "/my", "/resume"].includes(pathname);
  const goBack = () => window.history.length > 1 ? navigate(-1) : navigate("/my");

  return (
    <div
      className={`flex min-h-screen items-center justify-center bg-[#111827] p-0 ${
        // 바깥 여백도 같이 없앤다 — 프레임을 벗겨도 이 패딩이 남으면 화면 둘레에
        // 회색 띠가 생겨 여전히 '기기 안에 든 화면'처럼 보인다.
        isLanding || isSimulationFlow ? "sm:p-0 lg:block lg:p-0" : `sm:p-6 ${useFullDesktop ? "lg:block lg:p-0" : "lg:p-8"}`
      }`}
      style={{
        backgroundImage:
          "radial-gradient(circle at 50% 12%, rgba(73,112,171,.22), transparent 36%), linear-gradient(145deg, #172033 0%, #0D1422 48%, #182235 100%)",
      }}
    >
      <div id="app-shell"
        className={`relative flex h-screen w-full flex-col overflow-hidden bg-bg ${
          // 폰·태블릿에서는 기기 프레임처럼 보이게 두고,
          // PC(lg 이상)에서는 테두리·둥근 모서리·비율 제한을 전부 걷어 화면을 꽉 채운다.
          `max-w-phone sm:h-[900px] sm:max-h-[94vh] sm:rounded-[44px] sm:border sm:border-[#52627B]
               md:aspect-[16/10] md:h-auto md:max-h-[calc(100vh-48px)] md:max-w-[calc((100vh-48px)*1.6)] md:rounded-[32px]
               lg:max-w-[1240px] sm:ring-1 sm:ring-white/10
               sm:shadow-[0_30px_90px_rgba(0,0,0,.65),0_0_45px_rgba(65,118,190,.18)]`
        } ${useFullDesktop ? "lg:aspect-auto lg:h-auto lg:min-h-screen lg:max-h-none lg:max-w-none lg:overflow-visible lg:rounded-none lg:border-0 lg:ring-0 lg:shadow-none" : ""} ${
          // 랜딩과 시뮬 로딩은 **모든 구간에서** 기기 프레임을 벗는다.
          // useFullDesktop 은 lg(1024px) 이상에서만 프레임을 걷어서, 창이 그보다
          // 좁으면 md 의 16:10 비율·둥근 모서리가 그대로 남아 태블릿처럼 보였다.
          // 이 두 화면은 전체 화면을 쓰는 연출이라 중간 구간에도 테두리가 없어야 한다.
          isLanding || isSimulationFlow
            ? "sm:h-screen sm:max-h-none sm:max-w-none sm:rounded-none sm:border-0 sm:ring-0 sm:shadow-none md:aspect-auto md:h-screen md:max-h-none md:max-w-none md:rounded-none lg:max-w-none"
            : ""
        }`}
        style={{ backgroundImage: "radial-gradient(circle at 85% 8%, rgba(47,111,232,.12), transparent 32%), linear-gradient(180deg, #0B1423 0%, #08101D 100%)" }}
      >
        {/* 서비스 헤더 */}
        {!isLanding && <header className={`z-20 flex h-14 shrink-0 items-center justify-between border-b border-transparent px-5 lg:h-[76px] lg:border-line/70 lg:px-10 xl:px-14 ${useFullDesktop ? "lg:sticky lg:top-0 lg:bg-[#091321]/90 lg:backdrop-blur-xl" : ""}`}>
          <div className="flex items-center gap-2">
            {showBack && !isSimulationFlow && <button type="button" onClick={goBack} aria-label="이전 화면" className="tap flex h-10 w-10 items-center justify-center rounded-full bg-white/[.05] text-sub lg:hidden"><ArrowLeft size={19}/></button>}
          <button disabled={isSimulationFlow} onClick={() => navigate("/my")} className={`${showBack && !isSimulationFlow ? "hidden lg:flex" : "flex"} items-center gap-2 text-[17px] font-bold tracking-[-.035em] text-ink disabled:cursor-default lg:text-[20px]`}>
            <Sparkles size={18} className="hidden text-violet-400 lg:block" /> Parallel Me
          </button>
          </div>
          {/* 안내 5단계는 '네 곳을 오갑니다' — PC 는 이 네비, 폰은 TabBar 가 그 자리다.
              둘 다 같은 키를 달고, Tour 가 그중 실제로 보이는 쪽을 고른다. */}
          {isDesktopWorkspace && <nav data-tour="tabbar" className="absolute left-1/2 hidden h-full -translate-x-1/2 items-stretch gap-10 lg:flex xl:gap-14">
            {isSimulationFlow
              ? <div className="flex items-center gap-2 text-[12px] font-semibold text-violet-300"><LockKeyhole size={15}/> 결과를 저장한 뒤 나갈 수 있어요</div>
              : desktopTabs.map(([to,label,Icon])=><NavLink key={to} to={to} className={({isActive})=>`relative flex min-w-[84px] items-center justify-center gap-2 px-2 text-[14px] transition-colors after:absolute after:inset-x-0 after:bottom-0 after:h-0.5 after:bg-violet-400 ${isActive?"font-semibold text-violet-300 after:opacity-100":"text-sub hover:text-ink after:opacity-0"}`}><Icon size={15}/>{label}</NavLink>)}
          </nav>}
          <div className="flex items-center gap-3">
            {showReminders && !isSimulationFlow && <ReminderBell />}
            {showProfile && !isSimulationFlow && (
              <button
                onClick={() => navigate("/settings")}
                data-tour="settings"
                aria-label="프로필 · 설정"
                className="tap flex h-10 w-10 items-center justify-center rounded-full border border-violet-400/25 bg-violet-500/10 text-violet-400 transition-colors hover:bg-violet-500/15 lg:w-auto lg:gap-2 lg:px-3"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                  <circle cx="12" cy="8" r="3.2" />
                  <path d="M5 20c0-3.3 3.1-5.5 7-5.5s7 2.2 7 5.5" strokeLinecap="round" />
                </svg>
                <span className="hidden text-[12px] font-semibold text-sub lg:inline">탐험가님</span>
              </button>
            )}
          </div>
        </header>}

        {/* 화면 본문 (스크롤)
            key={pathname} 로 이미 화면마다 새로 마운트된다. 거기에 animate-fade 를
            얹어 부드럽게 올라오게 한다 — 안내 영상에서 화면이 툭툭 바뀌면 그 장면이
            그대로 남는다. 랜딩은 자체 인트로가 있어 건드리지 않는다. */}
        <main
          key={pathname}
          className={`no-scrollbar relative z-10 flex-1 ${isLanding ? "" : "animate-fade"} ${isLanding ? "overflow-hidden p-0 [&>*]:h-full [&>*]:w-full [&>*]:max-w-none" : `overflow-y-auto px-5 pb-7 pt-1 lg:px-9 lg:pb-8 lg:pt-8 [&>*]:mx-auto [&>*]:w-full ${useFullDesktop ? "lg:overflow-visible xl:px-14" : ""} ${isUniverseCanvas ? "lg:!overflow-hidden lg:!p-0" : ""}`} ${
            isLanding
              ? ""
              : isUniverseCanvas
                ? "[&>*]:max-w-none"
                : isOnboarding
                  ? "[&>*]:max-w-[1280px]"
                  : isDesktopWorkspace
                    ? "[&>*]:max-w-[1440px]"
                    // PC 에서는 프레임과 함께 본문도 넓힌다 — 배치는 그대로 두고 폭만 늘린다.
                    : useWideDesktop
                      ? "[&>*]:max-w-[1120px] xl:[&>*]:max-w-[1320px] 2xl:[&>*]:max-w-[1500px]"
                      : "[&>*]:max-w-phone"
          }`}
        >
          <Outlet />
        </main>

        {showTabBar && <TabBar />}

        {/* 오버레이(알람 패널·꾸미기 상점 등) 포탈 루트 — 프레임 전체를 덮는다 */}
        <div id="pm-overlay-root" />

        {/* 하루 한 번 '오늘의 한 걸음' 토스트 (포탈로 상단에 렌더) */}
        {showReminders && <ReminderToast />}

        {isLanding && <button type="button" onClick={() => setGuideOpen(true)} className="tap absolute right-5 top-5 z-30 flex items-center gap-1.5 rounded-full border border-white/15 bg-black/20 px-3 py-2 text-[11px] font-semibold text-white/80 backdrop-blur-md"><HelpCircle size={15}/> 사용 방법</button>}
        {/* 랜딩에서는 소개만 한다 — 아직 계정이 없어 짚어 줄 화면이 없다.
            안내를 받을지는 계정을 만들고 들어온 뒤(그리고 이후 물음표에서) 고른다. */}
        <UserGuide open={guideOpen} onClose={closeGuide} onStartTour={isLanding ? undefined : startTour} />
        {/* 안내는 화면을 넘나들며 이어진다 — 화면 안에 두면 라우트가 바뀔 때 끊긴다. */}
        <Tour />
        {/* 켜 둔 사람에게만 따라다니는 화면별 조언. 랜딩엔 설명할 화면이 없다. */}
        {!isLanding && <GuideAdvice />}
      </div>
    </div>
  );
}
