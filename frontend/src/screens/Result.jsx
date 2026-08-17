import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useResult } from "../data/ResultContext.jsx";
import { useDiary } from "../data/DiaryContext.jsx";
import { labelOf } from "../data/prediction.js";
import { detectLifeDomains } from "../data/choices.js";
import { occupationLabel } from "../data/profileOptions.js";
import { redactPII, redactEntries } from "../data/piiRedact.js";
import { saveMe, getScenario, getThirdPath } from "../data/api.js";
import { listUniverses, saveUniverse, universeFromResult } from "../data/savedUniverses.js";
import ServiceNotice from "../components/ServiceNotice.jsx";
import { Bookmark, Check, ChevronLeft, ChevronRight } from "lucide-react";
import LifeView from "../components/result/LifeView.jsx";
import ChangeView from "../components/result/ChangeView.jsx";
import ActionView from "../components/result/ActionView.jsx";
import AvatarComparison from "../components/result/AvatarComparison.jsx";
import DiarySignalCard from "../components/result/DiarySignalCard.jsx";
import KowepsEvidenceCard from "../components/result/KowepsEvidenceCard.jsx";
import RelationshipEffectCard from "../components/result/RelationshipEffectCard.jsx";
import KowepsTrajectoryView from "../components/result/KowepsEvidenceView.jsx";
import JobAnalysisView from "../components/result/JobAnalysisView.jsx";
import RelationshipView from "../components/result/RelationshipView.jsx";
import SoftCompareView from "../components/result/SoftCompareView.jsx";
import ResultQuickStats from "../components/result/ResultQuickStats.jsx";
import ResultDataNotes from "../components/result/ResultDataNotes.jsx";
import DetailedInsights from "../components/result/DetailedInsights.jsx";
import { softDomainOf } from "../data/softCompare.js";
import { DOMAIN_LABEL } from "../data/diarySignals.js";
import FutureYearPicker from "../components/FutureYearPicker.jsx";

// 저장은 단계가 아니라 '비교하고 선택'의 마무리 동작이다. 예전엔 3단계였는데
// 그 화면에 있던 건 아이콘 하나·문구 한 줄·버튼 두 개가 전부라, 단계 표시줄만
// 늘리고 클릭을 한 번 더 받는 역할이었다. 저장해야 나갈 수 있다는 규칙은 그대로
// 두고 위치만 2단계 하단으로 내렸다.
const RESULT_STEPS = ["결과 요약", "비교하고 선택"];

