import { createContext, useContext, useEffect, useMemo, useRef, useState } from "react";
import { getPredictionPair } from "./prediction.js";
import { DEFAULT_AVATAR } from "./avatarOptions.js";
import { generateSceneImages, runCompareRaw, runSimulateRaw } from "../api.js";
import { mapSimulateToPair } from "./simulateAdapter.js";
import { avatarToPngBlob } from "./avatarImage.js";
import { avatarGenerationSpec } from "./avatarOptions.js";
import { initDemoFromUrl, noteSimulationRun, recordScenario, loadUniverse } from "./myUniverse.js";
import { deriveDiaryInsights } from "./diarySignals.js";
import { toPlanetKey } from "./choices.js";
import storage from "./safeStorage.js";

// 결과 데이터 + 온보딩 프로필을 한 곳에 모으는 컨텍스트.
// runSimulation() 이 선택(choices)+심정(diary)으로 결과 쌍{a,b}을 만든다.
// ※ 지금은 목업(getPredictionPair). 백엔드 실연결은 api.js(runSimulate)를
//   내 결과 형태로 확장해 여기서 호출하면 됨(파일은 보존해둠).
const ResultContext = createContext(null);

// 발표/체험 링크의 ?demo=1 요청이 있을 때만 나의 우주 예시 기록을 준비한다.
initDemoFromUrl();

const DEFAULT_PROFILE = {
  name: "",
  age: 29,
  sex: null, // GOMS 코드: "1" 남 / "2" 여. 입력 없이 임의 기본값을 사용하지 않는다.
  sexConfirmed: false,
  major: "", // 전공 계열 — 교육 비교에서 사용자가 선택한 경우에만 사용
  // 직종은 기본값을 두지 않는다. 예전 기본값 "사회계열" 은 온보딩 직종 목록
  // (profileOptions.OCCUPATIONS)에 아예 없는 값이라, 사용자는 고른 적도 없고
  // 드롭다운에서 찾을 수도 없는 직종이 화면에 박혀 있었다.
  occupation: "",
  income: null, // 온보딩에서 직접 입력 → 백엔드 monthly_wage
  edu_level: 7, // 대졸
  occupation_group: null, // KSCO 직종 대분류 1~9 — 이직 시뮬레이션에서 수집
  employment_status: null, // KLIPS 종사상지위 1~5
  tenure_years: null, // 현재 일자리 근속연수
  firm_size: null, // KLIPS 기업규모 코드 1~11
  values: [], // qmode UI 표시용 가치 강제순위 — 온보딩에서 사용자가 직접 선택
  value_ranking: [], // 가치 카드 id 중요한 순 → 개인화 입력(백엔드가 가중치로 변환)
  mbti: "", // 심리 성향 input
  psych_answers: {}, // { D2:"…", D1:"…", D4:"…" } 서술형 답변 → disposition_block 로 전송
  avatarConfig: DEFAULT_AVATAR, // 아바타 빌더 선택(피부·머리·안경·배경)
};

// 프로필 영속 — 온보딩 입력·가치관 검사 결과가 새로고침에 날아가지 않도록 저장한다.
// (검사는 28문항 10분짜리라 다시 하라고 할 수 없다.)
const PROFILE_KEY = "pm.profile.v1";

function loadProfile() {
  try {
    const saved = JSON.parse(storage.getItem(PROFILE_KEY) || "null");
    if (!saved) return DEFAULT_PROFILE;
    const merged = { ...DEFAULT_PROFILE, ...saved };
    // 이전 버전은 입력 없이 sex="2"를 저장했다. 사용자가 직접 고른 기록이 없는
    // 값은 신뢰하지 않고 다시 선택하게 한다.
    if (!saved.sexConfirmed) merged.sex = null;
    return merged;
  } catch {
    return DEFAULT_PROFILE;
  }
}

// 아직 아무것도 돌리지 않은 상태의 결과. 첫 마운트와 resetSession 이 같은 값을 쓴다.
function blankResult() {
  return { ...getPredictionPair({ profile: DEFAULT_PROFILE, choiceA: "이직", choiceB: "유지" }), dataMode: "demo" };
}

