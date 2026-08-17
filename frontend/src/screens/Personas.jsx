// ─────────────────────────────────────────────────────────────
// 체험하기 — 일곱 개의 '평행한 1년' 중 하나를 고르는 화면.
//
// 여기는 로그인 대신 쓰는 프로필 선택 자리다. 고르는 것 말고 다른 조작을 두지 않는다
//   (검색·정렬·북마크·비교를 얹어 봤으나 7명뿐이라 도구가 목록보다 커졌고,
//    '추천순'·'나와 비슷한 사람' 은 아직 그렇게 부를 근거가 없는 값이었다).
//   남긴 건 선택 유형 알약 하나뿐 — 이건 카드에 실제로 붙어 있는 축이다.
//
// 카드에 필요한 값은 personaCards() 가 준다(1년치 기록은 안 읽는다).
// 고른 순간에만 enterPersona() 가 동적 import 로 기록을 가져와 슬롯에 심는다.
//
// 전환 뒤 새로고침을 하지 않는다: iframe·사파리에서는 저장소가 메모리라
//   (safeStorage.js) 새로고침하면 방금 심은 1년치가 날아간다. 대신 슬롯을 바꾸고
//   reloadProfile() 로 컨텍스트만 갈아끼운 뒤 navigate 로 이동한다.
//   기록은 restoreLive 가 쏘는 'pm:universe' 이벤트로 각 화면이 다시 읽는다.
//
// 얼굴은 각 페르소나의 profile.avatarConfig 를 아바타 빌더와 같은 엔진으로 그린다
//   (lib/renderAvatar.js). 그림 파일이 아니라 SVG 를 즉석에서 만드는 것이라 새로 받을
//   에셋이 없고, 나중에 파츠를 고쳐도 카드가 같이 따라온다.
//   avatarConfig 가 없는 인물은 예전처럼 이름 첫 글자로 대신한다.
//
// 배치: 4장 + 3장. 개수가 알약 필터로 바뀌어도 마지막 줄이 가운데로 모이도록
//   grid 가 아니라 flex-wrap + justify-center 로 깐다(grid 는 왼쪽에 붙어 비어 보인다).
// ─────────────────────────────────────────────────────────────

import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, Lock, Sparkles, UserPlus } from "lucide-react";
import { personaCards, personaTags } from "../data/personas/index.js";
import { enterPersona } from "../data/personaSession.js";
import { startFreshMySlot } from "../data/personaSlots.js";
import { useResult } from "../data/ResultContext.jsx";
import { avatarDataUri } from "../lib/renderAvatar.js";
import { AVATAR_BG } from "../components/Avatar.jsx";
import Stars from "../components/Stars.jsx";

// 선택 유형별 색. core.py 의 KIND_TREATMENT 와 같은 축이다.
const KIND_TONE = {
  이직: "border-sky-400/25 bg-sky-500/[.12] text-sky-200",
  창업: "border-amber-400/25 bg-amber-500/[.12] text-amber-200",
  휴식: "border-emerald-400/25 bg-emerald-500/[.12] text-emerald-200",
  해외: "border-violet-400/25 bg-violet-500/[.12] text-violet-200",
};

// 카드 7장이 한 화면에 있고 아바타 한 장을 그릴 때마다 SVG 를 만들어 문자열로 손보므로
// (renderAvatar.js) 매 렌더마다 다시 그리면 낭비다. config 는 프로필 모듈의 고정 참조라
// useMemo 의 의존값으로 그대로 쓸 수 있다.
function Face({ name, avatar, ready, size = 60 }) {
  const src = useMemo(() => (avatar ? avatarDataUri(avatar, { size: 96 }) : null), [avatar]);
  const box = "shrink-0 overflow-hidden rounded-full border transition-colors";
  const dim = { height: size, width: size };

  if (!src) {
    return (
      <div
        className={`${box} flex items-center justify-center font-bold tracking-[-.03em] ${
          ready
            ? "border-violet-400/30 bg-[linear-gradient(155deg,rgba(139,108,207,.35),rgba(47,111,232,.18))] text-white"
            : "border-white/10 bg-white/[.04] text-mut"
        }`}
        style={{ ...dim, fontSize: Math.round(size * 0.4) }}
        aria-hidden="true"
      >
        {name.slice(0, 1)}
      </div>
    );
  }

  return (
    <div
      // 아바타 SVG 는 배경이 투명하다. 어두운 테마에서 머리카락·윤곽선이 묻히므로
      // Avatar.jsx 와 같은 밝은 바탕을 깔아 프로필 사진처럼 보이게 한다.
      className={`${box} ${ready ? "border-white/15" : "border-white/10 opacity-55 grayscale"}`}
      style={{ ...dim, background: AVATAR_BG }}
      aria-hidden="true"
    >
      <img src={src} alt="" width={96} height={96} className="block h-full w-full" />
    </div>
  );
}