export default function Result() {
  const navigate = useNavigate();
  const {
    result, profile, scenarioDomains, retryVisuals, jobAnalyses, postings, relResults, talks,
    setFutureYears,
  } = useResult();
  const { a, b } = result;
  // 온보딩·설정의 직종(8분류) → 없으면 입력 화면의 KSCO 대분류. 둘 다 없으면 빈 문자열.
  const myOccupation = occupationLabel(profile);

  // 진로가 아닌 영역(관계·건강·일상·성장)은 KLIPS 수치가 맞지 않는다.
  // 그대로 두면 지표 필터에 하나도 안 걸려 '핵심 지표'가 빈 화면이 된다(관계가 그랬다).
  // 그 자리를 기록 기반 장면 비교로 바꾸고, 수치 탭은 뒤로 물린다.
  const softPlanet = softDomainOf([...(result.domains?.a || scenarioDomains?.a || []),
                                   ...(result.domains?.b || scenarioDomains?.b || [])]);
  const hasKowepsObservation = [a, b].some((side) => side.koweps_evidence?.available);
  // 관계 인과효과는 '집단 관측'과 성격이 달라(처치효과) 같은 탭에 두되 위에 놓는다.
  // 값이 없어도 '왜 없는지'가 있으면 탭을 연다 — 진학처럼 의도적으로 막은 경우다.
  const hasRelationshipEffects = [a, b].some(
    (side) => side.relationship_effects || side.relationship_effects_reason);
  const hasNumericComparison = hasComparableNumbers(a, b);

  const tabs = [
    ...(hasNumericComparison
      ? [{ key: "numbers", label: "수치 비교", View: (p) => <>
          <ChangeView {...p} />
          <LifeView {...p} />
        </> }]
      : []),
    { key: "record", label: "기록 근거", View: () => <>
      <DiarySignalCard />
      {softPlanet && <SoftCompareView a={a} b={b} planet={softPlanet} planetLabel={DOMAIN_LABEL[softPlanet] || ""} />}
    </> },
    ...(hasKowepsObservation || hasRelationshipEffects
      ? [{ key: "observation", label: "집단 관측", View: (p) => <>
          {hasRelationshipEffects && <RelationshipEffectCard a={a} b={b} />}
          {hasKowepsObservation && <KowepsEvidenceCard {...p} />}
        </> }]
      : []),
    // 입력에서 공고를 분석했을 때만 — 예측 수치 옆에서 그 공고를 다시 확인한다.
    ...(jobAnalyses?.length || postings?.length
      ? [{ key: "job", label: `공고 분석${(jobAnalyses?.length || postings?.length) > 1 ? ` ${jobAnalyses?.length || postings?.length}` : ""}`, View: JobAnalysisView }]
      : []),
    // 관계 선택지에서 대화를 담았을 때만.
    ...(relResults?.length || talks?.length
      ? [{ key: "rel", label: `관계 분석${(relResults?.length || talks?.length) > 1 ? ` ${relResults?.length || talks?.length}` : ""}`, View: RelationshipView }]
      : []),
  ];

  const [tab, setTab] = useState(
    hasNumericComparison ? "numbers" : hasKowepsObservation ? "observation" : "record",
  );
  const [step, setStep] = useState(0);
  const Active = (tabs.find((t) => t.key === tab) || tabs[0]).View;

  // 보관함 저장 — 화면에 보이는 A/B 그대로 담는다. 같은 비교를 같은 날 두 번 담지 않는다.
  const title = `${a.choice} vs ${b.choice}`;
  const today = new Date().toISOString().slice(0, 10);
  const [saved, setSaved] = useState(() =>
    listUniverses().some((u) => u.title === title && u.savedAt === today),
  );
  // 서사가 아직 오는 중이면 반쪽짜리 스냅샷이 저장된다 → 준비된 뒤에 담게 한다.
  const savable = !saved && !result.narrativeLoading;

  function changeFutureYear(years) {
    if (years === (result.futureYears ?? 3)) return;
    setFutureYears(years);
    navigate("/simulate");
  }

  function saveToArchive() {
    saveUniverse(
      universeFromResult(result, profile, { a: a.choice, b: b.choice }, result.domains || scenarioDomains),
    );
    setSaved(true);
  }

  return (
    <div className="relative">
      <h1 className="text-[21px] font-bold leading-[1.2] lg:text-[28px]">
        {/* 헤더는 '지금 내 프로필'을 그대로 보여준다. 예전엔 결과 객체 안의 스냅샷
            (a.meta)을 읽어서, 설정에서 나이·직종을 고친 뒤 결과 화면으로 돌아오면
            시뮬레이션을 돌리던 시점의 옛 값이 그대로 남아 있었다. */}
        {profile.age}세{myOccupation ? ` · ${myOccupation}` : ""}
      </h1>
      <p className="mt-1 text-[13px]">
        <span className="font-bold text-cyan">{labelOf(a.choice)}</span>
        <span className="text-mut"> vs </span>
        <span className="font-bold text-gold">{labelOf(b.choice)}</span>
      </p>
      <div className="mt-2 flex flex-col items-start gap-2 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-wrap items-center gap-2">
          <div className="inline-flex h-7 items-center rounded-full border border-violet-400/30 bg-violet-500/10 px-3 text-[11px] font-semibold text-violet-200">
            지금부터 {result.futureYears ?? 3}년 뒤의 두 미래
          </div>
          <FutureYearPicker
            years={result.futureYears ?? 3}
            onChange={changeFutureYear}
            ariaLabel="결과 기준 시점 변경"
            titleFor={(years) => `${years}년 뒤 기준으로 다시 분석`}
          />
        </div>
        {step !== 1 && <EvidenceModeBadge a={a} b={b} domains={result.domains || scenarioDomains} />}
      </div>
      {/* 서버에 못 닿았거나(offline) 서사만 생략된(busy) 상태를 **맨 위에서** 알린다.
          이게 없으면 목업 숫자가 아무 표시 없이 진짜처럼 보인다 — 경고가 근거 탭
          안쪽에만 있어서 첫 화면만 보고 지나가면 알 수 없었다. */}
      <ServiceNotice status={result.serviceStatus || "ok"} />

      <ol className="mt-5 grid gap-2" style={{ gridTemplateColumns: `repeat(${RESULT_STEPS.length}, minmax(0, 1fr))` }} aria-label="결과 확인 단계">
        {RESULT_STEPS.map((label, index) => (
          <li key={label} className="min-w-0">
            <div className={`h-1 rounded-full ${index <= step ? "bg-violet-400" : "bg-white/10"}`} />
            <span className={`mt-2 block truncate text-[10px] font-semibold lg:text-[11px] ${index === step ? "text-violet-300" : "text-mut"}`}>{index + 1}. {label}</span>
          </li>
        ))}
      </ol>

      {/* 근거 모드 배지는 '비교 분석'에서는 빼둔다 — 그 단계에는 항목별 근거가
          바로 아래에 있고, 배지는 A·B 중 가장 강한 근거만 골라 한 줄로 쓴 것이라
          나란히 놓으면 실제보다 단단해 보인다. 다른 단계에는 이 한 줄이 유일한
          "확정 예측이 아니다" 표시라 그대로 둔다. */}
      {step === 0 && <section className="mt-5 animate-fade">
      <AvatarComparison
        avatar={profile.avatarConfig}
        a={a}
        b={b}
        visuals={result.visuals}
        narrative={result.narrative}
        narrativeLoading={result.narrativeLoading}
        loading={result.imageLoading}
        error={result.visualError || result.narrativeError}
        onRetry={result.visualError ? retryVisuals : null}
      />
      <div className="mt-4 min-w-0 [&>section]:mt-0">
        <ResultQuickStats a={a} b={b} futureYears={result.futureYears ?? 3} />
        <ResultDataNotes a={a} b={b} futureYears={result.futureYears ?? 3} />
      </div>
      {hasKowepsObservation && (
        <div className="mt-4 min-w-0 [&>.bg-card]:mt-0">
          <KowepsTrajectoryView a={a} b={b} />
        </div>
      )}
      </section>}

      {step === 1 && <section className="mt-5 animate-fade lg:grid lg:grid-cols-[minmax(0,1.35fr)_minmax(300px,.65fr)] lg:items-start lg:gap-6">
        <div className="min-w-0">
      <DetailedInsights a={a} b={b} futureYears={result.futureYears ?? 3} />
      {/* data-tour — 사용 안내가 '결과는 각도를 바꿔가며 봐요' 단계에서 짚는 자리 */}
      <div data-tour="result-tabs" className="no-scrollbar my-2.5 flex gap-1.5 overflow-x-auto pb-1">
        {tabs.map((t) => {
          const on = t.key === tab;
          return (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`tap whitespace-nowrap rounded-2xl border px-3.5 py-2 text-xs transition-colors ${
                on ? "border-[#3a4a70] bg-[#2b3859] text-white" : "border-line bg-[#0E1424] text-sub"
              }`}
            >
              {t.label}
            </button>
          );
        })}
      </div>

      <div key={tab} className="animate-fade">
        <Active a={a} b={b} domains={result.domains || scenarioDomains} dataMode={result.dataMode || "demo"} />
      </div>
        </div>
        <aside className="mt-5 rounded-[22px] border border-white/10 bg-[#0B1424]/90 p-4 lg:sticky lg:top-5 lg:mt-2.5">
          <p className="text-[10px] font-bold tracking-[.14em] text-violet-300">결정 포인트</p>
          <p className="mt-2 text-[13px] font-semibold leading-relaxed text-ink">
            {result.narrative?.comparison?.question || "두 선택 중 지금 더 확인해보고 싶은 방향은 무엇인가요?"}
          </p>
          <div className="mt-4 border-t border-white/[.07] pt-4">
            <ActionView a={a} b={b} domains={result.domains || scenarioDomains} dataMode={result.dataMode || "demo"} />
          </div>
          <div className="mt-4 border-t border-white/[.07] pt-4">
            <PersonaScenario a={a} b={b} />
            <ThirdPath a={a} b={b} />
          </div>
        </aside>
      </section>}

      <div className="mt-6 flex flex-wrap items-center justify-between gap-2 border-t border-white/10 pt-4">
        {step > 0 ? (
          <button type="button" onClick={() => setStep((current) => current - 1)} className="tap flex items-center gap-1.5 rounded-xl px-3 py-2 text-[12px] font-semibold text-sub hover:bg-white/[.05]"><ChevronLeft size={15}/> 이전</button>
        ) : <span />}
        {step < RESULT_STEPS.length - 1 ? (
          <button
            type="button"
            onClick={() => setStep((current) => current + 1)}
            className="tap flex items-center gap-1.5 rounded-xl bg-violet-500 px-4 py-2.5 text-[12px] font-semibold text-white hover:bg-violet-400"
          >
            다음 단계 <ChevronRight size={15}/>
          </button>
        ) : (
          /* 마지막 단계 — 저장하고 나간다. 저장 전에는 나가기가 잠긴다(기존 규칙 유지).
             잠금 아이콘은 뺐다 — 저장 버튼이 바로 옆에 있어서 자물쇠까지 붙이면
             경고처럼 읽혔다. 이유는 버튼 밑 한 줄로만 조용히 알린다. */
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={saveToArchive}
              disabled={!savable}
              className={`tap flex items-center justify-center gap-1.5 rounded-xl border px-3.5 py-2.5 text-[12px] font-semibold transition-colors ${
                savable
                  ? "border-cyan/45 bg-cyan/[.12] text-cyan hover:bg-cyan/[.18]"
                  : "border-white/10 bg-white/[.04] text-mut"
              }`}
            >
              {saved ? (
                <><Check size={15} strokeWidth={2.4} /> 저장됨</>
              ) : result.narrativeLoading ? (
                "결과 준비 중…"
              ) : (
                <><Bookmark size={15} strokeWidth={2.1} /> 보관함에 저장</>
              )}
            </button>
            <button
              type="button"
              disabled={!saved}
              onClick={() => navigate("/archive", { replace: true })}
              className="tap flex items-center justify-center gap-1.5 rounded-xl bg-violet-500 px-4 py-2.5 text-[12px] font-semibold text-white transition-colors hover:bg-violet-400 disabled:cursor-not-allowed disabled:bg-white/[.06] disabled:text-mut"
            >
              나가기 <ChevronRight size={15}/>
            </button>
            {!saved && <p className="basis-full text-[10px] text-mut sm:basis-auto">보관함에 저장하면 나갈 수 있어요.</p>}
          </div>
        )}
      </div>
    </div>
  );
}

