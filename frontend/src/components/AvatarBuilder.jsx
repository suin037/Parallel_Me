import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import Avatar from "./Avatar.jsx";
import {
  BEARD,
  BROW_SHAPE_ITEMS,
  BROW_THICKNESS,
  CLOTHES,
  CLOTHES_COLORS,
  EYES,
  GLASSES_OPTIONS,
  HAIR_COLORS,
  HAIR_STYLES,
  MOUTH,
  SKIN_COLORS,
  TOONHEAD_CREDIT,
  normalizeAvatar,
  randomToonHead,
} from "../data/avatarOptions.js";
import { FACE_SHAPES } from "../data/customParts.js";
import AvatarFromPhoto from "./AvatarFromPhoto.jsx";

// 탭(기본/헤어/얼굴/스타일)으로 묶고, 각 항목은 화살표로 넘긴다.
// 가운데에는 그 선택을 적용한 아바타를 실제로 그려 보여준다 — 이름만으로는
// '옆가르마'와 '언더컷' 같은 것들이 구분되지 않는다.

const NONE = (label = "없음") => ({ id: null, label });
// 성별은 지금 속눈썹 하나만 좌우한다. 그래서 따로 저장하지 않고 lashes 를 그대로 쓴다 —
// 값이 하나뿐이라 '성별은 남자인데 속눈썹은 켜짐' 같은 어긋남이 생길 수 없다.
// 빌트인 눈에는 속눈썹이 늘 붙어 있어서, 끄지 않으면 남자 아바타가 여성적으로 보인다.
const GENDER = [
  { id: true, label: "여자" },
  { id: false, label: "남자" },
];
const FACE_ITEMS = Object.entries(FACE_SHAPES).map(([id, v]) => ({ id, label: v.label }));
const CATEGORIES = [
  ["base", "기본"],
  ["hair", "헤어"],
  ["face", "얼굴"],
  ["style", "스타일"],
];

function Arrow({ dir, onClick, label }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={`${label} ${dir < 0 ? "이전" : "다음"}`}
      className="tap flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-violet-400/25 bg-violet-500/10 text-[16px] text-violet-300 transition-transform active:scale-90"
    >
      {dir < 0 ? "‹" : "›"}
    </button>
  );
}

/**
 * 한 줄짜리 선택기. 끝에서 반대편으로 순환한다.
 * field 를 주면 그 값만 바꾼 아바타를 가운데에 미리 그린다.
 * (색은 화살표로 넘기기 부적합해서 ColorRow 가 따로 맡는다)
 */
function Stepper({ label, items, value, onPick, field, config }) {
  const found = items.findIndex((i) => i.id === value);
  const at = found < 0 ? 0 : found;
  const cur = items[at];
  const go = (d) => onPick(items[(at + d + items.length) % items.length].id);

  return (
    <div className="mt-2.5">
      <div className="mb-1.5 text-[11px] font-semibold text-sub">{label}</div>
      <div className="flex items-center gap-2 rounded-2xl border border-white/[.07] bg-[#0B1423] px-2.5 py-2">
        <Arrow dir={-1} onClick={() => go(-1)} label={label} />
        <div className="flex min-w-0 flex-1 items-center justify-center gap-2.5">
          <span className="flex h-14 w-14 shrink-0 items-center justify-center overflow-hidden rounded-xl bg-white/[.035]">
            <Avatar config={{ ...config, [field]: cur.id }} size={54} ring={false} />
          </span>
          <div className="min-w-0">
            <div
              className={`truncate text-[12px] font-medium ${
                cur.id == null ? "text-mut" : "text-ink"
              }`}
            >
              {cur.label}
            </div>
            <div className="text-[9px] text-mut">
              {at + 1} / {items.length}
            </div>
          </div>
        </div>
        <Arrow dir={1} onClick={() => go(1)} label={label} />
      </div>
    </div>
  );
}

/**
 * 색 선택. 화살표로 한 칸씩 넘기면 원하는 색까지 몇 번을 눌러야 하고,
 * 프리셋에 없는 색(카메라가 뽑아온 실제 머리색 등)은 아예 고를 수가 없었다.
 * 그래서 프리셋을 전부 펼쳐 보여주고, 옆에 색상표를 열 수 있게 둔다.
 */
