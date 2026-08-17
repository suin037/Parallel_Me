// 성민 — 카드용 프로필만. 1년치 기록은 ./seongmin.js 에 있다. (분리 이유는 jiwon.profile.js 참조)
export const profile = {
  name: "성민",
  age: 35,
  sex: "1", // GOMS 코드: 1 남 / 2 여
  sexConfirmed: true,
  major: "공학", // rulebase._FIELDS 계열명
  occupation: "설치·정비·생산", // Onboarding.OCCUPATIONS 직종
  // KSCO 대분류 8 — 장치·기계 조작 및 조립 종사자.
  //
  // 예전엔 3(사무 종사자)이었다. 태그라인의 '생산관리' 를 사무직으로 본 것인데,
  // 바로 윗줄의 직종 라벨(설치·정비·생산)과 어긋나서 화면에는 "사무 종사자" 가
  // 떴다. 모델이 실제로 읽는 건 이 코드 쪽이라(profileOptions.js 주석) 라벨만
  // 보고는 무엇으로 매칭되는지 알 수 없었다.
  //
  // 라벨에 맞춰 제조 생산직으로 통일한다. 설치·정비 쪽 비중이 더 크다고 보면
  // 7(기능원 및 관련 기능 종사자)로 바꾸면 된다 — 이 줄만 고치면 된다.
  occupation_group: 8,
  income: 380, // 월 만원
  edu_level: 7,
  tenure_years: 8,
  mbti: "ISTJ",
  value_ranking: ["family", "stability", "money", "meaning", "friends", "growth", "freedom", "status"],
  tagline: "제조사 생산관리 8년차 · 카페를 차릴지 남을지",
  choices: { a: "퇴사하고 직원 2명 규모 카페를 창업한다", b: "현재 직장을 유지한다" },
  // '조건 더 알려주기' 추천값(키 = scenarioIntake.DOMAIN_QUESTIONS 의 질문 key).
  // 창업은 business(runway·startup_cost), 유지는 career(time_horizon·income_change) 를 묻는다.
  conditionHints: {
    a: { runway: "8개월", startup_cost: "1억 2천만원", time_horizon: "3개월 안" },
    b: { time_horizon: "당분간 유지", income_change: "변화 없음" },
  },
  // 카드 얼굴. 값은 avatarOptions.js 의 id 를 그대로 쓴다(없는 id 는 조용히 무시된다).
  avatarConfig: {
    face: "square", hairStyle: "sideComed", hairColor: "2c1b18", skinColor: "d08b5b",
    eyes: "small", lashes: false, eyebrows: "neutral", browThickness: "thick",
    beard: "chin", mouth: "smile", clothes: "shirt", clothesColor: "25557c",
  },
};
