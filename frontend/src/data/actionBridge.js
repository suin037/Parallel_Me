// Action Bridge — 사용자가 선택한 미래를 실행 가능한 작은 실험으로 연결한다.
// 행동 자체는 검토 가능한 큐레이션 콘텐츠이며, LLM은 향후 표현 개인화에만 사용한다.

import { computeDiarySignals } from "./diarySignals.js";
import storage from "./safeStorage.js";

const GOAL_KEY = "pm.activeGoal.v1";

const COMMON_BASIS = {
  implementation: {
    basis: "실행 의도: 언제·어디서·무엇을 할지 정하면 행동으로 옮기기 쉬워집니다.",
    source: "Gollwitzer (1999), Implementation intentions",
  },
  possibleSelf: {
    basis: "가능자기: 원하는 미래 모습을 구체화하면 현재 행동의 방향을 잡는 데 도움이 됩니다.",
    source: "Markus & Nurius (1986), Possible selves",
  },
  smallExperiment: {
    basis: "작은 정보수집 실험으로 큰 결정을 내리기 전 불확실성을 줄이는 방식입니다.",
    source: "행동 실험·점진적 실행 원칙",
  },
};

const DOMAIN_ACTIONS = {
  career: [
    ["관심 선택지의 실제 업무를 아는 사람 1명에게 질문하기", "업무환경에 대한 추측을 실제 정보로 바꿔요.", "smallExperiment"],
    ["현재 조건과 원하는 조건을 각각 3개 적어 비교하기", "막연한 변화 욕구를 비교 가능한 기준으로 만들어요.", "possibleSelf"],
  ],
  education: [
    ["관심 과정의 모집요강과 비용을 15분만 확인하기", "필요 조건과 현실적인 부담을 먼저 확인해요.", "implementation"],
    ["재학생이나 수료자에게 물어볼 질문 3개 적기", "홍보자료에서 알기 어려운 경험 정보를 모아요.", "smallExperiment"],
  ],
  business: [
    ["해결하려는 문제를 겪는 사람 1명과 이야기하기", "아이디어보다 실제 문제의 존재를 먼저 확인해요.", "smallExperiment"],
    ["한 달 필수생활비와 버틸 수 있는 기간 계산하기", "사업 선택의 경제적 안전 범위를 확인해요.", "implementation"],
  ],
  finance: [
    ["A/B 각각의 월 고정비와 예상수입을 한 줄로 적기", "경제적 차이를 감정이 아닌 조건으로 비교해요.", "implementation"],
  ],
  health: [
    ["이번 주 회복을 방해하는 요인 하나와 줄일 행동 하나 정하기", "큰 변화 대신 실행 가능한 회복 행동부터 시작해요.", "implementation"],
  ],
  housing: [
    ["후보 지역의 주거비·이동시간·필수시설을 한 번 비교하기", "생활환경 선택의 숨은 비용을 확인해요.", "smallExperiment"],
  ],
  relationship: [
    ["상대에게 확인하고 싶은 기대와 경계를 각각 한 문장 적기", "관계 결정을 추측이 아닌 대화 가능한 질문으로 바꿔요.", "implementation"],
  ],
  lifestyle: [
    ["선택 이후의 평일 하루를 시간순으로 적어보기", "원하는 생활방식이 실제 일상과 맞는지 살펴봐요.", "possibleSelf"],
  ],
  long_term_values: [
    ["이 선택으로 지키고 싶은 가치와 포기 가능한 것을 하나씩 적기", "선택이 장기적인 가치와 맞는지 확인해요.", "possibleSelf"],
  ],
};

