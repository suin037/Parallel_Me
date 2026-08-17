// 다운 — 카드용 프로필만. 1년치 기록은 ./daun.js 에 있다. (분리 이유는 jiwon.profile.js 참조)
export const profile = {
  name: "다운",
  age: 30,
  sex: "2", // GOMS 코드: 1 남 / 2 여
  sexConfirmed: true,
  major: "사회", // rulebase._FIELDS 계열명
  occupation: "경영·사무·금융·보험", // Onboarding.OCCUPATIONS 직종
  occupation_group: 3, // KSCO 대분류 — 사무 종사자
  income: 300, // 월 만원 (회사 급여. 브랜드 수익은 아직 재투자 중이라 제외)
  edu_level: 7,
  tenure_years: 5,
  mbti: "ENFJ",
  value_ranking: ["meaning", "friends", "family", "freedom", "growth", "status", "money", "stability"],
  // tenure_years(5)는 회사 근속이고 브랜드는 2년차다 — 둘을 섞어 "브랜드 운영 5년차"로
  // 적었다가 기록(1분기 "브랜드 2년차")과 어긋났다.
  tagline: "마케터 겸 브랜드 운영 2년차 · 독립할지 겸업을 이어갈지",
  choices: { a: "회사를 나와 내 브랜드를 창업한다", b: "현재 직장을 유지한다" },
  // '조건 더 알려주기' 추천값(키 = scenarioIntake.DOMAIN_QUESTIONS 의 질문 key).
  // 편집숍 입점 조건이 '전업' 이라 3월이 사실상의 기한이다.
  conditionHints: {
    // "회사를 나와 …창업한다" 는 '회사' 쪽이 먼저 걸려 career 로 잡힌다(business 아님).
    // 그래서 career 질문(time_horizon·income_change)까지 채워둬야 빈칸이 안 생긴다.
    a: {
      runway: "6개월", startup_cost: "3,000만원",
      time_horizon: "3월까지", income_change: "월 300만원 → 브랜드 수익만",
    },
    b: { time_horizon: "승진 제안 수락", income_change: "변화 없음" },
  },
  // 카드 얼굴. 값은 avatarOptions.js 의 id 를 그대로 쓴다(없는 id 는 조용히 무시된다).
  avatarConfig: {
    face: "original", hairStyle: "bobShortParted", hairColor: "2c1b18", skinColor: "edb98a",
    eyes: "happy", eyebrows: "happy", browThickness: "normal",
    glasses: "round", mouth: "smile", clothes: "openJacket", clothesColor: "ff5c5c",
  },
};
