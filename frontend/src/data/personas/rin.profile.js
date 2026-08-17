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
  // B는 해외 취업이라 우리 패널(KLIPS·GOMS·YP·KOWEPS, 전부 국내)에 없는 경로다.
  //
  //   예전엔 분류기가 '남아' 키워드로 이걸 **'유지'(현직 잔류)** 로 보고(확신도
  //   0.58) 국내 잔류자 궤적 211만원을 그렸다 — 서사는 런던 이야기, 그래프는
  //   한국 이야기였다. 그건 명백한 오류라 `compare._is_out_of_scope_region` 이
  //   감지하도록 했다.
  //
  //   그렇다고 B를 통째로 비우면 A/B 비교가 반쪽이 되어 **체험 자체가 안 된다.**
  //   그래서 소득은 **오퍼 금액을 원화로 환산해 입력 조건으로 넣는다.** 이건
  //   모델이 낸 값이 아니라 린이 손에 쥔 오퍼이므로 '데이터가 없다'는 이유로
  //   지울 대상이 아니다. 은우의 280만원과 같은 성격이고, 화면도 같은 문구로
  //   "모델 예측이 아니라 입력"이라고 밝힌다.
  //
  //   여전히 비우는 것: 만족도·이탈확률. 이건 사용자가 적을 수 있는 값이 아니라
  //   모델만 낼 수 있고, 그 모델에 해당 데이터가 없다.
  //
  //   갈림길 자체를 국내로 바꾸는 안은 접었다. 1년치 기록(rin.js)이 통째로 런던
  //   이야기라 — 그래듀에이트 루트 2년, 스폰서십 거절 메일, Tom의 카페 매니저
  //   제안 — 갈림길만 바꾸면 기록과 결과가 서로 다른 얘기를 한다.
  choices: { a: "귀국해서 이직한다", b: "런던에 남아 현지 취업을 한다" },
  // '조건 더 알려주기' 추천값(키 = scenarioIntake.DOMAIN_QUESTIONS 의 질문 key).
  // 린은 비자 시계가 조건이다 — 졸업 후 체류 기한이 곧 결정 기한이 된다.
  //
  // B의 504만원 = £2,400 × 약 2,100원(2026년 8월 기준). 화살표 표기를 쓰는 이유는
  // 파서가 '→ 뒤의 값'을 목표 수준으로 읽기 때문이다(choice_conditions._ARROW).
  // ⚠ 세전 명목 환산이다 — 런던 월세·세율은 반영돼 있지 않다. 그대로 비교하면
  //   B가 실제보다 좋아 보이므로, 서사에서 생활비를 함께 다루게 둔다.
  conditionHints: {
    a: { time_horizon: "졸업 직후 (3개월 안)", income_change: "월 90만 → 300만" },
    b: { time_horizon: "비자 만료 전 (6개월)",
         income_change: "£2,400 오퍼 · 월 90만 → 504만 (환율 2,100원)" },
  },
  // 카드 얼굴. 값은 avatarOptions.js 의 id 를 그대로 쓴다(없는 id 는 조용히 무시된다).
  avatarConfig: {
    face: "pointedShort", hairStyle: "bun", hairColor: "a55728", skinColor: "f2d3b1",
    eyes: "wide", eyebrows: "raised", browThickness: "normal",
    mouth: "laugh", clothes: "tShirt", clothesColor: "a7ffc4",
  },
};
