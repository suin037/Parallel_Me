// ─────────────────────────────────────────────────────────────
// 체험하기 — 넷플릭스식 프로필 선택.
//
// 카드에 필요한 값은 personaCards() 가 준다(1년치 기록은 안 읽는다).
// 고른 순간에만 enterPersona() 가 동적 import 로 기록을 가져와 슬롯에 심는다.
//
// 전환 뒤 새로고침을 하지 않는다: iframe·사파리에서는 저장소가 메모리라
//   (safeStorage.js) 새로고침하면 방금 심은 1년치가 날아간다. 대신 슬롯을 바꾸고
//   reloadProfile() 로 컨텍스트만 갈아끼운 뒤 navigate 로 이동한다.
//   기록은 restoreLive 가 쏘는 'pm:universe' 이벤트로 각 화면이 다시 읽는다.
//
// 아바타는 아직 비워둔다 — 아바타 빌더 개편이 끝나면 profile.avatarConfig 를 채워
//   이 자리에 얼굴이 들어간다. 그때까지는 이름 첫 글자로 대신한다.
// ─────────────────────────────────────────────────────────────

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Check, Lock, UserPlus } from "lucide-react";
import { personaCards } from "../data/personas/index.js";
import { enterPersona, startMyAccount } from "../data/personaSession.js";
import { useResult } from "../data/ResultContext.jsx";

// 선택 유형별 색. core.py 의 KIND_TREATMENT 와 같은 축이다.
const KIND_TONE = {
  이직: "border-sky-400/30 bg-sky-500/10 text-sky-200",
  창업: "border-amber-400/30 bg-amber-500/10 text-amber-200",
  휴식: "border-emerald-400/30 bg-emerald-500/10 text-emerald-200",
};

function Face({ name, ready }) {
  return (
    <div
      className={`flex h-[72px] w-[72px] shrink-0 items-center justify-center rounded-full border text-[26px] font-bold tracking-[-.03em] shadow-[inset_0_0_28px_rgba(255,255,255,.06),0_0_28px_rgba(89,116,255,.12)] transition-colors sm:h-[84px] sm:w-[84px] sm:text-[30px] lg:h-[96px] lg:w-[96px] lg:text-[38px] ${
        ready
          ? "border-violet-400/30 bg-[linear-gradient(155deg,rgba(139,108,207,.35),rgba(47,111,232,.18))] text-white"
          : "border-white/10 bg-white/[.04] text-mut"
      }`}
      aria-hidden="true"
    >
      {name.slice(0, 1)}
    </div>
  );
}

export default function Personas() {
  const navigate = useNavigate();
  const { reloadProfile, resetSession, setOnboarded } = useResult();
  const cards = personaCards();
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState("");

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
    // 슬롯을 먼저 비운 뒤 온보딩으로 — 순서가 바뀌면 방금 입력한 프로필이 지워진다.
    startMyAccount();
    resetSession();      // 체험하던 인물의 결과가 내 계정 화면에 남지 않게
    reloadProfile();     // 비워진 저장소를 읽어 기본 프로필로 되돌린다
    navigate("/onboarding");
  }

  return (
    <div className="pb-8 lg:pb-12">
      <div className="pt-2 text-left lg:mx-auto lg:max-w-[760px] lg:pt-1 lg:text-center">
        <div className="text-[12px] font-semibold text-violet-300 lg:text-[14px]">체험하기</div>
        <h1 className="mt-1 text-[22px] font-bold tracking-[-.035em] lg:text-[38px]">
          누구의 1년으로 들어가 볼까요?
        </h1>
        <p className="mt-3 text-[12px] leading-relaxed text-sub lg:text-[14px] lg:leading-6">
          한 사람의 1년치 기록과 지금 고민 중인 두 선택이 담겨 있어요. 고르면 그 사람의
          <span className="lg:block"> 자리에서 바로 비교를 볼 수 있습니다.</span>
        </p>
        <p className="mt-1.5 text-[10px] leading-relaxed text-mut lg:text-[11px]">
          모두 합성(가상) 인물이며 실제 사용자의 기록이 아닙니다.
        </p>
      </div>

      {error && (
        <p className="mt-4 rounded-xl border border-amber-400/25 bg-amber-500/10 px-3.5 py-2.5 text-[11px] text-amber-200">
          {error}
        </p>
      )}

      <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:mx-auto lg:mt-7 lg:max-w-[1120px] lg:grid-cols-3 lg:gap-5">
        {cards.map((card) => (
          <button
            key={card.id}
            type="button"
            disabled={!card.ready || Boolean(busy)}
            onClick={() => pick(card)}
            aria-label={`${card.name} ${card.ready ? "체험 시작" : "준비 중"}`}
            className={`tap group relative flex items-center gap-4 rounded-[20px] border p-4 text-left transition-all lg:min-h-[250px] lg:flex-col lg:items-center lg:justify-center lg:gap-3 lg:rounded-[22px] lg:p-5 lg:text-center ${
              card.ready
                ? "border-white/[.14] bg-white/[.035] hover:-translate-y-0.5 hover:border-violet-400/55 hover:bg-violet-500/[.07] hover:shadow-[0_0_30px_rgba(139,108,207,.13)] active:scale-[.99]"
                : "cursor-default border-white/[.05] bg-white/[.015] opacity-60"
            } ${busy === card.id ? "border-violet-400 bg-violet-500/10 shadow-[0_0_24px_rgba(139,108,207,.32)]" : ""}`}
          >
            {busy === card.id && <span className="absolute right-4 top-4 flex h-7 w-7 items-center justify-center rounded-full bg-white text-violet-600"><Check size={16} strokeWidth={3} /></span>}
            <Face name={card.name} ready={card.ready} />

            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 lg:flex-col lg:gap-0.5">
                <span className="text-[16px] font-bold tracking-[-.02em] text-ink lg:text-[18px]">
                  {card.name}
                </span>
                <span className="text-[12px] text-mut">
                  {card.age} · {card.sex === "1" ? "남" : "여"}
                </span>
              </div>
              <p className="mt-0.5 truncate text-[12px] text-sub">{card.job}</p>
              <p className="mt-1.5 text-[11px] leading-[1.5] text-mut lg:min-h-[33px]">
                {card.tagline}
              </p>

              <div className="mt-2.5 flex flex-wrap items-center gap-1.5 lg:justify-center">
                <span
                  className={`rounded-full border px-2 py-[3px] text-[10px] font-semibold ${
                    KIND_TONE[card.kind] || "border-white/10 bg-white/5 text-sub"
                  }`}
                >
                  {card.kind}
                </span>
                <span className="rounded-full border border-white/10 bg-white/[.04] px-2 py-[3px] text-[10px] text-mut">
                  {card.mbti}
                </span>
                {!card.ready && (
                  <span className="ml-auto flex items-center gap-1 text-[10px] font-semibold text-mut">
                    <Lock size={11} /> 준비 중
                  </span>
                )}
              </div>
            </div>

          </button>
        ))}
      </div>

      <div className="mt-7 flex flex-col items-center justify-center gap-3 sm:flex-row">
        <button type="button" onClick={makeMine} disabled={Boolean(busy)} className="tap flex items-center gap-2 rounded-full border border-violet-400/25 bg-violet-500/[.07] px-4 py-2.5 text-[11px] font-semibold text-violet-200 hover:bg-violet-500/[.12]">
          <UserPlus size={14} /> 내 프로필로 시작하기
        </button>
        <button type="button" onClick={() => navigate("/")} className="tap px-3 py-2 text-[11px] font-semibold text-mut hover:text-sub">
          처음 화면으로
        </button>
      </div>
    </div>
  );
}
