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
  tagline: "프로덕트 디자이너 4년차 · 합격한 곳으로 옮길지 남을지",
  choices: { a: "합격한 회사로 이직한다", b: "지금 회사에 남는다" },
  // '조건 더 알려주기' 추천값. 키는 scenarioIntake.DOMAIN_QUESTIONS 의 질문 key 다.
  // 그 인물의 1년 기록에 실제로 나오는 수치만 적는다 — 지어내면 기록과 화면이 어긋난다.
  // 감지된 영역의 질문만 화면에 뜨므로, 여기 남는 키가 있어도 조용히 무시된다.
  conditionHints: {
    a: { time_horizon: "1개월 안", income_change: "40만원 증가" },
    b: { time_horizon: "당분간 유지", income_change: "연 3.2% 인상" },
  },
  // 카드 얼굴. 값은 avatarOptions.js 의 id 를 그대로 쓴다(없는 id 는 조용히 무시된다).
  avatarConfig: {
    face: "oval", hairStyle: "bobLong", hairColor: "2c1b18", skinColor: "f2d3b1",
    eyes: "wide", eyebrows: "neutral", browThickness: "thin",
    mouth: "smile", clothes: "turtleNeck", clothesColor: "3c4f5c",
  },
};
