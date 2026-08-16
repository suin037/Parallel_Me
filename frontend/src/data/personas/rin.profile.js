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
  tagline: "런던 석사 마무리 · 돌아올지 남을지",
  choices: { a: "귀국해서 이직한다", b: "런던에 남아 현지 취업을 한다" },
};
