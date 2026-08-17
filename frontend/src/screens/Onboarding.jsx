import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useResult } from "../data/ResultContext.jsx";
import { Eyebrow, Button } from "../components/ui.jsx";
import AvatarBuilder from "../components/AvatarBuilder.jsx";
import { OCCUPATIONS } from "../data/profileOptions.js";
import StarterDataDialog from "../components/StarterDataDialog.jsx";
import { seedStarterData } from "../data/personaSession.js";
import { saveActiveSlot } from "../data/personaSlots.js";

// 성향 = 가치 강제순위(8카드 → 5축). diary_module/qmode/value_ranking.py 와 1:1.
// 다중선택이 아니라 '순서'를 받는다 — "다 중요해요" 편향을 막고 진짜 우선순위를 드러냄.
const VALUE_CARDS = [
  { id: "money", label: "경제적 여유" },
  { id: "status", label: "인정·지위" },
  { id: "family", label: "가족·사랑" },
  { id: "friends", label: "친구·소속" },
  { id: "growth", label: "배움·성취" },
  { id: "freedom", label: "자유·자율" },
  { id: "meaning", label: "의미·나다움" },
  { id: "stability", label: "건강·안정" },
];
const VALUE_IDS = Object.fromEntries(VALUE_CARDS.map((card) => [card.label, card.id]));

// MBTI = 스타일 초기 prior(선택). qmode mbti.py 와 매칭. 확정 아님 — 일기가 갱신.
const MBTI_AXES = [
  { i: 0, a: ["E", "외향"], b: ["I", "내향"] },
  { i: 1, a: ["S", "감각"], b: ["N", "직관"] },
  { i: 2, a: ["T", "사고"], b: ["F", "감정"] },
  { i: 3, a: ["J", "계획"], b: ["P", "즉흥"] },
];

