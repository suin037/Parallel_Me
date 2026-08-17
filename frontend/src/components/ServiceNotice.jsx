// ─────────────────────────────────────────────────────────────
// 서비스 상태 안내 — 결과 화면 맨 위에 띄운다.
//
// 왜 필요한가: 백엔드가 안 붙으면 runSimulation 이 목업 값(getPredictionPair)을
//   그대로 두고 dataMode 만 "demo" 로 남긴다. 즉 **그럴듯한 가짜 숫자가 아무 표시
//   없이 화면에 뜬다.** 경고가 근거 탭 안쪽에만 있어서, 관람객이
//   첫 화면 숫자만 보고 지나가면 그게 예시인 줄 모른다. 심사 자리에서는 특히 위험하다.
//
// 그래서 상태를 세 가지로 나눠 맨 위에 띄운다.
//   offline  서버에 못 닿았다 → 지금 숫자는 예시다. 크게 알린다(빨강)
//   busy     서버는 멀쩡한데 서사만 생략됐다 → 수치는 진짜다. 부드럽게 알린다(노랑)
//   ok       아무것도 안 띄운다
//
// 문구 원칙: '고장'이 아니라 상황을 말한다. 그리고 **무엇이 진짜이고 무엇이
//   예시인지**를 문장 안에서 분명히 한다.
// ─────────────────────────────────────────────────────────────

import { AlertTriangle, Users, X } from "lucide-react";
import { useState } from "react";

const TONE = {
  offline: {
    icon: AlertTriangle,
    ring: "border-red-400/35 bg-red-500/[.09]",
    dot: "bg-red-500/20 text-red-300",
    title: "지금 연결이 원활하지 않아요",
    body: "아래 숫자와 그래프는 화면 확인용 예시입니다. 실제 예측이 아니니 참고만 해주세요.",
    hint: "잠시 뒤 다시 시도하면 실제 데이터로 계산돼요.",
  },
  busy: {
    icon: Users,
    ring: "border-amber-400/35 bg-amber-500/[.09]",
    dot: "bg-amber-500/20 text-amber-300",
    title: "지금 함께 보고 계신 분이 많아요",
    body: "두 미래의 숫자와 그래프는 실제 데이터로 계산된 값이에요. 다만 이야기로 풀어주는 부분은 잠시 쉬어갑니다.",
    hint: "조금 뒤에 다시 시도하면 서사까지 함께 보실 수 있어요.",
  },
};

/**
 * @param {"ok"|"offline"|"busy"} status
 * @param {() => void} [onRetry]
 */
export default function ServiceNotice({ status = "ok", onRetry }) {
  const [closed, setClosed] = useState(false);
  const tone = TONE[status];
  if (!tone || closed) return null;
  const Icon = tone.icon;

  return (
    <div
      role="status"
      className={`mt-3 flex items-start gap-3 rounded-[18px] border px-4 py-3.5 ${tone.ring}`}
    >
      <span className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${tone.dot}`}>
        <Icon size={16} />
      </span>

      <div className="min-w-0 flex-1">
        <p className="text-[13px] font-bold text-ink">{tone.title}</p>
        <p className="mt-1 text-[12px] leading-[1.6] text-sub">{tone.body}</p>
        <p className="mt-1 text-[11px] leading-[1.5] text-mut">{tone.hint}</p>
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="tap mt-2.5 rounded-full border border-white/15 bg-white/[.06] px-3.5 py-1.5 text-[11px] font-semibold text-ink hover:bg-white/[.1]"
          >
            다시 시도
          </button>
        )}
      </div>

      <button
        type="button"
        onClick={() => setClosed(true)}
        aria-label="안내 닫기"
        className="tap -mr-1 -mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-mut hover:bg-white/[.06]"
      >
        <X size={14} />
      </button>
    </div>
  );
}
