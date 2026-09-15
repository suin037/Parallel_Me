import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useResult } from "../data/ResultContext.jsx";
import { Eyebrow, Card } from "../components/ui.jsx";
import { MASCOTS } from "../data/result.js";
import ValueRankingInput from "../components/ValueRankingInput.jsx";
import ValueDeepTest from "../components/ValueDeepTest.jsx";
import { topAxes } from "../data/valueCards.js";
import { loadPrefs, savePrefs } from "../data/prefs.js";
import { OCCUPATIONS } from "../data/profileOptions.js";
import { PSYCH_QUESTIONS } from "../data/psychQuestions.js";
import Avatar from "../components/Avatar.jsx";
import AvatarBuilder from "../components/AvatarBuilder.jsx";
import Mascot from "../components/Mascot.jsx";
import PrivacyVault from "../components/PrivacyVault.jsx";
import { LEVEL_TITLES, XP_RULES, universeSummary } from "../data/myUniverse.js";
import { LEVEL_REWARDS } from "../data/unlocks.js";
import PetMascot from "../components/PetMascot.jsx";
import PetShop from "../components/PetShop.jsx";
import { Bell, ChevronRight, ClipboardCheck, Clock3, Compass, Coins, Info, ListChecks, LockKeyhole, Palette, Scale, ShieldCheck, Smartphone, Sprout, UserRound, LogOut } from "lucide-react";
import { toChoiceDomains } from "../data/choices.js";
import { logoutAccount } from "../data/personaSlots.js";
import { openGuide } from "../data/tour.js";
import { adviceOn, setAdvice } from "../data/guideAdvice.js";
import { TOONHEAD_CREDIT } from "../data/avatarOptions.js";

// 작은 on/off 토글 (track h-6/w-11 · thumb h-4/w-4 · translate 로 이동 — 크기 균형)
function Toggle({ on, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={on}
      className="tap inline-flex w-11 shrink-0 items-center justify-center"
    >
      <span className={`relative block h-5 w-9 rounded-full transition-colors ${on ? "bg-cyan" : "bg-[#28324D]"}`}>
        <span
          className={`absolute left-[3px] top-[3px] h-3.5 w-3.5 rounded-full bg-white shadow-sm transition-transform ${
            on ? "translate-x-4" : "translate-x-0"
          }`}
        />
      </span>
    </button>
  );
}

function ProfileItem({ label, value }) {
  return (
    <div className="grid grid-cols-[54px_1fr] items-center gap-1 py-1 text-[11px]">
      <span className="shrink-0 text-mut">{label}</span>
      <span className="min-w-0 truncate text-right font-medium text-ink" title={String(value)}>{value}</span>
    </div>
  );
}

// MBTI 16개 목록 대신 네 가지 축을 각각 이지선다로 선택한다.
const MBTI_AXES = [["E", "I"], ["N", "S"], ["T", "F"], ["J", "P"]];

function MbtiPicker({ value, onChange }) {
  const valid = /^[EI][NS][TF][JP]$/.test(value || "");
  const letters = valid ? value.split("") : [null, null, null, null];

  function pick(axisIndex, letter) {
    const next = valid ? value.split("") : ["I", "N", "T", "J"];
    next[axisIndex] = letter;
    onChange(next.join(""));
  }

  return (
    <div>
      <div className="grid grid-cols-4 gap-2">
        {MBTI_AXES.map((pair, axisIndex) => (
          <div key={pair.join("")} className="flex overflow-hidden rounded-xl border border-line">
            {pair.map((letter) => {
              const selected = letters[axisIndex] === letter;
              return (
                <button
                  key={letter}
                  type="button"
                  onClick={() => pick(axisIndex, letter)}
                  className={`tap flex-1 py-2.5 text-[14px] font-bold ${
                    selected ? "bg-cyan text-[#08131f]" : "bg-[#0E1424] text-sub"
                  }`}
                >
                  {letter}
                </button>
              );
            })}
          </div>
        ))}
      </div>
      <div className="mt-2 flex items-center justify-between">
        <span className="text-[13px] font-semibold text-ink">{valid ? value : "미설정"}</span>
        <button
          type="button"
          onClick={() => onChange("모름")}
          className={`tap rounded-full border px-3 py-1 text-[11px] ${
            valid ? "border-line text-mut" : "border-cyan text-cyan"
          }`}
        >
          모름
        </button>
      </div>
    </div>
  );
}

const NOTIF_LABELS = {
  checkin: "데일리 체크인 리마인더",
  actionBridge: "오늘의 할 일 (Action Bridge)",
  weekly: "주간 리포트",
};
const SETTINGS_META = {
  profile: ["프로필", "나를 표현하고 시뮬레이션 개인화에 사용할 정보를 관리합니다."],
  careerValues: ["직업 가치관", "간단한 질문으로 나에게 중요한 직업 가치를 알아보고 앞으로의 커리어 비교에 활용할 수 있어요."],
  security: ["개인정보 · 보안", "저장된 개인정보의 보호 상태를 확인합니다."],
  personalize: ["개인화", "우주와 가이드, 탐험 경험을 내 취향에 맞게 설정합니다."],
  notifications: ["알림 · 가이드", "필요한 알림과 함께할 가이드 캐릭터를 설정합니다."],
};