// 같은 영역에서도 사용자가 실제로 비교한 행동에 따라 첫 실험을 바꾼다.
// 결과를 예언하는 규칙이 아니라, 선택 사이의 불확실성을 검증하는 행동 설계다.
const SCENARIO_ACTIONS = [
  [/솔직.*대화|대화.*솔직|관계.*변화/, "relationship", "말하고 싶은 사실·감정·요청을 각각 한 문장으로 적기", "대화 전에 사실과 해석을 분리하면 방어적 반응을 줄이고 핵심 요청을 분명히 할 수 있어요.", "implementation"],
  [/전문가|객관.*의견|주변.*의견|조언/, "relationship", "같은 상황을 설명할 문장과 확인할 질문 2개를 적어 제3자에게 묻기", "조언을 결론으로 받아들이기보다 내가 놓친 정보와 관점을 수집하는 실험으로 사용해요.", "smallExperiment"],
  [/균형.*크게.*바꾸|생활.*크게.*바꾸/, "lifestyle", "바뀐 뒤의 평일을 30분 단위로 적고 유지하기 어려운 구간 하나 표시하기", "큰 변화의 만족감보다 실제 시간 구조가 지속 가능한지를 먼저 확인해요.", "possibleSelf"],
  [/일정.*기간|체험|시험|테스트/, "lifestyle", "체험 기간·바꿀 행동·중단 기준·판단 날짜를 한 줄씩 정하기", "기간과 종료 조건이 있는 작은 실험은 되돌릴 수 있어 큰 결정의 불확실성을 줄여요.", "implementation"],
];

// 일기 신호별 '확인 행동' — 최근 기록에서 드러난 상태를 다음 단계에 반영한다(로컬 규칙, API 0).
const SIGNAL_ACTIONS = {
  stabilityPreference: ["이직 시 최소 확보돼야 할 안전 조건 3개(급여 하한·고용형태·수습기간) 적기", "막연한 불안을 '확인 가능한 조건'으로 바꿔요.", "implementation"],
  jobDissatisfaction: ["최근 가장 스트레스였던 업무 상황 1개를 적고, 회사 문제인지 직무 문제인지 구분하기", "불만의 원인을 나눠야 이직이 답인지 알 수 있어요.", "smallExperiment"],
  growthStagnation: ["지난 6개월간 새로 배운 것 3개 적기 — 없으면 다음 자리에서 배우고 싶은 것 3개", "성장 정체가 자리 문제인지 시기 문제인지 살펴봐요.", "possibleSelf"],
  burnout: ["이번 주 회복을 방해하는 요인 하나와 줄일 행동 하나 정하기", "지친 상태의 결정은 미루고, 회복부터 확보해요.", "implementation"],
  jobChange: ["이직을 미루게 하는 진짜 이유를 한 문장으로 적기", "반복되는 고민의 핵심을 눈에 보이게 만들어요.", "possibleSelf"],
};

// signals = computeDiarySignals() 결과(선택). 있으면 강한 신호 순으로 확인 행동을 앞에 끼운다.
export function actionsFor(choice, domains = [], signals = null) {
  const keys = [...new Set(domains)].filter((key) => DOMAIN_ACTIONS[key]);
  const source = keys.length ? keys : fallbackDomains(choice);
  const domainList = source.flatMap((domain) =>
    DOMAIN_ACTIONS[domain].map(([text, purpose, basisKey]) => ({
      id: `${domain}:${text}`,
      domain,
      text,
      purpose,
      ...COMMON_BASIS[basisKey],
    })),
  );
  const scenarioList = SCENARIO_ACTIONS
    .filter(([pattern, domain]) => source.includes(domain) && pattern.test(String(choice || "")))
    .map(([, domain, text, purpose, basisKey]) => ({
      id: `scenario:${domain}:${text}`,
      domain,
      text,
      purpose,
      ...COMMON_BASIS[basisKey],
      tailored: true,
    }));

  const signalList = [];
  if (signals?.ok) {
    for (const s of (signals.signals || []).filter((x) => x.days > 0).sort((a, b) => b.days - a.days)) {
      const def = SIGNAL_ACTIONS[s.key];
      if (def) signalList.push({ id: `sig:${s.key}`, domain: "signal", signal: s.label, days: s.days, text: def[0], purpose: def[1], ...COMMON_BASIS[def[2]] });
    }
  }

  // 신호 행동 1개를 맨 앞에, 나머지는 시나리오·도메인 행동으로 채워 3개. 같은 문구는 한 번만.
  // (1개인 이유: 상한이 3이라 2개를 넣으면 선택 A/B를 검증하는 영역 행동이 1개로 밀린다.
  //  이직고민+직무불만처럼 신호는 동시에 잘 터져서 사실상 영역 행동이 사라진다.)
  const merged = [];
  const seen = new Set();
  for (const a of [...signalList.slice(0, 1), ...scenarioList, ...domainList]) {
    if (seen.has(a.text)) continue;
    seen.add(a.text);
    merged.push(a);
    if (merged.length >= 3) break;
  }
  return merged;
}

