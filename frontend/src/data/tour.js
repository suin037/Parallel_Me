// ─────────────────────────────────────────────────────────────
// 사용 안내 — 마스코트가 화면을 하나씩 짚으며 기능을 전부 해설한다.
//
// 글로 된 도움말은 안 읽는다. 그래서 화면을 어둡게 덮고 그 자리만 뚫어 보여준 뒤,
// 그 화면을 맡은 마스코트가 무엇을 하는 곳인지 말한다. 다음을 누르면 그 기능이
// 있는 화면으로 실제로 데려간다 — 설명만 듣는 것과 한 번 가 보는 것은 다르다.
//
// 넘기는 건 손이 기본이고, 말풍선의 '자동' 을 켜면 스스로 넘어간다.
//
// 챕터(chapter)로 묶는다 — "3 / 20" 만으로는 지금 어디쯤인지 알 수 없다.
// 말풍선 머리에 챕터 이름을 띄운다.
//
// 누가 말하는가 — result.js 의 MASCOTS 역할 그대로다.
//   · 코스모(행성 탐험가) 데이터와 결과를 분석한다 → 나의 우주 · 행성 · 결과 · 기업분석
//   · 루미(별빛 가이드)   기록과 별자리를 돌본다   → 일기 · 별자리 · 보관함 · 설정
//   · 노바(유성 가이드)   기회와 변화를 전한다     → 시뮬레이션
//
// 대상은 data-tour="키" 로 찾는다. 그 화면에 없는 단계(결과가 아직 없을 때의
// 결과 화면, 관계 선택지에서만 뜨는 대화 담기 등)는 조용히 건너뛴다 —
// 빈 스포트라이트는 안내가 아니라 고장으로 보인다.
//
// route 에는 쿼리를 붙일 수 있다("/settings?section=security"). 설정은 칸마다
// 다른 화면을 그리는데, 쿼리 없이는 그 칸을 열 방법이 없어 절반을 못 보여준다.
//
// 시뮬레이션 중간부터 결과까지는 shot(캡쳐본)으로 설명한다. 실제로 돌리면 비교 API
// 를 태우게 되는데, 안내를 한 번 볼 때마다 그걸 부를 이유가 없다 — 느리고, 결과가
// 매번 달라져 영상도 매번 달라진다. 그림은 frontend/public/tour/ 에 두고, 파일이
// 없으면 그 단계는 조용히 건너뛴다(깨진 이미지가 녹화되지 않게).
//
// 저장은 safeStorage — 사파리·iframe 에서 localStorage 가 막히면 안내가 아니라
// 앱이 통째로 죽는다.
// ─────────────────────────────────────────────────────────────
import storage from "./safeStorage.js";

const KEY = "pm.tour.v1";
const WANT = "pm.tour.want.v1";

/** 안내가 의미 있는 화면인가 — 랜딩·페르소나 고르기 중엔 짚을 대상이 없다. */
const NOT_YET = ["/", "/personas", "/onboarding", "/resume"];
export function canRunTourAt(pathname) {
  return !NOT_YET.includes(pathname);
}

/**
 * 실사용 안내 — 20컷.
 *
 * 구성은 앱을 쓰는 순서 그대로다.
 *   우주 3 (전체 · 행성 세부 · 별자리)
 *   일기 4 (챗봇 · 체크인과 돌보미 · 캘린더 · 오늘의 추천과 노래)
 *   시뮬레이션·결과 10 (소개 영상에서 쓴 장면과 문구를 그대로 쓴다)
 *   보관함 2 · 마무리 1
 *
 * core: true 는 '핵심만' 코스(키보드 C)에 들어가는 단계다.
 */
