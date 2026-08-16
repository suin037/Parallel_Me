// 시뮬 입력용 — 선택지 목록 + 자유서술 자동분류 (자체 완결, 백엔드 choice 규칙 미러)
export const SLOT_OPTIONS = [
  { key: "유지", label: "현상 유지", desc: "지금 그대로라면", emoji: "🌙" },
  { key: "이직", label: "이직", desc: "다른 회사·직무로 옮긴다", emoji: "🚀" },
  { key: "창업", label: "창업", desc: "내 사업을 시작한다", emoji: "🌱" },
  { key: "진학", label: "진학", desc: "대학원·유학으로 진학한다", emoji: "🎓" },
  // 예전엔 '퇴사'가 이직 키워드였다 — "퇴사하고 좀 쉬고 싶다"가 이직으로 분류돼
  // 옮겼을 때의 소득효과를 답했다. 쉬는 것과 옮기는 것은 다른 결정이라 갈랐다.
  { key: "휴식", label: "쉬어가기", desc: "퇴사·휴직하고 잠시 멈춘다", emoji: "🌤" },
];

// 삶 전체 분류 정본. 한 선택지는 여러 영역에 동시에 속할 수 있다.
// color = 그 영역의 행성 색. 보관함 카드·나의 우주가 같은 색으로 묶이도록 여기서 한 번만 정의한다.
export const LIFE_DOMAINS = [
  // '일'은 한 글자로 넣을 수 없다("일상·일정·매일·생일"이 전부 직업이 된다).
  // 대신 일을 가리키는 게 분명한 표현 단위로 넣는다 — "일을 줄이고", "일하는" 처럼
  // 서술어까지 붙은 형태만 잡으면 오탐 없이 "대학원 가면서 일을 줄이고" 를 직업으로 읽는다.
  { key: "career", label: "직업", emoji: "💼", color: "#4A90E2", keywords: ["회사", "직장", "직업", "이직", "퇴사", "휴직", "취업", "프리랜서", "근무", "직무", "업무", "출근", "야근", "일자리", "커리어", "경력", "일하", "일을 줄", "일을 쉬", "일을 그만", "일을 계속", "일을 병행", "일을 시작", "일을 하"] },
  { key: "education", label: "교육", emoji: "🎓", color: "#57C8E8", keywords: ["대학", "대학원", "진학", "유학", "공부", "교육", "학위", "석사", "박사", "자격증", "전공"] },
  { key: "business", label: "사업", emoji: "🌱", color: "#35B98A", keywords: ["창업", "사업", "자영", "개업", "장사", "가게", "카페", "법인", "스타트업", "대표"] },
  { key: "finance", label: "재무", emoji: "💰", color: "#E0954A", keywords: ["돈", "소득", "월급", "연봉", "저축", "투자", "대출", "빚", "비용", "재무", "생활비", "수입", "프리랜서"] },
  { key: "health", label: "건강", emoji: "🫶", color: "#F2789C", keywords: ["건강", "운동", "치료", "병원", "수면", "스트레스", "우울", "불안", "번아웃", "회복", "마음"] },
  { key: "housing", label: "주거", emoji: "🏠", color: "#C77FD6", keywords: ["이사", "이주", "독립", "집", "거주", "주거", "전세", "월세", "서울", "제주", "지방", "지역"] },
  { key: "relationship", label: "관계", emoji: "🤝", color: "#8B5CF6", keywords: ["결혼", "연애", "이별", "친구", "가족", "부모", "관계", "사람", "동료", "외로움", "대화", "전문가", "객관적인 의견", "조언", "남친", "여친", "남자친구", "여자친구", "애인", "연인", "헤어", "사귀", "데이트", "썸", "배우자", "남편", "아내"] },
  { key: "lifestyle", label: "생활방식", emoji: "🌿", color: "#8FBF3F", keywords: ["워라밸", "여가", "생활", "루틴", "시간", "여행", "취미", "재택", "자유", "삶", "프리랜서", "일정 기간", "체험", "새로운 방식"] },
  { key: "long_term_values", label: "장기 가치", emoji: "🧭", color: "#F5C86B", keywords: ["가치", "의미", "목표", "성장", "안정", "꿈", "미래", "자율", "보람", "장기"] },
];