// 일기 신호(이직·번아웃 등)는 진로 계열 목표에만 주입한다.
// 관계·건강 목표에 이직 실험이 끼면 엉뚱하므로 도메인·문구로 게이팅한다.
export function isJobGoal(choice, domains = []) {
  return (
    ["career", "finance", "business"].some((k) => domains.includes(k)) ||
    /이직|퇴사|유지|창업|진학|직장|커리어/.test(choice || "")
  );
}

/**
 * '오늘 할 일'의 단일 진입점 — 결과 화면·보관함·알람이 모두 이걸 통해야 한다.
 * 완료 여부는 doneActions 의 '문구 텍스트'로 대조하므로, 셋 중 하나라도 다른 인자로
 * actionsFor 를 부르면 서로 다른 문구가 나와 '했어요'가 어긋난다.
 *
 * @param signals computeDiarySignals() 결과. 생략하면 이 함수가 계산한다.
 *   여러 우주를 도는 루프에서는 밖에서 한 번 계산해 넘길 것(매번 일기 전체를 다시 읽는다).
 */
export function actionsForGoal(choice, domains = [], signals) {
  const sig = signals === undefined ? computeDiarySignals({ windowDays: 28 }) : signals;
  return actionsFor(choice, domains, isJobGoal(choice, domains) ? sig : null);
}

function fallbackDomains(choice) {
  const c = String(choice || "");
  if (/창업|사업|자영/i.test(c)) return ["business", "finance"];
  if (/진학|대학원|유학|석사|박사/.test(c)) return ["education", "finance"];
  if (/유지|현상|그대로/.test(c)) return ["career", "long_term_values"];
  return ["career", "finance"];
}

export function saveActiveGoal(goal) {
  const value = { ...goal, createdAt: new Date().toISOString(), completedActions: [] };
  try { storage.setItem(GOAL_KEY, JSON.stringify(value)); } catch { /* 저장 불가 환경 */ }
  return value;
}

export function loadActiveGoal() {
  try { return JSON.parse(storage.getItem(GOAL_KEY) || "null"); } catch { return null; }
}

export function clearActiveGoal() {
  try { storage.removeItem(GOAL_KEY); } catch { /* 저장 불가 환경 */ }
}

// 작은 실험에 적은 답을 목표의 completedActions 에 upsert(완료 기록). 빈 값이면 삭제.
export function saveActionResponse(actionId, text) {
  const goal = loadActiveGoal();
  if (!goal) return null;
  const v = (text || "").trim();
  const rest = (goal.completedActions || []).filter((a) => a.id !== actionId);
  const completedActions = v ? [...rest, { id: actionId, text: v }] : rest;
  const value = { ...goal, completedActions };
  try { storage.setItem(GOAL_KEY, JSON.stringify(value)); } catch { /* 저장 불가 환경 */ }
  return value;
}

// 저장된 우주의 결정(A/B) → 지금 탐험 중인 실제 선택. 보류면 null.
export function chosenChoice(u) {
  if (u?.decision === "A") return u.choiceA;
  if (u?.decision === "B") return u.choiceB;
  return null;
}
