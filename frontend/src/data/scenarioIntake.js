// 자유 선택을 계산 가능한 사건으로 구조화한다.
// 질문은 영역 공통 2개를 기본으로 하고, 실제 패널 사건에 필요한 조건만 1개 추가한다.
export const EVENT_RULES = [
  ["finance.savings_increase", /저축|적금|모으/, "저축 늘리기"],
  ["finance.debt_start", /대출|빚|돈을?\s*빌리/, "대출 시작"],
  ["lifestyle.work_hours_decrease", /근로시간.*줄|근무시간.*줄|주\s*4일|시간\s*단축/, "근로시간 줄이기"],
  ["career.occupation_change", /이직|전직|직종.*변경|진로.*변경/, "직업 이동"],
  ["education.level_increase", /진학|대학원|유학|학위/, "교육수준 높이기"],
  ["business.self_employment_start", /창업|자영|개업|사업.*시작|가게/, "창업"],
  ["housing.homeownership_start", /자가|내\s*집|주택.*구입|집.*구입/, "주택 구입"],
  ["housing.move", /이사|이주|거주지.*변경|독립/, "이사"],
  ["relationship.marriage_start", /결혼|혼인/, "결혼"],
  ["relationship.household_increase", /합가|출산|가구원.*증가/, "가구원 증가"],
  ["relationship.household_decrease", /분가|가구원.*감소/, "가구원 감소"],
  ["relationship.conversation", /솔직.*대화|대화.*솔직|마음.*말|관계.*변화/, "관계 대화 실험"],
  ["relationship.distance", /거리.*두|시간.*갖|연락.*줄|마음.*살펴/, "관계 거리두기 실험"],
];

export const DOMAIN_OUTCOMES = {
  career: ["소득·고용 안정", "직종·고용형태 변화", "직무·삶 만족"],
  education: ["학비·소득 공백", "학력·취업 전환", "교육·삶 만족"],
  business: ["사업소득·생존", "자영 전환·지속", "직무·건강·삶 만족"],
  finance: ["가처분소득·자산·부채", "선택 가능 여력", "재무 스트레스·삶 만족"],
  health: ["의료·근로 부담", "활동·기능 변화", "수면·스트레스·주관 건강"],
  housing: ["주거비·자산·부채", "통근·생활 기회", "주거·삶 만족"],
  relationship: ["가구 재정 변화", "관계 행동 지속", "가족·사회관계 만족·고립"],
  lifestyle: ["소득·생활비", "시간 활용 변화", "수면·여가·스트레스"],
  long_term_values: ["경제적 감당 가능성", "가치와 선택의 정합성", "장기 만족·후회 신호"],
};

// 네 번째 값 shared=true 는 **선택이 아니라 상황을 묻는 질문**이라는 뜻이다.
//
// 관계가 이 구분을 드러냈다. '연인과 솔직하게 대화하기' vs '잠시 거리를 두기'는
// 같은 관계에 대한 두 접근이라 "누구와의 관계인가", "현재 관계 상태는"의 답이
// A와 B에서 달라질 수 없다. 그런데 질문은 양쪽에 따로 떠서 같은 문장을 두 번
// 쓰게 했다. 반대로 "예상 월소득 변화"는 선택마다 다른 게 당연하다.
//
// shared 질문은 A·B의 영역이 같을 때만 하나로 합친다 — 영역이 다르면(A는 진로,
// B는 관계) 같은 key 라도 서로 다른 상황을 가리키므로 합치면 안 된다.
const DOMAIN_QUESTIONS = {
  career: [["time_horizon", "이 선택을 언제 실행할 예정인가요?", "예: 3개월 안"], ["income_change", "예상 월소득 변화가 있나요?", "예: 50만원 증가"]],
  education: [["duration", "교육 기간은 어느 정도인가요?", "예: 2년"], ["cost", "학비와 준비 비용은 얼마인가요?", "예: 총 2,000만원"]],
  business: [["runway", "소득 없이 버틸 수 있는 기간은?", "예: 8개월", true], ["startup_cost", "초기 필요 자금은?", "예: 3,000만원"]],
  finance: [["monthly_budget", "매달 감당 가능한 금액은?", "예: 40만원", true], ["time_horizon", "얼마 동안 유지할 계획인가요?", "예: 3년"]],
  health: [["current_level", "현재 불편 정도는?", "예: 수면 5시간, 스트레스 높음", true], ["frequency", "변화를 얼마나 자주 실천할 건가요?", "예: 주 3회"]],
  housing: [["housing_cost", "예상 보증금·월 주거비는?", "예: 보증금 1천/월 70"], ["commute", "통근시간은 어떻게 달라지나요?", "예: 20분 감소"]],
  relationship: [["relation_type", "누구와의 관계인가요?", "예: 연인·가족·친구·동료", true], ["current_state", "현재 관계 상태는 어떤가요?", "예: 갈등이 잦고 연락은 매일", true]],
  lifestyle: [["weekly_change", "일주일 기준 무엇이 얼마나 달라지나요?", "예: 근무 8시간 감소"], ["duration", "얼마 동안 시도할 계획인가요?", "예: 3개월"]],
  long_term_values: [["priority", "이 선택에서 가장 지키고 싶은 가치는?", "예: 안정·성장·관계", true], ["review_point", "언제 다시 판단할까요?", "예: 6개월 후"]],
};

export function interpretChoice(text, domains = []) {
  const found = EVENT_RULES.find(([, regex]) => regex.test(text || ""));
  const domain = domains[0] || found?.[0]?.split(".")[0] || "long_term_values";
  return { event: found?.[0] || `${domain}.unspecified`, eventLabel: found?.[2] || "구체 사건 미확인", domain };
}

export function questionsForChoice(text, domains = []) {
  const interpreted = interpretChoice(text, domains);
  // 표시용 영역과 **사건이 실제로 가리키는 영역**이 다를 수 있다.
  //
  //   "회사를 나와 내 브랜드를 창업한다"
  //     · 사건 규칙  → business.self_employment_start (business)
  //     · 표시 영역  → career  (choices.js 의 `business: "career"` — 창업도 일의 영역)
  //
  // 예전엔 표시 영역 하나만 보고 질문을 골라서, 창업인데도 career 질문
  // (실행 시점·월소득 변화)만 떴다. 창업의 핵심 조건인 **runway·초기자금**은
  // 화면에 나오지도 않으니 사용자가 적을 방법이 없었고, 다운의 3,000만원과
  // 성민의 1억 2천만원이 수치에 전혀 반영되지 않았다.
  //
  // 둘 중 하나를 고르는 대신 **합친다.** 사건 쪽을 먼저 놓아 더 구체적인 질문이
  // 위로 오게 하고, 키가 겹치면 앞의 것을 남긴다.
  const eventDomain = interpreted.event.split(".")[0];
  const order = eventDomain === interpreted.domain
    ? [interpreted.domain]
    : [eventDomain, interpreted.domain];

  //
  // shared 는 네 번째 자리에 있는 '상황 조건' 표시다(A 에서 물으면 B 에는 다시 안 묻는다).
  // 영역을 합치면서 이 값을 떨어뜨리면 B 카드에 공통 질문이 되살아난다.
  const seen = new Set();
  const questions = [];
  for (const key of order) {
    for (const [qKey, label, placeholder, shared = false] of DOMAIN_QUESTIONS[key] || []) {
      if (seen.has(qKey)) continue;
      seen.add(qKey);
      questions.push({ key: qKey, label, placeholder, shared });
    }
  }
  return { ...interpreted, questions };
}