function Chip({ tone, children }) {
  return <span className={`rounded-full border px-2.5 py-[3px] text-[10.5px] font-semibold ${tone}`}>{children}</span>;
}

function PersonaCard({ card, busy, onPick }) {
  const locked = !card.ready;
  const loading = busy === card.id;
  const label = `PARALLEL ${String(card.no + 1).padStart(2, "0")}`;

  return (
    <button
      type="button"
      disabled={locked || Boolean(busy)}
      onClick={() => onPick(card)}
      aria-label={locked ? `${card.name} 준비 중` : `${card.name}의 1년 체험 시작`}
      className={`tap group relative w-full overflow-hidden rounded-[20px] border p-5 text-left outline-none transition-all duration-200 focus-visible:ring-2 focus-visible:ring-violet-400/70 sm:w-[calc(50%-8px)] lg:w-[calc(25%-15px)] ${
        locked
          ? "cursor-default border-white/[.05] bg-white/[.012] opacity-55"
          : "border-white/[.09] bg-[#101A2B]/70 shadow-[0_18px_36px_-24px_rgba(0,0,0,.95)] backdrop-blur-sm hover:-translate-y-1 hover:border-violet-400/45 hover:bg-[#141F33]/80 hover:shadow-[0_26px_50px_-22px_rgba(0,0,0,.95),0_0_38px_-10px_rgba(139,108,207,.42)] active:scale-[.995]"
      } ${loading ? "border-violet-400/70 bg-violet-500/[.08]" : ""}`}
    >
      {/* 아바타 뒤에서 옅게 번지는 빛 — 평행우주로 난 구멍처럼 보이게 한다 */}
      <div
        className={`pointer-events-none absolute -left-8 -top-10 h-36 w-36 rounded-full blur-2xl transition-opacity duration-300 ${
          loading ? "opacity-90" : "opacity-0 group-hover:opacity-100"
        }`}
        style={{ background: "radial-gradient(circle, rgba(139,108,207,.42), rgba(47,111,232,.14) 55%, transparent 72%)" }}
        aria-hidden="true"
      />

      <div className="relative">
        <span className="text-[9.5px] font-bold uppercase tracking-[.18em] text-violet-300/70">{label}</span>

        <div className="mt-3.5 flex items-center gap-3.5">
          <Face name={card.name} avatar={card.avatar} ready={card.ready} size={60} />
          <div className="min-w-0 flex-1">
            <div className="text-[17px] font-bold leading-tight tracking-[-.02em] text-ink">{card.name}</div>
            <div className="mt-1 text-[11.5px] text-mut">
              {card.age} · {card.sex === "1" ? "남자" : "여자"}
            </div>
            <div className="mt-0.5 truncate text-[11.5px] text-sub/80">{card.job}</div>
          </div>
        </div>

        {/* 카드에서 가장 중요한 정보 — MBTI 가 아니라 '지금 무엇을 정해야 하는가' */}
        <p
          className={`mt-4 whitespace-pre-line border-t border-white/[.07] pt-4 text-[13px] font-semibold leading-[1.5] tracking-[-.01em] transition-colors ${
            locked ? "text-mut" : "text-ink/90 group-hover:text-white"
          }`}
        >
          {card.dilemma}
        </p>

        <div className="mt-4 flex items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-1.5">
            <Chip tone={KIND_TONE[card.kind] || "border-white/10 bg-white/5 text-sub"}>{card.kind}</Chip>
            <Chip tone="border-white/10 bg-white/[.04] text-mut">{card.mbti}</Chip>
          </div>

          {locked ? (
            <span className="flex shrink-0 items-center gap-1.5 text-[11px] font-semibold text-mut">
              <Lock size={12} /> 준비 중
            </span>
          ) : (
            <span className="flex shrink-0 items-center gap-1.5 text-[12px] font-semibold text-violet-300/80 transition-colors group-hover:text-violet-200">
              {loading ? "들어가는 중…" : "체험하기"}
              {!loading && <ArrowRight size={14} className="transition-transform duration-200 group-hover:translate-x-1" />}
            </span>
          )}
        </div>
      </div>
    </button>
  );
}