export const TOUR_STEPS = [
  // ── 1장 · 나의 우주 ───────────────────────────────────────
  {
    // 화면 전체가 그림인 곳이라 조명으로 자르지 않는다(full).
    id: "universe-map", core: true, full: true, route: "/my", act: "close-panels",
    mascot: "cosmo", chapter: "나의 우주",
    title: "여기가 나의 우주예요",
    body: "남긴 하루가 별이 되고, 삶의 영역마다 행성으로 모여요.",
    lines: [
      "행성 하나가 삶의 한 영역이에요 — 일 · 관계 · 건강 · 배움처럼요.",
      "행성 주위를 도는 별 묶음이 별자리예요. 한 주에 남긴 기록이 모인 거예요.",
      "크기와 밝기는 쌓인 기록의 양이지, 잘하고 못하고가 아니에요.",
      "드래그하면 돌아가고, 휠이나 두 손가락으로 확대·축소돼요.",
    ],
  },
  {
    // 말로만 "누르면 열려요" 하지 않고 실제로 연다(act) — 그 위에서 짚는다.
    id: "planet-panel", core: true, route: "/my", act: "open-planet",
    mascot: "cosmo", chapter: "나의 우주",
    title: "행성을 누르면 이렇게 열려요",
    body: "기록이 가장 많은 행성을 대신 열어봤어요. 그 영역만 모아 정리한 화면이에요.",
    lines: [
      "위쪽 숫자 세 칸 — 이 영역의 점수, 분류된 기록 수, 최근이 그 이전보다 나아졌는지.",
      "최근 흐름 · 영향 요인 — 기분 그래프와, 무엇이 이 영역을 흔드는지.",
      "좋았던 날 · 무거웠던 날은 요약이 아니라 그날 쓴 문장 그대로예요.",
      "맨 아래 '분석 기준 보기'에 이 숫자를 어떻게 냈는지 적혀 있어요. 안 쓴 날은 0점으로 치지 않아요.",
      "'미래 보기'를 누르면 이 영역을 중심으로 두 갈래 비교가 시작돼요.",
    ],
  },
  {
    id: "universe-map", core: true, full: true, route: "/my", act: "close-panels",
    mascot: "cosmo", chapter: "나의 우주",
    title: "별자리와 마름모도 눌러볼 수 있어요",
    body: "같은 지도 위에 있지만 여는 화면이 서로 달라요.",
    lines: [
      "별자리를 누르면 그 주에 무엇을 적었는지 날짜별로 펼쳐지고, 별 하나를 고르면 그날 일기가 열려요.",
      "별 개수 · 평균 기분 · 진폭도 함께 나와요. 진폭이 낮으면 잔잔했던 한 주예요.",
      "떠 있는 마름모는 저장해 둔 시뮬레이션 결과예요.",
    ],
  },

  // ── 2장 · 일기 ────────────────────────────────────────────
  {
    id: "diary-guides", core: true, route: "/home", mascot: "lumi", chapter: "일기",
    title: "쓸 말이 없으면 저희와 대화하세요",
    body: "카드를 밀어 주제를 고르면 그 주제로 물어봐요. 답만 해도 그대로 기록이 돼요.",
    lines: [
      "오늘의 일상 · 몸과 마음은 루미가, 고민과 선택은 코스모가 물어봐요.",
      "고민과 선택에서 나온 두 갈래는 시뮬레이션 화면에 그대로 올라가요.",
      "대화는 '기록 저장'을 누르면 오늘 일기에 함께 담겨요.",
    ],
  },
  {
    id: "diary-checkin", core: true, route: "/home", mascot: "lumi", chapter: "일기",
    title: "30초 체크인 — 글 없이도 하루가 남아요",
    body: "기분 5단계 · 에너지 · 오늘 쌓은 역량 · 감정 키워드만 고르면 끝이에요.",
    lines: [
      "고른 기분이 그날 별의 밝기가 되고, 저장하면 최근 평균과 견줘 '오늘의 변화'를 알려드려요.",
      "진행 중인 선택이 있으면 '오늘 그 행동을 했나요?'도 같이 물어봐요.",
      "화면 맨 위 작은 친구는 돌보미예요 — 지금 기분대로 서성이고, 쓰다듬거나 간식을 주면 좋아해요.",
      "기록을 쌓으면 코인이 모여 설정의 꾸미기 상점에서 쓸 수 있어요.",
    ],
  },
  {
    id: "diary-week", core: true, route: "/home", mascot: "lumi", chapter: "일기",
    title: "최근 7일과 전체 캘린더",
    body: "이번 주에 어떤 날을 남겼는지 한 줄로 보여줘요. 오른쪽 버튼이 전체 달력이에요.",
    lines: [
      "달마다 그 달의 황도 12궁 모양으로 기록이 모이고, 달을 고르면 주간 별자리로 펼쳐져요.",
      "주간 리포트에는 7일 막대 흐름 · 기록한 날 수 · 기분 평균 · 감정 키워드가 들어 있어요.",
      "그 주에 가장 좋았던 날과 힘들었던 날은 그날 문장 그대로 실려요.",
    ],
  },
  {
    id: "daily-suggest", core: true, route: "/home", mascot: "lumi", chapter: "일기",
    title: "오늘 해볼 만한 것도 권해요",
    body: "최근 2주 기록을 보고 몸 · 듣기 · 해보기 · 쉬기 · 사람으로 결을 나눠 세 가지를 골라요.",
    lines: [
      "기록이 많이 무거운 날엔 권하지 않고, 아무것도 안 해도 된다고만 말해요.",
      "아래에는 지금 들을 만한 노래도 놓여요. 일기에 가수 이야기가 있으면 그걸 씨앗으로, 없으면 지금 기분에 맞춰 골라요.",
      "곡은 실재하는 것만 올라와요 — 제목을 지어내지 않고, 눌러서 바로 들을 수 있어요.",
      "가라앉은 날 갑자기 신나는 쪽으로 밀지 않아요. '지금 마음 곁에'처럼 방향도 함께 적혀요.",
    ],
  },

  // ── 3장 · 시뮬레이션 · 결과 ───────────────────────────────
  // 소개 영상에서 쓴 장면과 문구를 그대로 쓴다.
  {
    id: "simulate-start", core: true, route: "/input", mascot: "nova", chapter: "시뮬레이션",
    title: "그리고 갈림길 앞에서",
    body: "이직할까, 남을까 — 혼자 재지 마세요.",
    lines: [
      "고민 중인 두 갈래를 나란히 놓고, 각각 어떤 미래가 되는지 비교해요.",
      "일기에 같은 고민이 반복해서 나왔으면 위쪽에 그걸로 채워진 비교를 권해요.",
    ],
  },
  {
    id: "shot-choices", core: true, shot: "/tour/sim-choices.png", mascot: "nova", chapter: "시뮬레이션",
    shotCaption: "선택지를 채운 입력 화면",
    title: "두 갈래를 적기만 하면",
    body: "나와 조건이 비슷한 사람들의 데이터가 붙습니다.",
    lines: [
      "적으면 그 선택이 어느 삶의 영역인지 자동으로 잡혀요.",
      "칸 안의 '조건 더 알려주기'를 펴면 금액 · 기간 · 상황을 그 선택 바로 밑에서 적어요.",
      "몇 년 뒤를 볼지는 1년부터 15년까지 고를 수 있어요. 지표마다 관측이 어디까지인지는 결과 화면이 밝혀줘요.",
    ],
  },
  {
    id: "shot-result-core", core: true, shot: "/tour/result-core.png", mascot: "cosmo", chapter: "결과",
    shotCaption: "두 선택의 핵심 차이",
    title: "3년 뒤, 두 개의 내가 나옵니다",
    body: "어디서 갈리는지부터 한 문장으로 말해줘요.",
    lines: ["UNIVERSE A · B 카드의 얼굴은 내가 만든 아바타예요."],
  },
  {
    id: "shot-result-story", core: true,
    shots: ["/tour/result-story-a.png", "/tour/result-story-b.png"],
    mascot: "cosmo", chapter: "결과",
    shotCaption: "왼쪽 A · 오른쪽 B",
    title: "두 미래를 나란히 놓고",
    body: "얻게 되는 것과 감수할 것을 같은 무게로 적어요.",
    lines: ["지금 / 변화 과정 / 그 이후 — 같은 틀로 쓰여 있어 나란히 두면 차이가 바로 보여요."],
  },
  {
    id: "shot-result-trajectory", core: true, shot: "/tour/result-trajectory.png",
    mascot: "cosmo", chapter: "결과",
    shotCaption: "1·3·5·10년 뒤 관측 변화",
    title: "한 시점이 아니라 흐름으로",
    body: "3년엔 앞서다 10년엔 뒤집히기도 해요. 교차하는 지점이 핵심이에요.",
    lines: ["보라선이 A, 노란선이 B — 가처분소득 · 직업 만족 · 생활 만족을 각각 그려요."],
  },
  {
    id: "shot-result-stats", core: true, shot: "/tour/result-stats.png", mascot: "cosmo", chapter: "결과",
    shotCaption: "A/B 기본 비교 통계",
    title: "숫자는 지어내지 않습니다",
    body: "관측된 값만 놓고, 없는 건 없다고 말해요.",
    lines: [
      "한쪽에만 있는 값은 '선택별 모델 참고'로 빼요. 없는 쪽을 0으로 채우지 않아요.",
      "삶의 만족은 조사가 2년까지라, 3년을 골라도 관측된 마지막 값을 그대로 보여줘요.",
      "소득은 명목값이라 물가가 섞여 있다는 것까지 화면이 먼저 밝혀요.",
    ],
  },
  {
    id: "shot-result-insights", core: true, shot: "/tour/result-insights.png", mascot: "cosmo", chapter: "결과",
    shotCaption: "결과에서 더 읽을 수 있는 것",
    title: "표본이 얇아지는 것까지",
    body: "300명으로 시작해 8년 차엔 23명 — 그 숫자의 무게를 같이 보여줘요.",
    lines: [
      "격차 — 몇 년 차부터 벌어져 그 시점에 얼마나 차이 나는지.",
      "결과 범위 — 가운데 50%가 얼마나 흩어졌는지. 넓은 건 성공 가능성이 아니라 편차가 크다는 뜻이에요.",
      "새 점수를 만들지 않고, 이미 연결된 관측값만 해석해요.",
    ],
  },
  {
    id: "shot-result-baseline", shot: "/tour/result-baseline.png", mascot: "cosmo", chapter: "결과",
    shotCaption: "두 집단의 출발점",
    title: "출발점부터 달랐다면",
    body: "선택이 만든 차이인지, 원래 있던 차이인지 갈라서 보여줘요.",
    lines: [
      "한쪽이 모든 항목에서 높게 출발했다면 그건 선택의 효과가 아니라 '어떤 사람들이 그 선택을 했는가'예요.",
      "맨 아래에 매칭에 쓴 조건이 그대로 적혀요 — 근속 · 나이 · 성별 · 임금 · 종업원 규모 · 학력.",
    ],
  },
  {
    id: "shot-result-tabs", shot: "/tour/result-tabs.png", mascot: "cosmo", chapter: "결과",
    shotCaption: "수치 비교 탭",
    title: "탭으로 각도를 바꿔 봐요",
    body: "수치 비교 · 기록 근거 · 집단 관측, 담아둔 재료가 있으면 공고 분석까지.",
    lines: [
      "한쪽만 예측이 있으면 '예측 없음'이라 적고 빈칸을 지어내지 않아요.",
      "오른쪽 칸은 탭을 바꿔도 남아요 — 결정 포인트 · 어느 방향을 더 알아볼지 · 제3의 길.",
    ],
  },
  {
    id: "shot-result-record", core: true, shot: "/tour/result-record.png", mascot: "lumi", chapter: "결과",
    shotCaption: "기록 근거 탭",
    title: "그리고 내 기록이 근거로",
    body: "최근 28일 동안 이직 고민이 며칠이었는지까지 읽어요.",
    lines: [
      "고른 가치와 기록의 무게중심이 다르면 그것도 짚어줘요.",
      "일기가 예측 숫자를 바꾸지는 않아요. 해석과 확인할 것을 만드는 데 써요.",
      "화면 맨 아래에서 보관함에 저장해야 이번 비교를 마치고 나갈 수 있어요.",
    ],
  },

  // ── 4장 · 보관함 ──────────────────────────────────────────
  {
    id: "archive-list", core: true, full: true, route: "/archive", mascot: "lumi", chapter: "보관함",
    title: "고른 뒤가 더 중요해요",
    body: "저장만 하는 곳이 아니라, 선택 이후를 이어 적는 항해일지예요.",
    lines: [
      "저장한 우주 · 탐험 중 · 회고 완료가 위에 숫자로 보이고, 전체 · 탐험 중 · 회고 대기 · 보류 · 완료로 걸러 볼 수 있어요.",
      "오른쪽 위 '새 갈림길'로 새 비교를 바로 시작할 수 있어요.",
    ],
  },
  {
    id: "archive-card", core: true, route: "/archive", mascot: "lumi", chapter: "보관함",
    title: "카드를 열면 이어서 적어요",
    body: "그때 비교한 두 선택과 결과가 그대로 들어 있어요.",
    lines: [
      "마음이 기운 쪽을 정하면 그 선택의 실행 항목이 만들어지고, 체크하면 저장돼요.",
      "며칠 지나면 회고할 때가 됐다고 알려드려요 — 헤더의 종에도 오늘 할 일로 떠요.",
      "여기 쌓인 회고가 다음 비교에서 나를 설명하는 재료가 됩니다.",
    ],
  },

  // ── 마무리 ────────────────────────────────────────────────
  {
    id: "tabbar", core: true, route: "/my", act: "close-panels", mascot: "cosmo", chapter: "마무리",
    title: "네 곳을 오갑니다",
    body: "홈 · 시뮬레이션 · 일기 · 보관함. 언제든 여기로 돌아올 수 있어요.",
    lines: [
      "기록이 없어도 비교는 할 수 있어요. 다만 쌓일수록 설명이 나에게 맞춰져요.",
      "이 안내는 설정 → 알림 · 가이드에서 언제든 다시 받을 수 있어요.",
      "이제 시작해볼까요?",
    ],
  },
];

