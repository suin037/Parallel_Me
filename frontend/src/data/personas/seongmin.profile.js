// 성민 — 카드용 프로필만. 1년치 기록은 ./seongmin.js 에 있다. (분리 이유는 jiwon.profile.js 참조)
export const profile = {
  name: "성민",
  age: 35,
  sex: "1", // GOMS 코드: 1 남 / 2 여
  sexConfirmed: true,
  major: "공학", // rulebase._FIELDS 계열명
  occupation: "설치·정비·생산", // Onboarding.OCCUPATIONS 직종
  occupation_group: 3, // KSCO 대분류 — 사무 종사자
  income: 380, // 월 만원
  edu_level: 7,
  tenure_years: 8,
  mbti: "ISTJ",
  value_ranking: ["family", "stability", "money", "meaning", "friends", "growth", "freedom", "status"],
  tagline: "제조사 생산관리 8년차 · 카페를 차릴지 버틸지",
  choices: { a: "퇴사하고 직원 2명 규모 카페를 창업한다", b: "현재 직장을 유지한다" },
};
