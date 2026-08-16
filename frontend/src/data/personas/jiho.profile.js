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
  tagline: "3번째 직장 1년차 · 조건 보고 옮길지 남을지",
  choices: { a: "더 좋은 조건으로 이직한다", b: "지금 회사에 남는다" },
  // '조건 더 알려주기' 추천값(키 = scenarioIntake.DOMAIN_QUESTIONS 의 질문 key).
  conditionHints: {
    a: { time_horizon: "1개월 안", income_change: "+18% (약 60만원 증가)" },
    b: { time_horizon: "1년은 더", income_change: "연 4% 인상" },
  },
  // 카드 얼굴. 값은 avatarOptions.js 의 id 를 그대로 쓴다(없는 id 는 조용히 무시된다).
  avatarConfig: {
    face: "pointed", hairStyle: "undercut", hairColor: "0e0e0e", skinColor: "edb98a",
    eyes: "small", lashes: false, eyebrows: "angry", browThickness: "normal",
    mouth: "smile", clothes: "openJacket", clothesColor: "3c4f5c",
  },
};
