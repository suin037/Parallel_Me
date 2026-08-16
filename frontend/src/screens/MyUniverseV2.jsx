import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Archive, CalendarDays, ChevronRight, Plus, X } from "lucide-react";
import UniverseMap from "../components/UniverseMap.jsx";
import Constellation from "../components/Constellation.jsx";
import { announceSurface } from "../data/guideAdvice.js";
import { domainScore, domainMentions, relationMix, metricOf, skillMix, MIN_FOR_SCORE } from "../data/domainScore.js";
import { PLANETS } from "../data/result.js";
import { adaptiveGroups, hasRecord, loadUniverse, scenariosByPlanet, starGroupsOf, todayKey } from "../data/myUniverse.js";
import { domainAnalysis, domainMonths, domainReport, detectRelationSubtype } from "../data/diarySignals.js";
import { futureMaterials, getCachedFuture, writeFuture, getCachedOpportunities, scanOpportunities } from "../data/futureApi.js";
import { expeditionsFor, startExpedition } from "../data/expeditions.js";
import { shapeOf, shapeLineFor, DOMAIN_THEME, MIN_RECORDS_TO_NAME, HONESTY_NOTE } from "../data/constellationRules.js";
import { useResult } from "../data/ResultContext.jsx";
import { loadSpeech } from "../data/dispositionApi.js";
import { planetSkin } from "../data/petShop.js";
import { PLANET_TEXTURES } from "../data/planetSurface.js";
import { josa, hasFinalConsonant } from "../lib/josa.js";

const DESCRIPTIONS = {
  career: "나의 진로와 커리어에 대한 고민, 선택, 방향성을 기록해요.",
  growth: "배움과 성취, 새로운 가능성을 향한 과정을 기록해요.",
  life: "일상에서 느낀 평온과 만족, 삶의 균형을 기록해요.",
  relation: "가족과 친구, 동료와 나눈 관계의 순간을 기록해요.",
  health: "몸과 마음의 변화, 회복과 돌봄의 기록을 모아요.",
};
const KEYWORDS = {
  career: ["진로 고민", "진로 탐색", "목표 설정", "취업 준비", "방향성"],
  growth: ["배움", "자기 확신", "도전", "성취"], life: ["일상", "평온", "균형", "만족"],
  relation: ["가족", "친구", "동료", "소통"], health: ["회복", "수면", "운동", "마음 건강"],
};

// 그 행성의 기록 — 별·분석과 같은 규칙(hasRecord + 저장된 domains)을 쓴다.
// 전에는 domains 가 없으면 career 로 밀어넣고 기분만 찍은 날도 셌다. 그래서
// '최근 기록'에 "(체크인만 남긴 날)"이 뜨고 개수도 별과 어긋났다.
function planetEntries(state, key) {
  return (state.checkins || []).filter(
    (entry) => hasRecord(entry) && Array.isArray(entry.domains) && entry.domains.includes(key),
  );
}
function dateLabel(date) { const [, month, day] = String(date).split("-"); return `${Number(month)}.${Number(day)}`; }

export default function MyUniverseV2() {
  const navigate = useNavigate();
  const { profile, setChoices, setScenarioTexts, setScenarioDomains } = useResult();
  const [state, setState] = useState(loadUniverse);
  const [planet, setPlanet] = useState(null);
  // 3D 에서 별자리를 누르면 그 별자리 하나를 펼쳐 본다(모양·상태·그 안의 기록).
  const [cluster, setCluster] = useState(null);
  // 가이드 조언에게 지금 무엇이 열려 있는지 알린다 — 행성·별자리는 라우트가 같다.
  useEffect(() => {
    announceSurface(cluster ? "cluster" : planet ? "planet" : null);
    return () => announceSurface(null);
  }, [cluster, planet]);
  const [skin,setSkin]=useState(planetSkin);
  useEffect(() => { const refresh = () => setState(loadUniverse()); window.addEventListener("pm:universe", refresh); return () => window.removeEventListener("pm:universe", refresh); }, []);
  useEffect(()=>{const refresh=()=>setSkin(planetSkin());window.addEventListener("pm:pet-shop",refresh);return()=>window.removeEventListener("pm:pet-shop",refresh);},[]);

  // /my?planet=career 로 들어오면 그 행성을 바로 펼친다. 결과 화면의 "기록 전체 보기"가
  // 여기로 보낸다 — 3D 지도에서 행성을 다시 찾아 누르게 하면 링크가 아니라 안내문이 된다.
  // 한 번 열고 주소에서 지운다. 안 지우면 모달을 닫고 새로고침할 때마다 다시 열린다.
  const [params, setParams] = useSearchParams();
  useEffect(() => {
    const key = params.get("planet");
    if (!key) return;
    const found = PLANETS.find((item) => item.key === key);
    if (found) { setPlanet(found); setCluster(null); }
    setParams({}, { replace: true });
  }, [params, setParams]);

  // 기회 카드를 누르면 그 갈림길이 채워진 채로 시뮬레이션이 열린다 —
  // 다시 타이핑하게 하면 '길을 내밀었다'는 의미가 없다. 영역도 그 행성으로 넘겨
  // 결과 시나리오가 원래 행성에 다시 쌓이게 한다.
  function pickOpportunity(item) {
    if (!planet) return;
    // 두 입력칸에는 '길 이름'만 넣는다 — 100자짜리 한 줄 칸이고 사용자가 직접 적는 자리다.
    // 전에는 카드 설명문(why, 두 문장)을 그대로 넣어 시뮬레이션 칸이 설명으로 꽉 찼다.
    // 왜 이 길이 나왔는지는 카드에서 이미 읽었으니 여기서 되풀이하지 않는다.
    setChoices({ a: item.choiceA, b: item.choiceB });
    setScenarioTexts({ a: item.choiceA, b: item.choiceB });
    setScenarioDomains({ a: [planet.key], b: [planet.key] });
    setPlanet(null);
    setCluster(null);
    navigate("/input");
  }

  const allGroups = useMemo(() => adaptiveGroups(null, state), [state]);
  const selectedGroups = useMemo(() => planet ? adaptiveGroups(planet.key, state) : allGroups, [planet, state, allGroups]);

  // 행성 둘레를 도는 별자리 = 그 영역의 일기. 전에는 시나리오 표식(현재/3개월/1년/3년
  // 고정 4개)이 돌고 있어서, 기록이 20개여도 별은 4개만 보였다.
  // "당신의 기록이 별이 되고, 별들이 연결되어 우주가 됩니다" 가 이 화면의 약속이다.
  const orbitGroups = useMemo(() => {
    // 전체 우주에서는 행성마다 최근 별자리 두 개만 보여준다. 모든 기록을 동시에
    // 띄우면 행성보다 선이 더 강해지고 같은 형태가 배경 무늬처럼 반복된다.
    // 과거 별자리는 행성을 선택하거나 기록 아카이브에서 그대로 확인할 수 있다.
    if (planet) return starGroupsOf(planet.key, state).slice(-6);
    return PLANETS.flatMap((item) => starGroupsOf(item.key, state).slice(-2));
  }, [planet, state]);
  const planetScenarios = useMemo(
    () => (planet ? scenariosByPlanet(planet.key, state) : []), [planet, state]);

  function openPlanet(key) { setPlanet(PLANETS.find((item) => item.key === key)); setCluster(null); }

  return (
    <div className="relative h-full min-h-[620px] overflow-hidden bg-[#030712] lg:min-h-[calc(100dvh-76px)]">
      <div className="pointer-events-none absolute left-8 top-6 z-20">
        <h1 className="text-[25px] font-bold tracking-[-.03em]">나의 우주</h1>
        <p className="mt-1 text-[11px] text-sub">당신의 기록이 별이 되고, 별들이 연결되어 우주가 됩니다.</p>
      </div>
      <div className="absolute right-6 top-5 z-30">
        <button type="button" onClick={() => navigate("/archive")} className="tap flex items-center gap-2 rounded-full border border-white/10 bg-black/25 px-3 text-[10px] text-sub backdrop-blur"><Archive size={13} /> 보관함</button>
      </div>
      {/* 패널이 열리면 지도를 왼쪽 절반으로 민다 — 패널 폭(50vw)과 같은 값이라야
          지도가 창 뒤로 숨지 않고 정확히 반반이 된다. */}
      <div data-tour="universe-map" className={`transition-[margin] duration-300 ease-out ${planet?"md:mr-[420px] lg:mr-[50vw] xl:mr-[50vw]":""}`}>
        <UniverseMap planets={PLANETS} groups={orbitGroups} skin={skin} scenarios={state.scenarios || []} selectedKey={planet?.key} onPlanetSelect={(key)=>key ? openPlanet(key) : (setPlanet(null),setCluster(null))} onConstellationOpen={(group,key)=>{
          // 기록 별자리를 누르면 그 별자리를 펼친다(행성 전체는 패널 안에서 열 수 있다).
          if (key) setPlanet(PLANETS.find((item) => item.key === key));
          setCluster(group);
        }} onScenarioOpen={(scenario)=>openPlanet(scenario.domain)} />
      </div>
      {/* 별자리도 누를 수 있다는 걸 여기서 말해 주지 않으면 아무도 안 눌러 본다. */}
      <p className="pointer-events-none absolute bottom-5 left-1/2 z-20 w-[min(92%,640px)] -translate-x-1/2 text-center text-[10px] leading-relaxed text-white/40">
        행성을 누르면 그 영역의 흐름과 미래가 열려요 · <span className="text-white/60">별자리를 누르면 그 주의 기록을 볼 수 있어요</span> · 드래그 회전 · 휠/핀치 확대
      </p>

      {/* 시나리오 마름모·카드는 모두 그 행성 모달로 모은다.
          예전 FutureScenarioPanel 은 시점 문구가 전부 고정 텍스트였고 br(세부 예측)이
          비어 있어 "세부 예측 결과가 아직 저장되지 않았습니다"만 뜨는 빈 화면이었다.
          행성 모달이 그 영역의 기록·기회·N년 뒤를 실제 데이터로 다 보여준다. */}
      {cluster && <ClusterPanel group={cluster} planet={planet} onClose={()=>setCluster(null)} onWhole={()=>setCluster(null)} />}
      {planet && !cluster && <PlanetModal planet={planet} state={state} onClose={() => setPlanet(null)} onSimulate={() => {
        setScenarioDomains({ a: [planet.key], b: [planet.key] });
        setPlanet(null);
        navigate("/input");
      }} />}
    </div>
  );
}

