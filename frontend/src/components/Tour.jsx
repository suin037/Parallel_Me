import { useEffect, useRef, useState } from "react";
// (useRef 는 말풍선 높이 측정에도 쓴다)
import { useLocation, useNavigate } from "react-router-dom";
import Mascot from "./Mascot.jsx";
import { MASCOTS } from "../data/result.js";
import { TOUR_STEPS, canRunTourAt, clearWantTour, markTourSeen, wantsTour } from "../data/tour.js";

// ─────────────────────────────────────────────────────────────
// 첫 사용 안내 — 화면을 어둡게 덮고 그 버튼만 뚫어 보여주고, 다음 화면으로 데려간다.
//
// Layout 에 마운트한다. 화면 안에 두면 라우트가 바뀔 때 같이 사라져 안내가 끊긴다.
//
// 구멍은 큰 box-shadow 로 낸다(캔버스·클립패스 없이 됨): 작은 사각형에 화면보다 큰
// 그림자를 주면 그 사각형만 빼고 전부 어두워진다.
// ─────────────────────────────────────────────────────────────

/**
 * 그 단계의 대상 중 **화면에 실제로 보이는** 것을 고른다.
 *
 * 탭바(TabBar)는 lg:hidden, 상단 네비는 lg 전용이라 같은 키를 둘 다 달아 둔다.
 * 그냥 querySelector 로 첫 번째를 집으면 PC 에서 숨은 탭바를 잡아 크기 0 인
 * 점만 뚫린다. getClientRects().length 는 display:none 이면 0 이라 이걸로 거른다.
 */
function findVisible(id) {
  const all = document.querySelectorAll(`[data-tour="${id}"]`);
  for (const el of all) if (el.getClientRects().length) return el;
  return null;
}