function ColorRow({ label, colors, value, onPick }) {
  const isCustom = value && !colors.includes(value);
  return (
    <div className="mt-2.5">
      <div className="mb-1.5 flex items-center justify-between">
        <span className="text-[11px] font-semibold text-sub">{label}</span>
        <label className="tap flex cursor-pointer items-center gap-1.5 text-[10px] font-semibold text-violet-300">
          색상표
          <input
            type="color"
            value={"#" + value}
            onChange={(e) => onPick(e.target.value.slice(1).toLowerCase())}
            aria-label={`${label} 직접 고르기`}
            className="h-6 w-6 cursor-pointer rounded-md border border-white/15 bg-transparent p-0"
          />
        </label>
      </div>
      <div className="flex flex-wrap gap-2 rounded-2xl border border-white/[.07] bg-[#0B1423] px-2.5 py-2.5">
        {colors.map((hex) => (
          <button
            key={hex}
            type="button"
            onClick={() => onPick(hex)}
            aria-label={`#${hex}`}
            aria-pressed={value === hex}
            className={`tap h-8 w-8 rounded-full transition ${
              value === hex
                ? "ring-2 ring-violet-300 ring-offset-2 ring-offset-[#0B1423]"
                : "border border-black/25"
            }`}
            style={{ background: "#" + hex }}
          />
        ))}
        {/* 프리셋에 없는 색(직접 고름·사진에서 뽑음)도 자리를 만들어 보여준다 */}
        {isCustom && (
          <span
            title="직접 고른 색"
            className="tap h-8 w-8 rounded-full ring-2 ring-violet-300 ring-offset-2 ring-offset-[#0B1423]"
            style={{ background: "#" + value }}
          />
        )}
      </div>
    </div>
  );
}

