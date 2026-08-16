// 지원 — 카드용 프로필만. 1년치 기록은 ../demoYear.js 에 있다.
//
// 왜 파일을 갈랐나: ES 모듈은 파일 단위로만 가져올 수 있어서, 기록 파일에서
//   `profile` 하나만 정적 import 하면 그 파일 전체(1년치 87KB)가 첫 화면 번들에
//   딸려 들어온다. 카드 7장을 그리는 데 필요한 건 이 20줄뿐이므로 여기로 옮겼다.
//   기록 파일은 이 값을 다시 export 하므로 출처는 여전히 하나다.
export const profile = {
  name: "지원",
  age: 29,
  sex: "2", // GOMS 코드: 1 남 / 2 여
  sexConfirmed: true,
  major: "예체능", // rulebase._FIELDS 계열명
  occupation: "예술·디자인·방송", // Onboarding.OCCUPATIONS 직종
  occupation_group: 2, // KSCO 대분류 — 전문가·관련 종사자
  income: 330, // 월 만원
  edu_level: 7,
  tenure_years: 4,
  mbti: "INFJ",
  value_ranking: ["growth", "meaning", "stability", "friends", "freedom", "family", "money", "status"],
  tagline: "프로덕트 디자이너 4년차 · 합격했는데 못 옮기고 있다",
  choices: { a: "합격한 회사로 이직한다", b: "지금 회사에 남는다" },
};
