import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useResult } from "../data/ResultContext.jsx";
import { LIFE_DOMAINS, detectPrimaryLifeDomain, domainLabel, suggestComparePrompts } from "../data/choices.js";
import { OCCUPATION_GROUPS } from "../data/profileOptions.js";
import { detectEmotions } from "../data/DiaryContext.jsx";
import { domainRumination } from "../data/diarySignals.js";
import { loadUniverse } from "../data/myUniverse.js";
import { questionsForChoice } from "../data/scenarioIntake.js";
import { classifyChoicePair } from "../api.js";
import { Caption } from "../components/ui.jsx";
import JobPostingInput from "../components/JobPostingInput.jsx";
import RelationshipInput from "../components/RelationshipInput.jsx";
import Mascot from "../components/Mascot.jsx";
import FutureYearPicker from "../components/FutureYearPicker.jsx";
import { WELLBEING_MAX_YEAR } from "../data/futureYears.js";
import { BriefcaseBusiness, GraduationCap, Sprout, Wallet, HeartPulse, House, Users, Leaf, Compass, ArrowRight, GitCompareArrows, History, Sparkles } from "lucide-react";

const MAJOR_FIELDS = ["공학", "자연", "사회", "인문", "교육", "예체능", "의약"];
const DOMAIN_ICONS = {
  career: BriefcaseBusiness, education: GraduationCap, business: Sprout,
  finance: Wallet, health: HeartPulse, housing: House,
  relationship: Users, lifestyle: Leaf, long_term_values: Compass,
};
const CAREER_DETAIL_DOMAINS = new Set(["career", "business"]);
const JOB_POSTING_INTENT = /이직|취업|재취업|입사|지원(?:할|하려|하고|하기|하는)?|옮기(?:기|려|고)|다른\s*(?:회사|직장)|새로운\s*(?:회사|직장|직무)/;
const NON_POSTING_CAREER_INTENT = /현재\s*(?:상황|직장|회사).*유지|그대로|남(?:기|는다)|휴직|쉬어가기|번아웃|업무량|근무시간|야근|창업|사업/;
const GENERIC_COUNTERPART = /현상\s*유지|지금처럼|그대로|계속|보류|하지\s*않|안\s*하|현재를?\s*유지/;
const EMPLOYMENT_STATUSES = [
  [1, "상용직"], [2, "임시직"], [3, "일용직"], [4, "고용주·자영업자"], [5, "무급가족 종사자"],
];
const FIRM_SIZES = [
  [1, "1~4명"], [2, "5~9명"], [3, "10~29명"], [4, "30~49명"],
  [5, "50~69명"], [6, "70~99명"], [7, "100~299명"], [8, "300~499명"],
  [9, "500~999명"], [10, "1,000명 이상"], [11, "잘 모르겠음·기타"],
];

function latestConversationFutures() {
  try {
    const checkins = loadUniverse().checkins || [];
    for (let i = checkins.length - 1; i >= 0; i -= 1) {
      const options = checkins[i]?.insights?.future_options;
      if (Array.isArray(options) && options.length === 2 && options.every((item) => item?.label)) {
        return options.map((item) => ({
          label: String(item.label).trim(),
          detail: String(item.detail || item.label).trim(),
        }));
      }
    }
  } catch { /* 저장 기록이 없으면 제안하지 않는다 */ }
  return null;
}

