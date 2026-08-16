// ─────────────────────────────────────────────────────────────
// 일기 신호 — 최근 2~4주 일기·체크인에서 '이직 고민'과 관련한 상태를 뽑는다.
//
// 정직선(중요): 이 신호는 예측 숫자(KLIPS 생존분석·인과효과)를 바꾸지 않는다.
//   · 무엇을 비교할지 제안하고(반복되는 고민 감지),
//   · 통계 결과를 "내 기준"으로 해석하는 재료로만 쓴다.
// 키워드 기반이라 정밀 측정이 아니라 "기록에서 드러난" 수준임을 화면에서도 그대로 밝힌다.
// ─────────────────────────────────────────────────────────────
import { loadUniverse, todayKey, hasRecord } from "./myUniverse.js";
import { CARD_BY_ID } from "./valueCards.js";
import { LIFE_DOMAINS, detectLifeDomains } from "./choices.js";

// 신호별 사전. 표현이 겹칠 수 있어 '드러난 정도'로만 읽는다(정밀 분류 아님).
const LEX = {
  jobChange: {
    label: "이직 고민",
    words: ["이직", "퇴사", "그만두", "그만둘", "옮기", "이력서", "면접", "경력직", "다른 회사", "회사를 떠"],
    axis: "성장",
  },
  jobDissatisfaction: {
    label: "직무 불만",
    words: ["상사", "야근", "회의", "눈치", "압박", "실적", "불만", "지친", "지쳐", "버티", "꼰대", "갈굼", "혼났", "업무가 많", "일이 많"],
    axis: "성장",
  },
  growthStagnation: {
    label: "성장 정체",
    words: ["정체", "지루", "반복", "똑같", "그대로", "도태", "배울 게 없", "성장이 없", "권태", "매너리즘"],
    axis: "성장",
  },
  stabilityPreference: {
    label: "안정 선호",
    words: ["안정", "안전", "불안", "무섭", "무서워", "두렵", "리스크", "위험", "포기", "놓기", "겁", "확실"],
    axis: "안정",
  },
  burnout: {
    label: "번아웃·소진",
    words: ["번아웃", "소진", "방전", "무기력", "탈진", "의욕이 없", "쉬고 싶", "지쳤"],
    axis: "안정",
  },
  // 진로 밖 영역 — 돌보미가 자기 영역의 신호로 말하려면 이 둘이 필요하다.
  // (전에는 사전이 전부 진로 쪽이라 어느 돌보미든 이직 얘기만 했다.)
  relationStrain: {
    label: "관계 마찰",
    words: ["서운", "섭섭", "다퉜", "싸웠", "싸우", "말다툼", "삐졌", "연락이 없", "연락이 뜸", "멀어",
            "오해", "서먹", "눈치 보", "혼자인 것 같", "외로", "지긋지긋", "헤어지", "이별", "손절"],
    axis: "관계",
  },
  lifeRhythm: {
    label: "흐트러진 리듬",
    words: ["늦잠", "미뤘", "미루", "하루종일", "하루 종일", "아무것도 못", "아무것도 안", "폰만",
            "누워만", "나갈 데가 없", "할 게 없", "심심", "무의미", "시간을 버", "정신없이 지나"],
    axis: "안정",
  },
  bodySignal: {
    label: "몸의 신호",
    words: ["잠을 못", "못 잤", "불면", "잠이 안", "두통", "어지럽", "속이 안", "아프", "몸살", "감기",
            "허리", "어깨가", "눈이 아", "체력이", "운동을 못", "폭식", "입맛이 없"],
    axis: "안정",
  },
};

function textOf(c) {
  const parts = [c.text, c.note];
  if (Array.isArray(c.answers)) for (const qa of c.answers) parts.push(qa?.a);
  else if (c.answers && typeof c.answers === "object") parts.push(...Object.values(c.answers));
  // '작은 실험'에 사용자가 적은 답만 포함(질문 프롬프트는 키워드 오탐 유발 → 제외).
  if (Array.isArray(c.experiments)) for (const e of c.experiments) parts.push(e?.text);
  return parts.filter(Boolean).join(" ");
}

function daysBetween(dateKey, ref) {
  return Math.round((new Date(ref + "T00:00:00") - new Date(dateKey + "T00:00:00")) / 86400000);
}

const avg = (arr) => (arr.length ? arr.reduce((s, x) => s + x, 0) / arr.length : null);

