import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import PetCreature from "./PetCreature.jsx";
import PetHearts from "./PetHearts.jsx";
import { careNeed, loadPet } from "../data/petCare.js";

// ─────────────────────────────────────────────────────────────
// 돌보미 미리보기 — 일기 화면 맨 위에서 지금 기분대로 서성인다.
//
// 돌보미는 설정 안에 있어서, 들어가 보지 않으면 얘가 어떤 상태인지 알 수가 없다.
// 그래서 매일 오는 화면(일기) 맨 위에 작게 띄운다. 간식도 쓰다듬기도 못 받으면
// 시무룩한 얼굴로 이쪽을 보고 있게 — 말로 조르지 않아도 눈에 띄게.
//
// 조르는 말은 한 번에 하나만 (careNeed 가 급한 것 하나를 고른다).
// 여러 개를 동시에 띄우면 잔소리로 읽힌다.
//
// 움직임은 아주 작게. 일기 쓰는 화면이라 시선을 뺏으면 안 된다.
// prefers-reduced-motion 이면 멈춘다.
// ─────────────────────────────────────────────────────────────
const CSS = `
@keyframes petpeek-walk {
  0%,100% { transform: translateX(-5px) }
  50%     { transform: translateX(5px) }
}
@keyframes petpeek-bob {
  0%,100% { transform: translateY(0) }
  50%     { transform: translateY(-3px) }
}
.petpeek-walk { animation: petpeek-walk 5.5s ease-in-out infinite }
.petpeek-bob  { animation: petpeek-bob 2.6s ease-in-out infinite }
/* 시무룩할 땐 돌아다니지 않는다 — 가만히 이쪽을 본다 */
.petpeek-sad .petpeek-walk { animation: none }
.petpeek-sad .petpeek-bob  { animation-duration: 4.2s }
@media (prefers-reduced-motion: reduce) {
  .petpeek-walk, .petpeek-bob { animation: none }
}
`;

export default function PetPeek({ size = 62 }) {
  const navigate = useNavigate();
  const [pet, setPet] = useState(loadPet);

  useEffect(() => {
    const refresh = () => setPet(loadPet());
    // 기록하면 간식이 생기고, 상점에서 꾸미면 모습이 바뀐다 — 둘 다 따라간다.
    window.addEventListener("pm:universe", refresh);
    window.addEventListener("pm:pet-shop", refresh);
    return () => {
      window.removeEventListener("pm:universe", refresh);
      window.removeEventListener("pm:pet-shop", refresh);
    };
  }, []);

  // 설정 첫 화면이 아니라 '개인화' 칸으로 — 거기 맨 위가 생활 관리 친구다.
  const openCare = () => navigate("/settings?section=personalize");

  const { mood, need, happiness } = careNeed(pet);
  const sad = mood === "시무룩";
  const glad = mood === "기쁨";

  return (
    <button
      type="button"
      onClick={openCare}
      aria-label={`돌보미 친구 · 기분 ${mood}${need ? ` · ${need.line}` : ""}`}
      className={`tap group relative flex shrink-0 items-end gap-2 rounded-[18px] px-1.5 py-1 transition-colors hover:bg-white/[.04] ${sad ? "petpeek-sad" : ""}`}
    >
      <style>{CSS}</style>

      {/* 조르는 말 — 필요할 때만 */}
      {need && (
        <span className="mb-3 hidden max-w-[150px] rounded-full border border-white/[.1] bg-[#0D1727] px-2.5 py-1 text-[9.5px] leading-tight text-sub shadow-[0_6px_20px_rgba(0,0,0,.4)] sm:block">
          {need.line}
        </span>
      )}

      <span className="relative block">
        {/* 기쁠 때 하트 — 설정의 돌보미 카드와 같은 모션을 쓴다 */}
        <PetHearts on={glad} size={size} />

        <span className="petpeek-walk block">
          <span className="petpeek-bob block">
            <PetCreature size={size} variant={pet.which} mood={mood} expr="idle" />
          </span>
        </span>
      </span>

      {/* 기분 막대 — 얼마나 시무룩한지 눈으로 보이게 */}
      <span className="absolute inset-x-1.5 bottom-0 h-[3px] overflow-hidden rounded-full bg-white/[.08]">
        <span
          className="block h-full rounded-full transition-[width] duration-500"
          style={{
            width: `${happiness}%`,
            background: sad ? "#7C8AA5" : happiness >= 66 ? "#8B6CCF" : "#C9A227",
          }}
        />
      </span>
    </button>
  );
}
