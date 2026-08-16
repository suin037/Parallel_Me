// 은우 — 카드용 프로필만. 1년치 기록은 ./eunwoo.js 에 있다. (분리 이유는 jiwon.profile.js 참조)
export const profile = {
  name: "은우",
  age: 32,
  sex: "2", // GOMS 코드: 1 남 / 2 여
  sexConfirmed: true,
  major: "사회", // rulebase._FIELDS 계열명
  occupation: "예술·디자인·방송", // Onboarding.OCCUPATIONS 직종
  occupation_group: 2, // KSCO 대분류 — 전문가·관련 종사자
  income: 310, // 월 만원
  edu_level: 7,
  tenure_years: 4,
  mbti: "INFP",
  value_ranking: ["freedom", "stability", "meaning", "friends", "family", "growth", "money", "status"],
  tagline: "광고대행사 AE 4년차 · 워라밸 찾아 옮길지 남을지",
  choices: { a: "워라밸을 위해 이직한다", b: "지금 회사에 남는다" },
  // 카드 얼굴. 값은 avatarOptions.js 의 id 를 그대로 쓴다(없는 id 는 조용히 무시된다).
  avatarConfig: {
    face: "oval", hairStyle: "wavyParted", hairColor: "724133", skinColor: "f2d3b1",
    eyes: "happy", eyebrows: "happy", browThickness: "thin",
    mouth: "smile", clothes: "shirt", clothesColor: "ffafb9",
  },
};
