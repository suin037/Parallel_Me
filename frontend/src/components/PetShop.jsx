import { useState } from "react";
import { createPortal } from "react-dom";
import {
  CATALOG, CATS, CAT_LABELS,
  coinsAvailable, owns, buy, toggleEquip, isEquipped, loadShop, consumeSnack,
} from "../data/petShop.js";

// 🛍️ 펫 꾸미기 상점 — 코인으로 배경·소품·가구 구매/장착, 간식은 먹이기(소비형).
export default function PetShop({ onClose, onChange, onFeed }) {
  const [shop, setShop] = useState(() => loadShop());
  const [cat, setCat] = useState("background");
  const [toast, setToast] = useState("");
  const coins = coinsAvailable(shop);

  function refresh(next) {
    setShop({ ...next });
    onChange && onChange();
  }
  function handleBuy(id) {
    const r = buy(id, shop);
    if (r.ok) refresh(r.state);
    else {
      setToast(r.reason);
      setTimeout(() => setToast(""), 1200);
    }
  }
  function handleEquip(id) {
    refresh(toggleEquip(id, shop));
  }
  function handleFeed(id) {
    const r = consumeSnack(id, shop);
    if (r.ok) {
      refresh(r.state);
      onFeed && onFeed(r.bond);
      setToast(`+${r.bond} 친밀도 냠냠`);
      setTimeout(() => setToast(""), 1200);
    } else {
      setToast(r.reason);
      setTimeout(() => setToast(""), 1200);
    }
  }

  const items = CATALOG.filter((it) => it.cat === cat);
  const root = typeof document !== "undefined" && document.getElementById("pm-overlay-root");

  const overlay = (
    <div className="fixed inset-0 z-[120] flex items-end justify-center bg-black/60 p-0 backdrop-blur-[2px] lg:items-center lg:p-6" onClick={onClose}>
      <div
        className="flex max-h-[88%] w-full flex-col overflow-hidden rounded-t-[24px] border-t border-white/10 bg-[#0F1826] lg:max-h-[84%] lg:w-[460px] lg:rounded-[24px] lg:border"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 헤더 */}
        <div className="flex items-center justify-between border-b border-white/8 px-5 py-3.5">
          <div className="text-[15px] font-bold text-ink">🛍️ 꾸미기 상점</div>
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1 rounded-full bg-[#F5C84620] px-2.5 py-1 text-[12px] font-bold text-[#F5C846]">
              🪙 {coins}
            </span>
            <button onClick={onClose} className="tap text-[18px] leading-none text-mut">✕</button>
          </div>
        </div>

        {/* 카테고리 탭 */}
        <div className="flex gap-1.5 px-4 pt-3">
          {CATS.map((c) => (
            <button
              key={c}
              onClick={() => setCat(c)}
              className={`tap flex-1 rounded-full py-1.5 text-[12px] font-semibold transition ${
                cat === c ? "bg-white/12 text-ink" : "text-mut hover:text-ink"
              }`}
            >
              {CAT_LABELS[c]}
            </button>
          ))}
        </div>

        {/* 아이템 그리드 */}
        <div className="grid max-h-[58vh] grid-cols-2 gap-2.5 overflow-y-auto p-4">
          {items.map((it) => {
            const owned = owns(it.id, shop);
            const equipped = isEquipped(it.id, shop);
            const canBuy = coins >= it.price;
            return (
              <div key={it.id} className="rounded-[16px] border border-white/8 bg-[#131F30] p-2.5">
                {/* 미리보기 */}
                <div className="mb-2 flex h-16 items-center justify-center overflow-hidden rounded-[12px] bg-black/20">
                  {it.cat === "background" ? (
                    <div className="h-full w-full" style={{ background: it.render }} />
                  ) : (
                    <span className="text-[30px]">{it.render}</span>
                  )}
                </div>
                <div className="mb-1.5 truncate text-[12px] font-semibold text-ink">{it.name}</div>

                {/* 액션 */}
                {it.cat === "snack" ? (
                  <button
                    onClick={() => handleFeed(it.id)}
                    disabled={!canBuy}
                    className="tap w-full rounded-lg bg-[#F5C846] py-1.5 text-[11.5px] font-bold text-[#3a2c05] disabled:opacity-40"
                  >
                    🪙 {it.price} 먹이기 <span className="opacity-70">+{it.bond}</span>
                  </button>
                ) : !owned ? (
                  <button
                    onClick={() => handleBuy(it.id)}
                    disabled={!canBuy}
                    className="tap w-full rounded-lg bg-[#F5C846] py-1.5 text-[11.5px] font-bold text-[#3a2c05] disabled:opacity-40"
                  >
                    🪙 {it.price} 구매
                  </button>
                ) : (
                  <button
                    onClick={() => handleEquip(it.id)}
                    className={`tap w-full rounded-lg py-1.5 text-[11.5px] font-bold ${
                      equipped ? "bg-cyan/25 text-cyan" : "bg-white/10 text-ink"
                    }`}
                  >
                    {equipped ? "장착중 ✓" : "장착"}
                  </button>
                )}
              </div>
            );
          })}
        </div>

        <p className="px-5 pb-4 text-[10px] leading-relaxed text-mut">
          코인은 기록·돌봄으로 쌓은 XP에서 자동 적립돼요 (100 XP당 1코인). 소품은 나중에 손그림으로 업그레이드 예정.
        </p>

        {toast && (
          <div className="pointer-events-none absolute bottom-6 left-1/2 -translate-x-1/2 rounded-full bg-black/80 px-4 py-2 text-[12px] font-semibold text-white">
            {toast}
          </div>
        )}
      </div>
    </div>
  );

  return root ? createPortal(overlay, root) : overlay;
}
