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
  tagline: "회사원 겸 브랜드 운영 · 본업을 바꿀지 고민",
  choices: { a: "회사를 나와 내 브랜드를 창업한다", b: "현재 직장을 유지한다" },
  avatarConfig: {
    face: "oval", hairStyle: "longParted", beard: null, eyes: "wide", lashes: true,
    eyebrows: "happy", browThickness: "normal", glasses: "none", mouth: "smile",
    clothes: "openJacket", skinColor: "edb98a", hairColor: "2c1b18", clothesColor: "25557c",
  },
};
