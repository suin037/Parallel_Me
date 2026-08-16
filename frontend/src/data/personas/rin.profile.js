// 린 — 카드용 프로필만. 1년치 기록은 ./rin.js 에 있다. (분리 이유는 jiwon.profile.js 참조)
export const profile = {
  name: "린",
  age: 27,
  sex: "2", // GOMS 코드: 1 남 / 2 여
  sexConfirmed: true,
  major: "사회", // rulebase._FIELDS 계열명
  // 직종은 '앞으로 할 일'이 아니라 지금 소득이 나오는 곳으로 잡는다 — 예측이 monthly_wage 를
  // 그 직종 분포에 대기 때문이다. 린의 £90만원은 카페 알바 소득이다.
  occupation: "영업·판매·서비스", // Onboarding.OCCUPATIONS 직종
  occupation_group: 4, // KSCO 대분류 — 서비스 종사자
  income: 90, // 월 만원 (알바 소득)
  edu_level: 8, // 석사
  tenure_years: 0,
  mbti: "ENFP",
  value_ranking: ["growth", "freedom", "meaning", "friends", "status", "money", "family", "stability"],
  tagline: "런던 석사 마무리 · 귀국할지 현지에 남을지",
  choices: { a: "귀국해서 이직한다", b: "런던에 남아 현지 취업을 한다" },
  // '조건 더 알려주기' 추천값(키 = scenarioIntake.DOMAIN_QUESTIONS 의 질문 key).
  // 린은 비자 시계가 조건이다 — 졸업 후 체류 기한이 곧 결정 기한이 된다.
  conditionHints: {
    a: { time_horizon: "졸업 직후 (3개월 안)", income_change: "월 90만 → 300만" },
    b: { time_horizon: "비자 만료 전 (6개월)", income_change: "현지 오퍼 기준 월 £2,400" },
  },
  // 카드 얼굴. 값은 avatarOptions.js 의 id 를 그대로 쓴다(없는 id 는 조용히 무시된다).
  avatarConfig: {
    face: "pointedShort", hairStyle: "bun", hairColor: "a55728", skinColor: "f2d3b1",
    eyes: "wide", eyebrows: "raised", browThickness: "normal",
    mouth: "laugh", clothes: "tShirt", clothesColor: "a7ffc4",
  },
};
