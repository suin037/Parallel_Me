// 도현 — 카드용 프로필만. 1년치 기록은 ./dohyun.js 에 있다. (분리 이유는 jiwon.profile.js 참조)
export const profile = {
  name: "도현",
  age: 31,
  sex: "1", // GOMS 코드: 1 남 / 2 여
  sexConfirmed: true,
  major: "공학", // rulebase._FIELDS 계열명
  occupation: "연구·공학기술", // Onboarding.OCCUPATIONS 직종
  occupation_group: 2, // KSCO 대분류 — 전문가·관련 종사자
  income: 420, // 월 만원
  edu_level: 7,
  tenure_years: 6,
  mbti: "INTP",
  value_ranking: ["stability", "freedom", "growth", "meaning", "friends", "family", "money", "status"],
  // 호버 카드에 띄우는 한 줄
  tagline: "게임사 백엔드 개발자 6년차 · 반년 쉬어갈지 버틸지",
  choices: { a: "번아웃으로 퇴사하고 반년 쉬어간다", b: "지금 회사에 남는다" },
  // '조건 더 알려주기' 추천값(키 = scenarioIntake.DOMAIN_QUESTIONS 의 질문 key).
  // 휴식은 career 와 health 두 영역을 함께 쓰므로 양쪽 키를 다 둔다 — 감지된 영역의
  // 질문만 뜨고 나머지는 무시된다.
  conditionHints: {
    a: {
      time_horizon: "반년 (6개월)", income_change: "월 420만원 → 0",
      current_level: "수면 5시간, 위염", frequency: "주 3회 산책",
    },
    b: {
      time_horizon: "일단 유지", income_change: "변화 없음",
      current_level: "수면 5시간, 위염", frequency: "주 1회도 어려움",
    },
  },
  // 카드 얼굴. 값은 avatarOptions.js 의 id 를 그대로 쓴다(없는 id 는 조용히 무시된다).
  // lashes:false — 빌트인 눈에는 속눈썹이 늘 붙어 있어 남자 아바타가 여성적으로 보인다.
  avatarConfig: {
    face: "original", hairStyle: "menCover", hairColor: "0e0e0e", skinColor: "edb98a",
    eyes: "small", lashes: false, eyebrows: "sad", browThickness: "normal",
    glasses: "square", mouth: "smile", clothes: "tShirt", clothesColor: "929598",
  },
};