// 선택과 무관한 참고 통계만 있을 때는 "수치 비교" 탭을 만들지 않는다.
// 실제로 A/B가 갈리거나 유사사례의 변화 비율이 준비된 경우에만 노출한다.
function hasComparableNumbers(a, b) {
  if ([a, b].some((side) => side.observed_outcomes?.status === "available")) return true;
  if ([a, b].some((side) => side.parallel_trajectory?.status === "available")) return true;
  if ([a, b].some((side) => Array.isArray(side.trajectory) && side.trajectory.length > 0)) return true;
  const num = (value) => (value === null || value === undefined || value === "" ? NaN : Number(value));
  const last = (rows) => (Array.isArray(rows) && rows.length
    ? num(rows.at(-1)?.value ?? rows.at(-1)?.median ?? rows.at(-1)?.satis_p50)
    : NaN);
  const pairs = [
    [num(a.expected_wage), num(b.expected_wage)],
    [num(a.causal_effect), num(b.causal_effect)],
    [num(a.survival_months), num(b.survival_months)],
    [last(a.wellbeing_trajectory), last(b.wellbeing_trajectory)],
  ];
  return pairs.some(([left, right]) => {
    const leftOk = Number.isFinite(left);
    const rightOk = Number.isFinite(right);
    return (leftOk || rightOk) && (!leftOk || !rightOk || left !== right);
  });
}

