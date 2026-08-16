import { useEffect, useMemo, useState } from "react";
import Mascot from "./Mascot.jsx";
import { X } from "lucide-react";
import PetCreature from "./PetCreature.jsx";
import PetHearts from "./PetHearts.jsx";
import storage from "../data/safeStorage.js";

// 닫은 제안을 기억하는 자리 — 값은 그 갈림길의 서명이다.
const NUDGE_OFF = "pm.nudge.off.v1";
import { loadShop, equippedItem } from "../data/petShop.js";
import { loadPet, claimDaily, petMascot, feedMascot, setWhich, moodOf, canPatToday, currentHappiness } from "../data/petCare.js";
import { hasCheckedInToday } from "../data/myUniverse.js";
import { guideNudge, GUIDE_DOMAIN } from "../data/diarySignals.js";

// 🧸 마스코트 육성(가벼운 버전) — 쓰다듬기(말랑 튕김) + 간식으로 친밀도 키우기.
// 3D 느낌은 CSS 소프트 그라디언트·그림자·squash/stretch로 '말랑말랑'하게.
const GUIDES = [
  { key: "nova", name: "노바", color: "#FF9EC0", glow: "rgba(255,158,192,.45)" },
  { key: "cosmo", name: "코스모", color: "#8B6CCF", glow: "rgba(124,195,255,.45)" },
  { key: "lumi", name: "루미", color: "#FFD97A", glow: "rgba(255,217,122,.45)" },
];

