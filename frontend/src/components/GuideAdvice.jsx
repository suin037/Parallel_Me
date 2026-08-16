import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { ChevronDown, X } from "lucide-react";
import Mascot from "./Mascot.jsx";
import { MASCOTS } from "../data/result.js";
import { adviceFor, adviceOn, setAdvice } from "../data/guideAdvice.js";

// ─────────────────────────────────────────────────────────────
// 가이드 조언 — 그 화면을 맡은 마스코트가 나와서 말풍선으로 설명한다.
//
// 화면에 상시로 붙는 도움말 상자가 아니다. '가이드 확인하기'를 켠 사람에게만
// 따라다니고, 닫으면 그걸로 끝난다.
//
// Layout 에 마운트한다. 화면 안에 두면 라우트가 바뀔 때 같이 사라진다.
// 지금 보는 화면이 바뀌면 말하는 마스코트도 바뀐다 — 행성·별자리처럼 라우트가
// 같은 패널은 열릴 때 pm:advice-surface 로 자기가 열렸다고 알린다.
//
// 넘어갈 때는 부드럽게. 이 안내로 영상을 찍기 때문에, 내용이 툭 바뀌면 그 장면이
// 그대로 남는다. key 를 바꿔 다시 마운트시키고 animate-fade 로 올라오게 한다.
// ─────────────────────────────────────────────────────────────
export default function GuideAdvice() {
  const { pathname } = useLocation();
  const [on, setOn] = useState(adviceOn);
  const [surface, setSurface] = useState(null);
  const [folded, setFolded] = useState(false);

  useEffect(() => {
    const sync = () => setOn(adviceOn());
    const onSurface = (e) => setSurface(e.detail || null);
    window.addEventListener("pm:advice", sync);
    window.addEventListener("pm:advice-surface", onSurface);
    return () => {
      window.removeEventListener("pm:advice", sync);
      window.removeEventListener("pm:advice-surface", onSurface);
    };
  }, []);

  // 화면을 옮기면 열려 있던 패널 이야기는 접는다.
  useEffect(() => { setSurface(null); setFolded(false); }, [pathname]);

  const advice = on ? adviceFor(pathname, surface) : null;
  if (!advice) return null;

  const who = MASCOTS[advice.mascot] || MASCOTS.lumi;
  const tint = who.color;

  return (
    // fixed 여야 한다. absolute 로 두면 화면이 아니라 **문서 전체** 아래에 붙어서,
    // 내용이 길어 페이지가 길어지면 카드가 화면 밖으로 밀려난다(스크롤해야 보인다).
    <div className="pointer-events-none fixed inset-x-0 bottom-0 z-[90] flex justify-center px-3 pb-[calc(env(safe-area-inset-bottom)+72px)] lg:pb-6">
      {/* key — 화면이 바뀌면 다시 올라오며 나타난다(툭 바뀌지 않게) */}
      <div
        key={advice.title}
        className="pointer-events-auto flex w-full max-w-[470px] animate-fade items-end gap-2"
      >
        {/* 말하는 친구 */}
        <div className="hidden shrink-0 flex-col items-center pb-1 sm:flex">
          <Mascot which={who.key} size={54} />
          <span className="mt-0.5 text-[9px] font-bold" style={{ color: tint }}>
            {who.name.split(" · ")[0]}
          </span>
        </div>

        {/* 말풍선 */}
        <div
          className="relative min-w-0 flex-1 overflow-hidden rounded-[20px] border bg-[#0D1727]/97 shadow-[0_22px_70px_rgba(0,0,0,.6)] backdrop-blur-xl"
          style={{ borderColor: `${tint}55` }}
        >
          {/* 말풍선 꼬리 — 마스코트 쪽을 가리킨다 */}
          <span
            className="absolute -left-[6px] bottom-6 hidden h-3 w-3 rotate-45 border-b border-l bg-[#0D1727] sm:block"
            style={{ borderColor: `${tint}55` }}
          />

          <div className="flex items-center gap-2 border-b border-white/[.07] px-3.5 py-2.5">
            {/* Mascot 은 className 을 받지 않아 감싸서 숨긴다.
                (왼쪽 큰 마스코트는 sm 이상에서만 나오므로 좁은 화면엔 여기 작은 게 선다) */}
            <span className="shrink-0 sm:hidden"><Mascot which={who.key} size={24} /></span>
            <div className="min-w-0 flex-1">
              <p className="text-[9px] font-bold tracking-[.14em]" style={{ color: tint }}>
                {who.tag}
              </p>
              <p className="truncate text-[12.5px] font-bold text-ink">{advice.title}</p>
            </div>
            <button
              type="button"
              onClick={() => setFolded((v) => !v)}
              aria-label={folded ? "설명 펼치기" : "설명 접기"}
              className="tap flex h-8 w-8 items-center justify-center rounded-full text-mut hover:bg-white/[.06]"
            >
              <ChevronDown size={16} className={`transition-transform duration-300 ${folded ? "" : "rotate-180"}`} />
            </button>
            {/* 끄기 — 다시 보려면 설정에서 켠다. */}
            <button
              type="button"
              onClick={() => setAdvice(false)}
              aria-label="가이드 끄기"
              className="tap flex h-8 w-8 items-center justify-center rounded-full text-mut hover:bg-white/[.06]"
            >
              <X size={15} />
            </button>
          </div>

          {!folded && (
            <div className="max-h-[40dvh] overflow-y-auto px-3.5 pb-3.5 pt-3">
              {advice.intro && (
                <p className="mb-2.5 text-[11.5px] font-semibold leading-relaxed text-ink">{advice.intro}</p>
              )}
              <ul className="space-y-2">
                {advice.lines.map((line, i) => (
                  <li key={line.label || i} className="flex gap-2 text-[11px] leading-relaxed text-sub">
                    <span className="mt-[6px] h-1 w-1 shrink-0 rounded-full" style={{ background: tint }} />
                    <span>
                      {line.label && <b className="font-semibold text-ink">{line.label}</b>}
                      {line.label && " — "}
                      {line.text}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