function EvidenceModeBadge({ a, b, domains }) {
  const selected = new Set([...(domains?.a || []), ...(domains?.b || [])]);
  const hasModel = [a, b].some((side) => side.evidence_level === "model" || side.parallel_trajectory?.status === "available");
  const hasMatched = [a, b].some((side) => side.koweps_evidence?.evidence_level === "personalized_matched_observation");
  const hasObserved = [a, b].some((side) => side.koweps_evidence?.available || Object.values(side.domain_stats || {}).some((item) => item.status === "available"));
  const mode = hasModel
    ? ["개인 조건 모델", "입력 조건을 모델과 유사사례 매칭에 사용했습니다.", "#9B72F2"]
    : hasMatched
      ? ["유사 조건 종단 관측", "나와 가까운 조건의 사건 발생군과 미발생군을 비교합니다.", "#7E9EFF"]
      : hasObserved
        ? ["집단 관측·참고 통계", "개인의 확정 미래가 아니라 관련 집단의 기준값입니다.", "#65C8B0"]
        : selected.has("relationship")
          ? ["관계 행동 시뮬레이션", "예측 점수 대신 실행 단계와 기록할 변화를 제시합니다.", "#F39A4A"]
          : ["설명 기반 탐색", "검증된 수치가 없는 부분은 서사와 행동 제안만 제공합니다.", "#8791A8"];
  return (
    <div
      className="flex items-start gap-2 rounded-xl border border-white/10 bg-white/[.035] px-3 py-2.5 lg:h-7 lg:items-center lg:rounded-full lg:bg-[#0D1727]/90 lg:py-0 lg:shadow-[0_8px_24px_rgba(0,0,0,.22)] lg:backdrop-blur"
      title={mode[1]}
    >
      <span className="mt-0.5 h-2 w-2 shrink-0 rounded-full lg:mt-0" style={{ backgroundColor: mode[2] }} />
      <div>
        <div className="text-[10px] font-bold" style={{ color: mode[2] }}>{mode[0]}</div>
        <div className="mt-0.5 text-[9px] leading-4 text-mut lg:hidden">{mode[1]}</div>
      </div>
    </div>
  );
}

