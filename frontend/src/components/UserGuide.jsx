import { BookOpen, Compass, GitCompareArrows, MessageSquareText, Orbit, Save, X } from "lucide-react";
import { setAdvice } from "../data/guideAdvice.js";

// 이 모달은 "이 서비스가 뭔지"를 한 장으로 말한다. 그다음 "그래서 어디를 누르면
// 되는지"는 화면을 직접 짚어 주는 안내(Tour)가 맡는다. 아래 두 버튼이 그 갈림길이다.
//
// 왜 고르게 하나: 처음 만든 계정에는 안내가 필요하지만, 둘러보고 싶은 사람에게
// 6단계를 강제로 태우면 그게 더 방해다. 켜고 끄는 걸 본인이 정하게 둔다.
// (나중에 마음이 바뀌면 헤더의 물음표나 설정에서 다시 열 수 있다.)

const STEPS = [
  { icon: GitCompareArrows, title: "두 갈림길 비교", text: "고민 중인 두 선택을 자유롭게 적으면 관련 삶의 영역과 데이터를 연결해요." },
  { icon: BookOpen, title: "기록으로 맥락 쌓기", text: "일기는 반복 고민·감정 흐름·가치 신호를 파악해 비교 주제와 심리 해석을 개인화해요." },
  { icon: Orbit, title: "나의 우주에서 흐름 보기", text: "기록은 별과 행성으로 쌓이고, 영역별 변화와 최근 흐름을 다시 볼 수 있어요." },
  { icon: Save, title: "선택 이후까지 기록", text: "비교 결과를 항해일지에 저장하고 결정·실행·회고를 이어갈 수 있어요." },
];

export default function UserGuide({ open, onClose, onStartTour }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[120] flex items-center justify-center bg-[#02050C]/80 px-4 py-6 backdrop-blur-md" onClick={onClose}>
      <section className="max-h-[min(760px,92dvh)] w-full max-w-[760px] overflow-y-auto rounded-[28px] border border-white/10 bg-[radial-gradient(circle_at_80%_0%,rgba(139,108,207,.22),transparent_36%),#0B1423] p-5 shadow-[0_30px_90px_rgba(0,0,0,.65)] sm:p-7" onClick={(event) => event.stopPropagation()}>
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="text-[11px] font-bold tracking-[.16em] text-violet-300">PARALLEL ME GUIDE</div>
            <h2 className="mt-1 text-[24px] font-bold tracking-[-.03em] sm:text-[30px]">선택을 대신하지 않고,<br />비교할 근거를 비춰드려요.</h2>
            <p className="mt-2 text-[12px] leading-relaxed text-sub sm:text-[13px]">비슷한 사람들의 관측 데이터와 내 기록을 함께 보며 두 선택의 가능성과 주의점을 살펴보는 서비스예요.</p>
          </div>
          <button type="button" onClick={onClose} aria-label="사용 안내 닫기" className="tap flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-white/[.07] text-sub"><X size={18}/></button>
        </div>
        <div className="mt-6 grid gap-3 sm:grid-cols-2">
          {STEPS.map(({ icon: Icon, title, text }, index) => (
            <div key={title} className="rounded-[20px] border border-white/[.08] bg-white/[.035] p-4">
              <div className="flex items-center gap-2"><span className="flex h-8 w-8 items-center justify-center rounded-full bg-violet-500/15 text-violet-300"><Icon size={16}/></span><span className="text-[10px] font-bold text-mut">0{index + 1}</span></div>
              <h3 className="mt-3 text-[14px] font-bold text-ink">{title}</h3>
              <p className="mt-1 text-[11px] leading-relaxed text-sub">{text}</p>
            </div>
          ))}
        </div>
        <div className="mt-4 rounded-2xl border border-violet-400/20 bg-violet-500/[.07] px-4 py-3 text-[11px] leading-relaxed text-sub">
          일기는 예측 숫자를 임의로 바꾸지 않고, 비교할 주제 추천·심리 해석·결과 설명과 안전 안내에 사용돼요. 결과는 확정 미래나 선택 권유가 아닙니다.
        </div>
        {/* onStartTour 가 없으면(랜딩) 소개만 하고 닫는다 — 짚어 줄 화면이 아직 없다. */}
        {onStartTour ? (
          <>
            <div className="mt-5 flex flex-col gap-2.5 sm:flex-row-reverse">
              <button
                type="button"
                onClick={() => { onClose(); onStartTour(); }}
                className="tap flex flex-1 items-center justify-center gap-2 rounded-full bg-[#8B6CCF] py-3.5 text-[13px] font-bold text-white"
              >
                <Compass size={16} /> 화면을 짚어주며 안내받기
              </button>
              <button
                type="button"
                onClick={() => { onClose(); setAdvice(true); }}
                className="tap flex flex-1 items-center justify-center gap-2 rounded-full border border-[#8B6CCF]/45 bg-[#8B6CCF]/12 py-3.5 text-[13px] font-semibold text-[#B8A4F2] hover:bg-[#8B6CCF]/20"
              >
                <MessageSquareText size={16} /> 가이드 확인하기
              </button>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="tap mt-2.5 w-full py-2 text-center text-[11px] text-mut hover:text-sub"
            >
              혼자 둘러볼게요
            </button>
            <p className="mt-1 text-center text-[10px] text-mut">
              가이드를 켜면 화면마다 무엇을 하는 곳인지 옆에서 알려드려요. 설정에서 다시 켤 수 있어요.
            </p>
          </>
        ) : (
          <button type="button" onClick={onClose} className="tap mt-5 w-full rounded-full bg-[#8B6CCF] py-3.5 text-[13px] font-bold text-white">이해했어요</button>
        )}
      </section>
    </div>
  );
}
