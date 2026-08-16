// ─────────────────────────────────────────────────────────────
// 온보딩 직후 — 시작 방식 고르기.
//
// 갓 만든 계정에는 기록이 없다. 그런데 **두 미래 비교 자체는 기록 없이도 된다**
//   (InputScreen 의 잠금 조건은 선택지 문구 두 개뿐이고, 백엔드 diary 는 Optional).
//   기록이 없을 때 약해지는 건 예측 숫자가 아니라 **개인화**다 —
//   일기에서 뽑는 감정·가치 신호가 없어 서술 순서·초점·확신도가 기본값으로 간다.
//   그래서 "시뮬레이션을 못 한다"고 쓰지 않는다. 사실이 아니고, 그렇게 쓰면
//   아무도 '빈 상태로 시작'을 고르지 않는다.
//
// 정직선: 예시 데이터는 지원(합성 인물)의 기록이다. 방금 입력한 본인 정보와
//   일기 내용이 어긋나는 게 정상이며, 출처를 여기서 밝힌다.
//   (personaSession.seedStarterData 가 sourceName·sourceTagline 을 돌려주는 이유)
// ─────────────────────────────────────────────────────────────

import { BookOpen, Check, Sparkles } from "lucide-react";

function Option({ icon: Icon, title, lead, points, note, tone, onClick, disabled }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`tap flex h-full flex-col rounded-[20px] border p-4 text-left transition-all active:scale-[.99] disabled:opacity-50 ${
        tone === "primary"
          ? "border-violet-400/35 bg-violet-500/[.1] hover:border-violet-400/60 hover:bg-violet-500/[.16]"
          : "border-white/[.09] bg-white/[.035] hover:border-white/20 hover:bg-white/[.06]"
      }`}
    >
      <span
        className={`flex h-9 w-9 items-center justify-center rounded-full ${
          tone === "primary" ? "bg-violet-500/20 text-violet-300" : "bg-white/[.07] text-sub"
        }`}
      >
        <Icon size={17} />
      </span>
      <span className="mt-3 text-[14px] font-bold text-ink">{title}</span>
      <span className="mt-1 text-[11px] leading-[1.55] text-sub">{lead}</span>

      <span className="mt-3 flex flex-col gap-1.5">
        {points.map((p) => (
          <span key={p} className="flex items-start gap-1.5 text-[11px] leading-[1.5] text-mut">
            <Check size={12} className="mt-[3px] shrink-0 text-violet-300/70" />
            {p}
          </span>
        ))}
      </span>

      {note && (
        <span className="mt-3 block border-t border-white/[.07] pt-2.5 text-[10px] leading-[1.5] text-mut">
          {note}
        </span>
      )}
    </button>
  );
}

export default function StarterDataDialog({ open, name, busy, onSample, onEmpty }) {
  if (!open) return null;
  const who = name?.trim() ? `${name.trim()}님` : "탐험가님";

  return (
    <div className="fixed inset-0 z-[130] flex items-center justify-center bg-[#02050C]/85 px-4 py-6 backdrop-blur-md">
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="starter-title"
        className="max-h-[min(720px,92dvh)] w-full max-w-[680px] overflow-y-auto rounded-[28px] border border-white/10 bg-[radial-gradient(circle_at_80%_0%,rgba(139,108,207,.22),transparent_36%),#0B1423] p-5 shadow-[0_30px_90px_rgba(0,0,0,.65)] sm:p-7"
      >
        <div className="text-[11px] font-bold tracking-[.16em] text-violet-300">WELCOME</div>
        <h2 id="starter-title" className="mt-1 text-[22px] font-bold tracking-[-.03em] sm:text-[26px]">
          {who}의 계정이 만들어졌어요
        </h2>

        <p className="mt-3 text-[12px] leading-relaxed text-sub sm:text-[13px]">
          두 미래 비교는 <b className="text-ink">지금 바로</b> 해볼 수 있어요. 다만 아직 일기 기록이
          없어서, <b className="text-ink">나에게 맞춘 해석의 정확도는 낮습니다.</b> 감정·가치 신호를
          뽑아낼 기록이 없어 설명이 일반적인 톤으로 나가고, ‘나의 우주’와 주간 리포트는 비어 있어요.
        </p>
        <p className="mt-2 text-[11px] leading-relaxed text-mut">
          예측 숫자(소득 궤적·인과효과·생존곡선)는 프로필만으로 계산되므로 어느 쪽을 고르든 같습니다.
          달라지는 건 그 숫자를 <b className="text-sub">얼마나 내 이야기로 풀어주는가</b> 예요.
        </p>

        <div className="mt-5 grid gap-3 sm:grid-cols-2">
          <Option
            icon={Sparkles}
            tone="primary"
            title="예시 기록 1년치로 시작"
            lead="기록이 쌓인 상태가 어떤 모습인지 모든 화면에서 바로 볼 수 있어요."
            points={[
              "나의 우주 · 별자리 · 주간 리포트가 채워짐",
              "성향 맞춤 해석이 작동하는 모습을 확인",
              "언제든 설정에서 지우고 처음부터 시작 가능",
            ]}
            note="넣는 기록은 지원(29세, 프로덕트 디자이너)의 합성 1년치예요. 방금 입력하신 정보와 일기 내용이 어긋나는 게 정상이며 ‘예시 데이터’ 배지가 붙습니다."
            disabled={busy}
            onClick={onSample}
          />
          <Option
            icon={BookOpen}
            title="빈 상태로 시작"
            lead="오늘부터 내 기록을 직접 쌓아가요. 서비스를 처음부터 그대로 겪어볼 수 있어요."
            points={[
              "두 미래 비교는 지금도 가능",
              "기록이 쌓일수록 해석이 나에게 맞춰짐",
              "나의 우주가 오늘 첫 별부터 시작",
            ]}
            note="일기가 없는 동안에는 맞춤 해석 대신 일반 해석이 나갑니다. 며칠치만 쌓여도 달라져요."
            disabled={busy}
            onClick={onEmpty}
          />
        </div>

        {busy && (
          <p className="mt-4 text-center text-[11px] font-semibold text-violet-300">
            준비하는 중이에요…
          </p>
        )}
      </section>
    </div>
  );
}
