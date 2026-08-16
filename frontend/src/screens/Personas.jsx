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
import { ArrowRight, Lock, UserPlus } from "lucide-react";
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
      className={`flex h-[72px] w-[72px] shrink-0 items-center justify-center rounded-full border text-[26px] font-bold tracking-[-.03em] transition-colors sm:h-[84px] sm:w-[84px] sm:text-[30px] ${
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
    <div className="pb-8">
      <div className="pt-2 lg:pt-4">
        <div className="text-[12px] font-semibold text-[#8B6CCF] lg:text-[13px]">체험하기</div>
        <h1 className="mt-0.5 text-[22px] font-bold tracking-[-.035em] lg:text-[32px]">
          누구의 1년으로 들어가 볼까요?
        </h1>
        <p className="mt-2 text-[12px] leading-relaxed text-sub lg:text-[13px]">
          한 사람의 1년치 기록과 지금 고민 중인 두 선택이 담겨 있어요. 고르면 그 사람의
          자리에서 바로 비교를 볼 수 있습니다.
        </p>
        <p className="mt-1.5 text-[11px] leading-relaxed text-mut">
          모두 합성(가상) 인물이며 실제 사용자의 기록이 아닙니다.
        </p>
      </div>

      {error && (
        <p className="mt-4 rounded-xl border border-amber-400/25 bg-amber-500/10 px-3.5 py-2.5 text-[11px] text-amber-200">
          {error}
        </p>
      )}

      <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:mt-7 lg:grid-cols-3 lg:gap-4">
        {cards.map((card) => (
          <button
            key={card.id}
            type="button"
            disabled={!card.ready || Boolean(busy)}
            onClick={() => pick(card)}
            aria-label={`${card.name} ${card.ready ? "체험 시작" : "준비 중"}`}
            className={`tap group relative flex items-center gap-4 rounded-[20px] border p-4 text-left transition-all lg:flex-col lg:items-start lg:gap-3 lg:p-5 ${
              card.ready
                ? "border-white/[.08] bg-white/[.035] hover:border-violet-400/35 hover:bg-white/[.06] active:scale-[.99]"
                : "cursor-default border-white/[.05] bg-white/[.015] opacity-60"
            } ${busy === card.id ? "border-violet-400/50 bg-violet-500/10" : ""}`}
          >
            <Face name={card.name} ready={card.ready} />

            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
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

              <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
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

            {card.ready && (
              <span className="hidden items-center gap-1 self-end text-[11px] font-semibold text-violet-300 opacity-0 transition-opacity group-hover:opacity-100 lg:flex">
                {busy === card.id ? "여는 중…" : "이 사람으로 시작"} <ArrowRight size={13} />
              </span>
            )}
          </button>
        ))}

        {/* 내 계정 카드 — 페르소나와 같은 자리에 둔다. */}
        <button
          type="button"
          onClick={makeMine}
          disabled={Boolean(busy)}
          className="tap flex items-center gap-4 rounded-[20px] border border-dashed border-violet-400/30 bg-violet-500/[.06] p-4 text-left transition-all hover:border-violet-400/50 hover:bg-violet-500/[.1] active:scale-[.99] lg:flex-col lg:items-start lg:gap-3 lg:p-5"
        >
          <div className="flex h-[72px] w-[72px] shrink-0 items-center justify-center rounded-full border border-violet-400/30 bg-violet-500/10 text-violet-300 sm:h-[84px] sm:w-[84px]">
            <UserPlus size={26} />
          </div>
          <div className="min-w-0 flex-1">
            <span className="text-[16px] font-bold tracking-[-.02em] text-ink lg:text-[18px]">
              나만의 계정 만들기
            </span>
            <p className="mt-1.5 text-[11px] leading-[1.5] text-mut">
              내 이름과 아바타로 시작해요. 기록은 오늘부터 직접 쌓습니다.
            </p>
          </div>
        </button>
      </div>

      <button
        type="button"
        onClick={() => navigate("/")}
        className="tap mx-auto mt-7 block text-[12px] font-semibold text-mut hover:text-sub"
      >
        처음 화면으로
      </button>
    </div>
  );
}