/**
 * 최근 windowDays 일의 일기에서 신호를 계산한다.
 * @returns {{ok:boolean, windowDays:number, n:number, days:number,
 *   signals:{key,label,days,intensity}[], jobChangeDays:number,
 *   moodTrend:number|null, revealed:{axis,label}|null }}
 */
export function computeDiarySignals({ windowDays = 28 } = {}, s = loadUniverse()) {
  const today = todayKey();
  const recent = s.checkins.filter((c) => {
    if (c.empty) return false;
    const d = daysBetween(c.date, today);
    return d >= 0 && d <= windowDays;
  });
  if (!recent.length) return { ok: false, windowDays, n: 0, days: 0, signals: [], jobChangeDays: 0, moodTrend: null, revealed: null };

  // 신호별로 "며칠에 걸쳐 나타났나"를 센다(하루에 여러 번은 1로).
  const hitDays = {};
  for (const key of Object.keys(LEX)) hitDays[key] = new Set();
  for (const c of recent) {
    const t = textOf(c);
    if (!t) continue;
    for (const [key, def] of Object.entries(LEX)) {
      if (def.words.some((w) => t.includes(w))) hitDays[key].add(c.date);
    }
  }

  const signals = Object.entries(LEX).map(([key, def]) => {
    const days = hitDays[key].size;
    return { key, label: def.label, axis: def.axis, days, intensity: days / recent.length };
  });

  // 기분 추세: 창 전반부 vs 후반부 평균 valence (번아웃/에너지 하강의 대리 지표).
  const moods = recent
    .filter((c) => c.valence != null)
    .sort((a, b) => a.date.localeCompare(b.date))
    .map((c) => c.valence);
  let moodTrend = null;
  if (moods.length >= 4) {
    const mid = Math.floor(moods.length / 2);
    moodTrend = +(avg(moods.slice(mid)) - avg(moods.slice(0, mid))).toFixed(2);
  }

  // 기록에서 드러난 무게중심 = 신호를 가치 축(성장/안정)으로 합산해 우세한 축.
  // 단일 신호가 아니라 축 단위로 봐야 "선택한 가치 vs 드러난 가치" 비교가 성립한다.
  const axisDays = {};
  for (const s of signals) axisDays[s.axis] = (axisDays[s.axis] || 0) + s.days;
  const topAxis = Object.entries(axisDays)
    .filter(([, d]) => d > 0)
    .sort((a, b) => b[1] - a[1])[0];
  const revealed = topAxis ? { axis: topAxis[0], days: topAxis[1] } : null;

  return {
    ok: true,
    windowDays,
    n: recent.length,
    days: new Set(recent.map((c) => c.date)).size,
    signals: signals.sort((a, b) => b.days - a.days),
    axisDays,
    jobChangeDays: hitDays.jobChange.size,
    moodTrend,
    revealed,
  };
}

// 온보딩에서 고른 가치의 대표 축(상위 1개)과, 기록에서 드러난 축을 비교한다.
// 라벨링용 — 가중치 계산이 아니다(backend 담당).
export function valueGap(profile, sig) {
  const topId = (profile?.value_ranking || [])[0];
  const selected = topId ? CARD_BY_ID[topId] : null;
  const selectedAxis = selected?.axis || null;
  const revealedAxis = sig?.revealed?.axis || null;
  return {
    selectedAxis,
    selectedLabel: selected?.label || null,
    revealedAxis,
    revealedLabel: revealedAxis, // 축 이름(성장/안정 …)을 그대로 라벨로
    aligned: selectedAxis && revealedAxis ? selectedAxis === revealedAxis : null,
  };
}