// ── 별자리 하나 펼쳐보기 ──────────────────────────────────────
// 3D 에서 별자리를 누르면 그 모양과 상태를 여기서 본다.
//
// 이름은 두 축이다 — 모양(그 묶음 기분의 평균×진폭)과 주제(그 별자리가 속한 영역).
// 영역을 주제로 써야 다섯 행성이 서로 다른 이름을 갖는다.
// 다만 이 묶음은 달력 한 주가 아니라 '그 영역 기록 7개'라, 문구를 '7일'이 아니라
// '기록 N개'로 쓴다. 성격 진단으로 읽히지 않게 개수를 항상 앞에 둔다.
function ClusterPanel({ group, planet, onClose, onWhole }) {
  const stars = group?.stars || [];
  const values = stars.map((s) => s.valence).filter((v) => v != null);
  const theme = DOMAIN_THEME[planet?.key] || "기록";
  const named = values.length >= MIN_RECORDS_TO_NAME;
  const shape = named ? shapeOf(values) : null;
  const withText = stars.filter((s) => (s.text || s.note || "").trim());
  const moods = stars.map((s) => s.mood).filter((m) => m != null);
  const avg = moods.length ? (moods.reduce((a, b) => a + b, 0) / moods.length).toFixed(1) : null;

  return (
    // 행성 패널과 같은 비율로 — 여기만 좁으면 별자리를 열 때마다 창 크기가 널뛴다.
    <aside className="absolute inset-y-5 right-5 z-[60] w-[min(420px,calc(100%-28px))] lg:w-[calc(50vw-2.5rem)] xl:w-[calc(50vw-2.5rem)] overflow-y-auto rounded-[24px] border border-white/10 bg-[#09111F]/95 p-5 shadow-[0_30px_90px_rgba(0,0,0,.62)] backdrop-blur-xl">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-[9px] tracking-[.15em] text-[#A88BE8]">RECORD CONSTELLATION</p>
          <h2 className="mt-1 text-[20px] font-bold">
            {named ? `${shape.adj}형 ${theme} 별자리` : "아직 이름 없는 별자리"}
          </h2>
          <p className="mt-1 text-[10px] text-mut">
            {planet?.label} · {group?.label || `별 ${stars.length}개`}
          </p>
        </div>
        <Close onClick={onClose} />
      </div>

      {/* 모양 — 그 묶음의 별을 그대로 그린다. */}
      <div className="mt-4 rounded-[20px] border border-white/[.07] bg-[#070D19] p-3">
        {/* seed 를 넘겨야 3D 우주에 떠 있던 그 별자리와 같은 모양이 나온다. */}
        <Constellation size={250} stars={stars} todayDate={todayKey()} seed={group?.weekStart} />
      </div>

      {/* 상태 */}
      <div className="mt-4 grid grid-cols-3 gap-2">
        <Mini label="별" value={stars.length} />
        <Mini label="평균 기분" value={avg ?? "—"} />
        <Mini label="진폭" value={shape ? shape.sd.toFixed(2) : "—"} />
      </div>

      <p className="mt-3 text-[11.5px] leading-relaxed text-sub">
        {named
          ? `이 기록 ${values.length}개는 ${shapeLineFor(planet?.key, shape.key)}`
          : `기록이 ${values.length}개라 아직 모양을 부르지 않았어요. ${MIN_RECORDS_TO_NAME}개부터 이름이 붙어요.`}
      </p>

      {withText.length > 0 && (
        <div className="mt-3 border-t border-white/[.06] pt-3">
          <p className="text-[9.5px] text-mut">이 별자리에 담긴 기록</p>
          <div className="mt-1.5 space-y-1">
            {withText.slice(0, 5).map((s) => (
              <p key={s.date} className="truncate text-[10.5px] text-sub">
                <span className="mr-1.5 text-mut">{dateLabel(s.date)}</span>
                {s.text || s.note}
              </p>
            ))}
          </div>
        </div>
      )}

      <button
        onClick={onWhole}
        className="tap mt-4 w-full rounded-xl border border-[#8B6CCF]/40 bg-[#8B6CCF]/10 text-[12px] font-bold text-[#C7B5F2]"
      >
        {planet?.label} 전체 보기
      </button>
      <p className="mt-3 text-[9px] leading-relaxed text-mut">{HONESTY_NOTE}</p>
    </aside>
  );
}

function Shell({ children, onClose, wide = false }) {
  return <div className="absolute inset-0 z-50 flex items-center justify-center bg-[#02040B]/65 p-5 backdrop-blur-[3px]" onClick={onClose}><section className={`max-h-[88%] overflow-y-auto rounded-[24px] border border-white/10 bg-[#0C1424]/95 p-5 shadow-[0_30px_90px_rgba(0,0,0,.55)] ${wide ? "w-[min(920px,92%)]" : "w-[min(660px,92%)]"}`} onClick={(e) => e.stopPropagation()}>{children}</section></div>;
}
function Close({ onClick }) { return <button type="button" onClick={onClick} className="tap flex h-9 w-9 items-center justify-center rounded-full text-sub"><X size={18} /></button>; }

// 그 행성(영역)으로 분류된 일기의 분석 — 기록 수·기분 흐름·자주 남긴 감정·월별 추이와
// 실제로 그날 쓴 문장. 시나리오(미래)와 기록(과거)이 한 행성에서 만나게 하는 부분이다.
const MOOD_COLORS = ["#E24B4A", "#D85A30", "#EDA100", "#5DCAA5", "#378ADD"];

// 연속 기분 흐름 그래프 — 기록 순서대로 이어지는 SVG polyline (이미지 아님, 데이터로 그림).
function Sparkline({ series = [], trend }) {
  if (series.length < 2) return null; // 점 하나짜리 선은 흐름이 아니다
  const W = 260, H = 40, PAD = 4;
  const xs = (i) => PAD + (i * (W - 2 * PAD)) / (series.length - 1);
  const ys = (v) => H - PAD - ((v + 1) / 2) * (H - 2 * PAD);
  const pts = series.map((p, i) => `${xs(i).toFixed(1)},${ys(p.v).toFixed(1)}`).join(" ");
  const col = trend == null ? "#8B6CCF" : trend > 0.1 ? "#5DCAA5" : trend < -0.1 ? "#F0736F" : "#8B6CCF";
  return (
    <div className="mt-2.5">
      <div className="mb-1 text-[8.5px] text-mut">기분 흐름 (기록 순서대로 이어짐)</div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ maxHeight: 44 }}>
        <line x1={PAD} y1={H / 2} x2={W - PAD} y2={H / 2} stroke="#28324D" strokeWidth="0.5" strokeDasharray="2 3" />
        <polyline points={pts} fill="none" stroke={col} strokeWidth="1.6" strokeLinejoin="round" strokeLinecap="round" />
        {series.map((p, i) => <circle key={i} cx={xs(i)} cy={ys(p.v)} r="1.6" fill={col} />)}
      </svg>
    </div>
  );
}
function DomainRecords({ planet, state, entries, recent }) {
  // 1년치가 들어오면 이 셋은 렌더마다 수백 개 기록을 다시 훑는다 — 상태가 바뀔 때만 돌린다.
  const a = useMemo(() => domainAnalysis(planet.key, state), [planet.key, state]);
  const months = useMemo(() => domainMonths(planet.key, state).slice(0, 6).reverse(), [planet.key, state]);
  const maxN = useMemo(() => Math.max(1, ...months.map((m) => m.analysis.n || 0)), [months]);

  if (!a?.ok) {
    return (
      <div className="mt-4 rounded-[18px] border border-white/[.07] bg-black/20 p-4">
        <p className="text-[11px] font-bold">이 영역의 기록</p>
        <p className="mt-2 text-[10px] leading-relaxed text-mut">{domainReport(a, planet.label)}</p>
      </div>
    );
  }

  return (
    <div className="mt-4 rounded-[18px] border border-white/[.07] bg-black/20 p-4">
      <div className="flex items-center justify-between">
        <p className="text-[11px] font-bold">이 영역의 기록</p>
        <span className="text-[10px] text-[#A88BE8]">{a.n}개 · 평균 {a.moodAvg}</span>
      </div>

      <p className="mt-2 text-[10.5px] leading-relaxed text-sub">{domainReport(a, planet.label)}</p>

      {/* 기분 흐름 — 결과 화면에 있던 그래프를 이리로 옮겼다. 월별 막대는 '언제 많이 썼나'를,
          이 선은 '기록 순서대로 어떻게 흘렀나'를 보여준다. 둘은 다른 질문에 답한다. */}
      <Sparkline series={a.series} trend={a.trend} />
      {/* 월별 기록량 — 이 영역을 언제 많이 썼는지 */}
      {months.length > 1 && (
        <div className="mt-3">
          <div className="flex items-end gap-1.5">
            {months.map((m) => {
              const n = m.analysis.n || 0;
              const mood = m.analysis.moodAvg;
              const col = mood ? MOOD_COLORS[Math.max(0, Math.min(4, Math.round(mood) - 1))] : "#39435F";
              return (
                <div key={m.month} className="flex flex-1 flex-col items-center gap-1">
                  <div className="flex h-[38px] w-full items-end">
                    <div className="w-full rounded-t-[3px]" style={{ height: `${Math.max(8, (n / maxN) * 100)}%`, background: col, opacity: 0.8 }} />
                  </div>
                  <span className="text-[8px] text-mut">{Number(m.month.split("-")[1])}월</span>
                </div>
              );
            })}
          </div>
          <p className="mt-1 text-[8.5px] text-mut">높이 = 기록 수 · 색 = 그달 평균 기분</p>
        </div>
      )}

      {a.topEmotions?.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {a.topEmotions.map((e) => (
            <span key={e} className="rounded-full border border-white/10 px-2 py-0.5 text-[9px] text-sub">{e}</span>
          ))}
        </div>
      )}

      {/* 대표 기록 — 숫자보다 그날 문장이 이 영역을 기억나게 한다.
          기분이 고른 구간에선 '가장 좋았던 날'이 부정적 문장으로 뽑히기도 해서,
          실제 기분값으로 표현을 가른다(4점 이상일 때만 '좋았던 날'). */}
      <div className="mt-3 space-y-1.5">
        {a.best?.text && (
          <div className="rounded-lg bg-[#5DCAA5]/[.08] px-2.5 py-1.5">
            <p className="text-[8.5px] text-[#5DCAA5]">
              {a.best.mood >= 4 ? "가장 좋았던 날" : "그중 나았던 날"} · {dateLabel(a.best.date)}
            </p>
            <p className="mt-0.5 text-[10px] leading-relaxed text-sub">“{a.best.text}”</p>
          </div>
        )}
        {a.worst?.text && a.worst.date !== a.best?.date && (
          <div className="rounded-lg bg-[#F0736F]/[.08] px-2.5 py-1.5">
            <p className="text-[8.5px] text-[#F0736F]">
              {a.worst.mood <= 2 ? "가장 힘들었던 날" : "그중 무거웠던 날"} · {dateLabel(a.worst.date)}
            </p>
            <p className="mt-0.5 text-[10px] leading-relaxed text-sub">“{a.worst.text}”</p>
          </div>
        )}
      </div>

      {/* 최근 기록 몇 개 */}
      {recent?.length > 0 && (
        <div className="mt-3 border-t border-white/[.06] pt-2.5">
          <p className="text-[9.5px] text-mut">최근 기록</p>
          <div className="mt-1.5 space-y-1">
            {recent.map((e, i) => (
              <p key={i} className="truncate text-[10px] text-sub">
                <span className="mr-1.5 text-mut">{dateLabel(e.date)}</span>
                {e.text || e.note || "(체크인만 남긴 날)"}
              </p>
            ))}
          </div>
        </div>
      )}

      <p className="mt-3 text-[8.5px] leading-relaxed text-mut">
        이 영역으로 분류된 기록만 모아 정리한 것이며, 성격 진단이나 예측이 아닙니다.
      </p>
    </div>
  );
}