// 문구에는 그 영역의 키워드가 반드시 하나 들어가야 한다. 여기 있는 문장은 사용자가
// 누르면 그대로 입력칸에 들어가고 detectLifeDomains 를 다시 통과하는데, 자기 영역
// 단어가 없으면 태그가 비거나(→ 폴백으로 장기 가치) 엉뚱한 영역으로 잡힌다.
// 예전 재무 b("…안정부터 만들기")는 '안정' 때문에 장기 가치로, 관계 b("…내 마음을
// 살펴보기")는 '마음' 때문에 건강으로 넘어갔다.
const COMPARE_PROMPTS = {
  career: { a: "새로운 회사나 역할로 옮기기", b: "지금 직장에 남아 조건을 조정해보기" },
  education: { a: "새로운 공부나 교육을 시작하기", b: "지금 공부 방식을 유지하며 경험을 더 쌓기" },
  business: { a: "작게라도 내 사업을 시작해보기", b: "창업을 미루고 준비 기간을 두기" },
  finance: { a: "수입을 늘리는 선택에 집중하기", b: "지출을 줄이고 대출 위험을 먼저 낮추기" },
  health: { a: "치료나 회복을 우선하는 쪽으로 바꾸기", b: "지금 일상을 유지하며 작은 건강 습관부터 만들기" },
  housing: { a: "새로운 지역이나 집으로 이사하기", b: "현재 거주지를 유지하며 조건을 개선하기" },
  relationship: { a: "관계에 변화를 주고 솔직하게 대화하기", b: "잠시 거리를 두고 관계를 다시 살펴보기" },
  lifestyle: { a: "일과 생활의 균형을 크게 바꾸기", b: "지금 생활에서 작은 변화를 시험해보기" },
  long_term_values: { a: "지금 중요한 가치를 따라 방향을 정하기", b: "장기적인 안정과 가능성을 더 확인하기" },
};

// A에 적은 길과 같은 문제를 다른 방식으로 풀 수 있는 B 후보들.
// 영역마다 하나만 보여주던 기존 방식과 달리, 같은 맥락 안에서 유지·조정·유예·시험을 비교한다.
const RELATED_ALTERNATIVES = {
  career: ["현재 직장에 남아 조건을 조정하기", "회사 안에서 직무나 팀을 바꿔보기", "이직을 미루고 필요한 역량부터 준비하기", "휴직이나 근무 형태 변경을 먼저 알아보기"],
  education: ["현업을 유지하며 공부를 병행하기", "진학을 미루고 단기 과정부터 들어보기", "학위 대신 실무 경험과 자격을 쌓기", "관심 분야 수업 하나로 먼저 시험해보기"],
  business: ["직장을 유지하며 사이드 프로젝트로 사업성을 시험하기", "준비 기간을 두고 고객 반응부터 확인하기", "혼자 창업하지 않고 함께할 동업자를 찾아보기", "창업 대신 관련 회사에서 경험을 쌓기"],
  finance: ["수입 확대보다 지출과 위험을 먼저 줄이기", "큰 결정을 미루고 소액으로 시험하기", "현재 계획을 유지하며 비상자금을 더 만들기", "큰 수익보다 매달 들어오는 소득 흐름을 우선하기"],
  health: ["현재 일상을 유지하며 작은 회복 습관부터 만들기", "혼자 버티기보다 치료나 상담의 도움을 받아보기", "일정을 줄이고 충분히 쉬는 기간을 갖기", "강한 변화 대신 지속 가능한 강도로 조정하기"],
  housing: ["현재 집에 머물며 불편한 조건을 개선하기", "바로 이사하지 않고 단기로 살아보기", "이사 시점을 뒤로 미루고 자금을 먼저 모으기", "다른 지역보다 현재 생활권 안에서 찾아보기"],
  relationship: ["바로 결론내리지 않고 솔직하게 대화해보기", "잠시 거리를 두고 관계를 다시 확인하기", "관계를 유지하되 경계와 조건을 분명히 하기", "주변이나 전문가에게 객관적인 의견을 구하기"],
  lifestyle: ["생활을 크게 바꾸지 않고 작은 변화부터 시험하기", "현재 루틴을 유지하며 시간 배분만 조정하기", "일정 기간만 새로운 방식을 체험해보기", "포기할 것과 유지할 것을 나눠 단계적으로 바꾸기"],
  long_term_values: ["지금의 안정을 유지하며 가능성을 더 확인하기", "결정을 미루고 판단 기준부터 분명히 하기", "가장 중요한 가치 하나만 우선해보기", "되돌릴 수 있는 작은 선택으로 먼저 시험하기"],
};

const VALUE_TO_DOMAINS = {
  money: ["finance"], status: ["career"], family: ["relationship"], friends: ["relationship"],
  growth: ["education", "career"], freedom: ["lifestyle"], meaning: ["long_term_values"],
  stability: ["health", "finance", "housing"],
};