// 신호 → 개인화 해석(③층)을 로컬로 생성한다. LLM 없음.
// "현재 준비 상태" + "우선 확인할 조건" — 예측 숫자는 건드리지 않고 읽는 법만 제시.
export function interpretSignals(sig, gap) {
  if (!sig?.ok) return null;
  const top = (sig.signals || []).filter((s) => s.days > 0);
  const has = (k) => top.some((s) => s.key === k);
  const down = sig.moodTrend != null && sig.moodTrend < -0.1;
  const up = sig.moodTrend != null && sig.moodTrend > 0.1;

  let readiness;
  if (has("burnout") || down) {
    readiness = { tone: "caution", text: "지쳐 있는 신호가 보여요. 큰 결정보다 회복을 먼저 확보하고, 판단은 컨디션이 올라온 뒤로 미뤄도 괜찮아요." };
  } else if (sig.jobChangeDays >= 3 && up) {
    readiness = { tone: "go", text: "고민이 반복되고 기분도 회복세예요. 막연히 미루기보다 실제로 조건을 알아보기 좋은 시점이에요." };
  } else if (sig.jobChangeDays >= 3) {
    readiness = { tone: "mid", text: "이직 고민이 자주 올라와요. 서두르기보다 아래 조건부터 하나씩 확인해 불확실성을 줄여보세요." };
  } else {
    readiness = { tone: "mid", text: "아직 한 방향으로 강하게 기운 신호는 적어요. 기록이 더 쌓이면 해석이 또렷해져요." };
  }

  const conditions = [];
  if (has("stabilityPreference")) conditions.push("이직 시 최소 확보돼야 할 안전 조건(급여 하한·고용형태)");
  if (has("jobDissatisfaction")) conditions.push("지금 불만이 '회사' 때문인지 '직무' 때문인지 구분");
  if (has("growthStagnation")) conditions.push("다음 자리에서 실제로 배우고 싶은 것 3가지");
  if (!conditions.length) conditions.push("가장 마음이 걸리는 조건 하나를 문장으로 적어보기");

  const valueNote =
    gap?.aligned === false
      ? `고른 가치(${gap.selectedAxis})와 기록의 무게중심(${gap.revealedAxis})이 달라요 — 무엇을 더 중요히 여기는지 짚어볼 지점.`
      : gap?.aligned === true
        ? `고른 가치와 기록이 같은 방향(${gap.selectedAxis})이라 그 기준으로 밀어도 될 신호예요.`
        : null;

  return { readiness, conditions: conditions.slice(0, 3), valueNote };
}

// 영역(행성)별 분석 — 그 영역으로 분류된 기록만 모아 그래프·요약 재료를 만든다.
// 각 행성의 별자리가 "그 삶의 영역의 흐름"을 보여주게 하는 용도. 로컬, LLM 없음.
const _val = (c) => (c.valence != null ? c.valence : c.mood != null ? (c.mood - 3) / 2 : null);
const _mv = (c) => c.mood ?? Math.round(_val(c) * 2 + 3);

// 별 목록(그 영역·그 기간의 기록) → 분석 결과. domainAnalysis/domainMonths 공용.
export function analyzeStars(stars, extra = {}) {
  if (!stars.length) return { ok: false, n: 0, ...extra };
  const series = stars.map((c) => ({ date: c.date, v: +_val(c).toFixed(2), mood: _mv(c) }));
  const moodAvg = +(series.reduce((a, x) => a + x.mood, 0) / series.length).toFixed(1);
  let trend = null;
  if (series.length >= 4) {
    const mid = Math.floor(series.length / 2);
    const avg = (arr) => arr.reduce((s2, x) => s2 + x.v, 0) / arr.length;
    trend = +(avg(series.slice(mid)) - avg(series.slice(0, mid))).toFixed(2);
  }
  const freq = {};
  for (const c of stars) {
    const e = c.keyword || c.emotion;
    if (e) freq[e] = (freq[e] || 0) + 1;
  }
  const topEmotions = Object.entries(freq).sort((a, b) => b[1] - a[1]).slice(0, 3).map(([e]) => e);
  const snip = (c) => {
    const first = Array.isArray(c.answers) ? c.answers[0]?.a : c.answers && typeof c.answers === "object" ? Object.values(c.answers)[0] : "";
    const t = (c.text || c.note || first || "").trim();
    return t.length > 54 ? t.slice(0, 54) + "…" : t;
  };
  const best = stars.reduce((a, b) => (_mv(b) >= _mv(a) ? b : a));
  const worst = stars.reduce((a, b) => (_mv(b) <= _mv(a) ? b : a));
  return { ok: true, n: stars.length, series, moodAvg, trend, topEmotions,
    best: { date: best.date, mood: _mv(best), text: snip(best) },
    worst: { date: worst.date, mood: _mv(worst), text: snip(worst) }, ...extra };
}

