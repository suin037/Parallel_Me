import { useCallback, useEffect, useMemo, useRef, useState } from "react";
// (useRef 는 말풍선 높이 측정에도 쓴다)
import { useLocation, useNavigate } from "react-router-dom";
import { Pause, Play } from "lucide-react";
import Mascot from "./Mascot.jsx";
import { MASCOTS } from "../data/result.js";
import {
  TOUR_STEPS, TOUR_CHAPTERS,
  canRunTourAt, clearWantTour, markTourSeen, stepDuration, wantsTour,
} from "../data/tour.js";

// ─────────────────────────────────────────────────────────────
// 첫 사용 안내 — 화면을 어둡게 덮고 그 버튼만 뚫어 보여주고, 다음 화면으로 데려간다.
//
// Layout 에 마운트한다. 화면 안에 두면 라우트가 바뀔 때 같이 사라져 안내가 끊긴다.
//
// 구멍은 큰 box-shadow 로 낸다(캔버스·클립패스 없이 됨): 작은 사각형에 화면보다 큰
// 그림자를 주면 그 사각형만 빼고 전부 어두워진다.
//
// 넘기는 건 손이 기본이다. 말풍선 머리의 '자동' 을 켜면 그때부터 글 양에 맞춘
// 시간만큼 머물다 스스로 넘어간다(stepDuration). 켜고 끄는 건 언제든 된다.
//
// 키보드도 받는다 — → · Space 다음, ← 이전, Esc 끝내기. 녹화 중에 마우스를
// 화면 위로 가져가지 않아도 되게.
//
// 캡쳐 단계(step.shot) — 시뮬레이션과 결과는 화면을 짚는 대신 미리 찍어 둔 그림을
// 띄우고 그 위에 설명한다. 실제로 돌리면 비교 API 를 태우게 되는데, 안내를 한 번
// 볼 때마다 그걸 부를 이유가 없다(느리고, 결과도 그때그때 달라 영상이 매번 달라진다).
// 그림이 없으면 조용히 다음으로 넘어간다 — 깨진 이미지가 그대로 녹화되지 않게.
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
  const { pathname, search } = useLocation();
  const [open, setOpen] = useState(false);
  const [at, setAt] = useState(0);
  const [box, setBox] = useState(null);
  // 대상을 찾은 단계의 id. boleean 이면 안 된다 — 같은 화면에서 단계만 바뀔 때
  // true→true 라 값이 안 변하고, 위치 재측정 effect 가 다시 돌지 않는다.
  // 그러면 설명은 새 단계인데 조명은 이전 자리에 남는다.
  // (같은 id 를 연달아 짚는 단계도 있어서 id 만으로는 부족하다 — 단계 번호를 붙인다.)
  const [readyId, setReadyId] = useState(null);
  // 말풍선 실제 높이. 상수로 가정하면 줄 수가 많은 단계에서 화면 밖으로 밀린다.
  const tipRef = useRef(null);
  const [tipH, setTipH] = useState(220);
  const timers = useRef([]);
  // 조명이 마지막으로 앉았던 자리. 없으면 화면 밖으로 밀어 둔다(첫 프레임에 안 보이게).
  const lastHoleRef = useRef({ top: -9999, left: -9999, width: 0, height: 0 });
  // 조명이 직전 프레임에 보였는지. 안 보이다 나타나는 순간에는 자리를 '이동'시키면
  // 안 된다 — 보이지 않는 곳에서 새 자리로 미끄러져 오는 게 눈에 띄기 때문이다.
  const wasVisibleRef = useRef(false);
  // 단계가 바뀐 직후 잠깐만 '미끄러지는' 구간을 둔다.
  //
  // 조명·말풍선 자리는 매 프레임 다시 재는 값이다. 거기에 트랜지션을 걸어두면
  // 값이 바뀔 때마다 보간이 처음부터 다시 시작돼, 화면이 떠오르는 동안(animate-fade
  // .35s) 계속 되감기며 뚝뚝 끊겨 보인다. 그래서 자리 이동은 단계가 바뀔 때만
  // 애니메이션하고, 그 뒤 추적은 즉시 반영한다(1:1로 따라붙어 오히려 매끄럽다).
  const [sliding, setSliding] = useState(false);
  // 자동 재생 — 영상 녹화용. 기본은 꺼둔다(혼자 읽는 사람에게는 재촉이 된다).
  const [auto, setAuto] = useState(false);
  // 코스 — 전체(20컷)가 기본이고, 급할 때 쓰는 짧은 코스가 하나 더 있다.
  // 고르는 버튼은 두지 않는다(대부분은 고를 일이 아니다). 키보드로만 — F 전체 · C 핵심만.
  const [mode, setMode] = useState("full");
  const steps = useMemo(
    () => (mode === "core" ? TOUR_STEPS.filter((item) => item.core) : TOUR_STEPS),
    [mode],
  );

  const clearTimers = () => {
    // interval 과 timeout 이 섞여 있다 — id 체계가 같아 둘 다 지운다.
    timers.current.forEach((id) => { clearInterval(id); clearTimeout(id); });
    timers.current = [];
  };

  // 스스로 시작하지 않는다 — 설정에서 '안내 받기'를 누른 그 순간에만 열린다.
  //
  // 예전에는 온보딩이 남긴 표시를 보고 앱에 들어오는 순간 저절로 떴다. 들어가자마자
  // 설명이 시작되면 화면을 볼 틈이 없고, 중간에 창을 닫으면 다음에 또 떴다.
  useEffect(() => {
    const start = () => {
      if (!wantsTour() || !canRunTourAt(window.location.pathname)) return;
      setAt(0);
      setOpen(true);
    };
    window.addEventListener("pm:tour-start", start);
    return () => { window.removeEventListener("pm:tour-start", start); clearTimers(); };
  }, []);

  const rawStep = open ? steps[at] : null;
  // 짧은 코스에서는 short 가 있으면 그걸 쓴다.
  //
  // 원칙 — 상세 설명은 **처음 보면 이해가 안 되는 것**에만 붙인다.
  // 일기·보관함·탭바처럼 보면 아는 화면은 짧은 코스에서 한 줄로 스치고,
  // 행성 해석 · 표본 감소 · 두 집단의 출발점처럼 설명이 있어야 읽히는 것은
  // 짧은 코스에서도 그대로 둔다.
  const step = rawStep && mode !== "full" && rawStep.short
    ? { ...rawStep, ...rawStep.short }
    : rawStep;
  const stepKey = step ? `${at}:${step.id}` : null;
  // 캡쳐는 한 장(shot) 또는 나란히 두 장(shots) — A/B 시나리오처럼 견줘 봐야 하는 화면.
  const shotList = step?.shots?.length ? step.shots : step?.shot ? [step.shot] : [];
  const isShot = shotList.length > 0;
  // full: 이 화면은 통째로 보여준다 — 조명으로 잘라내지 않고, 덮지도 않는다.
  // (나의 우주처럼 화면 전체가 그림인 곳은 반쪽만 밝히면 뭘 보여주는지 알 수 없다.)
  const isFull = Boolean(step?.full);

  const finish = useCallback(() => {
    // 안내가 열어 둔 창은 안내가 닫고 나간다 — 끝냈는데 행성 창이 열린 채로 남으면
    // 사용자가 연 것도 아닌 화면을 자기가 닫아야 한다.
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("pm:tour-act", { detail: "close-panels" }));
    }
    markTourSeen();
    clearWantTour();      // 다시 고르기 전엔 열리지 않는다
    clearTimers();
    setOpen(false);
    setAuto(false);
    setBox(null);
  }, []);

  const next = useCallback(() => {
    setAt((current) => {
      if (current + 1 < steps.length) return current + 1;
      finish();
      return current;
    });
  }, [finish, steps.length]);

  const prev = useCallback(() => setAt((current) => Math.max(0, current - 1)), []);

  // 단계가 바뀌면 그 화면으로 데려간 뒤, 대상이 나타날 때까지 기다린다.
  //
  // route 에 쿼리가 붙을 수 있다("/settings?section=security"). pathname 만 견주면
  // 설정 안에서 칸이 바뀌는 단계들이 영원히 "아직 도착 안 함"으로 남아 멈춘다.
  useEffect(() => {
    if (!step) return undefined;
    // 여기서 box 를 지우지 않는다. 지우면 구멍이 사라져 화면이 한 번 새까매졌다가
    // 새 자리에 툭 나타난다. 이전 구멍을 그대로 두면 새 위치로 **미끄러져 이동**한다.
    setReadyId(null);
    const here = `${pathname}${search || ""}`;
    if (step.route && step.route !== here) { navigate(step.route); return undefined; }

    // 그 화면에 무엇을 열어 두고 설명할지 — 화면 쪽이 pm:tour-act 를 듣고 연다.
    // (예: 행성 창을 실제로 열어 놓고 그 안을 짚는다. 닫힌 화면 위에서 "누르면
    //  열려요" 라고만 말하면 정작 그 안에 뭐가 있는지는 못 보여준다.)
    if (step.act) window.dispatchEvent(new CustomEvent("pm:tour-act", { detail: step.act }));

    // 캡쳐 단계와 전체 화면 단계는 짚을 대상이 없다 — 화면(또는 그림) 자체가 대상이다.
    if (isShot || isFull) { setBox(null); setReadyId(stepKey); return undefined; }

    let waited = 0;
    const find = setInterval(() => {
      const el = findVisible(step.id);
      if (el) {
        clearInterval(find);
        // 스크롤은 즉시. 부드럽게 굴리면 구멍이 스크롤을 뒤에서 쫓아가 출렁인다.
        el.scrollIntoView({ block: "center", behavior: "instant" });
        // 화면이 떠오르는 동안(animate-fade .35s — opacity + translateY 8px) 대상이
        // 계속 움직인다. 그때 조명을 켜면 움직이는 걸 쫓느라 뚝뚝 끊겨 보인다.
        // 다 뜨고 자리가 굳은 뒤에 켠다.
        const settle = setTimeout(() => setReadyId(stepKey), 380);
        timers.current.push(settle);
        return;
      }
      waited += 120;
      // 없는 단계에서 오래 멈춰 있으면 영상에 빈 화면이 그대로 남는다.
      // 1.5초면 화면 전환이 끝나고도 남으니, 그때까지 없으면 조용히 넘긴다.
      if (waited > 1500) {
        clearInterval(find);
        next();
      }
    }, 120);
    timers.current.push(find);
    return () => { clearInterval(find); clearTimers(); };
  }, [stepKey, pathname, search]); // eslint-disable-line react-hooks/exhaustive-deps

  // 대상 위치 추적 — 스크롤·리사이즈에도 구멍이 따라간다.
  useEffect(() => {
    if (!step || isShot || isFull || readyId !== stepKey) return undefined;
    // 매 프레임 다시 잰다. 200ms 간격으로 재면 scrollIntoView 가 부드럽게 움직이는
    // 동안 구멍이 계단처럼 끊겨 따라간다. 값이 그대로면 상태를 안 바꿔 헛렌더를 막는다.
    let raf = 0;
    const measure = () => {
      const el = findVisible(step.id);
      if (el) {
        const r = el.getBoundingClientRect();
        setBox((prev0) =>
          prev0 && prev0.top === r.top && prev0.left === r.left
            && prev0.width === r.width && prev0.height === r.height
            ? prev0
            : { top: r.top, left: r.left, width: r.width, height: r.height });
      }
      raf = requestAnimationFrame(measure);
    };
    raf = requestAnimationFrame(measure);
    return () => cancelAnimationFrame(raf);
  }, [readyId, stepKey, step, isShot, isFull]);

  // 자동 재생 — 대상을 찾아 조명이 앉은 뒤부터 시간을 센다.
  // (화면 전환을 기다리는 동안까지 세면 긴 설명이 반쯤 읽힌 채로 넘어간다.)
  useEffect(() => {
    if (!auto || !step || readyId !== stepKey) return undefined;
    const timer = setTimeout(next, stepDuration(step));
    return () => clearTimeout(timer);
  }, [auto, readyId, stepKey, step, next]);

  // 키보드 — 녹화 중에 마우스를 화면 위에 올리지 않아도 되게.
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (event) => {
      if (event.key === "ArrowRight" || event.key === " " || event.key === "Enter") {
        event.preventDefault(); next();
      } else if (event.key === "ArrowLeft") {
        event.preventDefault(); prev();
      } else if (event.key === "Escape") {
        event.preventDefault(); finish();
      } else if (["f", "c"].includes(event.key.toLowerCase())) {
        // 숨은 전환 — 버튼으로 둘 만큼 자주 쓰는 기능이 아니다(F 전체 · C 핵심만).
        event.preventDefault();
        setMode(event.key.toLowerCase() === "c" ? "core" : "full");
        setAt(0);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, next, prev, finish]);

  // 조명이 보였는지 기록해 둔다 — 다음 렌더에서 '방금 나타났는지'를 알기 위해.
  useEffect(() => { wasVisibleRef.current = Boolean(box); });

  useEffect(() => {
    setSliding(true);
    const timer = setTimeout(() => setSliding(false), 400);
    return () => clearTimeout(timer);
  }, [stepKey]);

  // 말풍선 높이를 따라간다 — 줄 수가 달라 높이가 매번 다르다.
  //
  // 렌더 직후에 한 번만 재면 안 된다. 말풍선에 transition 이 걸려 있어서 그때 재면
  // **애니메이션 중간 높이**가 잡히고, 그 뒤로는 다시 렌더되지 않아 그 값이 그대로
  // 남는다. 캡쳐 단계에서 그림이 말풍선 위로 겹쳐 내려오던 게 이 때문이었다.
  useEffect(() => {
    const el = tipRef.current;
    if (!el || typeof ResizeObserver === "undefined") return undefined;
    const ro = new ResizeObserver(() => {
      const h = el.getBoundingClientRect().height;
      setTipH((current) => (h && Math.abs(h - current) > 2 ? h : current));
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [open]);

  // 렌더 직후에도 한 번 잰다 — ResizeObserver 가 없는 환경(구형 사파리)과,
  // 관찰이 시작되기 전 첫 프레임을 메운다.
  useEffect(() => {
    if (!tipRef.current) return;
    const h = tipRef.current.getBoundingClientRect().height;
    if (h && Math.abs(h - tipH) > 2) setTipH(h);
  });

  if (!open || !step) return null;

  const pad = 8;
  const who = MASCOTS[step.mascot] || MASCOTS.lumi;
  const tint = who.color;
  const W = 420, GAP = 14, M = 16;
  const TIP_H = tipH;

  // ── 말풍선 자리 ────────────────────────────────────────────
  // 규칙은 하나다: **말풍선은 밝은 칸 밖에 둔다.**
  // 겹쳐 놓으면 조명 안의 화면과 설명 글자가 포개져 둘 다 못 읽는다.
  //
  // 아래 → 위 → 오른쪽 → 왼쪽 순으로 들어갈 자리를 찾는다. 네 곳 다 안 되면
  // ('나의 우주'처럼 대상이 화면을 거의 다 덮을 때) 조명 쪽을 줄여 자리를 만든다 —
  // 지도는 조금 덜 보여도 되지만 설명이 겹치면 화면 전체가 어지러워진다.
  const vw = typeof window !== "undefined" ? window.innerWidth : 0;
  const vh = typeof window !== "undefined" ? window.innerHeight : 0;
  let hole = box && {
    top: box.top - pad, left: box.left - pad,
    width: box.width + pad * 2, height: box.height + pad * 2,
  };
  const clampLeft = (value) => Math.max(M, Math.min(vw - W - M, value));
  const clampTop = (value) => Math.max(M, Math.min(vh - TIP_H - M, value));
  // 자리는 **항상 top/left 숫자**로만 잡는다.
  // bottom 이나 transform 을 섞어 쓰면, 단계가 바뀌며 지정 속성이 달라지는 순간
  // 브라우저가 보간할 값을 잃어 말풍선이 튄다(정확히 그 증상이었다).
  let tipStyle = { top: Math.round((vh - TIP_H) / 2), left: Math.round((vw - W) / 2) };
  // 조명에 자리를 양보해야 할 때만 말풍선 키를 묶는다(아래 마지막 분기).
  let tipMaxH = null;

  if (isFull) {
    // 전체 화면 단계 — 화면을 그대로 두고 말풍선만 왼쪽 아래 구석에 놓는다.
    tipMaxH = Math.round(vh * 0.42);
    tipStyle = { top: Math.max(M, vh - Math.min(TIP_H, tipMaxH) - M), left: M };
  } else if (isShot) {
    // 캡쳐 단계 — 그림은 위, 말풍선은 아래 가운데. 자리가 겹치지 않게 고정해 둔다.
    //
    // 말풍선 키를 화면의 34%로 묶는다. 이 단계는 **그림이 본론**인데, 줄이 많은
    // 설명이 그대로 자라면 그림이 손바닥만 해진다(탭 화면이 156px 까지 줄었다).
    // 넘치는 줄은 말풍선 안에서 스크롤된다.
    tipMaxH = Math.round(vh * 0.34);
    tipStyle = {
      top: Math.max(M, vh - Math.min(TIP_H, tipMaxH) - M),
      left: Math.round((vw - W) / 2),
    };
  } else if (hole) {
    const below = vh - (hole.top + hole.height) - GAP - M;
    const above = hole.top - GAP - M;
    const right = vw - (hole.left + hole.width) - GAP - M;
    const left = hole.left - GAP - M;
    const middle = clampTop(hole.top + hole.height / 2 - TIP_H / 2);

    if (below >= TIP_H) {
      tipStyle = { top: hole.top + hole.height + GAP, left: clampLeft(hole.left) };
    } else if (above >= TIP_H) {
      tipStyle = { top: hole.top - GAP - TIP_H, left: clampLeft(hole.left) };
    } else if (right >= W) {
      tipStyle = { top: middle, left: hole.left + hole.width + GAP };
    } else if (left >= W) {
      tipStyle = { top: middle, left: hole.left - GAP - W };
    } else {
      // 어디에도 안 들어간다 → 조명 아래쪽을 잘라 말풍선 자리를 낸다.
      //
      // 이때 말풍선 키를 화면의 42%로 묶는다. 안 묶으면 줄 많은 단계에서 말풍선이
      // 화면의 절반을 먹어 조명이 손바닥만 해진다(우주 지도가 그랬다).
      // 넘치는 줄은 말풍선 안에서 스크롤된다.
      tipMaxH = Math.round(vh * 0.42);
      const tip = Math.min(TIP_H, tipMaxH);
      const height = Math.max(160, vh - tip - GAP - M * 2 - hole.top);
      hole = { ...hole, height: Math.min(hole.height, height) };
      tipStyle = { top: Math.max(M, hole.top + hole.height + GAP), left: clampLeft(hole.left) };
    }
  }

  // 조명이 사라질 때 좌표가 0,0 으로 튀지 않도록 마지막 자리를 들고 있는다.
  if (hole) lastHoleRef.current = hole;
  const lastHole = hole || lastHoleRef.current;
  const justAppeared = Boolean(hole) && !wasVisibleRef.current;

  const chapterAt = TOUR_CHAPTERS.indexOf(step.chapter) + 1;

  return (
    <div className="fixed inset-0 z-[200]" role="dialog" aria-label="사용 안내">
      {/* 덮개와 조명 —
          단계가 바뀔 때마다 덮개를 붙였다 뗐다 하면 그 순간 화면이 번쩍인다.
          그래서 **둘 다 항상 그려 두고 투명도만 바꾼다**. 조명도 마지막 자리를
          기억해 두었다가 그 자리에서 사라져야 튀지 않는다.

          · 전체 화면 단계 : 덮개 0, 조명 0 — 화면을 그대로 보여준다.
          · 캡쳐 단계     : 덮개 1(불투명) — 반투명이면 뒤 글자가 그림 위로 비친다.
          · 그 밖         : 조명이 어둡게 덮고 대상만 뚫는다. 대상을 찾기 전에는
                            덮개로 가려 둔다(빈 구멍이 번쩍이지 않게). */}
      <div
        className="pointer-events-none absolute inset-0 transition-opacity duration-[320ms] ease-out"
        style={{
          background: isShot ? "#02050C" : "rgba(2,5,12,.82)",
          opacity: isFull ? 0 : hole ? 0 : 1,
        }}
      />
      <div
        className="pointer-events-none absolute rounded-[14px] transition-all duration-[360ms] ease-out"
        style={{
          top: lastHole.top, left: lastHole.left,
          width: lastHole.width, height: lastHole.height,
          boxShadow: "0 0 0 9999px rgba(2,5,12,.82)",
          outline: "2px solid rgba(139,108,207,.9)",
          opacity: hole ? 1 : 0,
          // 나타나는 순간에는 자리를 옮기지 않고 밝기만 올린다. 같은 화면에서
          // 자리만 바뀔 때는 그대로 미끄러진다.
          transitionProperty: justAppeared || !sliding
            ? "opacity"
            : "top, left, width, height, opacity",
        }}
      />

      {/* 배경 아무 데나 눌러도 다음으로 */}
      <button onClick={next} className="absolute inset-0 h-full w-full cursor-default" aria-label="다음" />

      {/* 캡쳐 단계 — 미리 찍어 둔 화면을 띄우고 그 위에 설명한다.
          그림이 아직 없으면(파일 미배치·경로 오타) 조용히 다음으로 넘긴다. */}
      {isShot && (
        <div
          className="pointer-events-none absolute inset-x-0 top-0 flex items-center justify-center px-4 pt-4"
          style={{ bottom: tipH + M * 2 }}
        >
          {/* 높이를 확실히 잡아 줘야 한다 — figure 높이가 auto 면 img 의 max-h-full(퍼센트)이
              무시돼 그림이 원본 크기로 늘어나 말풍선을 덮는다. h-full + flex-1 + min-h-0 조합.
              두 장이면 나란히 놓는다 — A/B 시나리오처럼 견줘 봐야 읽히는 화면이 있다. */}
          <figure className="flex h-full min-h-0 w-full flex-col items-center justify-center">
            <div className={`flex min-h-0 w-full flex-1 items-center justify-center ${shotList.length > 1 ? "gap-3" : ""}`}>
              {shotList.map((src) => (
                <img
                  key={src}
                  src={src}
                  alt={step.shotAlt || step.title}
                  onError={next}
                  className="h-full min-h-0 w-auto max-w-full rounded-[18px] border border-white/15 object-contain shadow-[0_28px_80px_rgba(0,0,0,.7)]"
                  style={shotList.length > 1 ? { maxWidth: `calc(50% - 0.375rem)` } : undefined}
                />
              ))}
            </div>
            {step.shotCaption && (
              <figcaption className="mt-2 shrink-0 text-[10px] text-mut">{step.shotCaption}</figcaption>
            )}
          </figure>
        </div>
      )}

      {/* 해설 말풍선 — 그 화면을 맡은 마스코트가 말한다 */}
      <div
        ref={tipRef}
        className="absolute flex max-h-[calc(100dvh-32px)] w-[min(420px,calc(100vw-32px))] flex-col overflow-hidden rounded-[20px] border bg-[#111A2C] shadow-[0_24px_70px_rgba(0,0,0,.62)] transition-all duration-[360ms] ease-out"
        style={{
          ...tipStyle,
          borderColor: `${tint}66`,
          ...(tipMaxH ? { maxHeight: tipMaxH } : {}),
          // 단계가 바뀔 때만 미끄러지고, 추적 중에는 곧바로 따라붙는다.
          transitionProperty: sliding ? "top, left, border-color" : "border-color",
        }}
      >
        {/* 전체 진행 막대 — 44단계짜리라 지금 어디쯤인지 눈으로도 보이게 */}
        <div className="h-[3px] w-full bg-white/[.06]">
          <div
            className="h-full transition-[width] duration-500 ease-out"
            style={{ width: `${((at + 1) / steps.length) * 100}%`, background: tint }}
          />
        </div>

        <div className="flex items-center gap-2.5 px-4 pb-2.5 pt-3">
          <Mascot which={who.key} size={46} />
          <div className="min-w-0 flex-1">
            <p className="text-[9px] font-bold tracking-[.14em]" style={{ color: tint }}>
              {who.tag}
            </p>
            {/* 챕터 이름 — 번호만으로는 지금 어느 장인지 알 수 없다 */}
            <p className="truncate text-[10px] text-mut">
              {chapterAt > 0 ? `${chapterAt}. ` : ""}{step.chapter} · {at + 1} / {steps.length}
            </p>
          </div>
          {/* 자동 재생 — 손으로 넘기는 게 기본이고, 이건 켜고 싶을 때만 켠다. */}
          <button
            onClick={() => setAuto((value) => !value)}
            aria-pressed={auto}
            aria-label={auto ? "자동 넘김 멈추기" : "자동으로 넘기기"}
            title={auto ? "자동 넘김 멈추기" : "자동으로 넘기기"}
            className="tap flex h-8 shrink-0 items-center gap-1 rounded-full border px-2 text-[9.5px] font-bold"
            style={auto
              ? { borderColor: `${tint}88`, background: `${tint}22`, color: tint }
              : { borderColor: "rgba(255,255,255,.12)", color: "#71809A" }}
          >
            {auto ? <Pause size={11} /> : <Play size={11} />}
            자동
          </button>
        </div>

        {/* 내용은 단계마다 새로 올라온다 — 글자가 툭 갈리지 않게.
            줄이 많으면 여기서만 스크롤한다(말풍선이 화면 밖으로 나가지 않게). */}
        <div key={at} className="animate-fade min-h-0 flex-1 overflow-y-auto px-4">
          <h3 className="text-[17px] font-bold leading-snug text-ink">{step.title}</h3>
          <p className="mt-2 text-[13.5px] leading-relaxed text-sub">{step.body}</p>
          {step.lines?.length > 0 && (
            <ul className="mt-2.5 space-y-1.5 border-t border-white/[.07] pt-2.5">
              {step.lines.map((line, i) => (
                <li key={i} className="flex gap-2 text-[12.5px] leading-relaxed text-sub">
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
            <button onClick={prev} className="tap rounded-lg border border-white/[.12] px-3 py-1.5 text-[11px] text-sub">
              이전
            </button>
          )}
          <button
            onClick={next}
            className="tap rounded-lg px-3.5 py-1.5 text-[11px] font-bold text-white"
            style={{ background: tint, color: "#12101B" }}
          >
            {at + 1 < steps.length ? "다음" : "시작하기"}
          </button>
        </div>
      </div>
    </div>
  );
}
