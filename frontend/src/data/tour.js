// ─────────────────────────────────────────────────────────────
// 첫 사용 안내 — 화면의 실제 버튼을 하나씩 짚고, 다음 화면으로 넘어가며 이어진다.
//
// 글로 된 도움말은 안 읽는다. 그래서 화면을 어둡게 덮고 그 버튼만 뚫어 보여준 뒤,
// 무엇을 하는 곳인지 한 줄로 말한다. 다음을 누르면 그 기능이 있는 화면으로 실제로
// 데려간다 — 설명만 듣는 것과 한 번 가 보는 것은 다르다.
//
// UserGuide(모달)와 역할이 다르다. 모달은 "이 서비스가 뭔지"를 한 장으로 말하고,
// 여기는 "그래서 어디를 누르면 되는지"를 화면에서 직접 짚는다. 모달의 두 버튼이
// 이 안내를 켜고 끄는 자리다.
//
// 대상은 data-tour="키" 로 찾는다. 화면에 없는 단계는 조용히 건너뛴다 —
// 빈 스포트라이트가 뜨면 안내가 아니라 고장으로 보인다.
//
// 저장은 safeStorage 로 한다. 사파리·iframe 에서는 localStorage 가 막히는데,
// 거기서 예외가 나면 안내가 아니라 앱이 통째로 죽는다.
// ─────────────────────────────────────────────────────────────
import storage from "./safeStorage.js";

const KEY = "pm.tour.v1";
// "안내를 받겠다"는 의사. 본 것(KEY)과 따로 둔다 —
// 랜딩에서 고르면 아직 계정이 없어 바로 시작할 수 없고, 온보딩을 마치고 앱에
// 들어온 뒤에 시작해야 한다. 그 사이를 이 표시가 건넌다.
const WANT = "pm.tour.want.v1";

/** 안내가 의미 있는 화면인가 — 랜딩·페르소나·온보딩·시뮬 진행 중엔 짚을 대상이 없다. */
const NOT_YET = ["/", "/personas", "/onboarding", "/simulate", "/resume"];
export function canRunTourAt(pathname) {
  return !NOT_YET.includes(pathname);
}

// 순서는 앱의 탭 순서를 따른다 — 홈(우주) · 시뮬레이션 · 일기 · 보관함.
// 사용자가 나중에 탭바를 볼 때 이미 지나온 길이라 지도가 머리에 남는다.
export const TOUR_STEPS = [
  {
    id: "universe-map", route: "/my",
    title: "여기가 나의 우주예요",
    body: "남긴 하루가 별이 되고, 삶의 영역마다 행성으로 모여요. 행성을 누르면 그 영역의 기록과 흐름이 열려요.",
  },
  {
    id: "simulate-start", route: "/input",
    title: "두 갈래를 나란히 놓아요",
    body: "고민 중인 선택 두 개를 적으면, 비슷한 사람들의 관측 데이터와 함께 각각의 미래를 비교해 보여줘요.",
  },
  {
    id: "diary", route: "/home",
    title: "오늘 하루를 남기는 곳",
    body: "기분만 눌러도 되고, 마스코트와 대화하듯 적어도 돼요. 이 기록이 비교 주제와 해석의 재료가 돼요.",
  },
  {
    id: "archive-list", route: "/archive",
    title: "고른 미래를 모아두는 곳",
    body: "비교 결과를 항해일지에 저장하고, 나중에 그래서 어떻게 됐는지 회고를 이어 적어요.",
  },
  {
    id: "tabbar", route: "/my",
    title: "네 곳을 오갑니다",
    body: "홈 · 시뮬레이션 · 일기 · 보관함. 언제든 여기로 돌아올 수 있어요.",
  },
  {
    id: "settings", route: "/my",
    title: "안내는 언제든 다시",
    body: "설정 → 알림 · 가이드에서 이 안내를 처음부터 다시 볼 수 있어요. 이제 시작해볼까요?",
  },
];

export function tourSeen() {
  return storage.getItem(KEY) === "1";
}

export function markTourSeen() {
  storage.setItem(KEY, "1");
}

/** 다시 볼 수 있게 표시만 지운다(바로 띄우지는 않는다). */
export function resetTour() {
  storage.removeItem(KEY);
}

// 계정을 만들고 앱에 처음 들어서는 순간 안내를 받을지 묻는다는 표시.
// 온보딩이 남기고 Layout 이 집어 간다.
const ASK = "pm.guide.ask.v1";

export function askGuideOnEnter() {
  storage.setItem(ASK, "1");
}

/** 안내 첫 화면(소개 모달)을 다시 연다 — 설정의 '안내 다시 보기'. */
export function openGuide() {
  if (typeof window !== "undefined") window.dispatchEvent(new Event("pm:guide-open"));
}

/** 한 번만 묻는다 — 읽으면서 표시를 지운다. */
export function takeGuideAsk() {
  if (storage.getItem(ASK) !== "1") return false;
  storage.removeItem(ASK);
  return true;
}

export function wantsTour() {
  return storage.getItem(WANT) === "1";
}

/** 안내가 끝났거나 건너뛰었다 — 다시 고르기 전엔 뜨지 않는다. */
export function clearWantTour() {
  storage.removeItem(WANT);
}

/**
 * 안내를 받겠다고 고른 순간 부른다("안내받기" 버튼, 설정의 "다시 보기").
 *
 * 자동으로는 절대 시작하지 않는다. 첫 진입이라고 무조건 띄우면 이미 계정이 있는
 * 사람이 다른 기기에서 들어와도 뜬다.
 *
 * 지금 앱 안이면 바로 시작하고(이벤트), 랜딩이면 표시만 남긴다 — 온보딩을 마치고
 * 앱에 들어오는 순간 Tour 가 그 표시를 보고 시작한다.
 * (화면 전환 직후엔 대상이 아직 안 붙어 있어 한 박자 늦춘다.)
 */
export function startTour() {
  resetTour();
  storage.setItem(WANT, "1");
  if (typeof window !== "undefined") {
    setTimeout(() => window.dispatchEvent(new Event("pm:tour-start")), 400);
  }
}