// 관계 하위유형 — 관계는 통짜가 아니라 연인/가족/친구/직장으로 나눠 분석해야 정확하다.
export const RELATION_SUBTYPES = {
  연인: ["남친", "여친", "애인", "연애", "이별", "썸", "사귀", "데이트", "연인", "남자친구", "여자친구"],
  가족: ["부모", "엄마", "아빠", "가족", "형제", "누나", "동생", "언니", "오빠", "할머니", "할아버지", "부모님"],
  친구: ["친구", "우정", "절친", "동창"],
  직장: ["동료", "상사", "직장 사람", "팀장", "부장", "회사 사람", "직장동료"],
};

// 입력 텍스트에서 관계 하위유형 감지. 없으면 null(=전체 관계).
export function detectRelationSubtype(text) {
  const t = text || "";
  for (const [k, words] of Object.entries(RELATION_SUBTYPES)) {
    if (words.some((w) => t.includes(w))) return k;
  }
  return null;
}

function _domainStars(planetKey, s, subtype) {
  // planetKey 없으면(null/"all") 전체 기록 — '별자리 만들기(전체 일기 평가)'용.
  const all = !planetKey || planetKey === "all";
  // hasRecord — 별 개수와 분석 대상이 어긋나지 않게 myUniverse 와 같은 규칙을 쓴다.
  let stars = s.checkins.filter(
    (c) => hasRecord(c) && (all || (Array.isArray(c.domains) && c.domains.includes(planetKey))),
  );
  // 관계 하위유형 필터 — 그 유형 키워드가 있는 기록만(있을 때만 적용, 없으면 전체 유지).
  if (subtype && RELATION_SUBTYPES[subtype]) {
    const words = RELATION_SUBTYPES[subtype];
    const matched = stars.filter((c) => words.some((w) => textOf(c).includes(w)));
    if (matched.length) stars = matched;
  }
  return stars.sort((a, b) => a.date.localeCompare(b.date));
}

// 그 영역 전체(모든 기간) 분석. subtype 주면 관계 하위유형만.
export function domainAnalysis(planetKey, s = loadUniverse(), subtype = null) {
  return analyzeStars(_domainStars(planetKey, s, subtype), { planetKey, subtype });
}

// 최근 windowDays 동안 가장 자주 기록된 영역(행성 key). 없으면 null.
// "이직 신호가 없을 때 카드가 실제 기록 주제를 반영"하는 데 쓴다.
export function dominantDomain({ windowDays = 28 } = {}, s = loadUniverse()) {
  const today = todayKey();
  const count = {};
  for (const c of s.checkins) {
    if (c.empty || !Array.isArray(c.domains)) continue;
    const d = daysBetween(c.date, today);
    if (d < 0 || d > windowDays) continue;
    for (const k of c.domains) count[k] = (count[k] || 0) + 1;
  }
  const top = Object.entries(count).sort((a, b) => b[1] - a[1])[0];
  return top ? top[0] : null;
}

// 그 영역을 '달(月)' 단위로 묶어 각 달의 분석을 낸다. 별자리 하나 = 한 달의 그 영역 내역.
// 최신 달 먼저. label 은 "2026년 8월" 형태.
export function domainMonths(planetKey, s = loadUniverse()) {
  const byMonth = {};
  for (const c of _domainStars(planetKey, s)) {
    const m = c.date.slice(0, 7); // YYYY-MM
    (byMonth[m] = byMonth[m] || []).push(c);
  }
  return Object.keys(byMonth)
    .sort((a, b) => b.localeCompare(a))
    .map((m) => {
      const [y, mm] = m.split("-");
      return { month: m, label: `${y}년 ${Number(mm)}월`, analysis: analyzeStars(byMonth[m], { planetKey, month: m }) };
    });
}

// 영역 분석 → 짧은 로컬 리포트 문장. 정직: 성격진단·예측 아님, 기록 요약.
export function domainReport(a, label) {
  if (!a?.ok) return `${label} 영역엔 아직 기록이 없어요. 일기가 이 영역으로 분류되면 여기에 흐름과 요약이 생겨요.`;
  const trendTxt =
    a.trend == null
      ? " 아직 흐름을 말하기엔 기록이 적어요."
      : a.trend > 0.1
        ? " 뒤로 갈수록 나아진 회복세예요."
        : a.trend < -0.1
          ? " 뒤로 갈수록 가라앉는 하강세예요."
          : " 큰 기복 없이 비슷하게 흘렀어요.";
  const emoTxt = a.topEmotions.length ? ` 이 영역에서 자주 남긴 감정은 ${a.topEmotions.join("·")}이에요.` : "";
  return `${label} 영역엔 기록이 ${a.n}개 쌓였고 기분은 평균 ${a.moodAvg}점.${trendTxt}${emoTxt}`;
}