const CAREER_VALUE_PREVIEW = [
  { label: "성장", desc: "배우고 발전할 기회", icon: Sprout, color: "#65D5B2" },
  { label: "안정", desc: "예측 가능한 일과 미래", icon: ShieldCheck, color: "#6CB7FF" },
  { label: "보상", desc: "연봉과 경제적 보상", icon: Coins, color: "#B58CFF" },
  { label: "균형", desc: "일과 개인 생활의 조화", icon: Scale, color: "#F08CB7" },
  { label: "자율성", desc: "내 방식으로 일할 자유", icon: Compass, color: "#E7BE68" },
];

function LevelRule({ label, xp }) {
  return (
    <div className="flex items-center justify-between rounded-xl border border-line bg-[#0B1423] px-3 py-2">
      <span>{label}</span>
      <span className="font-semibold text-cyan">+{xp} XP</span>
    </div>
  );
}

export default function Settings() {
  const navigate = useNavigate();
  const location = useLocation();
  const { profile, setProfile, setOnboarded, setChoices, setScenarioTexts, setScenarioDomains, resetSession } = useResult();
  const [prefs, setPrefs] = useState(loadPrefs);
  const [adviceUp, setAdviceUp] = useState(adviceOn);
  const [editingAvatar, setEditingAvatar] = useState(false);
  const [editingProfile, setEditingProfile] = useState(false);
  const [shopOpen, setShopOpen] = useState(false);
  const [profileDraft, setProfileDraft] = useState(null);
  // ?section=personalize 처럼 어느 칸을 열지 링크로 지정할 수 있다.
  // 일기 화면의 돌보미 미리보기가 이 링크로 '생활 관리 친구' 칸을 바로 연다.
  const SECTIONS = ["profile", "careerValues", "security", "personalize", "notifications"];
  const [activeSection, setActiveSection] = useState(() => {
    const s = new URLSearchParams(location.search).get("section");
    return SECTIONS.includes(s) ? s : "profile";
  });
  const [careerTestOpen, setCareerTestOpen] = useState(() => new URLSearchParams(location.search).get("careerValues") === "1");
  const universe = universeSummary();
  useEffect(() => {
    const q = new URLSearchParams(location.search);
    if (q.get("careerValues") === "1") {
      setActiveSection("careerValues");
      setCareerTestOpen(true);
      return;
    }
    const s = q.get("section");
    if (SECTIONS.includes(s)) setActiveSection(s);
  }, [location.search]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!editingAvatar) return undefined;
    const previousOverflow = document.body.style.overflow;
    const closeOnEscape = (event) => {
      if (event.key === "Escape") setEditingAvatar(false);
    };
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [editingAvatar]);
  // 돌보미가 제안한 갈림길로 시뮬레이션을 연다 — 영역마다 다른 두 선택지가 온다.
  // (전에는 어느 돌보미든 "이직 vs 유지"로 고정이었다.)
  function startCompare(nudge) {
    const a = nudge?.choiceA || "이직";
    const b = nudge?.choiceB || "현상 유지";
    setChoices({ a, b });
    setScenarioTexts({ a, b });
    if (nudge?.domain) { const ds = toChoiceDomains(nudge.domain); setScenarioDomains({ a: ds, b: ds }); }
    navigate("/input");
  }

  function startProfileEdit() {
    setProfileDraft({
      name: profile.name || "",
      age: profile.age ?? 29,
      sex: profile.sex || "",
      occupation: profile.occupation || "",
      income: Number(profile.income) > 0 ? String(profile.income) : "",
    });
    setEditingProfile(true);
  }

  function saveProfileEdit() {
    if (!profileDraft) return;
    setProfile((current) => ({
      ...current,
      name: profileDraft.name.trim(),
      age: Number(profileDraft.age),
      sex: profileDraft.sex,
      sexConfirmed: Boolean(profileDraft.sex),
      occupation: profileDraft.occupation,
      income: profileDraft.income === "" ? 0 : Number(profileDraft.income),
    }));
    setEditingProfile(false);
    setProfileDraft(null);
  }

  function update(patch) {
    setPrefs((p) => {
      const next = { ...p, ...patch };
      savePrefs(next);
      return next;
    });
  }
  function toggleNotif(key) {
    update({ notifications: { ...prefs.notifications, [key]: !prefs.notifications[key] } });
  }
  function setAnswer(qid, v) {
    setProfile((p) => ({ ...p, psych_answers: { ...(p.psych_answers || {}), [qid]: v } }));
  }
  function resetToStart() {
    resetSession();       // 화면에 떠 있는 결과·선택지·담아둔 자료
    logoutAccount();      // 저장된 기록까지 — 안 지우면 새 계정에 앞사람 1년치가 남는다
    setOnboarded(false);  // 랜딩으로 되돌림
    navigate("/");
  }

  // 설정은 읽는 화면이라 본문을 넓게 펴면 눈이 좌우로 흔들린다.
  // Layout 의 `[&>*]:max-w-*` 가 특이도로 이기므로 여기서 ! 로 되돌려 좁힌다.
  return (
    <div className="mx-auto w-full pb-4 lg:!max-w-[920px] lg:pb-12">
      <div className="flex items-center justify-between lg:items-end">
        <Eyebrow>SETTINGS · 설정</Eyebrow>
        <button onClick={() => navigate(-1)} className="tap text-[13px] text-sub">
          닫기
        </button>
      </div>
      <div>
        <h1 className="mb-1 text-[22px] font-bold tracking-[-.025em] lg:text-[34px]">{SETTINGS_META[activeSection][0]}</h1>
        <p className="mb-4 text-[11px] text-mut lg:mb-6 lg:text-[13px]">{SETTINGS_META[activeSection][1]}</p>
      </div>

      <div className="no-scrollbar -mx-1 mb-4 flex gap-2 overflow-x-auto px-1 lg:hidden">
        <SettingsNav active={activeSection === "profile"} onClick={() => setActiveSection("profile")} icon={UserRound}>프로필</SettingsNav>
        <SettingsNav active={activeSection === "careerValues"} onClick={() => setActiveSection("careerValues")} icon={ClipboardCheck}>직업 가치관</SettingsNav>
        <SettingsNav active={activeSection === "security"} onClick={() => setActiveSection("security")} icon={LockKeyhole}>보안</SettingsNav>
        <SettingsNav active={activeSection === "personalize"} onClick={() => setActiveSection("personalize")} icon={Palette}>개인화</SettingsNav>
        <SettingsNav active={activeSection === "notifications"} onClick={() => setActiveSection("notifications")} icon={Bell}>알림</SettingsNav>
        <button type="button" onClick={resetToStart} aria-label="로그아웃" title="로그아웃" className="tap flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border border-white/[.07] text-mut hover:border-danger/40 hover:bg-danger/10 hover:text-danger"><LogOut size={17}/></button>
      </div>

      <div className="lg:grid lg:grid-cols-[220px_minmax(0,1fr)] lg:items-start lg:gap-8 xl:grid-cols-[240px_minmax(0,1fr)] xl:gap-10">
        <aside className="hidden lg:sticky lg:top-[108px] lg:block">
          <nav className="rounded-[20px] border border-white/[.07] bg-[#0D1828]/75 p-2 shadow-[0_18px_45px_rgba(0,0,0,.18)] backdrop-blur-xl">
            <SettingsNav active={activeSection === "profile"} onClick={() => setActiveSection("profile")} icon={UserRound}>프로필</SettingsNav>
            <SettingsNav active={activeSection === "careerValues"} onClick={() => setActiveSection("careerValues")} icon={ClipboardCheck}>직업 가치관</SettingsNav>
            <SettingsNav active={activeSection === "security"} onClick={() => setActiveSection("security")} icon={LockKeyhole}>개인정보 · 보안</SettingsNav>
            <SettingsNav active={activeSection === "personalize"} onClick={() => setActiveSection("personalize")} icon={Palette}>개인화</SettingsNav>
            <SettingsNav active={activeSection === "notifications"} onClick={() => setActiveSection("notifications")} icon={Bell}>알림 · 가이드</SettingsNav>
          </nav>
          <button type="button" onClick={resetToStart} className="tap mt-3 flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-[12px] font-semibold text-mut transition-colors hover:bg-danger/10 hover:text-danger"><span className="flex h-8 w-8 items-center justify-center rounded-lg bg-white/[.04]"><LogOut size={15}/></span>로그아웃</button>
        </aside>

        <div className="min-w-0 lg:[&_.bg-card]:rounded-[22px] lg:[&_.bg-card]:border lg:[&_.bg-card]:border-white/[.06] lg:[&_.bg-card]:bg-[#0D1828]/80 lg:[&_.bg-card]:p-5 lg:[&_.bg-card]:shadow-[0_18px_45px_rgba(0,0,0,.18)]">

      {/* 생활 관리 친구 — 홈을 방해하지 않도록 설정에서 관리한다. */}
      {activeSection === "personalize" && <section className="animate-fade">
      <PetMascot onCompare={startCompare} />

      <Card>
        <div className="flex items-center justify-between gap-4"><div><div className="text-xs font-semibold text-mut">꾸미기 상점</div><p className="mt-1 text-[10px] leading-relaxed text-sub">배경·소품·간식·행성 스킨을 코인으로 사서 꾸며요.</p></div><button type="button" onClick={()=>setShopOpen(true)} className="tap shrink-0 rounded-xl bg-[#8B6CCF] px-4 text-[11px] font-bold">상점 열기</button></div>
      </Card>
      </section>}

      {/* 개인정보 암호화 */}
      {activeSection === "security" && <section className="animate-fade">
      <PrivacyVault />
      </section>}

      {/* 프로필 */}
      {activeSection === "profile" && <section className="animate-fade">
      <Card>
        <div className="grid gap-5 md:grid-cols-[minmax(180px,30%)_minmax(0,70%)] md:gap-0">
          <div className="relative flex min-w-0 flex-col items-center border-b border-white/[.07] pb-5 text-center md:border-b-0 md:border-r md:pb-0 md:pr-5">
            <button type="button" onClick={() => setEditingAvatar(true)} className="tap absolute right-0 top-0 rounded-lg px-2 py-1 text-[9px] font-semibold text-mut hover:bg-white/[.05] hover:text-cyan">수정</button>
            <Avatar config={profile.avatarConfig} size={104} />
            <h2 className="mt-3 max-w-full truncate text-[18px] font-bold text-ink">{profile.name?.trim() || "닉네임 미설정"}</h2>
            <p className="mt-1 text-[11px] text-sub">{profile.age}세 · {profile.occupation || "직종 미설정"}</p>
            <span className="mt-2 rounded-full border border-violet-400/25 bg-violet-500/10 px-3 py-1 text-[10px] font-bold text-violet-200">
              {profile.mbti && profile.mbti !== "모름" ? profile.mbti : "MBTI 미설정"}
            </span>
          </div>

          <div className="min-w-0 md:pl-6">
            <div className="mb-2 flex items-center justify-between">
              <h3 className="text-[13px] font-bold text-ink">기본 정보</h3>
              <button type="button" onClick={startProfileEdit} className="tap rounded-lg px-2 py-1 text-[9px] font-semibold text-mut hover:bg-white/[.05] hover:text-cyan">수정</button>
            </div>
            <div className="divide-y divide-line/70">
            <ProfileItem label="나이" value={`${profile.age}세`} />
            <ProfileItem label="성별" value={profile.sex === "1" ? "남성" : profile.sex === "2" ? "여성" : "—"} />
            <ProfileItem label="월소득" value={`${profile.income}만원`} />
            <ProfileItem label="중요 가치" value={topAxes(profile.value_ranking, 2).join(" · ") || "—"} />
            </div>
          </div>
        </div>
      </Card>

      {/* 레벨의 의미와 적립 규칙은 설정에서 확인한다. 나의 우주에는 현재 진행률만 표시. */}
      <Card>
        <details className="group">
          <summary className="tap flex cursor-pointer list-none items-center justify-between">
            <div>
              <div className="text-xs font-semibold text-mut">레벨 · 탐험 보상 안내</div>
              <div className="mt-1 text-[13px] font-bold text-ink">
                {universe.title} · Lv. {universe.level}
              </div>
            </div>
            <span className="text-[11px] text-cyan group-open:rotate-180">⌄</span>
          </summary>

          <div className="mt-4 border-t border-line pt-4">
            <div className="text-[11px] font-semibold text-sub">XP 적립 기준</div>
            <div className="mt-2 grid grid-cols-2 gap-2 text-[10px] text-mut">
              <LevelRule label="30초 체크인" xp={XP_RULES.checkin} />
              <LevelRule label="한 줄 기록" xp={XP_RULES.diary} />
              <LevelRule label="시뮬레이션" xp={XP_RULES.simulation} />
              <LevelRule label="평행우주 저장" xp={XP_RULES.universeSaved} />
              <LevelRule label="회고 작성" xp={XP_RULES.reflection} />
            </div>

            <div className="mt-4 text-[11px] font-semibold text-sub">레벨별 칭호</div>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {LEVEL_TITLES.map(([level, title]) => (
                <span key={level} className={`rounded-full border px-2.5 py-1 text-[10px] ${universe.level >= level ? "border-cyan/30 bg-cyan/10 text-cyan" : "border-line text-mut"}`}>
                  Lv.{level} {title}
                </span>
              ))}
            </div>

            <div className="mt-4 text-[11px] font-semibold text-sub">탐험 보상</div>
            <div className="mt-2 space-y-2">
              {LEVEL_REWARDS.map((reward) => (
                <div key={reward.id} className="flex items-center justify-between rounded-xl bg-[#0B1423] px-3 py-2.5">
                  <span className={universe.highestLevel >= reward.level ? "text-[11px] text-ink" : "text-[11px] text-mut"}>{reward.name}</span>
                  <span className="text-[10px] text-mut">Lv.{reward.level}</span>
                </div>
              ))}
            </div>
            <p className="mt-3 text-[10px] leading-relaxed text-mut">레벨과 XP는 앱 활동 지표이며 예측 결과나 정확도에는 영향을 주지 않아요.</p>
          </div>
        </details>
      </Card>

      {editingProfile && profileDraft && (
        <Card className="animate-fade">
          <div className="mb-3 flex items-center justify-between">
            <div>
              <div className="text-[13px] font-semibold text-ink">기본 정보 수정</div>
            </div>
            <button
              type="button"
              onClick={() => { setEditingProfile(false); setProfileDraft(null); }}
              className="tap text-[11px] text-sub"
            >
              취소
            </button>
          </div>

          <div className="space-y-3">
            <label className="block text-[11px] text-sub">
              이름 또는 닉네임
              <input
                type="text"
                maxLength={20}
                value={profileDraft.name}
                onChange={(e) => setProfileDraft((p) => ({ ...p, name: e.target.value }))}
                className="mt-1 w-full rounded-xl border border-line bg-[#0E1424] px-3.5 py-3 text-sm text-ink outline-none focus:border-cyan"
              />
            </label>

            <label className="block text-[11px] text-sub">
              나이 <span className="float-right font-semibold text-cyan">{profileDraft.age}세</span>
              <input
                type="range"
                min="18"
                max="70"
                value={profileDraft.age}
                onChange={(e) => setProfileDraft((p) => ({ ...p, age: Number(e.target.value) }))}
                className="mt-3 h-1 w-full cursor-pointer accent-cyan"
              />
            </label>

            <label className="block text-[11px] text-sub">
              성별
              <div className="mt-1 grid grid-cols-2 gap-2">
                {[["1", "남성"], ["2", "여성"]].map(([value, label]) => <button key={value} type="button" onClick={() => setProfileDraft((p) => ({ ...p, sex: value }))} className={`tap rounded-xl border py-2.5 text-[12px] ${profileDraft.sex === value ? "border-violet-400 bg-violet-500/15 text-violet-200" : "border-line bg-[#0E1424] text-sub"}`}>{label}</button>)}
              </div>
            </label>

            <label className="block text-[11px] text-sub">
              직종
              <select
                value={profileDraft.occupation}
                onChange={(e) => setProfileDraft((p) => ({ ...p, occupation: e.target.value }))}
                className="mt-1 w-full rounded-xl border border-line bg-[#0E1424] px-3.5 py-3 text-sm text-ink outline-none focus:border-cyan"
              >
                <option value="">직종을 골라주세요</option>
                {OCCUPATIONS.map((occupation) => <option key={occupation}>{occupation}</option>)}
              </select>
            </label>

            <label className="block text-[11px] text-sub">
              월소득
              <div className="mt-1 flex items-center gap-2">
                <input
                  type="number"
                  min="0"
                  step="1"
                  placeholder="예: 300"
                  value={profileDraft.income}
                  onChange={(e) => {
                    const income = e.target.value.replace(/^0+(?=\d)/, "");
                    setProfileDraft((p) => ({ ...p, income }));
                  }}
                  className="w-full rounded-xl border border-line bg-[#0E1424] px-3.5 py-3 text-sm text-ink outline-none focus:border-cyan"
                />
                <span className="whitespace-nowrap text-[11px] text-mut">만원 / 월</span>
              </div>
            </label>
          </div>

          <button
            type="button"
            onClick={saveProfileEdit}
            className="tap mt-4 w-full rounded-2xl bg-cyan py-3 text-sm font-bold text-[#08111f]"
          >
            변경사항 저장
          </button>
        </Card>
      )}

      </section>}

      {activeSection === "careerValues" && <section className="animate-fade">
        <section className="relative overflow-hidden rounded-[28px] border border-violet-400/30 bg-[linear-gradient(120deg,#182955_0%,#141C42_52%,#11162F_100%)] p-5 shadow-[0_24px_70px_rgba(20,31,78,.34)] sm:p-7 lg:p-9">
          <div className="pointer-events-none absolute -right-16 -top-24 h-64 w-64 rounded-full border-[42px] border-violet-400/[.08]" />
          <div className="pointer-events-none absolute -bottom-28 right-[20%] h-52 w-52 rounded-full bg-violet-500/15" />
          <div className="relative grid items-center gap-7 lg:grid-cols-[1fr_auto]">
            <div className="max-w-[590px]">
              <span className="inline-flex items-center gap-1.5 rounded-full border border-violet-300/20 bg-violet-400/20 px-3 py-1.5 text-[10px] font-bold text-violet-100"><ClipboardCheck size={13}/> 직업 가치관 검사</span>
              <h2 className="mt-4 text-[26px] font-bold tracking-[-.04em] text-white sm:text-[32px]">직업 가치관 알아보기</h2>
              <p className="mt-3 text-[12px] leading-6 text-white/75 sm:text-[13px]">내가 일에서 중요하게 생각하는 기준을 알아보세요.<br className="hidden sm:block"/> 검사 결과는 이후 모든 커리어 비교의 설명에 활용됩니다.</p>
              {(profile.career_values || []).length > 0 && (
                <div className="mt-4 rounded-xl border border-white/10 bg-black/15 px-3.5 py-2.5">
                  <p className="text-[9px] font-semibold text-violet-200">현재 나의 상위 가치</p>
                  <p className="mt-1 text-[12px] font-bold text-white">{profile.career_values.slice(0, 3).map((value) => value.name).join("  ·  ")}</p>
                </div>
              )}
              <div className="mt-5 flex flex-wrap items-center gap-4 text-[11px] text-white/70">
                <span className="flex items-center gap-1.5"><Clock3 size={15} className="text-violet-200"/> 약 3분</span><span className="h-4 w-px bg-white/15"/><span className="flex items-center gap-1.5"><ListChecks size={15} className="text-violet-200"/> 총 28문항</span>
              </div>
            </div>
            <button type="button" onClick={() => setCareerTestOpen(true)} className="tap flex w-full items-center justify-center gap-2 rounded-full bg-gradient-to-r from-[#7557E8] to-[#A273F4] px-7 py-4 text-[13px] font-bold text-white shadow-[0_14px_34px_rgba(117,87,232,.35)] lg:w-auto">
              {(profile.career_values || []).length > 0 ? "결과 보기·재검사" : "검사 시작하기"} <ChevronRight size={16}/>
            </button>
          </div>
        </section>

        <section className="mt-4 rounded-[26px] border border-white/[.09] bg-[#0B1628]/88 p-5 sm:p-6">
          <h2 className="text-[16px] font-bold text-ink">이런 직업 가치를 알아봐요</h2>
          <p className="mt-1 text-[10px] text-mut">두 가치 중 더 중요한 쪽을 고르며 나만의 우선순위를 찾습니다.</p>
          <div className="mt-4 grid gap-2.5 sm:grid-cols-2 lg:grid-cols-5">
            {CAREER_VALUE_PREVIEW.map(({ label, desc, icon: Icon, color }) => (
              <article key={label} className="rounded-2xl border border-white/[.09] bg-[#0E1A30] p-3.5">
                <span className="flex h-9 w-9 items-center justify-center rounded-full" style={{ color, backgroundColor: `${color}20` }}><Icon size={17}/></span>
                <h3 className="mt-3 text-[12px] font-bold text-ink">{label}</h3><p className="mt-1 text-[9.5px] leading-4 text-mut">{desc}</p>
              </article>
            ))}
          </div>
          <div className="mt-5 overflow-hidden rounded-2xl border border-violet-400/15 bg-[linear-gradient(100deg,rgba(54,76,151,.24),rgba(58,39,112,.2))] p-4 sm:flex sm:items-center sm:gap-5 sm:p-5">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-violet-500/20 text-violet-200"><Info size={18}/></span>
            <div className="mt-3 min-w-0 flex-1 sm:mt-0"><h3 className="text-[13px] font-bold text-ink">검사 결과는 이렇게 활용돼요</h3><p className="mt-1 text-[10px] leading-5 text-sub">커리어 A/B 비교에서는 내가 중요하게 보는 기준부터 설명하고, 채용 공고에서는 내 가치와 맞는 지점과 부딪힐 지점을 찾아줍니다.</p><p className="mt-1 text-[9px] leading-4 text-mut">예측 소득·인과효과·재직기간 같은 숫자를 바꾸지는 않습니다.</p></div>
            <div className="mt-4 flex shrink-0 items-center justify-center gap-2 sm:mt-0"><span className="rounded-xl border border-violet-300/20 bg-violet-500/15 px-3 py-2 text-[10px] font-bold text-violet-200">A 선택</span><span className="text-violet-300">↔</span><span className="rounded-xl border border-orange-300/20 bg-orange-400/10 px-3 py-2 text-[10px] font-bold text-orange-200">B 선택</span></div>
          </div>
          <p className="mt-4 flex items-start gap-2 rounded-xl border border-violet-400/20 bg-violet-500/[.07] px-3.5 py-3 text-[10px] leading-4 text-violet-200"><Info size={14} className="mt-px shrink-0"/> 검사는 선택 사항이에요. 검사하지 않아도 기본 조건으로 미래를 비교할 수 있습니다.</p>
          <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-[9px] text-mut">{profile.career_values_updated_at && <span>마지막 검사: {new Date(profile.career_values_updated_at).toLocaleDateString("ko-KR")}</span>}{profile.career_values_report && <a href={profile.career_values_report} target="_blank" rel="noreferrer" className="text-violet-300 hover:text-violet-200">커리어넷 공식 결과지 ↗</a>}</div>
        </section>
      </section>}

      {/* 가치 우선순위 — 성향 개인화 입력 (백엔드 personalize 로 전달) */}
      {activeSection === "profile" && <section className="animate-fade">

      <Card>
        <div className="mb-2 text-xs font-semibold text-mut">가치 우선순위</div>
        <ValueRankingInput
          value={profile.value_ranking}
          onChange={(v) => setProfile((p) => ({ ...p, value_ranking: v }))}
        />
      </Card>

      {/* 심리 성향 — MBTI + 서술형 질문 (→ disposition_block 으로 서사 개인화) */}
      <Card>
        <div className="mb-2 text-xs font-semibold text-mut">심리 성향</div>

        <label className="mb-1.5 block text-[11px] text-sub">MBTI</label>
        <MbtiPicker
          value={profile.mbti}
          onChange={(value) => setProfile((p) => ({ ...p, mbti: value }))}
        />
      </Card>

      {/* 기기 옮기기는 프로필 설정을 모두 확인한 뒤 만나는 마지막 항목이다. */}
      <Card>
        <div className="flex items-center justify-between gap-4">
          <div className="min-w-0">
            <div className="text-xs font-semibold text-mut">다른 기기에서 이어서 하기</div>
            <p className="mt-1 text-[10px] leading-relaxed text-sub">지금 기록을 링크·QR로 옮겨서 폰과 노트북을 오갈 수 있어요.</p>
          </div>
          <button type="button" onClick={() => navigate("/handoff")} className="tap flex shrink-0 items-center gap-1.5 rounded-xl bg-[#8B6CCF] px-4 py-2.5 text-[11px] font-bold text-white">
            <Smartphone size={13} /> 옮기기
          </button>
        </div>
      </Card>
      </section>}

      {/* 알림 설정 */}
      {activeSection === "notifications" && <section className="animate-fade">
      <Card>
        <div className="mb-1 text-xs font-semibold text-mut">알림</div>
        {Object.keys(NOTIF_LABELS).map((key) => (
          <div key={key} className="mt-2.5 flex items-center justify-between">
            <span className="text-[13px] text-sub">{NOTIF_LABELS[key]}</span>
            <Toggle on={!!prefs.notifications[key]} onClick={() => toggleNotif(key)} />
          </div>
        ))}
      </Card>

      {/* 사용 안내 — 안내를 다시 볼 수 있는 유일한 자리다(헤더에는 두지 않는다).
          첫 화면(소개)부터 열어 주고, 거기서 화면을 짚어줄지 다시 고를 수 있다. */}
      <div data-tour="guide-card">
      <Card>
        <div className="mb-1 text-xs font-semibold text-mut">사용 안내</div>
        <p className="text-[10px] leading-relaxed text-sub">
          서비스 소개부터 다시 열어요. 이어서 화면을 하나씩 짚어주는 안내도 받을 수 있어요.
        </p>
        <button
          type="button"
          onClick={openGuide}
          className="tap mt-3 flex w-full items-center justify-center gap-2 rounded-xl border border-[#9B82E8]/45 bg-[#8B6CCF]/15 py-2.5 text-[12px] font-semibold text-[#B8A4F2] transition-colors hover:bg-[#8B6CCF]/25"
        >
          <Compass size={14} /> 안내 받기
        </button>
        {/* 조언은 여기서 바로 껐다 켤 수 있다 — 모달을 거치지 않아도 되게. */}
        <div className="mt-3 flex items-center justify-between border-t border-white/[.07] pt-3">
          <div className="min-w-0 pr-3">
            <div className="text-[12px] text-sub">가이드 확인하기</div>
            <p className="mt-0.5 text-[10px] leading-relaxed text-mut">
              화면마다 무엇을 하는 곳인지 옆에서 알려드려요.
            </p>
          </div>
          <Toggle on={adviceUp} onClick={() => { setAdvice(!adviceUp); setAdviceUp(!adviceUp); }} />
        </div>
      </Card>
      </div>

      {/* 가이드 마스코트 */}
      <Card>
        <div className="mb-3 text-xs font-semibold text-mut">가이드 마스코트</div>
        <div className="space-y-3">
          {Object.values(MASCOTS).map((m) => (
            <div key={m.key} className="flex items-center gap-3">
              <Mascot which={m.key} size={48} />
              <div className="min-w-0">
                <div className="text-[11px] font-bold" style={{ color: m.color }}>{m.name} <span className="text-[9px] text-mut">· {m.tag}</span></div>
                <p className="mt-0.5 text-[10px] leading-relaxed text-sub">{m.desc}</p>
                <div className="mt-1 flex gap-1">{m.traits.map((t) => <span key={t} className="rounded-full border border-line px-1.5 py-0.5 text-[8px] text-mut">{t}</span>)}</div>
              </div>
            </div>
          ))}
        </div>
      </Card>
      </section>}

      <p className="mt-8 text-center text-[9px] leading-relaxed text-mut/70">
        아바타 디자인: {" "}
        <a href={TOONHEAD_CREDIT.creatorUrl} target="_blank" rel="noreferrer" className="underline">
          {TOONHEAD_CREDIT.title} by {TOONHEAD_CREDIT.creator}
        </a>
        {" · "}
        <a href={TOONHEAD_CREDIT.licenseUrl} target="_blank" rel="noreferrer" className="underline">
          {TOONHEAD_CREDIT.license}
        </a>
        {" · 일부 파츠 수정·추가"}
      </p>

      </div>
      </div>
      {editingAvatar && (
        <div
          className="fixed inset-0 z-[120] flex animate-backdrop-in items-end justify-center bg-[#02050C]/75 backdrop-blur-[5px] sm:items-center sm:p-6"
          role="dialog"
          aria-modal="true"
          aria-labelledby="avatar-editor-title"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) setEditingAvatar(false);
          }}
        >
          <div className="flex max-h-[92dvh] w-full max-w-[640px] animate-sheet-up flex-col rounded-t-[28px] border border-white/10 bg-[#0D1727] shadow-[0_-22px_70px_rgba(0,0,0,.55)] sm:animate-fade sm:max-h-[88vh] sm:rounded-[28px]">
            <div className="flex shrink-0 items-start justify-between gap-4 border-b border-white/[.07] px-5 py-4 sm:px-6">
              <div>
                <h2 id="avatar-editor-title" className="text-[17px] font-bold text-ink">아바타 수정</h2>
                <p className="mt-1 text-[10px] text-mut">화살표로 원하는 모습을 선택하세요. 변경 내용은 바로 저장돼요.</p>
              </div>
              <button
                type="button"
                onClick={() => setEditingAvatar(false)}
                className="tap flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-white/[.05] text-[20px] text-sub"
                aria-label="아바타 수정 닫기"
              >
                ×
              </button>
            </div>
            <div className="min-h-0 overflow-y-auto px-5 pb-6 sm:px-6">
              <AvatarBuilder
                config={profile.avatarConfig}
                // avatarChosen — 사람이 직접 고른 얼굴이라는 표시. 이게 있으면 체험하기로
                // 다시 들어와도 페르소나 얼굴이 덮어쓰지 않는다(personaSession 참고).
                onChange={(cfg) => setProfile((p) => ({ ...p, avatarConfig: cfg, avatarChosen: true }))}
              />
            </div>
            <div className="shrink-0 border-t border-white/[.07] bg-[#0D1727] px-5 py-3 sm:px-6">
              <button
                type="button"
                onClick={() => setEditingAvatar(false)}
                className="tap w-full rounded-xl bg-violet-500 py-3 text-[12px] font-bold text-white"
              >
                완료
              </button>
            </div>
          </div>
        </div>
      )}
      {careerTestOpen && (
        <div className="fixed inset-0 z-[120] flex animate-backdrop-in items-end justify-center bg-[#02050C]/75 backdrop-blur-[5px] sm:items-center sm:p-6" role="dialog" aria-modal="true" aria-label="직업 가치관검사">
          <div className="w-full max-w-[560px] animate-sheet-up rounded-t-[28px] border border-white/10 bg-[#0D1727] p-5 shadow-[0_-22px_70px_rgba(0,0,0,.55)] sm:animate-fade sm:rounded-[28px] sm:p-6">
            <div className="mb-4 flex items-start justify-between gap-4">
              <div>
                <h2 className="text-[17px] font-bold text-ink">직업 가치관검사</h2>
                <p className="mt-1 text-[10px] leading-4 text-mut">커리어넷 대학·일반용 28문항 · 결과는 프로필에 저장돼요.</p>
              </div>
              <button type="button" onClick={() => { setCareerTestOpen(false); navigate("/settings", { replace: true }); }} className="tap shrink-0 rounded-full px-3 text-[18px] text-mut" aria-label="검사 닫기">×</button>
            </div>
            <ValueDeepTest
              onDone={(data) => {
                setProfile((current) => ({
                  ...current,
                  career_values: data.ranking,
                  career_values_report: data.report_url,
                  career_values_updated_at: new Date().toISOString(),
                }));
                setCareerTestOpen(false);
                navigate("/settings", { replace: true });
              }}
              onClose={() => { setCareerTestOpen(false); navigate("/settings", { replace: true }); }}
            />
          </div>
        </div>
      )}
      {shopOpen&&<PetShop onClose={()=>setShopOpen(false)}/>} 
    </div>
  );
}

function SettingsNav({ active, onClick, icon: Icon, children }) {
  return <button type="button" onClick={onClick} className={`tap group flex shrink-0 items-center gap-2 rounded-xl px-3 py-2.5 text-[12px] font-semibold transition-colors lg:w-full lg:gap-3 ${active ? "bg-violet-500/20 text-violet-200" : "text-sub hover:bg-violet-500/10 hover:text-violet-200"}`}><span className={`flex h-8 w-8 items-center justify-center rounded-lg ${active ? "bg-violet-500/20" : "bg-white/[.04] group-hover:bg-violet-500/15"}`}><Icon size={15}/></span><span className="flex-1 whitespace-nowrap text-left">{children}</span><ChevronRight size={14} className={`hidden lg:block ${active ? "opacity-80" : "opacity-30"}`} /></button>;
}