/**
 * 시뮬레이션 요청에 실을 일기 신호를 모은다.
 *
 * 두 갈래를 **함께** 싣는다.
 *   chat    대화형 일기(ChatDiary)가 LLM 으로 뽑아 둔 insights. 가장 정확하지만
 *           앱에서 직접 대화하며 쓴 일기에만 있다.
 *   records 기록 자체에서 로컬로 파생한 신호(diarySignals.deriveDiaryInsights).
 *
 * 예전엔 chat 만 봤다. 그래서 '예시 1년치로 시작'으로 237개를 심어도 그 기록에는
 * insights 가 없어(personas/seed.js 의 addCheckin 이 안 채운다) 여기서 null 이 나갔고,
 * 시뮬레이션은 일기가 0개인 것과 똑같은 입력으로 돌았다 — 결과가 빈약했던 이유다.
 * 페르소나 체험도 같은 경로라 증상이 같았다.
 */
function collectDiaryInsights(limit = 7) {
  const universe = loadUniverse();
  const checkins = universe.checkins || [];
  const recent = checkins.filter((item) => item?.insights).slice(-limit);

  let chat = null;
  if (recent.length) {
    const unique = (items, max = 8) => [...new Set(items.filter(Boolean))].slice(0, max);
    const pick = (key) => unique(recent.flatMap((item) => item.insights?.[key] || []));
    chat = {
      decision_topics: unique(recent.map((item) => item.insights?.decision_topic)),
      goals: pick("goals"),
      priorities: pick("priorities"),
      constraints: pick("constraints"),
      concerns: pick("concerns"),
      preference_signals: recent
        .flatMap((item) => item.insights?.preference_signals || [])
        .filter((item) => item?.label && item?.evidence)
        .slice(-8),
    };
  }

  // 파생은 LLM 없이 로컬 계산이라 동기로 부른다. diarySignals 는 이미 12개 모듈이
  // 정적으로 쓰고 있어 동적 import 로 미뤄도 청크가 안 갈린다(vite 가 경고로 알려준다).
  let records = null;
  try {
    records = deriveDiaryInsights({}, universe);
  } catch { /* 파생 실패는 시뮬레이션을 막지 않는다 */ }

  if (!chat && !records) return null;
  return {
    source: chat && records ? "chat_diaries+records" : chat ? "recent_chat_diaries" : "diary_records",
    ...(chat || {}),
    ...(records ? { record_signals: records } : {}),
  };
}