// ── 이 영역의 N년 뒤 ──────────────────────────────────────────
// 행성 하나에 쌓인 셋(그 영역 일기 · 그 영역에서 돌린 시뮬레이션 · 저장한 우주의 회고)을
// 한 번에 읽어 "이대로 가면 N년 뒤" 를 서사로 받아온다. 예측 수치가 아니라 기록에서
// 끌어온 이야기라, 화면에도 그대로 밝힌다.
// ── 아직 안 가본 길 ──────────────────────────────────────────
// 이 서비스가 하는 일은 하나를 맞히는 게 아니라 놓치고 있던 선택지를 여러 개 보이게
// 하는 것이다. 기록을 읽어 아직 저울에 올려본 적 없는 갈림길을 내밀고, 누르면
// 그 두 선택지가 채워진 채로 시뮬레이션이 열린다.
const EFFORT_COLOR = {
  "지금 바로": "#5DCAA5",
  "몇 달 준비": "#EDA100",
  "길게 준비": "#8FB4F0",
};

function Opportunities({ planet, state, onPick, profile }) {
  const mat = useMemo(() => futureMaterials(planet.key, state), [planet.key, state]);
  const [found, setFound] = useState(() => getCachedOpportunities(planet.key));
  const [busy, setBusy] = useState(false);
  const [mine, setMine] = useState(() => expeditionsFor(planet.key));
  useEffect(() => {
    const refresh = () => setMine(expeditionsFor(planet.key));
    window.addEventListener("pm:expedition", refresh);
    return () => window.removeEventListener("pm:expedition", refresh);
  }, [planet.key]);

  // 이미 떠난 길인지 — 같은 제목을 또 권하면 카드가 지저분해진다.
  const stateOf = (title) => {
    const e = mine.find((x) => x.title === title);
    if (!e) return null;
    return e.doneAt ? "done" : e.gaveUpAt ? "dropped" : "going";
  };

  async function scan() {
    setBusy(true);
    try {
      setFound(await scanOpportunities(planet, { speech: loadSpeech(), state, profile }));
    } finally {
      setBusy(false);
    }
  }

  const stale = found?.ok && found.nRecords != null && mat.total > found.nRecords;

  return (
    <div className="mt-4 rounded-[18px] border border-[#5DCAA5]/25 bg-[#5DCAA5]/[.06] p-4">
      <div className="flex items-center justify-between">
        <p className="text-[11px] font-bold">아직 안 가본 길</p>
        {found?.ok && <span className="text-[9.5px] text-[#7FD9BB]">{found.items.length}개</span>}
      </div>
      <p className="mt-1 text-[9.5px] leading-relaxed text-mut">
        아는 두 갈래 사이에서만 고민하지 않도록, 기록에서 다른 길을 찾아봐요.
      </p>

      {!mat.ready ? (
        <p className="mt-2 text-[10px] leading-relaxed text-mut">
          이 영역 일기가 3개는 모여야 길을 찾을 수 있어요. 지금 {mat.total}개예요.
        </p>
      ) : (
        <>
          {found?.ok && (
            <div className="mt-3 space-y-2">
              {found.items.map((it, i) => {
                const st = stateOf(it.title);
                return (
                  <div key={i} className="rounded-xl border border-white/[.07] bg-black/25 p-3">
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-[11px] font-semibold text-ink">{it.title}</p>
                      {it.effort && (
                        <span
                          className="shrink-0 rounded-full px-2 py-0.5 text-[8.5px]"
                          style={{
                            color: EFFORT_COLOR[it.effort] || "#9FB0CE",
                            background: `${EFFORT_COLOR[it.effort] || "#9FB0CE"}1A`,
                          }}
                        >
                          {it.effort}
                        </span>
                      )}
                    </div>
                    {it.why && <p className="mt-1 text-[10px] leading-relaxed text-sub">{it.why}</p>}
                    {it.first && (
                      <p className="mt-1.5 text-[9.5px] leading-relaxed text-mut">첫 걸음 · {it.first}</p>
                    )}
                    {/* 두 갈래로 나간다 — 아직 모르겠으면 작게 다녀오고(탐험),
                        저울에 올릴 준비가 됐으면 바로 비교한다. */}
                    <div className="mt-2 flex gap-1.5">
                      {st === "done" ? (
                        <span className="flex-1 rounded-lg bg-[#5DCAA5]/15 py-1.5 text-center text-[10px] text-[#7FD9BB]">
                          다녀온 길 ✓
                        </span>
                      ) : st === "going" ? (
                        <span className="flex-1 rounded-lg bg-white/[.06] py-1.5 text-center text-[10px] text-mut">
                          탐험 중…
                        </span>
                      ) : (
                        <button
                          onClick={() => startExpedition({
                            planet: planet.key, planetLabel: planet.label, title: it.title,
                            step: it.first, why: it.why, choiceA: it.choiceA, choiceB: it.choiceB,
                          })}
                          className="tap flex-1 rounded-lg bg-[#3E9C7F] py-1.5 text-[10px] font-bold text-white"
                        >
                          작은 탐험으로 다녀오기
                        </button>
                      )}
                      <button
                        onClick={() => onPick(it)}
                        className="tap rounded-lg border border-white/[.09] px-2.5 py-1.5 text-[10px] text-sub"
                        title={`${it.choiceA} vs ${it.choiceB}`}
                      >
                        비교하기
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
          {found && !found.ok && found.reason && (
            <p className="mt-3 text-[10px] leading-relaxed text-mut">{found.reason}</p>
          )}

          <button
            onClick={scan}
            disabled={busy}
            className={`tap mt-3 w-full rounded-xl text-[12px] font-bold ${
              busy ? "bg-[#1E2740] text-mut" : "bg-[#3E9C7F] text-white"
            }`}
          >
            {busy ? "기록에서 길을 찾는 중…" : found?.ok ? "다시 찾기" : "이 영역의 길 찾기"}
          </button>
          {stale && (
            <p className="mt-1.5 text-[9px] text-[#EDA100]">
              길을 찾은 뒤 기록이 {mat.total - found.nRecords}개 늘었어요. 다시 찾으면 반영돼요.
            </p>
          )}
          <p className="mt-2 text-[8.5px] leading-relaxed text-mut">
            기록에 있는 흐름에서만 끌어온 제안이에요. 눌러서 바로 비교해볼 수 있어요.
          </p>
        </>
      )}
    </div>
  );
}

// 관측 거리 — 멀리 보려면 더 개척해야 한다. 쌓인 게 늘수록 먼 해가 열린다.
// 기록이 곧 망원경이고, 회고(선택하고 돌아와 적은 것)가 가장 멀리 보게 해준다.
// 멀리 보려면 더 개척해야 한다. 다만 '겪은 것'을 만드는 길이 시뮬레이션 하나뿐이면
// 5년·10년은 사실상 안 열린다. 작은 탐험을 다녀온 것도 같은 무게로 센다 —
// 오히려 상상한 갈림길보다 실제로 가서 알아온 쪽이 단단한 근거다.
const YEAR_TIERS = [
  { years: 1, need: { records: 3 } },
  { years: 3, need: { records: 10 } },
  { years: 5, need: { records: 10, probes: 1 } },
  { years: 10, need: { records: 10, probes: 1, deep: 1 } },
];

function tierState(tier, mat) {
  const trips = mat.trips?.length || 0;
  const have = {
    records: mat.total,
    probes: mat.sims.length + trips,          // 저울에 올렸거나 직접 다녀온 것
    deep: mat.reflections + trips,            // 그래서 알게 된 것을 적어둔 것
  };
  const missing = [];
  if (have.records < (tier.need.records || 0)) {
    missing.push(`일기 ${tier.need.records - have.records}개`);
  }
  if (have.probes < (tier.need.probes || 0)) missing.push("작은 탐험 1번(또는 시뮬레이션)");
  if (have.deep < (tier.need.deep || 0)) missing.push("탐험 기록 1개(또는 회고)");
  return { open: missing.length === 0, missing };
}

function FutureYears({ planet, state, profile }) {
  const mat = useMemo(() => futureMaterials(planet.key, state), [planet.key, state]);
  const tiers = useMemo(() => YEAR_TIERS.map((t) => ({ ...t, ...tierState(t, mat) })), [mat]);
  const furthest = useMemo(() => {
    const open = tiers.filter((t) => t.open);
    return open.length ? open[open.length - 1].years : null;
  }, [tiers]);

  const [years, setYears] = useState(() => furthest || 1);
  const [busy, setBusy] = useState(false);
  const [story, setStory] = useState(() => (furthest ? getCachedFuture(planet.key, furthest) : null));

  // 햇수를 바꾸면 그 햇수로 써둔 이야기가 있으면 꺼내고, 없으면 비운다.
  function pickYears(y) {
    setYears(y);
    setStory(getCachedFuture(planet.key, y));
  }

  async function write() {
    setBusy(true);
    try {
      setStory(await writeFuture(planet, years, { speech: loadSpeech(), state, profile }));
    } finally {
      setBusy(false);
    }
  }

  // 새 기록이 쌓였으면 다시 쓸 만하다고 알려준다(이야기는 쓴 시점에 묶여 있다).
  const stale = story?.ok && story.nRecords != null && mat.total > story.nRecords;

  return (
    <div className="mt-4 rounded-[18px] border border-[#4E7FD9]/25 bg-[#4E7FD9]/[.07] p-4">
      <div className="flex items-center justify-between">
        <p className="text-[11px] font-bold">이 영역의 N년 뒤</p>
        <span className="text-[9.5px] text-[#8FB4F0]">
          일기 {mat.total}개{mat.sims.length ? ` · 시뮬 ${mat.sims.length}개` : ""}
          {mat.trips?.length ? ` · 탐험 ${mat.trips.length}개` : ""}{mat.reflections ? ` · 회고 ${mat.reflections}개` : ""}
        </span>
      </div>

      {!furthest ? (
        <p className="mt-2 text-[10px] leading-relaxed text-mut">
          이 영역 일기가 3개는 모여야 1년 뒤가 보여요. 지금 {mat.total}개예요.
        </p>
      ) : (
        <>
          {/* 잠긴 해는 눌러도 안 열리고, 무엇을 더 쌓아야 열리는지만 알려준다. */}
          <div className="mt-3 grid grid-cols-4 gap-1.5">
            {tiers.map((t) => (
              <button
                key={t.years}
                onClick={() => t.open && pickYears(t.years)}
                disabled={!t.open}
                title={t.open ? undefined : `${t.missing.join(" + ")} 더 모으면 열려요`}
                className={`tap rounded-xl border py-2 text-[10px] font-semibold ${
                  !t.open
                    ? "border-white/[.05] text-[#4A5573]"
                    : years === t.years
                      ? "border-[#4E7FD9] bg-[#4E7FD9]/20 text-[#B6D0FA]"
                      : "border-white/[.07] text-mut"
                }`}
              >
                {t.open ? `${t.years}년 뒤` : `🔒 ${t.years}년`}
              </button>
            ))}
          </div>
          {tiers.some((t) => !t.open) && (
            <p className="mt-1.5 text-[9px] leading-relaxed text-mut">
              {(() => {
                const next = tiers.find((t) => !t.open);
                return `${next.missing.join(" + ")} 더 쌓이면 ${next.years}년 뒤까지 보여요 — 멀리 보려면 더 개척해야 해요.`;
              })()}
            </p>
          )}

          {story?.ok ? (
            <div className="mt-3 space-y-2.5">
              {story.now && (
                <div className="rounded-xl bg-black/20 p-3">
                  <p className="text-[9px] text-mut">지금 이 영역은</p>
                  <p className="mt-1 text-[10.5px] leading-relaxed text-sub">{story.now}</p>
                </div>
              )}
              <div className="rounded-xl border border-[#4E7FD9]/25 bg-black/25 p-3">
                <p className="text-[9px] text-[#8FB4F0]">{story.years}년 뒤</p>
                <p className="mt-1 text-[11px] leading-relaxed text-ink">{story.future}</p>
              </div>
              {story.hinge && (
                <div className="rounded-xl bg-[#EDA100]/[.08] p-3">
                  <p className="text-[9px] text-[#EDA100]">이 미래를 가르는 갈림길</p>
                  <p className="mt-1 text-[10.5px] leading-relaxed text-sub">{story.hinge}</p>
                </div>
              )}
              {story.basis?.length > 0 && (
                <div className="border-t border-white/[.06] pt-2.5">
                  <p className="text-[9px] text-mut">이 이야기를 끌어온 기록</p>
                  <ul className="mt-1 space-y-0.5">
                    {story.basis.map((b, i) => (
                      <li key={i} className="text-[9.5px] leading-relaxed text-mut">· {b}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          ) : story?.reason ? (
            <p className="mt-3 text-[10px] leading-relaxed text-mut">{story.reason}</p>
          ) : null}

          <button
            onClick={write}
            disabled={busy}
            className={`tap mt-3 w-full rounded-xl text-[12px] font-bold ${
              busy ? "bg-[#1E2740] text-mut" : "bg-[#4E7FD9] text-white"
            }`}
          >
            {busy ? "기록을 읽는 중…" : story?.ok ? "다시 쓰기" : `${years}년 뒤 이야기 쓰기`}
          </button>
          {stale && (
            <p className="mt-1.5 text-[9px] text-[#EDA100]">
              이야기를 쓴 뒤 기록이 {mat.total - story.nRecords}개 늘었어요. 다시 쓰면 반영돼요.
            </p>
          )}
          <p className="mt-2 text-[8.5px] leading-relaxed text-mut">
            예측이 아니라 내 기록에서 끌어온 이야기예요. 통계 예측치와는 무관합니다.
          </p>
        </>
      )}
    </div>
  );
}

function SummaryMetric({ label, value, suffix, accent }) {
  return <div className="px-3 text-center"><p className="text-[9px] text-mut">{label}</p><p className="mt-1 whitespace-nowrap text-[17px] font-bold tabular-nums" style={accent ? {color:accent} : undefined}>{value}<span className="ml-1 text-[10px] font-medium text-sub">{suffix}</span></p></div>;
}

function InsightCard({ tone, title, text }) {
  if (!text) return null;
  const good = tone === "good";
  const color = good ? "#65D6A6" : "#F0736F";
  return <div className="rounded-xl border px-3 py-3" style={{borderColor:`${color}30`,background:`${color}0D`}}><p className="text-[9.5px] font-semibold" style={{color}}>{title}</p><p className="mt-1.5 line-clamp-3 text-[10px] leading-relaxed text-sub">{text}</p></div>;
}

function TrendChart({ series, accent }) {
  const points = (series || []).slice(-24);
  if (points.length < 2) return <div className="mt-3 flex h-[150px] items-center justify-center rounded-2xl border border-white/[.06] bg-black/15 text-[10px] text-mut">기록이 2개 이상 쌓이면 흐름이 나타나요.</div>;
  const W=500,H=150,L=28,R=8,T=12,B=24;
  const x=(i)=>L+i*(W-L-R)/(points.length-1);
  const y=(v)=>T+(1-((Number(v)+1)/2))*(H-T-B);
  const line=points.map((p,i)=>`${x(i)},${y(p.v)}`).join(" ");
  const area=`${L},${H-B} ${line} ${x(points.length-1)},${H-B}`;
  return <div className="mt-3 overflow-hidden rounded-2xl border border-white/[.06] bg-black/15 px-2 pt-2">
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" aria-label="최근 기분 흐름 선 그래프">
      {[1,2,3,4,5].map((n)=>{const yy=T+(5-n)*(H-T-B)/4;return <g key={n}><line x1={L} y1={yy} x2={W-R} y2={yy} stroke="#293247" strokeWidth=".6"/><text x="4" y={yy+3} fill="#71809A" fontSize="8">{n}.0</text></g>;})}
      <defs><linearGradient id="planetTrendArea" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor={accent} stopOpacity=".25"/><stop offset="1" stopColor={accent} stopOpacity="0"/></linearGradient></defs>
      <polygon points={area} fill="url(#planetTrendArea)"/>
      <polyline points={line} fill="none" stroke={accent} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"/>
      {points.map((p,i)=><circle key={i} cx={x(i)} cy={y(p.v)} r={i===points.length-1?4:2} fill={accent} stroke={i===points.length-1?`${accent}55`:"none"} strokeWidth="6"/>)}
      <text x={L} y={H-7} fill="#71809A" fontSize="8">이전</text><text x={W-R} y={H-7} textAnchor="end" fill="#71809A" fontSize="8">최근</text>
    </svg>
  </div>;
}

// 이 행성에 붙은 별들 — 7개씩 순서대로 묶어 하나씩 넘겨 본다.
//
// 기간(주·달)으로 나누지 않는다. 기록이 띄엄띄엄한 사람은 '이번 주 별자리'가
// 계속 비어 보이는데, 그건 안 쓴 게 아니라 그 주에 이 영역 이야기가 없었을 뿐이다.
// 쌓인 순서대로 7개씩 채우면 빈 별자리가 안 생기고, 넘길수록 시간이 흐른다.
function StarGroups({ groups, accent, onClose }) {
  const [at, setAt] = useState(groups.length - 1); // 최근 묶음부터 본다
  const g = groups[at];
  if (!g) return null;

  const dated = g.stars.map((s) => s.date);
  const go = (d) => setAt((i) => Math.min(groups.length - 1, Math.max(0, i + d)));

  return (
    <div className="mt-4 rounded-2xl border border-white/[.08] bg-[#070D19] p-4">
      <div className="flex items-center justify-between gap-2">
        <div className="min-w-0">
          <p className="text-[9px] tracking-[.15em] text-[#A88BE8]">RECORD CONSTELLATION</p>
          <p className="mt-0.5 text-[12px] font-bold text-ink">
            {at + 1}번째 별자리 <span className="ml-1 text-[10px] font-medium text-mut">/ 전체 {groups.length}개</span>
          </p>
        </div>
        <Close onClick={onClose} />
      </div>

      <div className="mt-3 flex items-center gap-2">
        <button
          type="button"
          onClick={() => go(-1)}
          disabled={at === 0}
          aria-label="이전 별자리"
          className="tap flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-white/10 text-sub disabled:opacity-25"
        >
          <ChevronRight size={16} className="rotate-180" />
        </button>

        <div className="min-w-0 flex-1 rounded-[18px] border border-white/[.06] bg-black/25 py-2">
          <Constellation size={220} stars={g.stars} todayDate={todayKey()} seed={g.weekStart} />
        </div>

        <button
          type="button"
          onClick={() => go(1)}
          disabled={at === groups.length - 1}
          aria-label="다음 별자리"
          className="tap flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-white/10 text-sub disabled:opacity-25"
        >
          <ChevronRight size={16} />
        </button>
      </div>

      <p className="mt-2.5 text-center text-[10px] text-sub">
        {dated[0]?.slice(5)} ~ {dated[dated.length - 1]?.slice(5)}
        <span className="ml-2 text-mut">별 {g.filled}개{g.complete ? "" : " · 채우는 중"}</span>
      </p>

      <div className="mt-3 space-y-1.5 border-t border-white/[.07] pt-2.5">
        {g.stars.map((s) => (
          <p key={s.date} className="text-[9.5px] leading-relaxed text-mut">
            <span className="mr-2" style={{ color: accent }}>{dateLabel(s.date)}</span>
            {s.text || s.note || s.chatSummary || "짧게 남긴 기록"}
          </p>
        ))}
      </div>
    </div>
  );
}

// 관계 그래프 — 누구와의 이야기였나.
//
// 통짜 "관계 52번"은 연인 문제인지 직장 문제인지 모르는 숫자다. 나눠야
// 어느 쪽이 요즘 무거운지가 보인다.
function RelationMixChart({ mix, accent }) {
  if (!mix || !mix.total) {
    return (
      <div className="mt-4 rounded-2xl border border-white/[.08] bg-white/[.035] px-4 py-3.5">
        <span className="text-[11px] font-bold text-ink">누구와의 이야기인지 아직 몰라요</span>
        <p className="mt-1.5 text-[10px] leading-relaxed text-sub">
          기록에 &apos;엄마·친구·팀장&apos;처럼 누구인지 적히면 여기서 나눠 보여드려요.
        </p>
      </div>
    );
  }
  return (
    <div className="mt-4 rounded-2xl border border-white/[.08] bg-white/[.035] px-4 py-3.5">
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-[11px] font-bold text-ink">누구와의 이야기였나</span>
        <span className="shrink-0 text-[9px] text-mut">{mix.total}번 · 사람이 적힌 기록</span>
      </div>

      <div className="mt-3 space-y-2">
        {mix.items.map((it) => (
          <div key={it.key} className="flex items-center gap-2.5">
            <span className="w-[34px] shrink-0 text-[10px] text-sub">{it.key}</span>
            <span className="h-[7px] min-w-0 flex-1 overflow-hidden rounded-full bg-white/[.06]">
              <span
                className="block h-full rounded-full transition-[width] duration-500"
                style={{ width: `${(it.count / mix.max) * 100}%`, background: it.count ? accent : "transparent" }}
              />
            </span>
            <span className="w-[42px] shrink-0 text-right text-[10px] tabular-nums text-mut">
              {it.count}번<span className="ml-1 text-[9px]">{it.pct}%</span>
            </span>
          </div>
        ))}
      </div>

      <p className="mt-3 border-t border-white/[.07] pt-2.5 text-[10px] leading-relaxed text-sub">
        <b className="font-semibold text-ink">{mix.top}</b> 이야기가 가장 자주 나왔어요.
      </p>
      {mix.unknown > 0 && (
        <p className="mt-1 text-[9px] leading-relaxed text-mut">
          누구인지 안 적힌 기록 {mix.unknown}개는 세지 않았어요.
        </p>
      )}
    </div>
  );
}

// 진로·관계·성장성 그래프 — 주마다 이 영역 이야기가 몇 번 나왔나.
//
// 좋고 나쁨이 아니라 '요즘 이게 얼마나 마음에 걸리는지'다. 기분 그래프와 달리
// 왜곡될 여지가 없다 — 많이 적혔으면 실제로 많이 적힌 것이다.
function MentionChart({ mentions, accent, label }) {
  if (!mentions || !mentions.total) {
    return (
      <>
        <h3 className="text-[14px] font-bold">얼마나 자주 떠올랐나</h3>
        <p className="mt-2 text-[10px] text-mut">최근 {mentions?.weeks || 8}주 동안 {label} 이야기는 없었어요.</p>
      </>
    );
  }
  return (
    <>
      <div className="flex items-center justify-between">
        <h3 className="text-[14px] font-bold">얼마나 자주 떠올랐나</h3>
        <span className="text-[9px] text-mut">최근 {mentions.weeks}주 · 주별 기록 수</span>
      </div>

      <div className="mt-3 flex h-[76px] items-end gap-1.5">
        {mentions.bins.map((b) => (
          <div key={b.from} className="flex min-w-0 flex-1 flex-col items-center gap-1">
            <span className="text-[8px] tabular-nums text-mut">{b.count || ""}</span>
            <span
              className="w-full rounded-t-[3px] transition-[height] duration-500"
              style={{
                height: `${Math.max(2, (b.count / mentions.max) * 52)}px`,
                background: b.count ? accent : "rgba(255,255,255,.08)",
              }}
            />
            <span className="truncate text-[7.5px] text-mut">{b.label}</span>
          </div>
        ))}
      </div>

      <p className="mt-2.5 text-[10px] leading-relaxed text-sub">
        {mentions.rising === null
          ? `최근 ${mentions.weeks}주에 ${mentions.total}번 나왔어요.`
          : mentions.rising
            ? `최근 4주(${mentions.recent}번)가 그 앞 4주(${mentions.before}번)보다 늘었어요. 요즘 더 자주 떠오르고 있어요.`
            : `최근 4주(${mentions.recent}번)가 그 앞 4주(${mentions.before}번)보다 줄었어요.`}
      </p>
      <p className="mt-1 text-[9px] leading-relaxed text-mut">
        많이 적혔다고 나쁜 건 아니에요. 신경 쓰고 있다는 뜻이에요.
      </p>
    </>
  );
}

// 성장성 그래프 — 무엇에 시간을 썼는지의 분포.
//
// 막대 길이는 '가장 두터운 칸' 기준으로 잡는다. 전체 대비로 하면 다섯 칸이 다
// 짧아져서 차이가 안 보인다. 여기서 보고 싶은 건 절대량이 아니라 **치우침**이다.
function SkillMixChart({ mix, accent, why }) {
  if (!mix || !mix.total) {
    return (
      <div className="mt-4 rounded-2xl border border-white/[.08] bg-white/[.035] px-4 py-3.5">
        <span className="text-[11px] font-bold text-ink">아직 역량 기록이 없어요</span>
        <p className="mt-1.5 text-[10px] leading-relaxed text-sub">
          체크인에서 &apos;오늘 주로 쓴 역량&apos;을 고르면 여기에 쌓여요.
        </p>
      </div>
    );
  }
  const max = Math.max(...mix.items.map((i) => i.count), 1);
  const empty = mix.items.filter((i) => !i.count);

  return (
    <div className="mt-4 rounded-2xl border border-white/[.08] bg-white/[.035] px-4 py-3.5">
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-[11px] font-bold text-ink">무엇을 쌓았나요</span>
        <span className="shrink-0 text-[9px] text-mut">최근 {mix.windowDays}일 · {mix.total}일 기록</span>
      </div>

      <div className="mt-3 space-y-2">
        {mix.items.map((it) => (
          <div key={it.key} className="flex items-center gap-2.5">
            <span className="w-[46px] shrink-0 text-[10px] text-sub">{it.key}</span>
            <span className="h-[7px] min-w-0 flex-1 overflow-hidden rounded-full bg-white/[.06]">
              <span
                className="block h-full rounded-full transition-[width] duration-500"
                style={{ width: `${(it.count / max) * 100}%`, background: it.count ? accent : "transparent" }}
              />
            </span>
            <span className="w-[42px] shrink-0 text-right text-[10px] tabular-nums text-mut">
              {it.count}일<span className="ml-1 text-[9px]">{it.pct}%</span>
            </span>
          </div>
        ))}
      </div>

      <p className="mt-3 border-t border-white/[.07] pt-2.5 text-[10px] leading-relaxed text-sub">
        {/* josa() 는 단어까지 붙여서 돌려준다 — 조사만 떼어 쓰려다 '기획기획이' 가 됐었다. */}
        <b className="font-semibold text-ink">{mix.top}</b>{hasFinalConsonant(mix.top) ? "이" : "가"} 가장 두터워요.
        {empty.length
          ? ` ${empty.map((e) => e.key).join(" · ")}${hasFinalConsonant(empty[empty.length - 1].key) ? "은" : "는"} 아직 비어 있어요.`
          : ` ${mix.gap} 쪽이 가장 얇아요.`}
      </p>
      <p className="mt-1 text-[9px] leading-relaxed text-mut">
        {why} 쉰 날({mix.rest}일)은 역량이 아니라 따로 뒀어요.
      </p>
    </div>
  );
}

function PlanetModal({ planet, state, onClose, onSimulate }) {
  const entries = useMemo(() => planetEntries(state, planet.key), [state, planet.key]);
  const recent = useMemo(() => entries.slice(-3).reverse(), [entries]);
  const analysis = useMemo(() => domainAnalysis(planet.key, state), [planet.key, state]);
  const accent = planet.key === "life" ? "#F39A4A" : planet.to;
  // 영역마다 재는 방법이 다르다 — 삶의 만족·건강만 점수를 낸다.
  // 진로·관계·성장성은 점수 대신 '아직 안 가본 길'을 연다(domainScore.js 참고).
  const metric = metricOf(planet.key);
  const score = useMemo(
    () => (metric.kind === "score" ? domainScore(planet.key, entries) : null),
    [metric.kind, planet.key, entries],
  );
  const scoreReady = score && score.n >= MIN_FOR_SCORE;
  // 성장성 — 역량은 영역 분류와 무관하게 매일 남는다. 그래서 전체 체크인에서 센다.
  const mix = useMemo(
    () => (metric.kind === "mix" ? skillMix(state.checkins || []) : null),
    [metric.kind, state],
  );
  // 점수를 안 내는 영역이 쓰는 그래프 — 주별 언급 빈도.
  const mentions = useMemo(
    () => (metric.kind !== "score" ? domainMentions(entries) : null),
    [metric.kind, entries],
  );
  // 관계 — 연인·가족·친구·직장으로 나눈다(감지는 diarySignals 가 이미 한다).
  const relMix = useMemo(
    () => (metric.kind === "people" ? relationMix(entries, detectRelationSubtype) : null),
    [metric.kind, entries],
  );
  // 이 행성에 붙은 별 — 7개씩 순서대로. 기간이 아니라 쌓인 순서로 묶는다.
  const [starsOpen, setStarsOpen] = useState(false);
  const starGroups = useMemo(() => starGroupsOf(planet.key, state), [planet.key, state]);
  useEffect(() => { setStarsOpen(false); }, [planet.key]);
  const average = analysis?.ok ? Number(analysis.moodAvg) : null;
  const trend = analysis?.ok && Number.isFinite(Number(analysis.trend)) ? Number(analysis.trend) : null;
  const stable = trend == null || Math.abs(trend) < .25;
  // 점수를 안 내는 영역(진로·관계·성장성)에 '좋다/나쁘다'를 붙이면, 안 매긴다고
  // 해놓고 매기는 셈이다. 그런 영역은 기록이 쌓였다는 사실만 말한다.
  const status = metric.kind !== "score"
    ? (entries.length
        ? `${planet.label} 이야기가 ${entries.length}번 나왔어요. 아래에서 그 흐름을 볼 수 있어요.`
        : `아직 ${planet.label} 이야기는 없어요.`)
    : average == null
      ? `아직 ${planet.label}의 상태를 알아가는 중이에요.`
      : average >= 4 ? `요즘 ${josa(planet.label, "은", "는")} 전반적으로 좋은 흐름이에요.`
        : average >= 3 ? `요즘 ${josa(planet.label, "은", "는")} 전반적으로 안정적이에요.`
          : `요즘 ${planet.label}에 조금 더 돌봄이 필요해 보여요.`;
  const flow = analysis?.ok
    ? `최근 기록에는 ${stable ? "약간의 흔들림이 있지만, 전체 흐름은 비교적 안정적입니다." : trend > 0 ? "회복되는 흐름이 나타나고 있어요." : "조금 무거워지는 흐름이 보여요."}`
    : "기록이 쌓이면 최근 변화와 흐름을 여기에서 보여드릴게요.";
  const factors = analysis?.topEmotions?.slice(0, 3) || KEYWORDS[planet.key].slice(0, 3);
  const changeText = trend == null ? "—" : `${trend >= 0 ? "+" : ""}${trend.toFixed(1)}`;

  // PC 에서는 화면을 반으로 나눈다 — 왼쪽 지도, 오른쪽 이 창.
  // (아래 지도 쪽 여백도 같은 폭으로 밀어야 실제로 반반이 된다.)
  return <aside className="absolute inset-y-2 right-2 z-40 w-[min(430px,calc(100%-16px))] overflow-y-auto rounded-[26px] border border-white/10 bg-[#070E1B]/95 shadow-[0_30px_100px_rgba(0,0,0,.72)] backdrop-blur-2xl lg:inset-y-4 lg:right-4 lg:w-[calc(50vw-1.5rem)] xl:w-[calc(50vw-1.5rem)]">
    <div className="p-5 lg:p-6">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-4"><PlanetOrb planet={planet} /><div><p className="text-[9px] font-semibold tracking-[.2em]" style={{color:accent}}>FUTURE PLANET</p>
          <div className="mt-1 flex items-center gap-2">
            <h2 className="text-[25px] font-bold tracking-[-.035em] lg:text-[29px]">{planet.label}</h2>
            {/* 이 행성에 붙은 별을 펼쳐 본다. 이름 옆이라 '이 행성의 별'인 게 분명하다. */}
            {starGroups.length > 0 && (
              <button
                type="button"
                onClick={() => setStarsOpen((v) => !v)}
                aria-label={starsOpen ? "별자리 닫기" : `별자리 보기 (${starGroups.length}개)`}
                aria-pressed={starsOpen}
                className="tap flex h-8 w-8 items-center justify-center rounded-full border transition-colors"
                style={{
                  borderColor: starsOpen ? accent : "rgba(255,255,255,.14)",
                  background: starsOpen ? `${accent}22` : "transparent",
                }}
              >
                <svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true">
                  <path
                    d="M12 2.6l2.7 6.1 6.6.6-5 4.4 1.5 6.5L12 16.8 6.2 20.2l1.5-6.5-5-4.4 6.6-.6L12 2.6Z"
                    fill={starsOpen ? accent : "none"}
                    stroke={accent}
                    strokeWidth="1.6"
                    strokeLinejoin="round"
                  />
                </svg>
              </button>
            )}
          </div>
        </div></div>
        <Close onClick={onClose}/>
      </div>

      {starsOpen && <StarGroups groups={starGroups} accent={accent} onClose={() => setStarsOpen(false)} />}

      <p className="mt-5 text-[13px] font-semibold leading-relaxed text-ink">{status}</p>
      {/* 점수를 내는 영역(삶의 만족·건강)만 숫자를 앞세운다. */}
      {metric.kind === "score" ? (
        <>
          <div className="mt-4 grid grid-cols-3 divide-x divide-white/[.08] rounded-2xl border border-white/[.08] bg-white/[.035] py-3">
            <SummaryMetric label={metric.label} value={scoreReady ? score.value.toFixed(1) : "—"} suffix="/ 10" accent={accent}/>
            <SummaryMetric label="기록" value={entries.length} suffix="개" />
            <SummaryMetric label="최근 변화" value={changeText} accent={accent}/>
          </div>
          <p className="mt-2 text-[9.5px] leading-relaxed text-mut">
            {scoreReady
              ? `${josa(score.basis, "으로", "로")} 계산했어요 · 기록 ${score.n}일. ${metric.note}`
              : `기록이 ${MIN_FOR_SCORE}일 모이면 점수를 보여드려요. 며칠 치로 영역을 평가할 수는 없어서요.`}
          </p>
        </>
      ) : metric.kind === "mix" ? (
        // 성장성 — 한 숫자가 아니라 무엇을 얼마나 썼는지가 본론이다.
        <SkillMixChart mix={mix} accent={accent} why={metric.why} />
      ) : metric.kind === "people" ? (
        // 관계 — 통짜로 보면 안 된다. 연인·가족·친구·직장은 서로 다른 이야기다.
        <RelationMixChart mix={relMix} accent={accent} />
      ) : null}
      <p className="mt-3 text-[10px] leading-relaxed text-mut">{flow}</p>

      <section className="mt-6 border-t border-white/[.08] pt-5">
        {/* 점수를 안 내는 영역에 기분 그래프를 그리면, 점수는 안 매긴다면서
            그래프로는 매기는 셈이 된다. 거기는 '얼마나 자주 떠올랐나'를 센다. */}
        {metric.kind === "score" ? (
          <>
            <div className="flex items-center justify-between"><h3 className="text-[14px] font-bold">최근 흐름</h3><span className="text-[9px] text-mut">그날의 기분 · 5점 만점</span></div>
            <TrendChart series={analysis?.series || []} accent={accent}/>
          </>
        ) : (
          <MentionChart mentions={mentions} accent={accent} label={planet.label} />
        )}
        <p className="mt-3 text-[9px] font-semibold text-mut">영향 요인</p>
        <div className="mt-2 flex flex-wrap gap-2">{factors.map((factor)=><span key={factor} className="rounded-full border px-3 py-1.5 text-[10px] text-sub" style={{borderColor:`${accent}40`,background:`${accent}10`}}>{factor}</span>)}</div>

        {/* 이 두 장은 '그 영역이 좋았다/나빴다'가 아니라, 그 이야기를 적은 날들 중
            하루 기분이 가장 높고 낮았던 날의 기록이다. 제목에 그걸 드러낸다. */}
        {(analysis?.best?.text || analysis?.worst?.text) && <div className="mt-4 grid gap-2 sm:grid-cols-2">
          <InsightCard tone="good" title={`기분이 가장 좋았던 날 · ${analysis.best?.date ? dateLabel(analysis.best.date) : "—"}`} text={analysis.best?.text}/>
          <InsightCard tone="hard" title={`기분이 가장 무거웠던 날 · ${analysis.worst?.date ? dateLabel(analysis.worst.date) : "—"}`} text={analysis.worst?.text}/>
        </div>}

        <div className="mt-4">
          <details className="group rounded-xl border border-white/[.06] bg-black/15 px-3 py-2.5"><summary className="cursor-pointer list-none text-[10px] text-sub">최근 기록 {recent.length}개 보기 <ChevronRight size={12} className="float-right transition-transform group-open:rotate-90"/></summary><div className="mt-2 space-y-2 border-t border-white/[.06] pt-2">{recent.length ? recent.map((entry)=><p key={entry.date} className="text-[9.5px] leading-relaxed text-mut"><span className="mr-2" style={{color:accent}}>{dateLabel(entry.date)}</span>{entry.text || entry.note || "짧게 남긴 기록"}</p>) : <p className="text-[9.5px] text-mut">아직 기록이 없어요.</p>}</div></details>
        </div>
      </section>

      <section className="relative mt-6 overflow-hidden rounded-[20px] border p-5" style={{borderColor:`${accent}70`,background:`linear-gradient(135deg,${accent}1F,rgba(11,17,31,.72))`,boxShadow:`0 0 32px ${accent}12`}}>
        <span className="pointer-events-none absolute -left-10 -top-16 h-36 w-36 rounded-full blur-2xl" style={{background:`${accent}25`}}/>
        <div className="relative"><h3 className="text-[14px] font-bold">{josa(planet.label, "을", "를")} 높이면 어떤 미래가 펼쳐질까요?</h3>
          <button onClick={onSimulate} className="tap mt-4 flex w-full items-center justify-center gap-2 rounded-full py-3.5 text-[13px] font-bold text-white shadow-lg" style={{background:`linear-gradient(100deg,${accent},#E84E68)`}}>{planet.label} 미래 보기 <ChevronRight size={16}/></button>
          <p className="mt-2 text-center text-[9px] text-mut">이 영역을 중심으로 미래 시뮬레이션을 시작합니다.</p>
        </div>
      </section>

      {/* 분석 기준 — 모든 영역에서 맨 아래 한 자리에 둔다.
          숫자를 먼저 보고 궁금해진 사람이 찾아 내려오는 자리라, 위에 있으면
          읽기 전에 지나치고 중간에 있으면 본론을 끊는다.
          영역마다 재는 방법이 달라서(domainScore.js) 문구도 그 영역 것을 쓴다. */}
      <details className="group mt-5 rounded-xl border border-white/[.06] bg-black/15 px-3 py-2.5">
        <summary className="cursor-pointer list-none text-[10px] text-sub">
          분석 기준 보기 <ChevronRight size={12} className="float-right transition-transform group-open:rotate-90"/>
        </summary>
        <div className="mt-2 space-y-1.5 border-t border-white/[.06] pt-2 text-[9px] leading-relaxed text-mut">
          {metric.kind === "score" ? (
            <>
              <p><b className="text-sub">{metric.label}</b> — {josa(metric.basis, "으로", "로")} 계산해요.</p>
              <p>{metric.note}</p>
            </>
          ) : (
            <p><b className="text-sub">{metric.label}</b> — {metric.why}</p>
          )}
          <p>이 영역으로 분류된 기록만 셉니다. 적지 않은 날은 계산에서 빠지고, 0점으로 치지 않아요.</p>
          <p>성격 진단이나 미래 예측이 아닙니다.</p>
        </div>
      </details>
    </div>
  </aside>;
  /* Legacy modal layout retained below for reference only.
  return <Shell onClose={onClose} wide><div className="grid gap-6 md:grid-cols-[230px_1fr]">
    <div><div className="flex items-center gap-4"><PlanetOrb planet={planet} /><div><h2 className="text-[22px] font-bold">{planet.label}</h2><p className="mt-1 text-[11px] leading-relaxed text-sub">{DESCRIPTIONS[planet.key]}</p></div></div>
      <div className="mt-5 grid grid-cols-3 gap-2">{[["이번 주 별자리",groups.length],["기록한 주",groups.length],["누적 기록",entries.length]].map(([l,v])=><Mini key={l} label={l} value={v}/>)}</div>
      <button onClick={onWeek} className="tap mt-5 w-full rounded-xl bg-[#8B6CCF] text-[12px] font-bold">이번 주 별자리 보기</button>
      <button onClick={onAdd} className="tap mt-2 flex w-full items-center justify-center gap-2 rounded-xl border border-white/10 text-[12px] text-sub"><Plus size={14}/>기록 추가</button>
    </div>
    <div className="border-white/10 md:border-l md:pl-6"><div className="flex items-start justify-between"><div><p className="text-[11px] font-semibold text-sub">주요 키워드</p><div className="mt-2 flex flex-wrap gap-1.5">{KEYWORDS[planet.key].map(k=><span key={k} className="rounded-full bg-white/[.05] px-2.5 py-1 text-[9px] text-sub">{k}</span>)}</div></div><Close onClick={onClose}/></div>
      <p className="mb-2 mt-6 text-[11px] font-semibold text-sub">최근 기록</p><div className="divide-y divide-white/[.06] rounded-xl bg-black/10 px-3">{recent.length ? recent.map(e=><div key={e.date} className="flex justify-between gap-4 py-3 text-[11px]"><span className="truncate text-sub">{e.text || e.note || "기록한 하루"}</span><span className="text-mut">{dateLabel(e.date)}</span></div>) : <p className="py-5 text-[11px] text-mut">아직 기록이 없어요.</p>}</div>
      <button onClick={onArchive} className="tap mt-3 text-[11px] text-cyan">전체 아카이브 보기 <ChevronRight size={13} className="inline"/></button></div>
  </div></Shell>; */
}

function FutureScenarioPanel({ planet, future, onClose, onCompare }) {
  const scenario = future.scenario || future;
  const [horizon,setHorizon] = useState(future.selectedPoint?.horizon || "현재");
  useEffect(()=>setHorizon(future.selectedPoint?.horizon || "현재"),[future]);
  const branches = scenario.br?.filter(Boolean) || [];
  const horizonCopy = {
    "현재":"선택을 앞둔 지금의 조건과 출발점을 보여줍니다.",
    "3개월":"초기 적응과 비용, 가장 먼저 체감할 변화를 살펴봅니다.",
    "1년":"생활 패턴과 만족도, 성장 방향이 자리 잡는 시점입니다.",
    "3년":"선택이 장기적인 경로와 기회에 만든 차이를 확인합니다.",
  };
  return <aside className="absolute inset-y-5 right-5 z-[60] w-[min(430px,calc(100%-40px))] lg:w-[calc(50vw-2.5rem)] xl:w-[calc(50vw-2.5rem)] overflow-y-auto rounded-[24px] border border-white/10 bg-[#09111F]/95 p-5 shadow-[0_30px_90px_rgba(0,0,0,.62)] backdrop-blur-xl">
    <div className="flex items-start justify-between"><div><p className="text-[9px] tracking-[.15em] text-[#A88BE8]">FUTURE CONSTELLATION</p><h2 className="mt-1 text-[20px] font-bold">{scenario.title || `${planet?.label || "미래"} 시나리오`}</h2><p className="mt-1 text-[10px] text-mut">{planet?.label} · {scenario.date || "저장된 미래"}</p></div><Close onClick={onClose}/></div>
    <div className="mt-5"><p className="text-[10px] font-semibold text-sub">미래 시점</p><div className="mt-2 grid grid-cols-4 gap-1.5">{["현재","3개월","1년","3년"].map((item)=><button key={item} onClick={()=>setHorizon(item)} className={`tap rounded-xl border py-2 text-[10px] font-semibold ${horizon===item?"border-[#8B6CCF] bg-[#8B6CCF]/20 text-[#CDBDF3]":"border-white/[.07] text-mut"}`}>{item}</button>)}</div></div>
    <div className="mt-4 rounded-[18px] border border-[#8B6CCF]/25 bg-[#8B6CCF]/[.07] p-4"><p className="text-[10px] font-bold text-[#BBA4ED]">{horizon}의 나</p><p className="mt-2 text-[12px] leading-relaxed text-sub">{horizonCopy[horizon]}</p>{branches.length?<div className="mt-3 space-y-2">{branches.map((text,i)=><div key={i} className="rounded-xl bg-black/20 p-3 text-[10px] leading-relaxed text-sub"><b className="mr-2 text-[#A88BE8]">미래 {String.fromCharCode(65+i)}</b>{text}</div>)}</div>:<p className="mt-3 text-[10px] text-mut">세부 예측 결과가 아직 저장되지 않았습니다. 다시 시뮬레이션하면 이 시점의 변화가 채워집니다.</p>}</div>
    <div className="mt-4 grid grid-cols-3 gap-2"><Mini label="시나리오" value={branches.length || 1}/><Mini label="시간축" value="4"/><Mini label="근거" value={branches.length?"연결":"대기"}/></div>
    <button onClick={onCompare} className="tap mt-4 w-full rounded-xl bg-[#8B6CCF] text-[12px] font-bold">다른 미래와 비교하기</button>
    <p className="mt-3 text-[9px] leading-relaxed text-mut">예측은 확정된 미래가 아니라 현재 입력과 관측 근거를 바탕으로 한 탐색 결과입니다.</p>
  </aside>;
}

function WeekModal({ planet, group, picked, onPick, onClose, onReport }) {
  if (!group) return null;
  return <aside className="absolute inset-y-5 right-5 z-[60] w-[min(430px,calc(100%-40px))] lg:w-[calc(50vw-2.5rem)] xl:w-[calc(50vw-2.5rem)] overflow-y-auto rounded-[24px] border border-white/10 bg-[#09111F]/95 p-5 shadow-[0_30px_90px_rgba(0,0,0,.62)] backdrop-blur-xl">
    <div className="flex items-start justify-between"><div><p className="text-[9px] tracking-[.15em] text-[#A88BE8]">ORBITING CONSTELLATION</p><h2 className="mt-1 text-[20px] font-bold">{planet?.label || "나의 우주"} · 별자리</h2><p className="mt-1 text-[11px] text-mut">{dateLabel(group.weekStart)} — {dateLabel(group.weekEnd)}</p></div><Close onClick={onClose}/></div>
    <div className="mt-4 rounded-[20px] border border-white/[.07] bg-[#070D19] p-3"><Constellation size={250} stars={group.stars} todayDate={todayKey()} selectedDate={picked?.date} onSelect={(star)=>!star.future&&onPick(star)}/></div>
    <p className="mt-2 text-[9px] leading-relaxed text-mut">별을 선택하면 해당 날짜의 기록이 아래에 열립니다.</p>
    {picked ? <RecordPreview record={picked}/> : <div className="mt-4 rounded-xl border border-white/[.06] bg-black/15 p-4 text-[11px] leading-relaxed text-mut">별자리의 별을 선택하면 그날 작성한 일기가 표시됩니다.</div>}
  </aside>;
}

function ReportModal({ planet, group, onClose }) {
  const stars=group.stars.filter(s=>!s.empty), moods=stars.map(s=>s.mood||3), avg=moods.length?(moods.reduce((a,b)=>a+b,0)/moods.length).toFixed(1):"—";
  return <Shell onClose={onClose} wide><div className="flex items-start justify-between"><div><h2 className="text-[20px] font-bold">{planet?.label || "전체"} · {dateLabel(group.weekStart)} - {dateLabel(group.weekEnd)} 주간 리포트</h2><p className="mt-1 text-[11px] text-mut">이번 주 기록을 한눈에 돌아봅니다.</p></div><Close onClick={onClose}/></div>
    <div className="mt-5 grid gap-3 md:grid-cols-4"><ReportCard title="체크인 현황" value={`${group.filled}/7`} text="이번 주 체크인"/><ReportCard title="감정 흐름" value={avg} text="평균 기분"/><ReportCard title="반복 키워드" value={KEYWORDS[planet?.key||"career"][0]} text="가장 자주 나타남"/><ReportCard title="이번 주 한줄 요약" value="기록이 방향을 만들고 있어요" text="작은 변화를 이어가세요"/></div>
  </Shell>;
}

function ArchiveModal({ state, onClose, onPlanet, onRecord }) {
  const recent=(state.checkins||[]).filter(e=>!e.empty).slice(-5).reverse();
  return <Shell onClose={onClose} wide><div className="flex items-start justify-between"><div><h2 className="text-[20px] font-bold">기록 아카이브</h2><p className="mt-1 text-[11px] text-mut">행성별 기록과 별자리를 찾아보세요.</p></div><Close onClick={onClose}/></div><div className="mt-5 grid gap-6 md:grid-cols-2"><div className="divide-y divide-white/[.07]">{PLANETS.map(p=>{const entries=planetEntries(state,p.key);return <button key={p.key} onClick={()=>onPlanet(p)} className="tap flex w-full items-center gap-4 py-3 text-left"><PlanetOrb planet={p} small/><div className="min-w-0 flex-1"><div className="text-[12px] font-bold">{p.label}</div><p className="truncate text-[10px] text-mut">{entries.at(-1)?.text||DESCRIPTIONS[p.key]}</p></div><span className="text-[11px] text-sub">{entries.length}개 기록</span><ChevronRight size={15}/></button>})}</div>
    <div className="border-white/10 md:border-l md:pl-5"><p className="mb-2 text-[11px] font-semibold text-sub">최근 기록</p><div className="divide-y divide-white/[.07]">{recent.map(e=><button key={e.date} onClick={()=>onRecord(e)} className="tap flex w-full items-center justify-between gap-3 py-3 text-left"><div className="min-w-0"><div className="text-[11px] font-semibold">{dateLabel(e.date)}</div><p className="mt-1 truncate text-[10px] text-mut">{e.text||e.note||"기록한 하루"}</p></div><ChevronRight size={14}/></button>)}</div></div></div>
  </Shell>;
}

function RecordModal({ record, onClose, onRelated }) { return <Shell onClose={onClose}><div className="flex items-start justify-between"><div><p className="text-[10px] text-mut">기록 상세</p><h2 className="mt-1 text-[19px] font-bold">{dateLabel(record.date)}</h2></div><Close onClick={onClose}/></div><RecordPreview record={record}/><button onClick={onRelated} className="tap mt-4 text-[11px] text-cyan">관련 별자리 보기 <ChevronRight size={13} className="inline"/></button></Shell>; }
function RecordPreview({ record }) { return <div className="mt-4 rounded-xl border border-white/[.07] bg-black/10 p-4"><div className="grid grid-cols-3 gap-3 text-[10px]"><Mini label="기분" value={record.mood?`${record.mood}/5`:"—"}/><Mini label="에너지" value={record.energy?`${record.energy}/5`:"—"}/><Mini label="키워드" value={record.emotion||"기록"}/></div><p className="mt-4 text-[12px] leading-relaxed text-sub">{record.text||record.note||"이날의 기록이 아직 짧아요."}</p></div>; }
function Mini({label,value}) { return <div className="rounded-xl bg-white/[.035] px-2 py-3 text-center"><div className="text-[15px] font-bold text-ink">{value}</div><div className="mt-1 text-[9px] text-mut">{label}</div></div>; }
function ReportCard({title,value,text}) { return <div className="min-h-[145px] rounded-[18px] border border-white/[.07] bg-black/10 p-4"><div className="text-[10px] font-semibold text-sub">{title}</div><div className="mt-5 text-[21px] font-bold text-cyan">{value}</div><p className="mt-2 text-[10px] leading-relaxed text-mut">{text}</p></div>; }
function PlanetOrb({planet,small=false}) {
  return <span className={`relative block shrink-0 overflow-hidden rounded-full border border-white/15 bg-black ${small?"h-10 w-10":"h-16 w-16"}`}>
    <img src={PLANET_TEXTURES[planet.key]} alt="" className="h-full w-full object-cover" />
    <span className="pointer-events-none absolute inset-0 rounded-full shadow-[inset_-9px_-8px_14px_rgba(0,0,0,.72),inset_3px_3px_7px_rgba(255,255,255,.12)]" />
  </span>;
}