// A/B 외의 '제3의 길' — 성향+일기신호로 LLM이 생성 (재구성 제안, 수치 예측 아님)
function ThirdPath({ a, b }) {
  const { profile } = useResult();
  const { entries } = useDiary();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const [res, setRes] = useState(null);

  async function run() {
    setBusy(true); setErr(null); setRes(null);
    try {
      // 진로 계열일 때만 일기 entries(→ 이직 신호)를 넘긴다. 관계 등은 선택지만으로
      // 제안받아 이직 프레임이 섞이지 않게 한다(LLM은 선택지를 보고 해당 분야로 제안).
      const isJob = detectLifeDomains(`${a.choice} ${b.choice}`).some((k) => ["career", "finance", "business"].includes(k))
        || /이직|퇴사|유지|창업|진학|직장|커리어/.test(`${a.choice}${b.choice}`);
      // 외부 AI 전송 전 PII 마스킹 — 이름·연봉·연락처 등 원문 개인정보를 가린다.
      const known = { name: profile.name, company: "" };
      const rawEntries = entries.map((e) => ({
        date: e.date, mood: e.mood, text: e.text, answers: e.answers || {},
        energy: e.energy, competency: e.competency, emotion: e.emotion,
      }));
      const r = await getThirdPath({
        choice_a: redactPII(a.choice, known).masked,
        choice_b: redactPII(b.choice, known).masked,
        // 결과 스냅샷(a.meta)이 아니라 지금 프로필을 보낸다 — 프로필을 고친 뒤
        // 생성하면 옛 나이·직종으로 서사가 쓰이던 자리다.
        age: profile.age,
        major: occupationLabel(profile),
        entries: isJob ? redactEntries(rawEntries, known).entries : [],
      });
      if (!r.ok) throw new Error(r.reason === "no_api_key" ? "서버에 ANTHROPIC_API_KEY 미설정" : r.reason || "생성 실패");
      setRes(r);
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <details className="group mb-3 rounded-2xl border border-gold/35 bg-[#211a10] px-3.5 py-3">
      <summary className="cursor-pointer list-none text-[12px] font-bold text-gold">
        💡 A와 B 모두 확신이 없다면
        <span className="ml-1 text-[10px] font-normal text-mut group-open:hidden">· 제3의 길 보기</span>
      </summary>
      <div className="mt-3 flex items-center justify-between gap-3">
        <p className="text-[10px] leading-relaxed text-mut">내 성향과 기록을 바탕으로 다른 선택지를 찾아봅니다.</p>
        <button
          onClick={run}
          disabled={busy}
          className="tap shrink-0 rounded-xl bg-gold px-3 py-1.5 text-[11px] font-bold text-[#2a1e05] disabled:opacity-60"
        >
          {busy ? "찾는 중…" : res ? "다시" : "제안 받기"}
        </button>
      </div>
      {err && <p className="mt-2 text-[10px] text-[#F0736F]">API 실패 — 서버(:8000) 켜졌나요? {err}</p>}
      {res ? (
        <>
          <p className="mt-2 text-[13px] font-semibold leading-relaxed text-ink">{res.title}</p>
          {res.rationale && <p className="mt-1.5 whitespace-pre-line text-[12px] leading-relaxed text-sub">{res.rationale}</p>}
          <p className="mt-1.5 text-[10px] text-mut">
            {res.signal_used ? "✓ 내 일기 신호 반영 · " : ""}정답이 아니라 재구성 제안이에요 — 수치 예측이 아닙니다.
          </p>
        </>
      ) : (
        null
      )}
    </details>
  );
}

// 저장된 내 성향(온보딩+일기) → 이 이직 예측 서사에 반영 (수치 불변, 순서·톤만)
function PersonaScenario({ a, b }) {
  const { profile } = useResult();
  const { entries } = useDiary();
  const jc = a.choice === "이직" ? a : b.choice === "이직" ? b : null;
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const [res, setRes] = useState(null);

  if (!jc) return null; // 이직 시나리오 없으면 표시 안 함

  async function run() {
    setBusy(true); setErr(null); setRes(null);
    try {
      await saveMe({
        ranked_cards: profile.values,
        mbti: profile.mbti,
        profile: { age: profile.age, occupation: profile.occupation, income: profile.income },
        entries: entries.map((e) => ({
          date: e.date, mood: e.mood, text: e.text, answers: e.answers || {},
          energy: e.energy, competency: e.competency, emotion: e.emotion,
        })),
      });
      const r = await getScenario({
        uid: "me", choice: "이직",
        expected_wage: jc.expected_wage || 0,
        causal_effect: jc.causal_effect || 0,
        survival_months: jc.survival_months || 0,
        age: profile.age, major: occupationLabel(profile),
      });
      setRes(r);
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mb-3 mt-1 rounded-2xl border border-cyan bg-[#1D1730] p-3.5">
      <div className="flex items-center justify-between">
        <div className="text-[13px] font-bold text-cyan">🔮 내 성향이 반영된 이직 서사</div>
        <button
          onClick={run}
          disabled={busy}
          className="tap rounded-xl bg-cyan px-3 py-1.5 text-[11px] font-bold text-[#04203a] disabled:opacity-60"
        >
          {busy ? "생성 중…" : res ? "다시" : "생성"}
        </button>
      </div>
      {err && <p className="mt-2 text-[10px] text-[#F0736F]">API 실패 — 서버(:8000) 켜졌나요? {err}</p>}
      {res ? (
        <>
          <p className="mt-2 whitespace-pre-line text-[12px] leading-relaxed text-sub">{res.narrative}</p>
          <p className="mt-1.5 text-[10px] text-mut">
            {res.persona_used
              ? "✓ 저장된 내 성향(온보딩+일기) 반영 — 예측 수치는 동일, 서술 순서·톤만 조정"
              : "성향 미반영(저장된 데이터 없음)"}
          </p>
        </>
      ) : (
        !busy && (
          <p className="mt-2 text-[11px] text-mut">
            온보딩+일기로 만든 내 성향을 저장하고, 이 이직 예측에 반영한 서사를 생성해요.
          </p>
        )
      )}
    </div>
  );
}