export default function Onboarding() {
  const navigate = useNavigate();
  const { profile, setProfile, setOnboarded } = useResult();

  const [visibleThrough, setVisibleThrough] = useState(0);
  const stepRefs = useRef([]);
  const [incomeInput, setIncomeInput] = useState(() =>
    Number(profile.income) > 0 ? String(profile.income) : "",
  );
  const agePct = ((profile.age - 18) / 52) * 100;
  const ranked = profile.values; // 라벨 배열, 앞이 1순위
  const steps = ["이름", "나이", "성별", "직종", "소득", "가치", "성격유형", "아바타"];

  useEffect(() => {
    const node = stepRefs.current[visibleThrough];
    if (!node || visibleThrough === 0) return;
    const timer = window.setTimeout(() => node.scrollIntoView({ behavior: "smooth", block: "center" }), 80);
    return () => window.clearTimeout(timer);
  }, [visibleThrough]);

  // 갓 만든 계정에는 기록이 없다. 홈으로 바로 보내지 않고 시작 방식을 먼저 고르게 한다.
  //   (두 미래 비교는 기록 없이도 되지만, 맞춤 해석이 약해지는 걸 여기서 알린다.)
  const [starterOpen, setStarterOpen] = useState(false);
  const [starterBusy, setStarterBusy] = useState(false);

  function finish() {
    if (!profile.sex) return;
    setStarterOpen(true);
  }

  function enterApp() {
    setOnboarded(true); // 이후 홈 탭은 '나의 우주' 허브로 진입
    // 안내는 여기서 띄우지 않는다. 들어가자마자 설명이 시작되면 화면을 볼 틈이
    // 없다 — 필요한 사람이 설정 → 알림 · 가이드에서 직접 연다.
    navigate("/my");
  }

  async function startWithSample() {
    setStarterBusy(true);
    await seedStarterData();   // 지원의 1년치 — '예시 데이터' 배지가 함께 붙는다
    enterApp();
  }

  function startEmpty() {
    setStarterBusy(true);
    saveActiveSlot(new Date().toISOString()); // 방금 입력한 프로필을 내 슬롯에 담아둔다
    enterApp();
  }

  function reveal(index) {
    if (index <= visibleThrough) {
      // 이미 열려 있는 단계도 다시 선택하면 그 단계로 확실히 이동한다.
      window.setTimeout(() => {
        stepRefs.current[index]?.scrollIntoView({ behavior: "smooth", block: "center" });
      }, 0);
      return;
    }
    setVisibleThrough(index);
  }

  function revealOnEnter(event, index) {
    // 한글 조합 중 Enter는 글자 확정에 사용되므로 다음 항목을 열지 않는다.
    if (event.key !== "Enter" || event.nativeEvent?.isComposing) return;
    event.preventDefault();
    reveal(index);
  }

  function updateIncome(value) {
    const normalized = value.replace(/^0+(?=\d)/, "");
    setIncomeInput(normalized);
    setProfile((p) => ({ ...p, income: normalized === "" ? null : Number(normalized) }));
  }

  /**
   * 성별 선택 — 속눈썹 초기값도 여기서 정한다.
   *
   * 아바타 만들기에서 이 항목의 이름은 '속눈썹'이다. 실제로 바꾸는 게 속눈썹
   * 하나뿐인데 '성별'이라 부르면, 속눈썹을 켜고 싶은 사람이 자기 성별을 바꿔야
   * 한다. 그래서 이름은 속눈썹으로 두고, 첫 값만 여기서 정해 준다.
   * 아바타 단계는 이 뒤에 오므로 사용자가 고친 값을 덮어쓸 일이 없다.
   */
  function pickSex(value) {
    setProfile((p) => ({
      ...p,
      sex: value,
      sexConfirmed: true,
      avatarConfig: { ...(p.avatarConfig || {}), lashes: value === "2" },
    }));
    reveal(3);
  }

  function confirmIncome() {
    if (incomeInput === "") return;
    reveal(5);
  }

  // 탭한 순서 = 우선순위. 다시 누르면 해제(뒤 순위 자동 당겨짐). 부분순위 허용.
  function toggleRank(label) {
    setProfile((p) => {
      const has = p.values.includes(label);
      const values = has ? p.values.filter((x) => x !== label) : [...p.values, label];
      return {
        ...p,
        values,
        // 기존 /simulate 개인화 입력도 같은 순서로 함께 갱신한다.
        value_ranking: values.map((value) => VALUE_IDS[value]).filter(Boolean),
      };
    });
  }

  // MBTI 4축 각각 한 글자 선택(같은 거 다시 누르면 해제). 4글자 다 차야 유효.
  const mbtiCur = (profile.mbti || "").padEnd(4, "·");
  function pickMbti(i, letter) {
    setProfile((p) => {
      const cur = (p.mbti || "").padEnd(4, "·").split("");
      cur[i] = cur[i] === letter ? "·" : letter;
      const s = cur.join("");
      return { ...p, mbti: s === "····" ? "" : s };
    });
  }

  const stepContent = [
    <div key="name">
      <label className="mb-2 block text-xs text-sub">이름</label>
      <input type="text" value={profile.name || ""} maxLength={20} autoFocus
        aria-label="이름" placeholder="이름 또는 닉네임"
        onChange={(e) => setProfile((p) => ({ ...p, name: e.target.value }))}
        onKeyDown={(e) => profile.name?.trim() && revealOnEnter(e, 1)}
        className="w-full rounded-xl border border-line bg-[#0E1424] px-3.5 py-3 text-sm text-ink outline-none placeholder:text-mut focus:border-cyan" />
      {profile.name?.trim() && visibleThrough < 1 && (
        <Button type="button" className="mt-3" onClick={() => reveal(1)}>다음</Button>
      )}
    </div>,
    <div key="age">
      <div className="mb-4 flex items-end justify-between gap-3">
        <div>
          <label className="block text-xs font-semibold text-sub">나이</label>
          <p className="mt-1 text-[10px] text-mut">같은 연령대의 관측 결과를 비교할 때 사용해요.</p>
        </div>
        <div className="shrink-0 rounded-xl border border-violet-400/25 bg-violet-500/[.08] px-3 py-1.5 text-right">
          <span className="text-[18px] font-bold tabular-nums text-white">{profile.age}</span><span className="ml-1 text-[10px] font-semibold text-violet-300">세</span>
        </div>
      </div>
      <input type="range" min="18" max="70" value={profile.age}
        onChange={(e) => {
          setProfile((p) => ({ ...p, age: Number(e.target.value) }));
          reveal(2);
        }}
        className="h-1 w-full cursor-pointer appearance-none rounded-full outline-none
          [&::-webkit-slider-thumb]:h-[18px] [&::-webkit-slider-thumb]:w-[18px]
          [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:rounded-full
          [&::-webkit-slider-thumb]:bg-white [&::-webkit-slider-thumb]:shadow-[0_0_8px_rgba(127,212,255,.6)]"
        style={{ background: `linear-gradient(90deg, #8B6CCF, #8B6CCF ${agePct}%, #1E2740 ${agePct}%)` }} />
      <div className="mt-3 flex justify-between text-[11px] text-mut"><span>18세</span><span>70세</span></div>
      {visibleThrough < 2 && (
        <Button type="button" className="mt-3" onClick={() => reveal(2)}>다음</Button>
      )}
    </div>,
    <div key="sex">
      <label className="mb-2 block text-xs font-semibold text-sub">성별</label>
      <div className="grid grid-cols-2 gap-2.5">
        {[["1", "♂", "남성"], ["2", "♀", "여성"]].map(([value, symbol, label]) => (
          <button
            key={value}
            type="button"
            onClick={() => pickSex(value)}
            className={`tap flex min-h-[72px] w-full items-center justify-between rounded-2xl border px-4 py-3 text-sm font-semibold transition-colors ${
              profile.sex === value
                ? "border-violet-400 bg-violet-500/15 text-violet-200 shadow-[inset_0_0_20px_rgba(139,108,207,.1)]"
                : "border-line bg-[#0E1424] text-sub"
            }`}
          >
            <span className={`flex h-9 w-9 items-center justify-center rounded-full text-[20px] ${
              profile.sex === value ? "bg-violet-500/20 text-violet-300" : "bg-white/[.05] text-mut"
            }`}>{symbol}</span>
            <span className="text-right">{label}</span>
          </button>
        ))}
      </div>
      {profile.sex && visibleThrough < 3 && (
        <Button type="button" className="mt-3" onClick={() => reveal(3)}>다음</Button>
      )}
    </div>,
    <div key="occupation">
      <label className="mb-2 block text-xs text-sub">직종</label>
      <select value={OCCUPATIONS.includes(profile.occupation) ? profile.occupation : ""}
        onChange={(e) => {
          setProfile((p) => ({ ...p, occupation: e.target.value }));
          reveal(4);
        }}
        className={`w-full rounded-xl border border-line bg-[#0E1424] px-3.5 py-3 text-sm outline-none focus:border-cyan ${
          OCCUPATIONS.includes(profile.occupation) ? "text-ink" : "text-mut"
        }`}>
        <option value="" disabled hidden>직종을 골라주세요</option>
        {OCCUPATIONS.map((o) => <option key={o} className="text-ink">{o}</option>)}
      </select>
      {OCCUPATIONS.includes(profile.occupation) && visibleThrough < 4 && (
        <Button type="button" className="mt-3" onClick={() => reveal(4)}>다음</Button>
      )}
    </div>,
    <div key="income">
      <label className="mb-2 block text-xs text-sub">현재 월소득</label>
      <div className="flex items-center gap-2">
        <input type="number" min="0" step="1" value={incomeInput}
          placeholder="예: 300"
          onChange={(e) => updateIncome(e.target.value)}
          onKeyDown={(e) => incomeInput !== "" && revealOnEnter(e, 5)}
          className="w-full rounded-xl border border-line bg-[#0E1424] px-3.5 py-3 text-sm text-ink outline-none focus:border-cyan" />
        <span className="whitespace-nowrap text-[11px] text-mut">만원 / 월</span>
      </div>
      {incomeInput !== "" && visibleThrough < 5 && (
        <Button className="mt-3" onClick={confirmIncome}>다음</Button>
      )}
    </div>,
    <div key="values">
      <div className="flex items-center justify-between gap-3">
        <label className="text-xs text-sub">지금 내 삶에서 중요한 <b className="text-cyan">순서대로</b> 골라주세요 </label>
        <span className="shrink-0 text-[11px] text-mut">3순위 선택 권장  ({ranked.length}개 선택)</span>
      </div>
      <div className="mt-2 flex flex-col gap-1.5">
        {VALUE_CARDS.map((c) => {
          const rank = ranked.indexOf(c.label); // -1 = 미선택
          const on = rank >= 0;
          return (
            <button
              key={c.id}
              onClick={() => toggleRank(c.label)}
              className={`tap flex items-center gap-3 rounded-xl border px-3.5 py-2.5 text-left transition-colors ${
                on ? "border-cyan bg-[#211735] shadow-[inset_0_0_20px_rgba(112,75,163,.12)]" : "border-line bg-[#0E1424]"
              }`}
            >
              <span
                className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[11px] font-bold transition-colors ${
                  on ? "bg-[#8B6CCF] text-white" : "bg-[#1E2740] text-mut"
                }`}
              >
                {on ? rank + 1 : "+"}
              </span>
              <span className="flex-1">
                <span className={`text-[13px] font-semibold ${on ? "text-cyan" : "text-ink"}`}>
                  {c.label}
                </span>
              </span>
            </button>
          );
        })}
      </div>
      {ranked.length > 0 && (
        <button type="button" onClick={() => reveal(6)}
          className="tap mt-2.5 w-full rounded-xl border border-cyan bg-[#1D1730] py-2.5 text-[12px] font-semibold text-cyan">
          선택 완료
        </button>
      )}
    </div>,
    <div key="mbti">
      <label className="mb-1 block text-xs text-sub">성격유형 (MBTI) <span className="text-[10px] text-mut">· 선택</span></label>
      <div className="flex flex-col gap-1.5">
        {MBTI_AXES.map((ax) => (
          <div key={ax.i} className="flex gap-1.5">
            {[ax.a, ax.b].map(([letter, ko]) => {
              const on = mbtiCur[ax.i] === letter;
              return (
                <button
                  key={letter}
                  onClick={() => pickMbti(ax.i, letter)}
                  className={`tap flex-1 rounded-xl border py-2 text-[12px] transition-colors ${
                    on ? "border-cyan bg-[#1D1730] text-cyan" : "border-line bg-[#0E1424] text-sub"
                  }`}
                >
                  <b className="mr-1">{letter}</b>
                  {ko}
                </button>
              );
            })}
          </div>
        ))}
      </div>
      <button type="button" onClick={() => reveal(7)}
        className="tap mt-2.5 w-full rounded-xl border border-cyan bg-[#1D1730] py-2.5 text-[12px] font-semibold text-cyan">
        다음
      </button>
    </div>,
    <div key="avatar">
      <label className="mb-2 block text-xs text-sub">내 아바타 만들기</label>
      <AvatarBuilder
        config={profile.avatarConfig}
        // avatarChosen — 사람이 직접 고른 얼굴이라는 표시(personaSession 참고).
        onChange={(cfg) => setProfile((p) => ({ ...p, avatarConfig: cfg, avatarChosen: true }))}
      />
    </div>
  ];

  return (
    <div className="lg:grid lg:min-h-[calc(100vh-140px)] lg:grid-cols-[330px_minmax(0,1fr)] lg:items-start lg:gap-14 xl:grid-cols-[380px_minmax(0,1fr)] xl:gap-20">
      <aside className="hidden lg:sticky lg:top-[112px] lg:block">
        <p className="text-[12px] font-bold tracking-[.16em] text-violet-300">START YOUR UNIVERSE</p>
        <h1 className="mt-4 text-[38px] font-bold leading-[1.18] tracking-[-.04em]">당신의 선택을<br />더 잘 이해하기 위해</h1>
        <p className="mt-4 max-w-[310px] text-[13px] leading-6 text-sub">입력한 정보는 두 미래를 같은 기준으로 비교하고 결과를 개인화하는 데 사용됩니다.</p>
        <ol className="mt-9 space-y-2">
          {steps.map((label, index) => {
            const current = index === visibleThrough;
            const complete = index < visibleThrough;
            return <li key={label} className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-[12px] transition-colors ${current ? "bg-violet-500/15 font-semibold text-violet-200" : complete ? "text-sub" : "text-mut"}`}><span className={`flex h-7 w-7 items-center justify-center rounded-full border text-[10px] font-bold ${current ? "border-violet-400 bg-violet-500/20" : complete ? "border-violet-400/30 bg-violet-500/10 text-violet-300" : "border-white/10"}`}>{complete ? "✓" : index + 1}</span>{label}</li>;
          })}
        </ol>
      </aside>

      <main className="min-w-0 lg:max-w-[760px] lg:rounded-[28px] lg:border lg:border-white/[.07] lg:bg-[#0C1727]/70 lg:p-8 lg:shadow-[0_24px_70px_rgba(0,0,0,.24)] lg:backdrop-blur-xl xl:p-10">
        <Eyebrow>나를 알려주세요 · {Math.min(visibleThrough + 1, steps.length)}/{steps.length}</Eyebrow>
        <h2 className="mb-5 hidden text-[26px] font-bold tracking-[-.03em] lg:block">나만의 평행우주 준비하기</h2>
        <div className="mb-8 flex gap-1.5">
          {steps.map((label, index) => (
            <b key={label} className={`h-1 flex-1 rounded-full ${index <= visibleThrough ? "bg-[#8B6CCF] shadow-[0_0_8px_rgba(139,108,207,.22)]" : "bg-[#1E2740]"}`} />
          ))}
        </div>

        <div className="space-y-5 lg:space-y-6">
          {stepContent.slice(0, visibleThrough + 1).map((content, index) => (
            <section ref={(node) => { stepRefs.current[index] = node; }} key={steps[index]} className="scroll-mt-24 animate-fade lg:rounded-[18px] lg:border lg:border-white/[.055] lg:bg-black/10 lg:p-5">
              {content}
            </section>
          ))}
        </div>

        {visibleThrough >= steps.length - 1 && (
          <Button disabled={!profile.sex} className="mb-2 mt-8 lg:ml-auto lg:max-w-[320px]" onClick={finish}>저장하고 시작하기</Button>
        )}
      </main>
      <StarterDataDialog
        open={starterOpen}
        name={profile.name}
        busy={starterBusy}
        onSample={startWithSample}
        onEmpty={startEmpty}
      />
    </div>
  );
}