export default function InputScreen() {
  const navigate = useNavigate();
  const {
    profile, setProfile, choices, setChoices,
    scenarioTexts, setScenarioTexts, scenarioDomains, setScenarioDomains,
    scenarioContexts, setScenarioContexts,
    futureYears, setFutureYears,
    diary, setDiary, postings, setPostings, analyzePostings,
    talks, setTalks, analyzeTalks,
  } = useResult();
  // 두 선택지 중 하나라도 '관계'로 잡히면 관계 상담 흐름으로 전환한다.
  // 선택지가 어느 영역인지에 따라 아래에 뜨는 입력이 통째로 바뀐다.
  // 관계면 대화·연락 내역을, 직업이면 직업 정보·공고·가치관 검사를 한 묶음으로.
  // 단, choices 기본값이 {이직, 유지}라 아무것도 안 썼을 때 직업으로 오인된다 —
  // 실제로 무언가 적었을 때만 영역 입력을 편다.
  const typed = Boolean(scenarioTexts.a?.trim() || scenarioTexts.b?.trim());
  const allDomains = [...(scenarioDomains.a || []), ...(scenarioDomains.b || [])];
  const isRelationship = typed && allDomains.includes("relationship");
  const textA = scenarioTexts.a;
  const textB = scenarioTexts.b;
  const [domainAuto, setDomainAuto] = useState({ a: true, b: true });
  const [focused, setFocused] = useState(textA && !textB ? "b" : "a");
  const [rumination, setRumination] = useState(() => domainRumination({ windowDays: 28, threshold: 4 }));
  const [conversationFutures, setConversationFutures] = useState(latestConversationFutures);
  const [classifying, setClassifying] = useState(false);

  // "이직하기 vs 지금처럼 유지"처럼 B가 맥락 의존 표현이면 단독 키워드가 없어도
  // A와 같은 비교 영역으로 읽는다. A/B 어느 쪽에 먼저 적어도 동일하게 동작한다.
  useEffect(() => {
    if (!textA.trim() || !textB.trim()) return;
    setScenarioDomains((prev) => {
      let a = domainAuto.a ? detectPrimaryLifeDomain(textA) : (prev.a || []);
      let b = domainAuto.b ? detectPrimaryLifeDomain(textB) : (prev.b || []);
      if (!a.length && GENERIC_COUNTERPART.test(textA) && b.length) a = [...b];
      if (!b.length && GENERIC_COUNTERPART.test(textB) && a.length) b = [...a];
      if (a.join("|") === (prev.a || []).join("|") && b.join("|") === (prev.b || []).join("|")) return prev;
      return { ...prev, a, b };
    });
  }, [textA, textB, domainAuto.a, domainAuto.b, setScenarioDomains]);

  useEffect(() => {
    const refresh = () => setRumination(domainRumination({ windowDays: 28, threshold: 4 }));
    window.addEventListener("pm:universe", refresh);
    return () => window.removeEventListener("pm:universe", refresh);
  }, []);

  function applySuggestedCompare() {
    if (!rumination.compare) return;
    const next = { a: rumination.compare.a, b: rumination.compare.b };
    setScenarioTexts(next);
    setChoices(next);
    setScenarioDomains({ a: [rumination.domain.key], b: [rumination.domain.key] });
    setDomainAuto({ a: true, b: true });
    setFocused("a");
  }

  function applyConversationFutures() {
    if (!conversationFutures) return;
    const next = { a: conversationFutures[0].detail, b: conversationFutures[1].detail };
    setScenarioTexts(next);
    setChoices(next);
    setScenarioDomains({
      a: detectPrimaryLifeDomain(`${conversationFutures[0].label} ${conversationFutures[0].detail}`),
      b: detectPrimaryLifeDomain(`${conversationFutures[1].label} ${conversationFutures[1].detail}`),
    });
    setDomainAuto({ a: true, b: true });
    setFocused("a");
    setConversationFutures(null);
  }

  function onText(side, value) {
    const field = side.toLowerCase();
    setScenarioTexts((prev) => ({ ...prev, [field]: value }));
    setChoices((prev) => ({ ...prev, [field]: value.trim() || prev[field] }));
    if (domainAuto[field]) {
      setScenarioDomains((prev) => ({ ...prev, [field]: detectPrimaryLifeDomain(value) }));
    }
  }

  function toggleDomain(side, key) {
    const field = side.toLowerCase();
    setDomainAuto((prev) => ({ ...prev, [field]: false }));
    setScenarioDomains((prev) => {
      const current = prev[field] || [];
      const next = current.includes(key) ? current.filter((item) => item !== key) : [...current, key];
      return { ...prev, [field]: next };
    });
  }

  function resetDomainDetection(side) {
    const field = side.toLowerCase();
    const text = field === "a" ? textA : textB;
    setDomainAuto((prev) => ({ ...prev, [field]: true }));
    setScenarioDomains((prev) => ({ ...prev, [field]: detectPrimaryLifeDomain(text) }));
  }

  function chooseSuggestion(side, value) {
    onText(side.toUpperCase(), value);
    if (side === "a") setFocused("b");
  }

  const normalizedA = textA.trim().replace(/\s+/g, " ");
  const normalizedB = textB.trim().replace(/\s+/g, " ");
  const duplicate = Boolean(normalizedA && normalizedB && normalizedA === normalizedB);
  const sameCategory = Boolean(normalizedA && normalizedB && !duplicate && scenarioDomains.a.some((key) => scenarioDomains.b.includes(key)));
  const missingDomains = Boolean(normalizedA && normalizedB && (!scenarioDomains.a.length || !scenarioDomains.b.length));
  // 실제 직업·창업 영역일 때만 직업 정보와 공고 입력을 연다. 건강·관계·주거·가치
  // 비교를 "관계만 아니면 커리어"로 처리하던 조건이 잘못된 직업 질문의 원인이었다.
  const isCareer = typed && allDomains.some((domain) => CAREER_DETAIL_DOMAINS.has(domain));
  const comparisonText = `${textA} ${textB}`;
  const isJobMove = isCareer
    && JOB_POSTING_INTENT.test(comparisonText)
    && !(NON_POSTING_CAREER_INTENT.test(textA) && NON_POSTING_CAREER_INTENT.test(textB));
  const needJobDetails = isCareer;
  // 직업정보가 없으면 전체 유사 집단으로 자동 완화한다. 입력 화면 진행을 막지는 않는다.
  const jobDetailsMissing = needJobDetails && profile.occupation_group == null;
  // 성별은 유사집단 매칭의 정확도를 높이는 선택 정보다.
  // 비어 있어도 전체 집단 기준으로 비교할 수 있으므로 진행 자체를 막지 않는다.
  const blocked = !normalizedA || !normalizedB || duplicate;
  const needMajor = scenarioDomains.a.includes("education") || scenarioDomains.b.includes("education");
  const emotions = detectEmotions(`${diary} ${textA} ${textB}`);
  // 위 useEffect 의 GENERIC_COUNTERPART 상속은 "현상 유지·지금처럼" 류만 잡는다.
  // 그 밖에도 단독으로는 영역이 없는 B가 많아("실무 경험 더 쌓기", 앱이 제안하는
  // 관련대안 칩 다수) 여기서 한 번 더 상속한다. 이걸 startComparison 에서만 하면
  // 아래 intake 가 빈 영역으로 계산돼 B의 추가 질문·결과변수·context.domain 이
  // 전부 '장기 가치'로 굳는다 — 영역 태그는 직업인데 백엔드로는 long_term_values
  // 가 나가던 자리다.
  const personalizationCount = Number(isJobMove && (postings || []).length > 0)
    + Number((profile?.career_values || []).length > 0)
    + Number(Boolean(diary.trim()));
  // "지금처럼 유지"처럼 자체 키워드가 없는 쪽은 반대 선택지의 영역을 상속한다.
  // intake도 이 확정 영역으로 계산해야 화면 태그와 백엔드 context.domain이 일치한다.
  const inheritedDomains = {
    a: scenarioDomains.a?.length ? scenarioDomains.a : scenarioDomains.b || [],
    b: scenarioDomains.b?.length ? scenarioDomains.b : scenarioDomains.a || [],
  };
  const intakeA = questionsForChoice(textA, inheritedDomains.a);
  const intakeB = questionsForChoice(textB, inheritedDomains.b);

  function updateContext(side, intake, key, value) {
    const field = side.toLowerCase();
    setScenarioContexts((prev) => ({
      ...prev,
      [field]: { event: intake.event, event_label: intake.eventLabel, domain: intake.domain, answers: { ...(prev[field]?.answers || {}), [key]: value } },
    }));
  }

  async function startComparison() {
    const fallback = (choice) => {
      if (["이직", "유지"].includes(choice)) return ["career"];
      if (choice === "진학") return ["education"];
      if (choice === "창업") return ["business"];
      // 쉬어가기는 일만의 결정이 아니다 — 대개 건강·소진이 같이 걸려 있어
      // 두 영역을 함께 켠다(9영역 근거가 한쪽만 붙으면 판단 재료가 반쪽이 된다).
      if (choice === "휴식") return ["career", "health"];
      return ["long_term_values"];
    };
    // 영역을 먼저 확정하고, 그 영역으로 intake 를 다시 계산한다. 순서가 반대면
    // 전송되는 choice_*_context.domain 이 영역 태그와 어긋난다(백엔드는 이 값을
    // 서사 프롬프트와 KOWEPS 사건 판정에 쓴다).
    let resolved = {
      a: inheritedDomains.a.length ? inheritedDomains.a : fallback(choices.a),
      b: inheritedDomains.b.length ? inheritedDomains.b : fallback(choices.b),
    };
    let resolvedA = questionsForChoice(textA, resolved.a);
    let resolvedB = questionsForChoice(textB, resolved.b);
    setClassifying(true);
    try {
      const canonical = await classifyChoicePair({
        choiceA: textA,
        choiceB: textB,
        domainsA: resolved.a,
        domainsB: resolved.b,
      });
      resolved = {
        a: canonical.A?.domains?.length ? canonical.A.domains : resolved.a,
        b: canonical.B?.domains?.length ? canonical.B.domains : resolved.b,
      };
      resolvedA = {
        ...resolvedA,
        event: canonical.A?.event || resolvedA.event,
        eventLabel: canonical.A?.event_label || resolvedA.eventLabel,
        domain: canonical.A?.domain || resolvedA.domain,
      };
      resolvedB = {
        ...resolvedB,
        event: canonical.B?.event || resolvedB.event,
        eventLabel: canonical.B?.event_label || resolvedB.eventLabel,
        domain: canonical.B?.domain || resolvedB.domain,
      };
    } catch {
      // 서버가 꺼진 로컬·오프라인 환경에서는 기존 프론트 감지값으로 진행한다.
    } finally {
      setClassifying(false);
    }
    const nextContexts = {
      a: { event: resolvedA.event, event_label: resolvedA.eventLabel, domain: resolvedA.domain, answers: scenarioContexts.a?.answers || {} },
      b: { event: resolvedB.event, event_label: resolvedB.eventLabel, domain: resolvedB.domain, answers: scenarioContexts.b?.answers || {} },
    };
    setScenarioContexts(nextContexts);
    setScenarioDomains(resolved);
    // 담아둔 재료는 시뮬레이션과 함께 분석을 시작한다(결과 화면에서 확인).
    if ([...resolved.a, ...resolved.b].includes("relationship")) analyzeTalks(talks);
    if ([...resolved.a, ...resolved.b].some((domain) => CAREER_DETAIL_DOMAINS.has(domain)) && (postings || []).length) analyzePostings(postings, textA || choices.a);
    // React 상태 반영과 라우트 이동이 같은 틱에 일어나면 Simulate가 이전 context를
    // 읽을 수 있다. 확정 분류를 navigation state로도 직접 넘겨 첫 API 요청부터 쓴다.
    navigate("/simulate", { state: { classifiedDomains: resolved, classifiedContexts: nextContexts } });
  }

  function focusFirstChoice() {
    setFocused("a");
    requestAnimationFrame(() => {
      const input = document.getElementById("choice-a-input");
      input?.scrollIntoView({ behavior: "smooth", block: "center" });
      window.setTimeout(() => input?.focus(), 350);
    });
  }

  return (
    <div className="-mx-5 -mt-1 min-h-full px-5 pb-7 pt-3 lg:mx-auto lg:px-4 lg:pb-12 lg:pt-0 xl:px-6">
      <section className="relative overflow-hidden py-7 lg:grid lg:min-h-[310px] lg:grid-cols-[.9fr_1.1fr] lg:items-center lg:gap-10 lg:py-10">
        <div className="relative z-10 max-w-[630px]">
          <div className="text-[11px] font-bold tracking-[.08em] text-violet-300 lg:text-[13px]">두 미래를 비교하고, 더 나은 선택을 발견하세요</div>
          <h1 className="mt-2 text-[32px] font-medium leading-[1.15] tracking-[-.055em] text-ink sm:text-[38px] lg:text-[48px] xl:text-[54px]">
            오늘은 어떤 갈림길을<br className="hidden sm:block" /> 비춰볼까요?
          </h1>
          <p className="mt-3 max-w-[540px] text-[12px] leading-6 text-sub lg:text-[14px]">두 가지 선택지의 미래를 시뮬레이션하고, 나에게 더 잘 맞는 길을 데이터와 이야기로 비교해보세요.</p>
          <div className="mt-5 flex flex-col gap-2.5 sm:flex-row">
            <button type="button" data-tour="simulate-start" onClick={focusFirstChoice} className="tap flex items-center justify-center gap-2 rounded-xl border border-violet-300/50 bg-gradient-to-r from-[#7250DB] to-[#8B61E8] px-6 py-3.5 text-[13px] font-bold text-white shadow-[0_12px_34px_rgba(114,80,219,.28)]">
              <Sparkles size={16} /> 시뮬레이션 시작
            </button>
            <button type="button" onClick={() => navigate("/archive")} className="tap flex items-center justify-center gap-2 rounded-xl border border-white/15 bg-white/[.035] px-6 py-3.5 text-[13px] font-semibold text-sub hover:bg-white/[.07]">
              <History size={16} /> 최근 시뮬 이어보기
            </button>
          </div>
        </div>

        <div className="pointer-events-none relative hidden h-[270px] lg:block" aria-hidden="true">
          <div className="absolute left-1/2 top-1/2 h-[170px] w-[400px] -translate-x-1/2 -translate-y-1/2 rounded-[50%] border border-violet-300/25 [transform:translate(-50%,-50%)_rotate(-8deg)]" />
          <div className="absolute left-1/2 top-1/2 h-[110px] w-[510px] -translate-x-1/2 -translate-y-1/2 rounded-[50%] border border-[#F5C86B]/20 [transform:translate(-50%,-50%)_rotate(8deg)]" />
          <div className="absolute left-1/2 top-1/2 h-44 w-44 -translate-x-1/2 -translate-y-1/2 overflow-hidden rounded-full border border-violet-200/40 bg-[#17102D] shadow-[0_0_35px_rgba(139,108,207,.62),18px_2px_35px_rgba(245,180,107,.28)]">
            <img src="/planet-textures/career.png" alt="" className="h-full w-full object-cover" />
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_35%_28%,rgba(255,255,255,.28),transparent_24%),linear-gradient(105deg,transparent_45%,rgba(0,0,0,.7)_88%)]" />
          </div>
          <div className="absolute left-[13%] top-[38%] h-9 w-9 overflow-hidden rounded-full border border-violet-300/40 shadow-[0_0_18px_rgba(139,108,207,.45)]"><img src="/planet-textures/growth.png" alt="" className="h-full w-full object-cover" /></div>
          <div className="absolute right-[10%] top-[46%] h-8 w-8 overflow-hidden rounded-full border border-[#F5C86B]/50 shadow-[0_0_18px_rgba(245,200,107,.4)]"><img src="/planet-textures/relation.png" alt="" className="h-full w-full object-cover" /></div>
          <span className="absolute left-[6%] top-[22%] h-1 w-1 rounded-full bg-white shadow-[0_0_9px_2px_white]" />
          <span className="absolute right-[18%] top-[18%] h-1.5 w-1.5 rounded-full bg-[#D9C8FF] shadow-[0_0_12px_3px_#9B72F2]" />
          <span className="absolute bottom-[15%] left-[28%] h-1 w-1 rounded-full bg-[#F5C86B] shadow-[0_0_10px_2px_#F5C86B]" />
        </div>
      </section>
      {conversationFutures && (
        <button type="button" onClick={applyConversationFutures} className="tap mt-3 flex w-full items-center gap-3 rounded-[18px] border border-violet-400/40 bg-[#1D1730] px-4 py-3.5 text-left transition-colors hover:bg-[#16264a] lg:max-w-[720px]">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-violet-500/15 text-violet-300">
            <Mascot which="cosmo" size={24} />
          </span>
          <span className="min-w-0 flex-1">
            <span className="block text-[13px] font-semibold text-violet-200">코스모와 나눈 대화에서 두 미래를 찾았어요</span>
            <span className="block text-[11px] text-sub">{conversationFutures[0].label} vs {conversationFutures[1].label} · 눌러서 채운 뒤 수정할 수 있어요</span>
          </span>
        </button>
      )}
      {rumination.prompt && (
        <button type="button" onClick={applySuggestedCompare} className="tap mt-3 flex w-full items-center gap-3 rounded-[18px] border border-cyan/40 bg-[#1D1730] px-4 py-3.5 text-left transition-colors hover:bg-[#16264a] lg:mt-5 lg:max-w-[720px] lg:px-5 lg:py-4">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-violet-500/15 text-violet-400">
            <GitCompareArrows size={18} strokeWidth={2} />
          </span>
          <span className="min-w-0 flex-1">
            <span className="block text-[13px] font-semibold text-cyan">최근 {rumination.windowDays}일 동안 {rumination.domain.label} 이야기가 {rumination.count}일 나타났어요</span>
            <span className="block text-[11px] text-sub">{rumination.compare.action}을 추천해요 · 누르면 선택지가 채워져요</span>
          </span>
        </button>
      )}

      <section className="mt-4 overflow-hidden rounded-[24px] border border-white/[.08] bg-[#08111F]/65 shadow-[0_20px_60px_rgba(0,0,0,.24)] lg:mt-6 lg:rounded-[26px]">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/10 px-4 py-3.5 lg:px-7">
          <div className="flex items-baseline gap-3">
            <h2 className="text-[14px] font-bold text-ink lg:text-[16px]">빠른 비교 시작</h2>
            <p className="hidden text-[10px] text-mut sm:block">두 선택지를 입력하고, 나의 두 미래를 비교해보세요.</p>
          </div>
          <CompactFuturePicker futureYears={futureYears} setFutureYears={setFutureYears} />
        </div>
      <div data-tour="choices" className="relative flex min-h-0 flex-col overflow-hidden lg:flex-row">
        <ChoicePanel
          inputId="choice-a-input"
          side="A" text={textA} domains={scenarioDomains.a} domainAuto={domainAuto.a}
          intake={intakeA} context={scenarioContexts.a}
          active={focused === "a"} suggestions={suggestComparePrompts({ side: "a", recentDomains: rumination.domains, valueRanking: profile.value_ranking, otherText: textB })}
          suggestionLabel="이런 식으로 시작할 수 있어요"
          onFocus={() => setFocused("a")} onText={(value) => onText("A", value)}
          onSuggestion={(value) => chooseSuggestion("a", value)}
          onDomain={(key) => toggleDomain("A", key)} onRedetect={() => resetDomainDetection("A")}
          onConditionChange={(key, value) => updateContext("a", intakeA, key, value)}
        />

        {/* 실제 flex 구분 영역. 패널의 활성 너비가 변해도 VS가 콘텐츠 위로 겹치지 않는다. */}
        <div className="pointer-events-none relative z-20 flex h-16 shrink-0 items-center justify-center lg:h-auto lg:w-16 lg:flex-col">
          <span className="absolute left-0 right-0 top-1/2 h-px bg-gradient-to-r from-transparent via-white/20 to-transparent lg:bottom-0 lg:left-1/2 lg:right-auto lg:top-0 lg:h-auto lg:w-px lg:bg-gradient-to-b" />
          <span className="flex h-12 w-12 items-center justify-center rounded-full border border-white/15 bg-[#07101E] text-[13px] font-black text-white shadow-[0_0_30px_rgba(75,126,255,.22)]">VS</span>
        </div>

        <ChoicePanel
          inputId="choice-b-input"
          side="B" text={textB} domains={scenarioDomains.b} domainAuto={domainAuto.b}
          intake={intakeB} context={scenarioContexts.b}
          active={focused === "b"} suggestions={suggestComparePrompts({ side: "b", recentDomains: rumination.domains, valueRanking: profile.value_ranking, otherText: textA })}
          suggestionLabel={textA.trim() ? "A와 비교할 수 있는 다른 길이에요" : "이런 식으로 시작할 수 있어요"}
          onFocus={() => setFocused("b")} onText={(value) => onText("B", value)}
          onSuggestion={(value) => chooseSuggestion("b", value)}
          onDomain={(key) => toggleDomain("B", key)} onRedetect={() => resetDomainDetection("B")}
          onConditionChange={(key, value) => updateContext("b", intakeB, key, value)}
        />
      </div>
      </section>

      {duplicate && <Caption className="text-danger">두 미래가 같아요. 회사·조건·상황 중 하나를 다르게 적어주세요.</Caption>}

      {needJobDetails && (
        <section className="mt-4 animate-fade rounded-[22px] border border-cyan/30 bg-[#0B1729]/90 p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="text-[13px] font-bold text-ink">일과 관련된 비교를 더 정확히 하려면</div>
              <div className="mt-1 text-[11px] leading-relaxed text-muted">이직·쉬어가기처럼 일이 걸린 시뮬레이션에서 쓰는 값이라 한 번만 입력하면 돼요. 다음 비교에도 다시 사용할 수 있어요.</div>
              <p className="mt-1 text-[11px] leading-relaxed text-mut">유사 조건 비교에 사용하며, 선택 결과를 확정하는 정보는 아니에요.</p>
            </div>
            <span className="shrink-0 rounded-full bg-cyan/15 px-2 py-1 text-[9px] font-bold text-cyan">선택 입력</span>
          </div>

          <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <JobField label="현재 직종 대분류">
              <select value={profile.occupation_group ?? ""} onChange={(event) => setProfile((prev) => ({ ...prev, occupation_group: event.target.value === "" ? null : Number(event.target.value) }))} className="tap w-full rounded-xl border border-line bg-[#0E1424] px-3 py-2.5 text-[12px] text-ink outline-none focus:border-cyan">
                <option value="">선택해주세요</option>
                {OCCUPATION_GROUPS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </JobField>

            <JobField label="고용 형태 · 선택">
              <select value={profile.employment_status ?? ""} onChange={(event) => setProfile((prev) => ({ ...prev, employment_status: event.target.value === "" ? null : Number(event.target.value) }))} className="tap w-full rounded-xl border border-line bg-[#0E1424] px-3 py-2.5 text-[12px] text-ink outline-none focus:border-cyan">
                <option value="">선택해주세요</option>
                {EMPLOYMENT_STATUSES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </JobField>

            <JobField label="현 일자리 근속기간 · 선택">
              <div className="flex items-center gap-2">
                <input type="number" min="0" max="50" step="0.5" value={profile.tenure_years ?? ""} placeholder="예: 2.5" onChange={(event) => setProfile((prev) => ({ ...prev, tenure_years: event.target.value === "" ? null : Number(event.target.value) }))} className="w-full rounded-xl border border-line bg-[#0E1424] px-3 py-2.5 text-[12px] text-ink outline-none placeholder:text-mut focus:border-cyan" />
                <span className="shrink-0 text-[11px] text-mut">년</span>
              </div>
            </JobField>

            <JobField label="회사 규모 · 선택">
              <select value={profile.firm_size ?? ""} onChange={(event) => setProfile((prev) => ({ ...prev, firm_size: event.target.value === "" ? null : Number(event.target.value) }))} className="tap w-full rounded-xl border border-line bg-[#0E1424] px-3 py-2.5 text-[12px] text-ink outline-none focus:border-cyan">
                <option value="">입력하지 않아도 돼요</option>
                {FIRM_SIZES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </JobField>
          </div>
        </section>
      )}

      {needMajor && (
        <details className="group mt-3 w-fit max-w-full rounded-xl border border-white/10 bg-[#0B1423]/80">
          <summary className="tap flex cursor-pointer list-none items-center gap-2 px-3 py-2 text-[11px] font-semibold text-sub [&::-webkit-details-marker]:hidden">
            <span>전공 계열</span>
            <span className="font-normal text-mut">{profile.major || "선택사항"}</span>
            <span className="text-[9px] text-mut transition-transform group-open:rotate-180">▼</span>
          </summary>
          <div className="border-t border-white/10 p-2.5">
            <select value={profile.major || ""} onChange={(event) => setProfile((prev) => ({ ...prev, major: event.target.value }))} className="tap min-w-[180px] rounded-lg border border-line bg-[#0E1424] px-3 py-2 text-[12px] text-ink outline-none focus:border-cyan">
              <option value="">선택하지 않음</option>
              {MAJOR_FIELDS.map((major) => <option key={major} value={major}>{major}</option>)}
            </select>
          </div>
        </details>
      )}

      {/* 지원하려는 공고가 있으면 붙여넣기 → 요구역량 + 내 성향과의 접점·마찰점.
          공고 수집은 약관 문제가 커서 크롤링 대신 붙여넣기로 받는다. */}
      {/* 선택지가 어느 영역인지에 따라 담는 재료가 달라진다.
          관계면 그 관계의 대화를, 그 밖이면 지원하려는 공고를. */}
      {/* 관계면 대화·연락 내역 하나만. */}
      {isRelationship && <RelationshipInput talks={talks} setTalks={setTalks} />}

      {normalizedA && normalizedB && (isCareer ? (
        <section className="mt-4 animate-fade rounded-[22px] border border-white/10 bg-[#0B1423]/80 p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h2 className="text-[13px] font-bold text-ink">더 정교하게 보고 싶다면</h2>
              <p className="mt-1 text-[10px] text-mut">선택 사항 · 입력하지 않아도 바로 비교할 수 있어요.</p>
            </div>
            <span className="rounded-full bg-violet-500/15 px-2.5 py-1 text-[10px] font-bold text-violet-200">{personalizationCount} / {isJobMove ? 3 : 2} 추가됨</span>
          </div>
          <div className="mt-3 border-t border-white/10 pt-1">
            {isJobMove && <JobPostingInput postings={postings} setPostings={setPostings} />}
            <ValueTestSection profile={profile} navigate={navigate} />
            <DiaryContextSection diary={diary} setDiary={setDiary} emotions={emotions} />
          </div>
          <p className="mt-3 text-[10px] text-violet-200">현재 개인화 수준: {personalizationCount >= (isJobMove ? 3 : 2) ? "정교함" : personalizationCount > 0 ? "상세" : "기본"}</p>
        </section>
      ) : (
        <DiaryContextSection diary={diary} setDiary={setDiary} emotions={emotions} />
      ))}

      <button type="button" disabled={blocked || classifying} onClick={startComparison} className={`tap mt-4 flex w-full items-center justify-center gap-2 rounded-full py-4 text-[15px] font-bold transition-all lg:ml-auto lg:max-w-[420px] lg:py-4.5 ${blocked || classifying ? "bg-white/10 text-mut" : "bg-[#F4F0FF] text-[#08101D] shadow-[0_14px_34px_rgba(139,108,207,.25)]"}`}>
        {classifying ? "선택 영역 확인 중…" : "두 미래 비교 시작하기"} {!classifying && <ArrowRight size={17} />}
      </button>
    </div>
  );
}

function DiaryContextSection({ diary, setDiary, emotions }) {
  return (
    <details className="smooth-details mt-3 rounded-2xl border border-white/10 bg-[#0B1423]/80 px-3.5 py-3">
      <summary className="cursor-pointer text-[11px] font-semibold text-sub">
        🙂 결과 설명에 반영할 현재 마음 · 선택 {diary.trim() && <span className="ml-1 text-[10px] text-[#C7B5F2]">추가됨</span>}
      </summary>
      <div className="details-body">
        <div className="details-body-inner pt-2">
          <p className="text-[10px] leading-4 text-mut">예측 숫자나 A/B 결과는 바꾸지 않아요. 감정에 맞는 심리 근거, 설명의 어조와 주의 안내에만 반영해요.</p>
          <input value={diary} onChange={(event) => setDiary(event.target.value)} placeholder="왜 이 선택이 망설여지는지 한 줄로 적어보세요" className="mt-3 w-full rounded-xl border border-line bg-bg px-3 py-2.5 text-xs text-ink outline-none focus:border-cyan" />
          {emotions.length > 0 && <Caption>감정은 결과 설명의 말투와 맥락에 반영됩니다.</Caption>}
        </div>
      </div>
    </details>
  );
}

// 1~10년 전부 고를 수 있다(소득 궤적은 매 연차 실측이 있다). 기본은 자주 쓰는
// 값(1·3·5·10)만 보여주고 "더보기"로 펼친다 — 열 개를 다 늘어놓으면 좁은
// 폭에서 두 줄로 꺾여 부산했다.
function CompactFuturePicker({ futureYears, setFutureYears }) {
  const beyondWellbeing = futureYears > WELLBEING_MAX_YEAR;
  return (
    <FutureYearPicker
      className="w-full sm:w-auto"
      years={futureYears}
      onChange={setFutureYears}
      label="몇 년 뒤?"
      ariaLabel="미래 비교 시점"
      titleFor={(years) => `${years}년 후 비교`}
      note={
        // 만족도만 관측 천장이 낮다 — 고르기 전에 미리 알린다. 막지는 않는다:
        // 소득·재직기간은 10년까지 실측이 있어서 함께 막으면 그쪽이 손해다.
        beyondWellbeing && (
          <p className="mt-1.5 text-[9px] leading-4 text-mut sm:text-right">
            삶의 만족은 {WELLBEING_MAX_YEAR}년까지만 관측돼요 — 소득·재직기간은 {futureYears}년 기준으로 나옵니다.
          </p>
        )
      }
    />
  );
}

function ChoiceConditions({ side, intake, context, onChange }) {
  const color = side === "A" ? "#9B72F2" : "#F39A4A";
  const answers = context?.answers || {};
  const completed = intake.questions.filter((question) => String(answers[question.key] || "").trim());
  const hasAnswers = completed.length > 0;
  const [open, setOpen] = useState(() => hasAnswers);

  if (!intake.questions.length) return null;

  return (
    <div
      className={`mt-3 overflow-hidden rounded-xl border bg-[#0B1424]/75 transition-colors ${hasAnswers ? "border-white/12" : "border-dashed border-white/15"}`}
      style={hasAnswers ? { borderColor: `${color}35` } : undefined}
    >
      <button
        type="button"
        onClick={(event) => { event.stopPropagation(); setOpen((value) => !value); }}
        className="tap flex w-full items-center justify-between gap-3 px-3.5 py-3 text-left"
        aria-expanded={open}
      >
        <span className="min-w-0">
          <span className="block text-[11px] font-bold text-ink">
            <span className="mr-2 inline-flex h-4 w-4 items-center justify-center rounded border border-white/20 bg-black/15 text-[10px]" style={{ color }}>
              {open ? "−" : "+"}
            </span>
            {hasAnswers ? `조건 ${completed.length}개 입력됨` : "조건 더 알려주기"}
          </span>
          {!hasAnswers && <span className="mt-1 block truncate text-[9px] text-mut">금액·기간·상황 등 · 입력하지 않아도 비교할 수 있어요</span>}
          {hasAnswers && !open && (
            <span className="mt-1 block truncate text-[9px] text-mut">
              {completed.map((question) => `${question.label} ${answers[question.key]}`).join(" · ")}
            </span>
          )}
        </span>
        <span className="shrink-0 rounded-full bg-white/[.06] px-2 py-1 text-[9px]" style={{ color }}>
          {hasAnswers ? "수정" : "선택 입력"}
        </span>
      </button>
      {open && (
        <div className="grid gap-3 border-t border-white/[.07] px-3.5 pb-3.5 pt-3 sm:grid-cols-2">
          {intake.questions.map((question) => (
            <label key={question.key} className="block">
              <span className="mb-1 block text-[10px] text-sub">{question.label}</span>
              <input value={answers[question.key] || ""} onChange={(event) => onChange(question.key, event.target.value)} placeholder={question.placeholder} className="w-full rounded-lg border border-white/15 bg-[#101A31] px-3 py-2.5 text-[11px] font-semibold text-ink outline-none placeholder:font-normal placeholder:text-mut focus:border-violet-400" />
            </label>
          ))}
        </div>
      )}
    </div>
  );
}

// 직업가치관검사 단독 섹션 — 공고 없이도 검사만 할 수 있게. 결과는 프로필에 남아
// 이후 공고 분석·시뮬레이션 서사가 계속 쓴다.
function ValueTestSection({ profile, navigate }) {
  const done = (profile?.career_values || []).length > 0;

  return (
    <div className="mt-3 rounded-2xl border border-white/10 bg-[#0B1423]/80 px-3.5 py-3">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[11px] font-semibold text-sub">✨ 직업 가치관</p>
          <p className="mt-1 truncate text-[10px] text-mut">
            {done ? `${profile.career_values.slice(0, 3).map((v) => v.name).join(" > ")} 반영 중` : "한 번 검사하면 이후 직업 비교에도 계속 반영돼요."}
          </p>
        </div>
        <button type="button" onClick={() => navigate("/settings?careerValues=1")} className="tap shrink-0 rounded-xl border border-violet-400/35 bg-violet-500/10 px-3 text-[10px] font-bold text-violet-200">
          {done ? "결과 보기" : "설정에서 검사"}
        </button>
      </div>
    </div>
  );
}

function JobBlock({ title, tone = "#8B6CCF", children }) {
  return (
    <div className="rounded-xl border border-white/[.07] bg-black/15 px-3 py-2.5">
      <p className="text-[10px] font-bold" style={{ color: tone }}>{title}</p>
      <ul className="mt-1.5 space-y-1.5">{children}</ul>
    </div>
  );
}

function JobField({ label, children }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-[10px] font-semibold text-sub">{label}</span>
      {children}
    </label>
  );
}