export default function AvatarBuilder({ config, onChange }) {
  const avatar = normalizeAvatar(config);
  const [category, setCategory] = useState("base");
  const [camera, setCamera] = useState(false);
  const set = (patch) => onChange({ ...avatar, ...patch });

  useEffect(() => {
    if (!camera) return undefined;
    const closeOnEscape = (event) => {
      if (event.key === "Escape") setCamera(false);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [camera]);

  // 미리보기용 config — 항목별 차이가 잘 보이도록 가리는 요소(안경·수염)를 걷어낸다.
  const bare = { ...avatar, glasses: "none", beard: null };

  return (
    <div className="overflow-hidden rounded-[22px] border border-white/[.07] bg-[#091321]/75 p-3.5 sm:p-4">
      <div className="grid gap-4 sm:grid-cols-[160px_minmax(0,1fr)] sm:items-start">
        <div className="flex flex-col items-center rounded-[18px] border border-white/[.06] bg-[radial-gradient(circle_at_50%_35%,rgba(139,108,207,.2),transparent_58%),rgba(0,0,0,.12)] p-4 sm:sticky sm:top-3">
          <Avatar config={avatar} size={132} />
          <strong className="mt-2 text-[12px]">나의 아바타</strong>
          <button
            type="button"
            onClick={() => onChange(randomToonHead())}
            className="tap mt-2 rounded-full border border-violet-400/25 bg-violet-500/10 px-3 py-1.5 text-[10px] font-semibold text-violet-300"
          >
            🎲 다른 조합 보기
          </button>
          <button
            type="button"
            onClick={() => setCamera((v) => !v)}
            className="tap mt-1.5 rounded-full border border-white/10 bg-white/[.04] px-3 py-1.5 text-[10px] font-semibold text-sub"
          >
            📷 카메라로 맞추기
          </button>
        </div>

        <div className="min-w-0">
          <div className="grid grid-cols-4 gap-1 rounded-xl bg-black/20 p-1">
            {CATEGORIES.map(([key, label]) => (
              <button
                key={key}
                type="button"
                onClick={() => setCategory(key)}
                className={`tap rounded-lg py-2 text-[10px] font-semibold transition-colors ${
                  category === key ? "bg-violet-500/25 text-violet-200" : "text-mut hover:text-sub"
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          {category === "base" && (
            <>
              <Stepper
                label="성별"
                items={GENDER}
                value={avatar.lashes !== false}
                field="lashes"
                config={bare}
                onPick={(v) => set({ lashes: v })}
              />
              <Stepper
                label="얼굴형"
                items={FACE_ITEMS}
                value={avatar.face}
                field="face"
                config={bare}
                onPick={(v) => set({ face: v })}
              />
              <ColorRow
                label="피부색"
                colors={SKIN_COLORS}
                value={avatar.skinColor}
                onPick={(v) => set({ skinColor: v })}
              />
            </>
          )}

          {category === "hair" && (
            <>
              <Stepper
                label="헤어스타일"
                items={HAIR_STYLES}
                value={avatar.hairStyle}
                field="hairStyle"
                config={bare}
                onPick={(v) => set({ hairStyle: v })}
              />
              <ColorRow
                label="헤어 컬러"
                colors={HAIR_COLORS}
                value={avatar.hairColor}
                onPick={(v) => set({ hairColor: v })}
              />
            </>
          )}

          {category === "face" && (
            <>
              <Stepper
                label="눈"
                items={EYES}
                value={avatar.eyes}
                field="eyes"
                config={bare}
                onPick={(v) => set({ eyes: v })}
              />
              <Stepper
                label="눈썹 모양"
                items={BROW_SHAPE_ITEMS}
                value={avatar.eyebrows}
                field="eyebrows"
                config={bare}
                onPick={(v) => set({ eyebrows: v })}
              />
              <Stepper
                label="눈썹 굵기"
                items={BROW_THICKNESS}
                value={avatar.browThickness}
                field="browThickness"
                config={bare}
                onPick={(v) => set({ browThickness: v })}
              />
              <Stepper
                label="표정"
                items={MOUTH}
                value={avatar.mouth}
                field="mouth"
                config={bare}
                onPick={(v) => set({ mouth: v })}
              />
            </>
          )}

          {category === "style" && (
            <>
              <Stepper
                label="안경"
                items={GLASSES_OPTIONS}
                value={avatar.glasses}
                field="glasses"
                config={{ ...avatar, beard: null }}
                onPick={(v) => set({ glasses: v })}
              />
              <Stepper
                label="수염"
                items={[NONE(), ...BEARD]}
                value={avatar.beard}
                field="beard"
                config={{ ...avatar, glasses: "none" }}
                onPick={(v) => set({ beard: v })}
              />
              <Stepper
                label="의상"
                items={CLOTHES}
                value={avatar.clothes}
                field="clothes"
                config={avatar}
                onPick={(v) => set({ clothes: v })}
              />
              <ColorRow
                label="의상 컬러"
                colors={CLOTHES_COLORS}
                value={avatar.clothesColor}
                onPick={(v) => set({ clothesColor: v })}
              />
            </>
          )}
        </div>
      </div>

      {camera && createPortal(
        <div
          className="fixed inset-0 z-[140] flex items-end justify-center bg-[#02050C]/75 backdrop-blur-[5px] sm:items-center sm:p-6"
          role="dialog"
          aria-modal="true"
          aria-label="카메라로 아바타 맞추기"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) setCamera(false);
          }}
        >
          <div className="w-full max-w-[460px] animate-sheet-up rounded-t-[28px] border border-white/10 bg-[#0D1727] p-3 shadow-[0_-22px_70px_rgba(0,0,0,.55)] sm:animate-fade sm:rounded-[28px]">
            <AvatarFromPhoto
              current={avatar}
              onResult={(cfg) => {
                // 모델이 고른 값만 덮어쓴다. 나머지(의상 등)는 사용자가 고른 걸 유지한다.
                onChange({ ...avatar, ...cfg });
                setCamera(false);
              }}
              onClose={() => setCamera(false)}
            />
          </div>
        </div>,
        document.body
      )}

      {/* CC BY 4.0 — 저작자·라이선스·변경 사실 세 가지 모두 의무. 지우지 말 것. */}
      <p className="mt-4 text-center text-[8px] leading-relaxed text-mut">
        <a href={TOONHEAD_CREDIT.creatorUrl} target="_blank" rel="noreferrer" className="underline">
          {TOONHEAD_CREDIT.title} by {TOONHEAD_CREDIT.creator}
        </a>
        {" · "}
        <a href={TOONHEAD_CREDIT.licenseUrl} target="_blank" rel="noreferrer" className="underline">
          {TOONHEAD_CREDIT.license}
        </a>
        {" · 원저작물에서 일부 파츠를 추가·변경했습니다"}
      </p>
    </div>
  );
}