// 반복 고민 넛지에 쓸 판단 — 최근 windowDays 안에 이직 고민이 threshold일 이상 나타났나.
// 돌보미별 넛지 — 그 돌보미가 맡은 영역의 신호로 말하고, 그 영역에 맞는 갈림길을 권한다.
//   노바=일상 / 코스모=고민과 선택(진로) / 루미=몸과 마음
// 전에는 셋 다 jobChange 하나만 봐서 어느 돌보미를 골라도 "이직 고민이 N일" 이었다.
export const GUIDE_DOMAIN = { nova: "life", cosmo: "career", lumi: "health" };

const DOMAIN_NUDGE = {
  career: {
    keys: ["jobChange", "jobDissatisfaction", "growthStagnation"],
    a: "이직", b: "현상 유지",
    ask: "이직 vs 현상 유지, 지금 비교해볼까요?",
  },
  health: {
    keys: ["burnout", "bodySignal"],
    a: "속도 줄이기", b: "지금 속도 유지",
    ask: "쉬어가기 vs 지금 속도, 비교해볼까요?",
  },
  relation: {
    keys: ["relationStrain"],
    a: "먼저 말 꺼내기", b: "지금처럼 두기",
    ask: "먼저 말 꺼내기 vs 지금처럼 두기, 비교해볼까요?",
  },
  growth: {
    keys: ["growthStagnation"],
    a: "새로 배우기 시작", b: "지금 하던 것 이어가기",
    ask: "새로 배울까요, 하던 걸 더 밀까요?",
  },
  life: {
    // 일상은 자기 신호어만 본다. 관계·건강 신호를 빌려 쓰면 "일상 · 관계 마찰이 4일"
    // 처럼 영역이 섞인 말이 나온다(실제로 그랬다).
    keys: ["lifeRhythm"],
    a: "생활 리듬 바꾸기", b: "지금 리듬 유지",
    ask: "리듬을 바꿔볼까요, 지금대로 갈까요?",
  },
};

/** 받침이 있으면 '이', 없으면 '가'. "직무 불만이(가)" 같은 표기를 없앤다. */
function subjectParticle(word) {
  const last = (word || "").trim().slice(-1);
  const code = last.charCodeAt(0);
  if (!last || code < 0xac00 || code > 0xd7a3) return "가";
  return (code - 0xac00) % 28 ? "이" : "가";
}

export const DOMAIN_LABEL = {
  career: "진로", relation: "관계", health: "건강", growth: "성장", life: "일상",
};

/**
 * 한 영역의 알림. 근거는 둘이다 —
 *   (1) 그 영역으로 분류된 일기 중 무거웠던 날(기분 2 이하)
 *   (2) 그 영역과 맞물리는 신호어가 나온 날
 * 키워드만 보면 그 영역 일기를 써도 특정 단어가 없으면 못 잡고,
 * 기분만 보면 왜 무거운지 말할 수 없다. 둘 다 본다.
 */
export function domainAlert(domain, { windowDays = 28, heavyMin = 3, signalMin = 4 } = {}, s = loadUniverse()) {
  const conf = DOMAIN_NUDGE[domain] || DOMAIN_NUDGE.career;
  const today = todayKey();
  const inWindow = s.checkins.filter((c) => {
    if (!hasRecord(c)) return false;
    const d = daysBetween(c.date, today);
    return d >= 0 && d <= windowDays;
  });
  // 영역 판정 — 저장된 태그가 있으면 그것, 없으면 본문의 신호어로 본다.
  // (자동 태깅은 서버가 붙이는데 안 붙은 기록이 많다. 태그만 믿으면 알림이 아예 안 뜬다.)
  const words = conf.keys.flatMap((k) => LEX[k]?.words || []);
  const mine = inWindow.filter((c) => {
    if (Array.isArray(c.domains) && c.domains.length) return c.domains.includes(domain);
    const t = textOf(c);
    return t && words.some((w) => t.includes(w));
  });
  const heavyDays = new Set(mine.filter((c) => c.mood != null && c.mood <= 2).map((c) => c.date)).size;

  const sig = computeDiarySignals({ windowDays }, s);
  const rows = (sig.signals || []).filter((x) => conf.keys.includes(x.key) && x.days > 0);
  const top = rows.sort((a, b) => b.days - a.days)[0];
  const signalDays = top?.days || 0;

  const bySignal = signalDays >= signalMin;
  const byMood = heavyDays >= heavyMin;
  // 왜 알리는지 한 문장 — 근거가 화면에 그대로 보여야 넘겨짚은 말이 아니게 된다.
  const reason = bySignal
    ? `${top.label}${subjectParticle(top.label)} ${signalDays}일`
    : byMood
      ? `${DOMAIN_LABEL[domain]} 기록 중 무거웠던 날 ${heavyDays}일`
      : "";

  return {
    domain,
    domainLabel: DOMAIN_LABEL[domain] || domain,
    prompt: bySignal || byMood,
    label: top?.label || "",
    particle: subjectParticle(top?.label || ""),
    count: signalDays,
    heavyDays,
    records: mine.length,
    reason,
    windowDays,
    choiceA: conf.a,
    choiceB: conf.b,
    ask: conf.ask,
  };
}

