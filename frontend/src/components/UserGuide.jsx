import { BookOpen, GitCompareArrows, Orbit, Save, X } from "lucide-react";

const STEPS = [
  { icon: GitCompareArrows, title: "두 갈림길 비교", text: "고민 중인 두 선택을 자유롭게 적으면 관련 삶의 영역과 데이터를 연결해요." },
  { icon: BookOpen, title: "기록으로 맥락 쌓기", text: "일기는 반복 고민·감정 흐름·가치 신호를 파악해 비교 주제와 심리 해석을 개인화해요." },
  { icon: Orbit, title: "나의 우주에서 흐름 보기", text: "기록은 별과 행성으로 쌓이고, 영역별 변화와 최근 흐름을 다시 볼 수 있어요." },
  { icon: Save, title: "선택 이후까지 기록", text: "비교 결과를 항해일지에 저장하고 결정·실행·회고를 이어갈 수 있어요." },
];

export default function UserGuide({ open, onClose }) {
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
        <button type="button" onClick={onClose} className="tap mt-5 w-full rounded-full bg-[#8B6CCF] py-3.5 text-[13px] font-bold text-white">이해했어요</button>
      </section>
    </div>
  );
}