/** 챕터 순서 — 말풍선에 "3장 중 …" 대신 이름을 띄우는 데 쓴다. */
export const TOUR_CHAPTERS = TOUR_STEPS.reduce(
  (list, step) => (list.includes(step.chapter) ? list : [...list, step.chapter]),
  [],
);

/**
 * 자동 재생에서 이 단계를 얼마나 보여줄지(ms).
 *
 * 단계마다 글 양이 두 배 넘게 차이 난다. 같은 시간을 주면 짧은 단계는 지루하고
 * 긴 단계는 다 읽기 전에 넘어간다 — 녹화본에서는 그게 그대로 남는다.
 */
export function stepDuration(step) {
  if (!step) return 6000;
  const chars = [step.title, step.body, ...(step.lines || [])].join("").length;
  return Math.min(18000, 3600 + chars * 58);
}

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

/** 안내 첫 화면(소개 모달)을 다시 연다 — 설정의 '안내 받기'. */
export function openGuide() {
  if (typeof window !== "undefined") window.dispatchEvent(new Event("pm:guide-open"));
}

export function wantsTour() {
  return storage.getItem(WANT) === "1";
}

/** 안내가 끝났거나 건너뛰었다 — 다시 고르기 전엔 뜨지 않는다. */
export function clearWantTour() {
  storage.removeItem(WANT);
}

/**
 * 안내를 받겠다고 고른 순간 부른다.
 *
 * 자동으로는 절대 시작하지 않는다. 첫 진입이라고 무조건 띄우면 이미 계정이 있는
 * 사람이 다른 기기에서 들어와도 뜬다.
 *
 * 지금 앱 안이면 바로 시작하고, 랜딩이면 표시만 남긴다 — 온보딩을 마치고 앱에
 * 들어오는 순간 Tour 가 그 표시를 보고 시작한다.
 */
export function startTour() {
  resetTour();
  storage.setItem(WANT, "1");
  if (typeof window !== "undefined") {
    setTimeout(() => window.dispatchEvent(new Event("pm:tour-start")), 400);
  }
}