// 짧은 키워드가 무관한 단어 속에 섞여 잡히던 것들. 매칭 전에 지운다.
// '집'(주거) 하나 때문에 "치료와 회복에 집중하기"가 건강+주거로 잡혀, 사용자가
// 꺼낸 적 없는 주거 영역이 결과 화면에 '근거 부족' 카드로 떴다.
// '불안정'은 '불안'(건강)과 '안정'(장기 가치)에 동시에 걸려 고용 얘기가 두 영역으로 샜다.
// '일하'(직업)를 열면서 같이 막아야 하는 것들 — "동일하게", "매일", "제일" 처럼
// 일이 일(work)이 아닌 자리. 지워도 다른 영역 키워드는 건드리지 않는다.
const FALSE_FRIENDS = /집중|집안|집합|편집|모집|수집|밀집|소집|불안정|동일|통일|균일|단일|매일|생일|제일/g;

// 이 단어들은 삶의 맥락을 보태지만, 하나만으로 분석 영역을 확정하기에는 너무 넓다.
// 영역별로 따로 두는 이유는 "프리랜서"처럼 직업을 정하는 데에는 충분하지만
// 재무·생활방식을 동시에 주영역으로 만들면 안 되는 단어가 있기 때문이다.
const WEAK_DOMAIN_KEYWORDS = {
  finance: new Set(["프리랜서"]),
  health: new Set(["스트레스", "불안", "마음"]),
  relationship: new Set(["사람", "전문가", "객관적인 의견", "조언"]),
  lifestyle: new Set(["시간", "자유", "삶", "프리랜서", "일정 기간", "새로운 방식"]),
  long_term_values: new Set(["성장", "안정", "미래"]),
};

export function detectLifeDomains(text) {
  const normalized = (text || "").trim().toLowerCase().replace(FALSE_FRIENDS, " ");
  if (!normalized.trim()) return [];
  return LIFE_DOMAINS
    .filter((domain) => domain.keywords.some((keyword) => normalized.includes(keyword)))
    .map((domain) => domain.key);
}

/**
 * 시뮬레이션 입력용 대표 영역 감지.
 * 강한 단서가 있는 영역 하나만 반환하고, 일반적인 보조 단어만 있으면 사용자가
 * 직접 고를 수 있도록 비워 둔다. 일기 태깅은 기존 detectLifeDomains의 복수 영역을 유지한다.
 */
export function detectPrimaryLifeDomain(text) {
  const normalized = (text || "").trim().toLowerCase().replace(FALSE_FRIENDS, " ");
  if (!normalized.trim()) return [];

  const ranked = LIFE_DOMAINS.map((domain, index) => {
    const weak = WEAK_DOMAIN_KEYWORDS[domain.key] || new Set();
    let strongMatches = 0;
    let weakMatches = 0;
    for (const keyword of domain.keywords) {
      if (!normalized.includes(keyword)) continue;
      if (weak.has(keyword)) weakMatches += 1;
      else strongMatches += 1;
    }
    return { key: domain.key, index, strongMatches, score: strongMatches * 3 + weakMatches };
  })
    .filter((item) => item.strongMatches > 0)
    .sort((left, right) => right.score - left.score || left.index - right.index);

  return ranked.length ? [ranked[0].key] : [];
}

/** 최근 기록·가치·반대편 입력을 반영하고, 서로 다른 영역 후보를 반환한다. */
export function suggestComparePrompts({ side = "a", recentDomains = [], valueRanking = [], otherText = "", limit = 4 } = {}) {
  const otherDomains = new Set(detectLifeDomains(otherText));
  const recentScore = new Map(
    (recentDomains || [])
      .filter((item) => typeof item === "string" || Number(item.count || 0) > 0)
      .map((item, index) => [item.key || item, typeof item === "string" ? 1 : Number(item.count) - index * .01]),
  );
  const valueScore = new Map();
  (valueRanking || []).forEach((id, index) => {
    for (const key of VALUE_TO_DOMAINS[id] || []) valueScore.set(key, Math.max(valueScore.get(key) || 0, 1 - index * .08));
  });
  const fallbackOrder = side === "a"
    ? ["career", "relationship", "education", "health", "housing", "lifestyle", "finance", "business", "long_term_values"]
    : ["lifestyle", "health", "relationship", "housing", "finance", "education", "career", "long_term_values", "business"];

  // B는 A의 감지 영역을 최우선으로 사용한다. 복수 영역이면 각 영역 후보를 번갈아
  // 구성해 A와 무관한 인기 키워드가 끼어들지 않게 한다.
  if (side === "b" && otherText.trim() && otherDomains.size) {
    const rankedDomains = [...otherDomains].sort((left, right) => {
      const leftScore = (recentScore.get(left) || 0) * 2 + (valueScore.get(left) || 0);
      const rightScore = (recentScore.get(right) || 0) * 2 + (valueScore.get(right) || 0);
      return rightScore - leftScore;
    });
    const related = [];
    for (let optionIndex = 0; related.length < limit; optionIndex += 1) {
      let added = false;
      for (const key of rankedDomains) {
        const text = RELATED_ALTERNATIVES[key]?.[optionIndex];
        if (text && !related.some((item) => item.text === text)) {
          related.push({ key: `${key}-${optionIndex}`, text, score: 10 - optionIndex });
          added = true;
          if (related.length === limit) break;
        }
      }
      if (!added) break;
    }
    if (related.length) return related;
  }

  return fallbackOrder
    .map((key, fallbackIndex) => ({
      key,
      text: COMPARE_PROMPTS[key][side === "b" ? "b" : "a"],
      score: (recentScore.get(key) || 0) * 4 + (valueScore.get(key) || 0) * 2 + (otherDomains.has(key) ? 1.5 : 0) - fallbackIndex * .01,
    }))
    .sort((left, right) => right.score - left.score)
    .slice(0, limit);
}