export default function PetMascot({ onCompare }) {
  const [pet, setPet] = useState(() => claimDaily(loadPet()));
  // 상점에서 산 배경·소품 — 사거나 장착하면 바로 반영되게 이벤트를 듣는다.
  const [shop, setShop] = useState(loadShop);
  useEffect(() => {
    const refresh = () => setShop(loadShop());
    window.addEventListener("pm:pet-shop", refresh);
    return () => window.removeEventListener("pm:pet-shop", refresh);
  }, []);
  const bgItem = equippedItem("background", shop);
  const accItem = equippedItem("accessory", shop);
  const [squish, setSquish] = useState(0); // 탭할 때마다 +1 → 애니 리트리거
  const [hearts, setHearts] = useState([]);
  const [eating, setEating] = useState(false);
  const [crumbs, setCrumbs] = useState([]); // 와구와구 부스러기
  const [expr, setExpr] = useState("idle"); // 리액션 표정(^ᴗ^)
  const [nonce, setNonce] = useState(0); // 하트 id용(랜덤 대신)

  // 상호작용하면 잠깐 웃는 표정(^ᴗ^)으로.
  function react(ms = 1400) {
    setExpr("happy");
    setTimeout(() => setExpr("idle"), ms);
  }

  // 기록하면 간식 지급(하루 1회) — 화면 갱신 이벤트에 반응.
  useEffect(() => {
    const h = () => setPet((p) => claimDaily(p));
    window.addEventListener("pm:universe", h);
    return () => window.removeEventListener("pm:universe", h);
  }, []);

  const guide = GUIDES.find((g) => g.key === pet.which) || GUIDES[1];
  // 넛지는 고른 돌보미의 영역에서 뽑는다 — 노바=일상 / 코스모=진로 / 루미=몸과 마음.
  // 전에는 셋 다 이직 신호만 봐서 누구를 골라도 같은 말을 했다.
  const nudge = useMemo(
    () => guideNudge(GUIDE_DOMAIN[pet.which] || "career", { windowDays: 28, threshold: 4 }),
    [pet.which],
  );
  // 저장값이 아니라 '방치한 날만큼 깎은' 값으로 본다.
  // 일기 화면 미리보기와 같은 계산을 써야 두 곳의 기분이 어긋나지 않는다.
  const [nudgeOff, setNudgeOff] = useState(() => storage.getItem(NUDGE_OFF) || "");
  const happinessNow = currentHappiness(pet);
  const mood = moodOf(happinessNow);
  const pattedToday = !canPatToday(pet);
  const checkedIn = hasCheckedInToday();
  // 신호가 없을 때도 돌보미마다 자기 영역의 말을 한다 — 셋이 같은 말을 하면
  // 굳이 나눠 둔 의미가 없다.
  const IDLE = {
    nova: {
      done: "오늘도 남겼네요. 며칠 쌓이면 내 하루의 리듬이 보여요.",
      todo: "오늘 하루는 어땠어요? 한 줄만 적어도 리듬이 잡혀요.",
    },
    cosmo: {
      done: "오늘 상태는 기록했어요. 무리해서 결정하지 말고, 떠오른 갈림길을 한 줄로 남겨두세요.",
      todo: "아직 오늘 상태를 모르겠어요. 30초 체크인을 하면 오늘에 맞는 다음 행동을 같이 정해볼게요.",
    },
    lumi: {
      done: "오늘 몸 상태도 남겨줘서 고마워요. 잠·피로가 쌓이면 흐름이 보여요.",
      todo: "요즘 몸은 좀 어때요? 잠이나 피로만 적어둬도 신호가 보여요.",
    },
  };
  const idle = IDLE[pet.which] || IDLE.cosmo;

  function dismissNudge() {
    storage.setItem(NUDGE_OFF, nudgeSig);
    setNudgeOff(nudgeSig);
  }

  // 닫은 제안은 다시 꺼내지 않는다.
  //
  // 같은 갈림길을 계속 들이밀면 조언이 아니라 잔소리가 된다. 그래서 '이 갈림길'
  // 단위로 기억한다 — 다른 고민이 새로 보이면 그건 다른 제안이라 다시 뜬다.
  // (날짜 기준으로 접으면 내일 같은 말을 또 하게 된다.)
  const nudgeSig = nudge.prompt
    ? `${nudge.label || ""}|${nudge.choiceA || ""}|${nudge.choiceB || ""}`
    : "";
  const showNudge = Boolean(nudge.prompt && onCompare && nudgeSig && nudgeOff !== nudgeSig);

  const guideMessage = showNudge
    ? `최근 ${nudge.windowDays}일 동안 ${nudge.label}${nudge.particle} ${nudge.count}일 나타났어요. 기록만 하기보다 두 선택을 비교해볼까요?`
    : checkedIn ? idle.done : idle.todo;

  // 동물을 직접 누르면: 토닥토닥 모션만(친밀도 변화 없음).
  function tapOnly() {
    setSquish((s) => s + 1);
    react();
    const id = nonce;
    setNonce((n) => n + 1);
    const dx = (id % 3) * 14 - 14; // -14/0/14 번갈아
    setHearts((hs) => [...hs, { id, dx }]);
    setTimeout(() => setHearts((hs) => hs.filter((x) => x.id !== id)), 900);
  }

  // 쓰다듬기 버튼: 하루 1회, 친밀도 +랜덤(1~10).
  function pat() {
    if (pattedToday) return;
    const np = petMascot(pet);
    const gained = np.bond - pet.bond;
    setPet(np);
    setSquish((s) => s + 1);
    react();
    const id = nonce;
    setNonce((n) => n + 1);
    setHearts((hs) => [...hs, { id, dx: 0, label: `+${gained}` }]);
    setTimeout(() => setHearts((hs) => hs.filter((x) => x.id !== id)), 1000);
  }
  function feed() {
    if (pet.snacks <= 0 || eating) return;
    setPet((p) => feedMascot(p));
    setEating(true);
    react(1400);
    // 와구와구 — 씹을 때마다 부스러기가 입가에서 튄다(4번 베어물기).
    let bite = 0;
    const chomp = setInterval(() => {
      bite += 1;
      const base = nonce + bite * 100;
      setNonce((n) => n + 1);
      const batch = [0, 1, 2].map((k) => {
        const seed = base * 3 + k;
        return {
          id: seed,
          cx: ((seed % 9) - 4) * 6, // -24~24 좌우로 튀기
          cy: 14 + ((seed % 4) * 5), // 아래로 떨어짐
          s: 0.55 + (seed % 3) * 0.22,
          c: seed % 2 ? "#E9B872" : "#C08535",
        };
      });
      setCrumbs((cs) => [...cs, ...batch]);
      setTimeout(() => setCrumbs((cs) => cs.filter((x) => !batch.some((b) => b.id === x.id))), 620);
      if (bite >= 4) clearInterval(chomp);
    }, 230);
    // 다 먹으면 만족 튕김 + 하트
    setTimeout(() => {
      setEating(false);
      setSquish((s) => s + 1);
      const id = nonce + 999;
      setHearts((hs) => [...hs, { id, dx: 0 }]);
      setTimeout(() => setHearts((hs) => hs.filter((x) => x.id !== id)), 900);
    }, 1150);
  }

  return (
    <div className="mb-2 mt-3 overflow-hidden rounded-[22px] border border-white/10 bg-[#101A2A]/70 p-4 backdrop-blur">
      <style>{`
        @keyframes pm-bob { 0%,100%{ transform: translateY(0) } 50%{ transform: translateY(-6px) } }
        @keyframes pm-squish {
          0%{ transform: scale(1,1) } 28%{ transform: scale(1.18,0.82) }
          55%{ transform: scale(0.9,1.12) } 76%{ transform: scale(1.06,0.95) } 100%{ transform: scale(1,1) }
        }
        @keyframes pm-heart { 0%{ transform: translateY(0) scale(.6); opacity:0 } 25%{ opacity:1 } 100%{ transform: translateY(-44px) scale(1.1); opacity:0 } }
        @keyframes pm-chomp { 0%,100%{ transform: scale(1,1) } 50%{ transform: scale(1.07,0.9) } }
        @keyframes pm-blink { 0%,90%,100%{ transform: scaleY(1) } 94%{ transform: scaleY(0.08) } }
        @keyframes pm-cookie-eat {
          0%   { transform: translate(30px,-14px) rotate(-10deg) scale(1); opacity:0 }
          12%  { transform: translate(4px,-2px) rotate(-4deg) scale(1); opacity:1 }
          26%  { transform: translate(2px,0) scale(.82) }
          31%  { transform: translate(2px,0) scale(.62) }
          50%  { transform: translate(1px,1px) scale(.58) }
          55%  { transform: translate(1px,1px) scale(.4) }
          74%  { transform: translate(0,2px) scale(.36) }
          79%  { transform: translate(0,2px) scale(.18) }
          100% { transform: translate(0,3px) scale(0); opacity:0 }
        }
        @keyframes pm-crumb { 0%{ transform: translate(0,0) scale(1); opacity:1 } 100%{ transform: translate(var(--cx), var(--cy)) scale(.3); opacity:0 } }
      `}</style>

      <div className="flex items-center justify-between">
        <div>
          <div className="text-[13px] font-bold text-ink">내 생활 관리 친구</div>
          <div className="mt-0.5 text-[9.5px] text-mut">기록을 살피고 다음 행동을 알려줘요</div>
        </div>
        <div className="flex items-center gap-1">
          <span className="mr-1 text-[9.5px] text-mut">돌보미</span>
          {GUIDES.map((g) => (
            <button
              key={g.key}
              onClick={() => setPet((p) => ({ ...setWhich(g.key, p) }))}
              aria-label={`${g.name}가 돌보기`}
              className={`tap flex h-7 w-7 items-center justify-center rounded-full border transition ${pet.which === g.key ? "border-white/40 bg-white/10" : "border-transparent opacity-45"}`}
            >
              <Mascot which={g.key} size={20} />
            </button>
          ))}
        </div>
      </div>

      {/* 말풍선 — 폭이 카드 전체(374px)라 98px 캐릭터의 말로 보이지 않았다.
          캐릭터 무대(220px)에 가깝게 좁히고 가운데 정렬하고, 아래로 꼬리를 달아
          누가 하는 말인지 모양으로 드러낸다. */}
      <div className="relative mx-auto mt-3 max-w-[268px] rounded-2xl border border-white/10 bg-[#0B1423]/80 px-3.5 py-2.5 text-center text-[11px] leading-relaxed text-sub">
        <span className="mr-1 font-bold" style={{ color: guide.color }}>{guide.name}</span>
        {guideMessage}
        {showNudge && (
          <>
            {/* 닫기 — 지금 이 갈림길은 됐다는 뜻. 다른 고민이 보이면 그때 다시 뜬다. */}
            <button
              type="button"
              onClick={dismissNudge}
              aria-label="이 제안 닫기"
              className="tap absolute right-1 top-1 flex h-6 w-6 items-center justify-center rounded-full text-mut hover:bg-white/[.08] hover:text-sub"
            >
              <X size={13} />
            </button>
            <button type="button" onClick={() => onCompare(nudge)} className="tap mt-2 block w-full rounded-xl border border-cyan/35 bg-cyan/10 py-2 text-[11px] font-bold text-cyan">
              {nudge.choiceA} vs {nudge.choiceB} 비교하기
            </button>
          </>
        )}
        {/* 꼬리 — 아래 두 변만 남긴 정사각형을 돌려 말풍선에서 뻗어 나온 것처럼 */}
        <span className="absolute bottom-[-6px] left-1/2 h-3 w-3 -translate-x-1/2 rotate-45 border-b border-r border-white/10 bg-[#0B1423]" />
      </div>

      {/* 무대 — 말랑한 마스코트 */}
      <div className="relative mx-auto mt-2 flex h-[118px] w-full max-w-[220px] items-end justify-center">
        {/* 상점 배경 — 후광보다 뒤에 깔린다 */}
        {bgItem && <div className="pointer-events-none absolute inset-0 rounded-[18px]" style={{ background: bgItem.render }} />}
        {/* 배경 후광 */}
        <div className="pointer-events-none absolute inset-0" style={{ background: `radial-gradient(circle at 50% 44%, ${guide.glow}, transparent 62%)` }} />
        {/* 바닥 그림자 */}
        <div className="absolute bottom-3 h-3 w-24 rounded-[50%] bg-black/40 blur-md" />
        {/* 하트 */}
        {hearts.map((h) => (
          <span key={h.id} className="pointer-events-none absolute bottom-[96px] whitespace-nowrap text-[18px]" style={{ left: `calc(50% + ${h.dx}px)`, transform: "translateX(-50%)", animation: "pm-heart .9s ease-out forwards" }}>
            {h.label ? <span className="text-[13px] font-bold text-[#FFC6DC]">{h.label} 💗</span> : "💗"}
          </span>
        ))}
        {/* 마스코트 (아이들 bob + 탭 squish) */}
        <button
          onClick={tapOnly}
          aria-label={`${guide.name} 토닥토닥`}
          className="tap relative mb-4 select-none"
          style={{
            animation: eating ? "pm-chomp .23s ease-in-out infinite" : "pm-bob 2.6s ease-in-out infinite",
            transformOrigin: "50% 100%",
            filter: mood === "시무룩" ? "grayscale(.35) brightness(.9)" : "none",
          }}
        >
          <div key={squish} style={{ animation: "pm-squish .5s cubic-bezier(.34,1.56,.64,1)", transformOrigin: "50% 100%" }}>
            {/* 젤리 광택 */}
            <div className="relative">
              {/* 기쁠 때 하트 — 일기 화면의 미리보기와 같은 모션을 쓴다(같은 친구다) */}
              <PetHearts on={mood === "기쁨"} size={98} />
              <PetCreature size={98} variant={guide.key} mood={mood} expr={expr} />
              <div className="pointer-events-none absolute left-[24%] top-[24%] h-8 w-8 rounded-full bg-white/45 blur-[7px]" />
              {/* 장착 소품 — 원본 좌표는 size 124 기준이라 우리 크기(98)에 맞춰 비율로 줄인다 */}
              {accItem && (
                <span
                  className="pointer-events-none absolute"
                  style={{
                    top: `${(accItem.pos?.top ?? 2) * (98 / 124)}px`,
                    left: accItem.pos?.left ?? "50%",
                    transform: `translateX(-50%)${accItem.pos?.rotate ? ` rotate(${accItem.pos.rotate}deg)` : ""}`,
                    fontSize: `${(accItem.pos?.size ?? 24) * (98 / 124)}px`,
                    lineHeight: 1,
                  }}
                >
                  {accItem.render}
                </span>
              )}
              {/* 입가로 날아와 와구와구 사라지는 쿠키 */}
              {eating && (
                <span
                  key={squish + "-cookie"}
                  className="pointer-events-none absolute left-1/2 top-[62%] -translate-x-1/2 text-[17px]"
                  style={{ animation: "pm-cookie-eat 1.15s ease-in-out forwards" }}
                >
                  🍪
                </span>
              )}
              {/* 튀는 부스러기 */}
              {crumbs.map((c) => (
                <span
                  key={c.id}
                  className="pointer-events-none absolute left-1/2 top-[64%] block rounded-[1px]"
                  style={{
                    width: 3, height: 3, background: c.c,
                    "--cx": `${c.cx}px`, "--cy": `${c.cy}px`,
                    transform: `scale(${c.s})`,
                    animation: "pm-crumb .6s ease-out forwards",
                  }}
                />
              ))}
            </div>
          </div>
        </button>
      </div>

      {/* 상태 + 액션 */}
      <div className="mt-1 flex items-center gap-2 text-[11px]">
        <span className="text-mut">기분</span>
        <span className="font-semibold" style={{ color: mood === "기쁨" ? "#5DCAA5" : mood === "시무룩" ? "#F0A0A0" : "#8B6CCF" }}>
          {mood === "기쁨" ? "😊 기쁨" : mood === "시무룩" ? "🥺 시무룩" : "🙂 보통"}
        </span>
      </div>
      <div className="mt-1.5 flex items-center gap-2">
        <span className="w-[38px] shrink-0 text-[10px] text-mut">친밀도</span>
        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-[#223047]">
          <div className="h-full rounded-full transition-[width] duration-300" style={{ width: `${pet.bond}%`, background: `linear-gradient(90deg, ${guide.color}, #fff6)` }} />
        </div>
        <span className="w-[30px] shrink-0 text-right text-[10px] tabular-nums text-mut">{pet.bond}</span>
      </div>

      <div className="mt-3 flex gap-2">
        <button
          onClick={pat}
          disabled={pattedToday}
          className="tap flex-1 rounded-xl border border-white/12 bg-white/5 py-2 text-[12px] font-semibold text-ink disabled:opacity-45"
        >
          {pattedToday ? "☑ 오늘 쓰다듬기 완료" : "✋ 쓰다듬기"}
        </button>
        <button
          onClick={feed}
          disabled={pet.snacks <= 0 || eating}
          className="tap flex-1 rounded-xl py-2 text-[12px] font-semibold text-[#04203a] disabled:opacity-40"
          style={{ background: `linear-gradient(90deg, ${guide.color}, #ffffffcc)` }}
        >
          🍪 간식 주기 ({pet.snacks})
        </button>
      </div>
      <p className="mt-2 text-[9.5px] leading-relaxed text-mut">친밀도와 캐릭터 기분은 게임 보상이며 예측 점수에는 반영되지 않아요.</p>
    </div>
  );
}
