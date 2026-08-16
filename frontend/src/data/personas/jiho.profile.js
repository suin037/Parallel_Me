// 지호 — 카드용 프로필만. 1년치 기록은 ./jiho.js 에 있다. (분리 이유는 jiwon.profile.js 참조)
export const profile = {
  name: "지호",
  age: 29,
  sex: "1", // GOMS 코드: 1 남 / 2 여
  sexConfirmed: true,
  major: "사회", // rulebase._FIELDS 계열명
  occupation: "경영·사무·금융·보험", // Onboarding.OCCUPATIONS 직종
  occupation_group: 3, // KSCO 대분류 — 사무 종사자
  income: 340, // 월 만원
  edu_level: 7,
  tenure_years: 1,
  mbti: "INTJ",
  value_ranking: ["money", "status", "growth", "stability", "freedom", "meaning", "family", "friends"],
  tagline: "3번째 직장 1년차 · 다음 이직을 저울질 중",
  choices: { a: "더 좋은 조건으로 이직한다", b: "지금 회사에 남는다" },
  avatarConfig: {
    face: "square", hairStyle: "undercut", beard: null, eyes: "wide", lashes: false,
    eyebrows: "raised", browThickness: "normal", glasses: "none", mouth: "smile",
    clothes: "shirt", skinColor: "f2d3b1", hairColor: "0e0e0e", clothesColor: "5199e4",
  },
};