function ChoicePanel({ inputId, side, text, domains, domainAuto, intake, context, active, suggestions, suggestionLabel, onFocus, onText, onSuggestion, onDomain, onRedetect, onConditionChange }) {
  const [editingDomains, setEditingDomains] = useState(false);
  const isA = side === "A";
  const accentText = isA ? "text-[#8B6CCF]" : "text-[#FFB85C]";

  return (
    <section onClick={onFocus} className="relative min-h-0 min-w-0 flex-1 basis-0 overflow-hidden px-4 py-4 lg:px-7 lg:py-6 xl:px-9">
      <div className={`text-[11px] font-black tracking-[.12em] ${accentText}`}>CHOICE {side}</div>
      <textarea
        id={inputId}
        value={text}
        onFocus={onFocus}
        onChange={(event) => onText(event.target.value)}
        rows={1}
        maxLength={180}
        placeholder={isA ? "첫 번째 길을 적어주세요" : "두 번째 길을 적어주세요"}
        className={`mt-2 block max-h-[110px] min-h-[62px] w-full min-w-0 max-w-full resize-none overflow-y-auto break-words rounded-xl border bg-[#10182D] px-4 py-4 text-[17px] font-bold leading-[1.4] tracking-[-.025em] text-ink outline-none placeholder:text-white/25 lg:mt-3 lg:text-[20px] ${isA ? "border-violet-400/35 focus:border-violet-400/75" : "border-orange-400/35 focus:border-orange-300/75"}`}
      />

      {!text.trim() && active && (
        <div className="mt-3 min-w-0 overflow-hidden">
          <div className="mb-2 text-[10px] text-mut">{suggestionLabel}</div>
          <div className="flex min-w-0 flex-wrap gap-1.5">
            {suggestions.map((item) => <button key={item.key} type="button" onClick={(event) => { event.stopPropagation(); onSuggestion(item.text); }} className={`tap max-w-full truncate rounded-full border border-white/10 bg-white/[.06] px-2.5 py-1.5 text-[10px] ${accentText}`}>{item.text}</button>)}
          </div>
        </div>
      )}

      {text.trim() && (
        <div className="mt-2 min-w-0 overflow-hidden">
          <div className="flex items-center gap-2 px-0.5 text-[10px]">
            <span className="font-semibold text-sub">분석 영역</span>
            <span className="min-w-0 flex-1 truncate text-mut">{domains.map(domainLabel).join(" · ") || "영역을 확인해주세요"}</span>
            <button type="button" onClick={(event) => { event.stopPropagation(); setEditingDomains((value) => !value); }} className={accentText}>{editingDomains ? "닫기" : "수정"}</button>
          </div>
          {editingDomains && (
            <div className="mt-2">
              <p className="mb-2 text-[9px] text-mut">대표 영역은 자동으로 하나만 골라요. 관련 영역은 직접 추가할 수 있어요.</p>
              <div className="grid grid-cols-3 gap-1.5">
                {LIFE_DOMAINS.map((domain) => {
                  const selected = domains.includes(domain.key);
                  const DomainIcon = DOMAIN_ICONS[domain.key];
                  return <button type="button" key={domain.key} aria-pressed={selected} onClick={(event) => { event.stopPropagation(); onDomain(domain.key); }} className={`tap flex min-w-0 overflow-hidden items-center justify-center gap-1 rounded-xl border px-1.5 py-1.5 text-[9px] ${selected ? `${isA ? "border-[#8B6CCF] bg-[#211832]" : "border-[#D8933E] bg-[#352511]"} ${accentText}` : "border-white/10 bg-black/10 text-mut"}`}>{DomainIcon && <DomainIcon size={11} className="shrink-0 text-violet-400" />}<span className="truncate">{domain.label}</span></button>;
                })}
                {!domainAuto && <button type="button" onClick={(event) => { event.stopPropagation(); onRedetect(); }} className={`col-span-3 py-1 text-[10px] ${accentText}`}>자동 감지 다시 적용</button>}
              </div>
            </div>
          )}
        </div>
      )}

      {text.trim() && (
        <ChoiceConditions side={side} intake={intake} context={context} onChange={onConditionChange} />
      )}
    </section>
  );
}