export function domainLabel(key) {
  return LIFE_DOMAINS.find((domain) => domain.key === key)?.label || key;
}

export function domainColor(key) {
  return LIFE_DOMAINS.find((domain) => domain.key === key)?.color || "#6E7C93";
}

export const labelOf = (c) => (c === "유지" ? "현상 유지" : c);

// 우선순위: '이직' 행동어가 있으면 목적지(스타트업 등)보다 이직 우선.
// 예) "스타트업으로 이직할지" → 창업(X) → 이직(O)
const KW = {
  이직: ["이직", "옮기", "옮길", "전직", "갈아타", "이직할", "회사 옮", "다른 회사로"],
  진학: ["진학", "대학원", "유학", "석사", "박사", "학위", "로스쿨", "편입", "공부하러"],
  창업: ["창업", "사업", "자영", "개업", "장사", "내 사업", "법인", "대표", "차릴", "차리", "스타트업 차"],
  // '퇴사'는 여기 둔다. 갈 곳이 정해졌으면 보통 '이직·옮기'를 같이 쓰고,
  // 그러면 위의 이직 검사가 먼저 잡는다(행동어 최우선).
  휴식: ["휴직", "쉬어가", "쉬고 싶", "쉬려", "잠시 쉬", "좀 쉬", "퇴사", "그만두", "그만둘",
        "번아웃", "공백기", "갭이어", "안식년", "재충전"],
  유지: ["유지", "그대로", "현직", "잔류", "남을", "남기", "계속 다니", "계속 있", "안 옮", "지금 회사"],
};
export function classifyChoice(text) {
  if (!text || !text.trim()) return null;
  if (KW.이직.some((k) => text.includes(k))) return "이직";
  if (KW.진학.some((k) => text.includes(k))) return "진학";
  if (KW.창업.some((k) => text.includes(k))) return "창업";
  if (KW.휴식.some((k) => text.includes(k))) return "휴식";
  if (KW.유지.some((k) => text.includes(k))) return "유지";
  // 근거 키워드가 없으면 오분류하지 않고 사용자가 직접 고르게 한다.
  return null;
}

/**
 * 행성 key → 선택지 영역 key(들). toPlanetKey 의 반대 방향.
 *
 * 두 어휘가 따로 있다 — 화면(행성)은 5개, 선택지 분류는 9개. 홈 알림은 행성 key 로
 * 말하는데 결과 화면의 지표 필터는 선택지 key 로 거른다. 그대로 넘기면 relation·
 * growth·life 가 사전에 없어 "연결된 수치 데이터가 없습니다" 로 빠진다.
 */
export const PLANET_TO_DOMAINS = {
  career: ["career", "finance", "business"],
  growth: ["education", "long_term_values"],
  health: ["health"],
  relation: ["relationship"],
  life: ["housing", "lifestyle"],
};

export function toChoiceDomains(planetKey) {
  return PLANET_TO_DOMAINS[planetKey] || [];
}

// ── 삶의 영역(LIFE_DOMAINS) → 나의 우주 행성(PLANETS) 키 ──────────────
// 두 키 체계가 다르다. 시뮬레이션 분류는 9개(career·education·business…),
// 행성은 5개(career·life·relation·health·growth). 시나리오를 올바른 행성에
// 꽂으려면 이 변환이 필요하다. (일기 태깅 domain_tag.py 는 이미 행성 키로 나온다.)
const DOMAIN_TO_PLANET = {
  career: "career",
  business: "career",          // 창업도 일의 영역
  finance: "career",           // 행성 '진로'가 진로·일·돈을 포괄
  education: "growth",
  long_term_values: "growth",
  health: "health",
  relationship: "relation",
  housing: "life",
  lifestyle: "life",
};

/** 감지된 영역 배열 → 행성 키 하나. 없으면 null(호출부가 기본값 결정). */
export function toPlanetKey(domains = []) {
  for (const d of domains) {
    if (DOMAIN_TO_PLANET[d]) return DOMAIN_TO_PLANET[d];
  }
  return null;
}