export function ResultProvider({ children }) {
  const [profile, setProfile] = useState(loadProfile);
  useEffect(() => {
    try {
      storage.setItem(PROFILE_KEY, JSON.stringify(profile));
    } catch { /* 저장 실패는 무시 — 기능은 계속 동작 */ }
  }, [profile]);
  const [choices, setChoices] = useState({ a: "이직", b: "유지" });
  const [scenarioTexts, setScenarioTexts] = useState({ a: "", b: "" });
  const [scenarioDomains, setScenarioDomains] = useState({ a: [], b: [] });
  const [scenarioContexts, setScenarioContexts] = useState({ a: {}, b: {} });
  const [futureYears, setFutureYears] = useState(3);
  const [diary, setDiary] = useState("");
  const [result, setResult] = useState(blankResult);
  // 한 번이라도 실제 비교를 실행했다면 시뮬레이션 탭은 입력 화면이 아니라
  // 마지막 결과로 돌아간다. 라우트가 바뀌어도 Provider가 유지되므로 결과도 보존된다.
  const [hasSimulationResult, setHasSimulationResult] = useState(false);
  const [onboarded, setOnboarded] = useState(false);
  // 관계 선택지일 때 담아두는 대화·연락 내역(붙여넣기·화면 캡처). 공고와 같은 흐름:
  // 입력에서 담고, 시뮬레이션 후 결과에서 분석을 본다.
  const [talks, setTalks] = useState([]);              // [{id, tag, transcript, images, label}]
  const [relResults, setRelResults] = useState([]);
  const [relBusy, setRelBusy] = useState(false);

  // 실행 세대 번호. 늦게 도착한 응답이 이미 지나간 화면을 덮어쓰지 못하게 막는다.
  // resetSession() 이 이 값을 올리므로 인물을 바꾸면 진행 중이던 호출은 버려진다.
  const simulationRunRef = useRef(0);

  async function analyzeTalks(list = talks) {
    if (!list.length) { setRelResults([]); return; }
    const runId = simulationRunRef.current;
    setRelBusy(true);
    try {
      const { analyzeRelationship } = await import("./relationshipApi.js");
      const results = [];
      // 대화는 이미지 포함이라 무거워서 하나씩 — 동시에 던지면 타임아웃이 잦다.
      for (const t of list) {
        // eslint-disable-next-line no-await-in-loop
        const data = await analyzeRelationship(t).catch(() => ({ error: "network", label: t.label }));
        if (simulationRunRef.current !== runId) return;
        results.push({ ...data, label: t.label, tag: t.tag });
        setRelResults([...results]);
      }
    } finally {
      if (simulationRunRef.current === runId) setRelBusy(false);
    }
  }

  // 공고는 입력 화면에서 '담기만' 하고(원문), 분석은 시뮬레이션을 돌린 뒤 결과 화면에서 보여준다.
  const [postings, setPostings] = useState([]);        // [{id, text, label}]
  const [jobAnalyses, setJobAnalyses] = useState([]);  // 분석 결과(순서 = postings)
  const [jobBusy, setJobBusy] = useState(false);

  /** 담아둔 공고들을 한꺼번에 분석한다 — 시뮬레이션 시작과 함께 백그라운드로 돌린다. */
  async function analyzePostings(list = postings, choice = null) {
    if (!list.length) { setJobAnalyses([]); return; }
    const runId = simulationRunRef.current;
    setJobBusy(true);
    try {
      const { analyzeJobPosting } = await import("./jobAnalysis.js");
      const results = await Promise.all(
        list.map((p) =>
          analyzeJobPosting({ posting: p.text, choice, profile })
            .then((data) => (data.ok ? { ...data, posting: p.text } : { ok: false, label: p.label, reason: data.reason }))
            .catch(() => ({ ok: false, label: p.label, reason: "network" })),
        ),
      );
      if (simulationRunRef.current !== runId) return;
      setJobAnalyses(results);
    } finally {
      if (simulationRunRef.current === runId) setJobBusy(false);
    }
  }

  // 선택(choices)+심정(diary) → 결과 쌍 {a,b} 생성. (지금은 목업)
  async function runSimulation(opts = {}) {
    const runId = ++simulationRunRef.current;
    const choiceA = opts.choiceA || choices.a;
    const choiceB = opts.choiceB || choices.b;
    const currentDiary = opts.diary ?? diary;
    // 시나리오가 꽂힐 행성 — 선택지에서 감지한 영역으로 정한다.
    // 예전엔 loadUniverse().planet(마지막에 고른 행성)을 썼는데, 새 우주 화면은 그 값을
    // 저장하지 않아 항상 기본값 'career'가 되고 모든 시나리오가 진로 행성에만 쌓였다.
    const domainsForScenario = [
      ...(opts.choiceADomains ?? scenarioDomains.a ?? []),
      ...(opts.choiceBDomains ?? scenarioDomains.b ?? []),
    ];
    const scenarioDomain = toPlanetKey(domainsForScenario) || loadUniverse().planet || "career";
    noteSimulationRun();
    // 그 날 그 영역(현재 행성)에서 시나리오를 만들었음을 기록 → 지구본에 ◆ 로 표시.
    try {
      recordScenario({
        domain: scenarioDomain,
        title: choiceB ? `${choiceA} vs ${choiceB}` : `${choiceA} 시나리오`,
      });
    } catch {
      /* 시나리오 기록 실패 무시 */
    }
    // 이 시뮬레이션이 어느 행성 얘기였는지 결과에 남긴다 — 보관함에 저장한 뒤
    // 회고까지 붙으면 '그 영역의 N년 뒤'를 쓸 때 재료로 다시 꺼내 쓴다.
    const pair = { ...getPredictionPair({ profile, choiceA, choiceB, detail: currentDiary }),
                   dataMode: "demo", planetDomain: scenarioDomain,
                   futureYears: opts.futureYears ?? futureYears };
    setResult(pair);
    setHasSimulationResult(true);
    const diaryInsights = collectDiaryInsights();
    const withDiaryInsights = (context) => ({
      ...(context || {}),
      ...(diaryInsights ? { diary_insights: diaryInsights } : {}),
    });
    const requestArgs = {
      profile,
      futureYears: opts.futureYears ?? futureYears,
      choiceA,
      choiceB,
      choiceADetail: opts.choiceADetail ?? scenarioTexts.a,
      choiceBDetail: opts.choiceBDetail ?? scenarioTexts.b,
      choiceADomains: opts.choiceADomains ?? scenarioDomains.a,
      choiceBDomains: opts.choiceBDomains ?? scenarioDomains.b,
      choiceAContext: withDiaryInsights(opts.choiceAContext ?? scenarioContexts.a),
      choiceBContext: withDiaryInsights(opts.choiceBContext ?? scenarioContexts.b),
      diary: currentDiary,
    };
    // 로딩 화면의 단계 표시는 이 콜백으로만 움직인다. 타이머로 미리 채우면
    // 실제로 끝나지 않은 일을 끝난 것처럼 보여주게 된다.
    const report = typeof opts.onProgress === "function" ? opts.onProgress : () => {};

    let preview;
    try {
      report("connect");
      const comparison = await runCompareRaw(requestArgs);
      report("compare");
      const real = mapSimulateToPair({ compare: comparison }, {
        choiceA,
        choiceB,
        detailA: opts.choiceADetail ?? scenarioTexts.a,
        detailB: opts.choiceBDetail ?? scenarioTexts.b,
      });
      preview = {
        ...pair,
        ...(real || {}),
        dataMode: real ? "model" : "demo",
        // 서버에 닿았으니 수치는 진짜다. 서사 생략(폭주 가드)은 아래 서사 단계에서 판별한다.
        serviceStatus: real ? "ok" : "offline",
        domains: {
          a: opts.choiceADomains ?? scenarioDomains.a,
          b: opts.choiceBDomains ?? scenarioDomains.b,
        },
        narrativeLoading: true,
        imageLoading: true,
        futureYears: requestArgs.futureYears,
      };
      setResult(preview);
      setHasSimulationResult(true);
      report("ready");
      try {
        const summarize = (side) => {
          if (!side) return "";
          const signals = [
            side.choice,
            side.expected_wage != null ? `예상 소득 ${Math.round(side.expected_wage).toLocaleString()}만원` : "",
            side.causal_effect != null ? `추정 변화 ${Number(side.causal_effect).toFixed(1)}%` : "",
            side.risk_label || side.coverage || "",
          ].filter(Boolean);
          return signals.join(" · ");
        };
        recordScenario({
          domain: scenarioDomain,
          title: choiceB ? `${choiceA} vs ${choiceB}` : `${choiceA} 시나리오`,
          br: [summarize(preview.a), summarize(preview.b)].filter(Boolean),
        });
      } catch {
        /* 우주 패널 요약 저장 실패는 결과 화면을 막지 않는다. */
      }
    } catch (error) {
      // 서버에 못 닿았다 → 화면에 남는 건 목업 값이다. 결과 화면이 그걸 숨기지
      // 않도록 serviceStatus 로 알린다(ServiceNotice 가 맨 위에 띄운다).
      const fallback = {
        ...pair,
        dataMode: "demo",
        serviceStatus: "offline",
        narrativeError: error.message,
      };
      setResult(fallback);
      return fallback;
    }

    // 이미지와 Claude 서사를 동시에 시작한다. 이미지는 사용자가 쓴 A/B 문장을
    // 먼저 활용하고, 수동 재생성 때는 완성된 서사를 사용한다.
    const fastVisualPromise = (async () => {
      const avatarBlob = await avatarToPngBlob(profile.avatarConfig);
      return generateSceneImages({
        avatarBlob,
        avatarSpec: avatarGenerationSpec(profile.avatarConfig, profile.sex),
        choiceA,
        choiceB,
        futureYears: requestArgs.futureYears,
        narrative: {
          a: requestArgs.choiceADetail || choiceA,
          b: requestArgs.choiceBDetail || choiceB,
          visual_a: {},
          visual_b: {},
        },
      });
    })().then(
      (visual) => ({ visual, error: null }),
      (error) => ({ visual: null, error }),
    );

    // 결과 화면은 수치가 준비되는 즉시 열고, 느린 Claude·이미지는 뒤에서 채운다.
    void (async () => {
      try {
        const simulation = await runSimulateRaw(requestArgs);
        if (simulationRunRef.current !== runId) return;
        const narrative = simulation.narrative || {};
        // 접속 폭주 가드가 서사만 생략한 경우(backend/usage_guard.py).
        // 수치는 진짜이므로 오류로 처리하지 않고 '지금 사람이 많다'로 안내한다.
        if (narrative._busy) {
          setResult({
            ...preview,
            serviceStatus: "busy",
            narrativeLoading: false,
            imageLoading: false,
          });
          return;
        }
        const hasStory = (story) => typeof story === "string" ? Boolean(story.trim()) : Boolean(story?.summary?.trim());
        if (!hasStory(narrative.a) || !hasStory(narrative.b) || narrative._skipped) {
          throw new Error("Claude 응답을 A/B 서사 형식으로 읽지 못했습니다.");
        }
        const storyResult = {
          ...preview,
          narrative,
          evidence: simulation.evidence,
          narrativeLoading: false,
          imageLoading: true,
        };
        setResult(storyResult);

        try {
          const { visual, error: imageError } = await fastVisualPromise;
          if (imageError) throw imageError;
          if (simulationRunRef.current !== runId) return;
          setResult({ ...storyResult, visuals: visual.images, visualModel: visual.model, imageLoading: false });
        } catch (imageError) {
          if (simulationRunRef.current !== runId) return;
          setResult({ ...storyResult, imageLoading: false, visualError: imageError.message });
        }
      } catch (error) {
        if (simulationRunRef.current !== runId) return;
        setResult({ ...preview, narrativeLoading: false, imageLoading: false, narrativeError: error.message });
      }
    })();
    return preview;
  }

  async function retryVisuals() {
    const narrative = result.narrative;
    if (!narrative?.a || !narrative?.b) {
      throw new Error("이미지에 사용할 서사가 아직 준비되지 않았어요.");
    }
    setResult((current) => ({ ...current, imageLoading: true, visualError: null }));
    try {
      const avatarBlob = await avatarToPngBlob(profile.avatarConfig);
      const visual = await generateSceneImages({
        avatarBlob,
        avatarSpec: avatarGenerationSpec(profile.avatarConfig, profile.sex),
        choiceA: result.a.choice,
        choiceB: result.b.choice,
        futureYears: result.futureYears ?? futureYears,
        narrative,
      });
      setResult((current) => ({
        ...current,
        visuals: visual.images,
        visualModel: visual.model,
        imageLoading: false,
        visualError: null,
      }));
    } catch (error) {
      setResult((current) => ({ ...current, imageLoading: false, visualError: error.message }));
    }
  }

  /**
   * 저장소의 프로필을 다시 읽어온다 — 페르소나 슬롯을 갈아끼운 직후에 부른다.
   *
   * 예전에는 전환 뒤 window.location.reload() 로 컨텍스트를 새로 띄웠다. 그런데
   * iframe·사파리에서는 저장소가 메모리라(safeStorage) **새로고침하면 방금 심은
   * 1년치가 통째로 날아간다.** 그래서 새로고침 대신 이 함수로 상태만 갈아끼운다.
   * 기록(pm.myuniverse.v1)은 restoreLive 가 쏘는 'pm:universe' 이벤트로 각 화면이
   * 알아서 다시 읽으므로, 여기서는 프로필만 맡는다.
   */
  function reloadProfile() {
    setProfile(loadProfile());
  }

  /**
   * 시뮬레이션 세션을 처음 상태로 되돌린다 — 로그아웃·페르소나 전환에서 부른다.
   *
   * 왜 필요한가: 프로필은 슬롯이 갈아끼우고 reloadProfile() 이 읽어오지만, 결과·선택지·
   * 담아둔 공고와 대화는 이 Provider 의 메모리에만 있다. Provider 는 라우트가 바뀌어도
   * 언마운트되지 않으므로, 인물을 바꿔도 앞사람의 결과 화면이 그대로 남아 있었다
   * (프로필은 도현인데 선택지와 아바타는 지원인 상태).
   *
   * 세대 번호를 먼저 올린다 — 서사·이미지는 수십 초 걸려서, 돌고 있는 도중에 인물을
   * 바꾸면 늦게 도착한 응답이 새 인물의 화면을 덮어쓴다.
   */
  function resetSession() {
    simulationRunRef.current += 1;
    setChoices({ a: "이직", b: "유지" });
    setScenarioTexts({ a: "", b: "" });
    setScenarioDomains({ a: [], b: [] });
    setScenarioContexts({ a: {}, b: {} });
    setFutureYears(3);
    setDiary("");
    setResult(blankResult());
    setHasSimulationResult(false);
    setPostings([]);
    setJobAnalyses([]);
    setJobBusy(false);
    setTalks([]);
    setRelResults([]);
    setRelBusy(false);
  }

  const value = useMemo(
    () => ({
      profile, setProfile, reloadProfile, resetSession,
      choices, setChoices,
      scenarioTexts, setScenarioTexts,
      scenarioDomains, setScenarioDomains,
      scenarioContexts, setScenarioContexts,
      futureYears, setFutureYears,
      diary, setDiary,
      result, setResult,
      hasSimulationResult,
      runSimulation, retryVisuals, onboarded, setOnboarded,
      postings, setPostings,
      jobAnalyses, setJobAnalyses, jobBusy, analyzePostings,
      talks, setTalks, relResults, relBusy, analyzeTalks,
    }),
    [profile, choices, scenarioTexts, scenarioDomains, scenarioContexts, futureYears, diary, result, hasSimulationResult, onboarded,
     postings, jobAnalyses, jobBusy, talks, relResults, relBusy],
  );

  return <ResultContext.Provider value={value}>{children}</ResultContext.Provider>;
}

export function useResult() {
  const ctx = useContext(ResultContext);
  if (!ctx) throw new Error("useResult must be used within <ResultProvider>");
  return ctx;
}