export default function Tour() {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const [open, setOpen] = useState(false);
  const [at, setAt] = useState(0);
  const [box, setBox] = useState(null);
  // 대상을 찾은 단계의 id. boolean 이면 안 된다 — 5·6단계처럼 **같은 화면에서 단계만
  // 바뀔 때** true→true 라 값이 안 변하고, 위치 재측정 effect 가 다시 돌지 않는다.
  // 그러면 설명은 새 단계인데 조명은 이전 자리에 남는다.
  const [readyId, setReadyId] = useState(null);
  // 말풍선 실제 높이. 상수로 가정하면 줄 수가 많은 단계에서 화면 밖으로 밀린다.
  const tipRef = useRef(null);
  const [tipH, setTipH] = useState(220);
  const timers = useRef([]);

  const clearTimers = () => { timers.current.forEach(clearInterval); timers.current = []; };

  // 스스로 시작하지 않는다 — 사용자가 안내를 고른 표시가 있을 때만 열린다.
  //
  // 랜딩에서 골랐다면 그때는 짚을 화면이 없다. 그래서 표시만 남겨 두고, 온보딩을
  // 마치고 앱 화면에 들어오는 이 시점에 시작한다. 설정에서 눌렀다면 이미 앱
  // 안이라 이벤트로 곧장 열린다.
  useEffect(() => {
    const start = () => {
      if (!wantsTour() || !canRunTourAt(window.location.pathname)) return;
      setAt(0);
      setOpen(true);
    };
    window.addEventListener("pm:tour-start", start);
    return () => { window.removeEventListener("pm:tour-start", start); clearTimers(); };
  }, []);

  useEffect(() => {
    if (open || !wantsTour() || !canRunTourAt(pathname)) return;
    setAt(0);
    setOpen(true);
  }, [pathname, open]);

  const step = open ? TOUR_STEPS[at] : null;

  // 단계가 바뀌면 그 화면으로 데려간 뒤, 대상이 나타날 때까지 기다린다.
  useEffect(() => {
    if (!step) return;
    // 여기서 box 를 지우지 않는다. 지우면 구멍이 사라져 화면이 한 번 새까매졌다가
    // 새 자리에 툭 나타난다. 이전 구멍을 그대로 두면 새 위치로 **미끄러져 이동**한다.
    setReadyId(null);
    if (step.route && step.route !== pathname) { navigate(step.route); return; }

    let waited = 0;
    const find = setInterval(() => {
      const el = findVisible(step.id);
      if (el) {
        clearInterval(find);
        // 스크롤은 즉시. 부드럽게 굴리면 구멍이 스크롤을 300ms 뒤에서 쫓아가
        // 출렁인다. 어차피 화면은 덮여 있어 스크롤 자체는 보이지 않고,
        // 눈에 보이는 움직임은 구멍이 새 자리로 미끄러지는 것뿐이다.
        el.scrollIntoView({ block: "center" });
        setReadyId(step.id);
        return;
      }
      waited += 120;
      // 없는 단계에서 오래 멈춰 있으면 영상에 빈 화면이 그대로 남는다.
      // 1.5초면 화면 전환이 끝나고도 남으니, 그때까지 없으면 조용히 넘긴다.
      if (waited > 1500) {
        clearInterval(find);
        setAt((i) => (i + 1 < TOUR_STEPS.length ? i + 1 : i));
        if (at + 1 >= TOUR_STEPS.length) finish();
      }
    }, 120);
    timers.current.push(find);
    return () => clearInterval(find);
  }, [step, pathname]); // eslint-disable-line react-hooks/exhaustive-deps

  // 대상 위치 추적 — 스크롤·리사이즈에도 구멍이 따라간다.
  useEffect(() => {
    if (!step || readyId !== step.id) return;
    // 매 프레임 다시 잰다. 200ms 간격으로 재면 scrollIntoView 가 부드럽게 움직이는
    // 동안 구멍이 계단처럼 끊겨 따라간다. 값이 그대로면 상태를 안 바꿔 헛렌더를 막는다.
    let raf = 0;
    const measure = () => {
      const el = findVisible(step.id);
      if (el) {
        const r = el.getBoundingClientRect();
        setBox((prev) =>
          prev && prev.top === r.top && prev.left === r.left
            && prev.width === r.width && prev.height === r.height
            ? prev
            : { top: r.top, left: r.left, width: r.width, height: r.height });
      }
      raf = requestAnimationFrame(measure);
    };
    raf = requestAnimationFrame(measure);
    return () => cancelAnimationFrame(raf);
  }, [readyId, step]);

  // 단계가 바뀌면 말풍선 높이를 다시 잰다 — 줄 수가 달라 높이가 매번 다르다.
  useEffect(() => {
    if (!tipRef.current) return;
    const h = tipRef.current.getBoundingClientRect().height;
    if (h && Math.abs(h - tipH) > 2) setTipH(h);
  });

  function finish() {
    markTourSeen();
    clearWantTour();      // 다시 고르기 전엔 열리지 않는다
    clearTimers();
    setOpen(false);
    setBox(null);
  }
  const next = () => (at + 1 < TOUR_STEPS.length ? setAt(at + 1) : finish());

  if (!open || !step) return null;

  const pad = 8;
  const hole = box && {
    top: box.top - pad, left: box.left - pad,
    width: box.width + pad * 2, height: box.height + pad * 2,
  };
  // 말풍선 자리 — 대상 아래에, 아래가 좁으면 위에.
  //
  // 둘 다 안 되는 경우가 있다: '나의 우주'처럼 대상이 화면을 거의 다 덮으면
  // 아래도 위도 자리가 없다. 그때 위쪽 계산을 그대로 쓰면 말풍선이 화면 밖으로
  // 밀려나 아예 안 보인다. 그래서 마지막엔 무조건 화면 안으로 가둔다.
  const who = MASCOTS[step.mascot] || MASCOTS.lumi;
  const tint = who.color;
  const W = 340, GAP = 14, M = 16;
  const TIP_H = tipH;
  let tipStyle = { top: "50%", left: "50%", transform: "translate(-50%,-50%)" };
  if (hole) {
    const under = hole.top + hole.height + GAP;
    const over = hole.top - GAP - TIP_H;
    const top = under + TIP_H <= window.innerHeight - M ? under
      : over >= M ? over
      : window.innerHeight - TIP_H - M;   // 둘 다 안 들어가면 화면 아래쪽에 띄운다
    tipStyle = {
      top: Math.max(M, top),
      left: Math.max(M, Math.min(window.innerWidth - W - M, hole.left)),
    };
  }

  return (
    <div className="fixed inset-0 z-[200]" role="dialog" aria-label="사용 안내">
      {/* 대상을 아직 못 찾았으면 화면만 덮어 둔다(빈 구멍이 번쩍이지 않게) */}
      {!hole && <div className="absolute inset-0 bg-[#02050C]/82" />}
      {hole && (
        <div
          className="pointer-events-none absolute rounded-[14px] transition-all duration-[360ms] ease-out"
          style={{
            top: hole.top, left: hole.left, width: hole.width, height: hole.height,
            boxShadow: "0 0 0 9999px rgba(2,5,12,.82)",
            outline: "2px solid rgba(139,108,207,.9)",
          }}
        />
      )}

      {/* 배경 아무 데나 눌러도 다음으로 */}
      <button onClick={next} className="absolute inset-0 h-full w-full cursor-default" aria-label="다음" />

      {/* 해설 말풍선 — 그 화면을 맡은 마스코트가 말한다 */}
      <div
        ref={tipRef}
        className="absolute flex max-h-[calc(100dvh-32px)] w-[min(340px,calc(100vw-32px))] flex-col overflow-hidden rounded-[20px] border bg-[#111A2C] shadow-[0_24px_70px_rgba(0,0,0,.62)] transition-all duration-[360ms] ease-out"
        style={{ ...tipStyle, borderColor: `${tint}66` }}
      >
        <div className="flex items-center gap-2.5 px-4 pb-2.5 pt-3">
          <Mascot which={who.key} size={38} />
          <div className="min-w-0 flex-1">
            <p className="text-[9px] font-bold tracking-[.14em]" style={{ color: tint }}>
              {who.tag}
            </p>
            <p className="text-[10px] text-mut">{at + 1} / {TOUR_STEPS.length}</p>
          </div>
        </div>

        {/* 내용은 단계마다 새로 올라온다 — 글자가 툭 갈리지 않게.
            줄이 많으면 여기서만 스크롤한다(말풍선이 화면 밖으로 나가지 않게). */}
        <div key={at} className="animate-fade min-h-0 flex-1 overflow-y-auto px-4">
          <h3 className="text-[14.5px] font-bold leading-snug text-ink">{step.title}</h3>
          <p className="mt-1.5 text-[11.5px] leading-relaxed text-sub">{step.body}</p>
          {step.lines?.length > 0 && (
            <ul className="mt-2.5 space-y-1.5 border-t border-white/[.07] pt-2.5">
              {step.lines.map((line, i) => (
                <li key={i} className="flex gap-2 text-[11px] leading-relaxed text-sub">
                  <span className="mt-[6px] h-1 w-1 shrink-0 rounded-full" style={{ background: tint }} />
                  <span>{line}</span>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="mt-3 flex items-center gap-2 px-4 pb-3.5">
          <button onClick={finish} className="tap text-[11px] text-mut">건너뛰기</button>
          <div className="flex-1" />
          {at > 0 && (
            <button onClick={() => setAt(at - 1)} className="tap rounded-lg border border-white/[.12] px-3 py-1.5 text-[11px] text-sub">
              이전
            </button>
          )}
          <button
            onClick={next}
            className="tap rounded-lg px-3.5 py-1.5 text-[11px] font-bold text-white"
            style={{ background: tint, color: "#12101B" }}
          >
            {at + 1 < TOUR_STEPS.length ? "다음" : "시작하기"}
          </button>
        </div>
      </div>
    </div>
  );
}
