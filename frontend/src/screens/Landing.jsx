import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "../components/ui.jsx";
import { startMyAccount } from "../data/personaSession.js";
import { hasMyRecords, startFreshMySlot } from "../data/personaSlots.js";
import { useResult } from "../data/ResultContext.jsx";

export default function Landing() {
  const navigate = useNavigate();
  const { reloadProfile } = useResult();
  // 보관된 기록이 있는지는 화면을 그릴 때 한 번만 본다(랜딩에서는 바뀌지 않는다).
  const [mine] = useState(hasMyRecords);

  // 내 계정으로 가기 전에 슬롯을 먼저 비운다 — 순서가 바뀌면(온보딩 뒤에 부르면)
  // activateSlot 의 restoreLive({}) 가 방금 입력한 pm.profile.v1 을 지운다.
  // 전체 새로고침 대신 reloadProfile() 로 이전 프로필 잔상을 지운다 — iframe·사파리에서는
  // 저장소가 메모리라(safeStorage) 새로고침하면 세션이 통째로 날아간다.
  // 새로 만들기 — 보관해 둔 기록까지 비우고 빈 상태로 시작한다.
  // (예전에는 슬롯을 '복구'해서, 새 계정인데 앞사람 1년치가 그대로 따라왔다.)
  function makeMyAccount() {
    startFreshMySlot();
    reloadProfile();
    navigate("/onboarding");
  }

  // 로그아웃하며 보관해 둔 기록으로 돌아간다. 로그인이 없어 '같은 사람'인지는
  // 확인할 수 없다 — 이 기기에 남아 있는 마지막 계정이라는 뜻이다.
  function continueMyAccount() {
    startMyAccount();
    reloadProfile();
    navigate("/my");
  }

  return (
    <div className="relative flex min-h-full flex-col overflow-hidden">
      <div className="absolute inset-0 bg-[#050914]">
        <video
          className="absolute inset-0 h-full w-full object-cover"
          src="/space-intro.mp4"
          autoPlay
          loop
          muted
          playsInline
          preload="auto"
          aria-label="별과 행성이 펼쳐지는 우주 인트로"
        />
        <div className="absolute inset-0 bg-gradient-to-b from-[#030712]/15 via-[#050914]/25 to-[#07101E]/95" />
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_68%_38%,transparent_0%,rgba(3,7,18,.08)_35%,rgba(3,7,18,.48)_100%)]" />
      </div>

      <div className="relative z-10 flex min-h-full flex-1 flex-col justify-end px-5 pb-7 pt-20 sm:px-8 sm:pb-8 lg:flex-row lg:items-end lg:justify-between lg:gap-16 lg:px-14 lg:pb-14 xl:px-20 xl:pb-16 2xl:px-24">
        <div className="max-w-[620px] lg:pb-1">
          <p className="mb-3 text-[11px] font-bold tracking-[.18em] text-violet-300 lg:text-[13px]">✦ PARALLEL ME</p>
          <h1 className="mb-2 text-[32px] font-bold leading-[1.16] tracking-[-.04em] text-white lg:text-[52px] xl:text-[60px]">
            고민되는 두 선택,
            <br />조금 더 선명하게
          </h1>
          <p className="mt-4 text-sm leading-relaxed text-white/75 lg:text-[16px] lg:leading-7">
            나와 비슷한 실제 사람들의 데이터로
            <br />두 선택 이후의 가능성을 살펴봅니다.
          </p>
        </div>

        <div className="mt-5 flex flex-col gap-3 lg:mt-0 lg:w-auto lg:min-w-[380px] lg:flex-row-reverse lg:items-center lg:justify-end lg:gap-3">
          <Button className="lg:min-w-[150px] lg:px-7 lg:py-4" onClick={() => navigate("/personas")}>
            체험하기
          </Button>
          <Button variant="ghost" className="whitespace-nowrap lg:min-w-[190px] lg:bg-white/10 lg:px-7 lg:py-4 lg:backdrop-blur-md" onClick={makeMyAccount}>
            나만의 계정 만들기
          </Button>
        </div>
        {/* 로그아웃하며 보관해 둔 기록이 있을 때만 — 로그인이 없어서 '이 기기에
            남아 있는 마지막 계정'이라는 뜻이고, 문구도 그렇게 적는다. */}
        {mine && (
          <button
            type="button"
            onClick={continueMyAccount}
            className="tap mt-3 self-start text-[12px] text-white/70 underline underline-offset-4 hover:text-white lg:mt-4"
          >
            이 기기에 남아 있는 내 기록으로 이어서 하기
          </button>
        )}
      </div>
    </div>
  );
}