/** 문제가 드러난 영역 전부 — 무거운 쪽부터. 홈에서 각각 알림으로 띄운다. */
export function domainAlerts(opts = {}, s = loadUniverse()) {
  return Object.keys(DOMAIN_NUDGE)
    .map((d) => domainAlert(d, opts, s))
    .filter((a) => a.prompt)
    .sort((a, b) => (b.heavyDays + b.count) - (a.heavyDays + a.count));
}

/** 돌보미 하나의 넛지 — 그 돌보미가 맡은 영역의 알림. */
export function guideNudge(domain, opts = {}, s = loadUniverse()) {
  return domainAlert(domain, opts, s);
}

export function jobChangeRumination({ windowDays = 14, threshold = 3 } = {}, s = loadUniverse()) {
  const sig = computeDiarySignals({ windowDays }, s);
  return { ...sig, prompt: sig.jobChangeDays >= threshold, count: sig.jobChangeDays, windowDays };
}

// 시뮬레이션 자유서술 입력과 동일한 9영역 분류 정본을 사용한다.
export const DOMAIN_COMPARE = {
  career: { a: "현재 진로 유지", b: "진로 변경", action: "진로의 두 방향" },
  education: { a: "현재 학습 경로 유지", b: "진학·교육 시작", action: "배움의 두 방향" },
  business: { a: "현재 일 유지", b: "창업·사업 시작", action: "일과 사업의 두 방향" },
  finance: { a: "현재 재무 방식 유지", b: "재무 계획 변경", action: "돈 관리의 두 방향" },
  health: { a: "현재 생활 유지", b: "회복 방식 변경", action: "건강 회복의 두 방향" },
  housing: { a: "현재 거주 유지", b: "이사·주거 변경", action: "주거의 두 방향" },
  relationship: { a: "현재 관계 방식 유지", b: "관계에 변화 주기", action: "관계의 두 방향" },
  lifestyle: { a: "현재 생활방식 유지", b: "생활방식 변경", action: "생활의 두 방향" },
  long_term_values: { a: "현재 선택 유지", b: "가치에 맞게 방향 변경", action: "삶의 두 방향" },
};

/** 최근 기록에서 같은 삶의 영역이 서로 다른 날짜에 반복됐는지 계산한다. */
export function domainRumination({ windowDays = 28, threshold = 4 } = {}, s = loadUniverse()) {
  const today = todayKey();
  const byDomain = Object.fromEntries(LIFE_DOMAINS.map((domain) => [domain.key, new Set()]));
  let consideredDays = 0;
  for (const checkin of s.checkins || []) {
    if (checkin.empty) continue;
    const distance = daysBetween(checkin.date, today);
    if (distance < 0 || distance > windowDays) continue;
    const text = textOf(checkin).trim();
    if (!text) continue;
    consideredDays += 1;
    for (const key of detectLifeDomains(text)) byDomain[key]?.add(checkin.date);
  }
  const domains = LIFE_DOMAINS.map((domain) => ({
    key: domain.key, label: domain.label, emoji: domain.emoji, count: byDomain[domain.key].size,
  })).sort((a, b) => b.count - a.count);
  const top = domains[0];
  const prompt = Boolean(top && top.count >= threshold);
  return {
    ok: consideredDays > 0, prompt, count: top?.count || 0, windowDays, threshold,
    consideredDays, domain: prompt ? top : null, domains,
    compare: prompt ? DOMAIN_COMPARE[top.key] : null,
    method: "simulation-domain-classifier",
  };
}