export default function Personas() {
  const navigate = useNavigate();
  const { reloadProfile, resetSession, setOnboarded } = useResult();

  // 카드 번호(PARALLEL 01…)는 등록 순서로 고정한다 — 알약으로 걸러도 같은 사람은 같은 번호.
  // personaCards() 는 매번 새 객체를 만드므로 한 번만 부른다(아바타 참조가 유지돼야 Face 의 메모가 산다).
  const cards = useMemo(() => personaCards().map((c, i) => ({ ...c, no: i })), []);
  const tags = useMemo(() => personaTags(), []);

  const [busy, setBusy] = useState(null);
  const [error, setError] = useState("");
  const [tag, setTag] = useState("전체");

  const list = tag === "전체" ? cards : cards.filter((c) => c.tags.includes(tag));

  async function pick(card) {
    if (!card.ready || busy) return;
    setBusy(card.id);
    setError("");
    const res = await enterPersona(card.id, { reload: false });
    if (!res.ok) {
      setBusy(null);
      setError("이 프로필은 아직 기록이 준비되지 않았어요.");
      return;
    }
    resetSession();      // 앞사람의 결과·선택지를 비운다 (로그아웃을 안 거치고 와도 섞이지 않게)
    reloadProfile();     // 슬롯이 넣어준 프로필을 컨텍스트에 반영
    setOnboarded(true);  // 이제 '/' 로 돌아가도 랜딩이 아니라 우주로 간다
    navigate("/my");
  }

  function makeMine() {
    // 랜딩의 '나만의 계정 만들기' 와 같은 뜻이어야 한다 — 빈 상태로 시작.
    //
    // 여기만 startMyAccount()(= activateSlot) 로 남아 있었다. 그건 **복구**라서
    // 체험하기 화면을 거쳐 계정을 만들면 보관해 둔 앞사람 기록이 그대로 따라왔다.
    // Landing 은 startFreshMySlot() 으로 고쳐졌는데 이 경로가 빠져 있었다.
    //
    // 슬롯을 먼저 비운 뒤 온보딩으로 — 순서가 바뀌면 방금 입력한 프로필이 지워진다.
    startFreshMySlot();
    resetSession();      // 체험하던 인물의 결과가 내 계정 화면에 남지 않게
    reloadProfile();     // 비워진 저장소를 읽어 기본 프로필로 되돌린다
    navigate("/onboarding");
  }

  return (
    <div className="relative pb-10 lg:pb-14">
      {/* 배경 — UI 뒤로 물러나 있어야 한다. 별·빛무리·궤도선만 아주 옅게. */}
      <div className="pointer-events-none absolute -left-[10vw] -right-[10vw] -top-16 bottom-0 -z-0 overflow-hidden" aria-hidden="true">
        <div
          className="absolute left-1/2 top-0 h-[520px] w-[820px] -translate-x-1/2 blur-3xl"
          style={{ background: "radial-gradient(ellipse at center, rgba(89,116,255,.16), rgba(139,108,207,.09) 45%, transparent 70%)" }}
        />
        <Stars count={22} twinkle />
        <svg className="absolute -bottom-24 right-[6%] h-[420px] w-[420px] opacity-[.16]" viewBox="0 0 400 400" fill="none">
          <ellipse cx="200" cy="200" rx="190" ry="72" stroke="rgba(160,180,255,.55)" strokeWidth="1" transform="rotate(-22 200 200)" />
          <ellipse cx="200" cy="200" rx="140" ry="52" stroke="rgba(160,180,255,.35)" strokeWidth="1" transform="rotate(-22 200 200)" />
          <path d="M40 300 A 190 190 0 0 1 360 300" stroke="rgba(139,108,207,.35)" strokeWidth="1" />
        </svg>
      </div>

      <div className="relative z-10">
        {/* 히어로 — 카드 7장이 한 화면에 남도록 짧게 */}
        <div className="pt-2 text-left lg:mx-auto lg:max-w-[720px] lg:pt-1 lg:text-center">
          <div className="inline-flex items-center gap-1.5 rounded-full border border-violet-400/20 bg-violet-500/[.08] px-2.5 py-1 text-[10.5px] font-bold uppercase tracking-[.16em] text-violet-200">
            <Sparkles size={11} /> 체험하기
          </div>
          <h1 className="mt-2.5 text-[23px] font-bold tracking-[-.04em] lg:text-[36px]">
            누구의{" "}
            <span className="bg-[linear-gradient(100deg,#8FA9FF,#B98CFF)] bg-clip-text text-transparent">1년</span>
            으로 들어가 볼까요?
          </h1>
          <p className="mt-2.5 text-[12px] leading-relaxed text-sub lg:text-[13.5px] lg:leading-6">
            7개의 다른 삶, 7개의 다른 선택.
            <span className="lg:block"> 나와 비슷한 고민을 가진 사람의 1년을 먼저 살아보세요.</span>
          </p>
          <p className="mt-1.5 text-[10px] leading-relaxed text-mut">
            모두 합성(가상) 인물이며 실제 사용자의 기록이 아닙니다.
          </p>
        </div>

        {/* 선택 유형 알약 — 카드에 실제로 붙어 있는 축만 나온다(personaTags) */}
        <div className="no-scrollbar -mx-5 mt-4 flex items-center gap-1.5 overflow-x-auto px-5 lg:mx-0 lg:mt-6 lg:justify-center lg:px-0">
          {["전체", ...tags].map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setTag(t)}
              aria-pressed={tag === t}
              className={`tap shrink-0 rounded-full border px-3.5 py-1.5 text-[11.5px] font-semibold transition-colors ${
                tag === t
                  ? "border-violet-400/50 bg-violet-500/[.16] text-violet-100"
                  : "border-white/[.09] bg-white/[.025] text-sub hover:border-white/20 hover:text-ink"
              }`}
            >
              {t}
            </button>
          ))}
        </div>

        {error && (
          <p className="mt-3.5 rounded-xl border border-amber-400/25 bg-amber-500/10 px-3.5 py-2.5 text-[11px] text-amber-200">
            {error}
          </p>
        )}

        {/* 4장 + 3장. flex-wrap 이라 마지막 줄이 가운데로 모인다. */}
        <div className="mt-4 flex flex-wrap justify-center gap-4 lg:mt-7 lg:gap-5">
          {list.map((card) => (
            <PersonaCard key={card.id} card={card} busy={busy} onPick={pick} />
          ))}
        </div>

        <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row lg:mt-10">
          <button type="button" onClick={makeMine} disabled={Boolean(busy)} className="tap flex items-center gap-2 rounded-full border border-violet-400/25 bg-violet-500/[.07] px-4 py-2.5 text-[11px] font-semibold text-violet-200 hover:bg-violet-500/[.12]">
            <UserPlus size={14} /> 내 프로필로 시작하기
          </button>
          <button type="button" onClick={() => navigate("/")} className="tap px-3 py-2 text-[11px] font-semibold text-mut hover:text-sub">
            처음 화면으로
          </button>
        </div>
      </div>
    </div>
  );
}
