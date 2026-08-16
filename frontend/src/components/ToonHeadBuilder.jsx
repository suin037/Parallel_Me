import { useMemo } from "react";
import { createAvatar } from "@dicebear/core";
import { toonHead } from "@dicebear/collection";
import {
  BEARD,
  BROW_SHAPE_ITEMS,
  BROW_THICKNESS,
  CLOTHES,
  CLOTHES_COLORS,
  DEFAULT_TOONHEAD,
  EYES,
  GLASSES_OPTIONS,
  HAIR_COLORS,
  HAIR_STYLES,
  MOUTH,
  SKIN_COLORS,
  TOONHEAD_CREDIT,
  hairStyleById,
  randomToonHead,
  toDicebearOptions,
} from "../data/toonHeadOptions.js";
import {
  FACE_SHAPES,
  overlayCustomHair,
  overlayEars,
  overlayGlasses,
  replaceBrows,
  replaceFaceShape,
} from "../data/customParts.js";

// toonHead 부위별 아바타 빌더. 모든 선택지는 화살표로 넘긴다.
// 앞머리/뒷머리/수염은 "없음"을 포함하고, 나머지는 항상 하나가 선택돼 있다.

const ARROW_BTN = {
  width: 30,
  height: 30,
  borderRadius: "50%",
  border: "1px solid #ccc",
  background: "#fff",
  cursor: "pointer",
  fontSize: 14,
  lineHeight: 1,
  color: "#333",
  flexShrink: 0,
};

/**
 * ◀ 라벨 (n/N) ▶ 형태의 선택기. 끝에서 반대편으로 순환한다.
 * items: [{ id, label }] — "없음"이 필요하면 호출부에서 id:null 로 앞에 끼워 넣는다.
 * preview: 현재 값을 색 원 등으로 미리 보여주고 싶을 때 쓰는 노드.
 */
function Stepper({ label, items, value, onPick, preview = null }) {
  const found = items.findIndex((i) => i.id === value);
  const at = found < 0 ? 0 : found;
  const move = (d) => onPick(items[(at + d + items.length) % items.length].id);

  return (
    <div style={{ marginTop: 12 }}>
      <div style={{ marginBottom: 4, fontSize: 11, color: "#666" }}>{label}</div>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <button type="button" onClick={() => move(-1)} style={ARROW_BTN} aria-label={`${label} 이전`}>
          ◀
        </button>

        <div
          style={{
            flex: 1,
            minWidth: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 8,
            padding: "7px 10px",
            borderRadius: 8,
            border: "1px solid #ddd",
            background: "#fafbfc",
            fontSize: 13,
          }}
        >
          {preview}
          <span
            style={{
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
              color: items[at].id == null ? "#999" : "#222",
            }}
          >
            {items[at].label}
          </span>
          <span style={{ fontSize: 11, color: "#aaa", flexShrink: 0 }}>
            {at + 1}/{items.length}
          </span>
        </div>

        <button type="button" onClick={() => move(1)} style={ARROW_BTN} aria-label={`${label} 다음`}>
          ▶
        </button>
      </div>
    </div>
  );
}

const NONE = (label = "없음") => ({ id: null, label });

/** 색 목록을 Stepper 가 먹을 수 있는 형태로. 라벨 대신 색 원을 미리보기로 쓴다. */
function colorItems(hexes) {
  return hexes.map((h, i) => ({ id: h, label: `${i + 1}번 색` }));
}

function ColorDot({ hex }) {
  return (
    <span
      style={{
        width: 18,
        height: 18,
        borderRadius: "50%",
        background: "#" + hex,
        border: "1px solid #bbb",
        flexShrink: 0,
      }}
    />
  );
}

const FACE_ITEMS = Object.entries(FACE_SHAPES).map(([id, f]) => ({ id, label: f.label }));

// 얼굴형·눈·눈썹·안경을 직접 그려 넣었으므로 CC BY 4.0 의 '변경 사실 표시' 의무가 있다.
const HAS_CUSTOM_PARTS = true;

export default function ToonHeadBuilder({ config, onChange }) {
  const c = { ...DEFAULT_TOONHEAD, ...(config || {}) };
  const set = (patch) => onChange({ ...c, ...patch });

  const uri = useMemo(() => {
    const style = hairStyleById(c.hairStyle);
    let svg = createAvatar(toonHead, {
      seed: "me",
      size: 200,
      ...toDicebearOptions(c),
    }).toString();

    // 순서가 중요하다: 얼굴 → 눈 → 눈썹(모두 교체) → 커스텀 머리 → 안경(덧씌움)
    svg = replaceFaceShape(svg, c.face);
    svg = replaceBrows(svg, c.eyebrows, c.browThickness, "#" + c.hairColor);
    if (style.custom) {
      svg = overlayCustomHair(svg, style.hair, {
        hair: "#" + c.hairColor,
        skin: "#" + c.skinColor,
        clothes: "#" + c.clothesColor,
      });
      // 커스텀 앞머리가 귀를 덮으므로 귀만 다시 위에 그려 앞으로 빼낸다.
      svg = overlayEars(svg, "#" + c.skinColor);
    }
    svg = overlayGlasses(svg, c.glasses);
    return "data:image/svg+xml;utf8," + encodeURIComponent(svg);
  }, [c]);

  return (
    <div>
      <div style={{ display: "flex", gap: 16, alignItems: "flex-start" }}>
        <img
          src={uri}
          alt="내 아바타"
          width={160}
          height={160}
          style={{ display: "block", borderRadius: 12, background: "#f6f7f9", flexShrink: 0 }}
        />
        <div>
          <button
            type="button"
            onClick={() => onChange(randomToonHead())}
            style={{
              padding: "8px 14px",
              borderRadius: 6,
              border: "1px solid #7FD4FF",
              background: "#12203a",
              color: "#7FD4FF",
              cursor: "pointer",
              fontSize: 13,
            }}
          >
            무작위로 뽑기
          </button>
          <button
            type="button"
            onClick={() => onChange({ ...DEFAULT_TOONHEAD })}
            style={{
              marginLeft: 8,
              padding: "8px 14px",
              borderRadius: 6,
              border: "1px solid #ccc",
              background: "#fff",
              color: "#333",
              cursor: "pointer",
              fontSize: 13,
            }}
          >
            처음으로
          </button>
          <p style={{ fontSize: 11, color: "#888", lineHeight: 1.6, marginTop: 10 }}>
            화살표로 넘겨서 고르세요.
          </p>
        </div>
      </div>

      <div style={{ maxWidth: 380 }}>
        <Stepper label="얼굴형" items={FACE_ITEMS} value={c.face} onPick={(v) => set({ face: v })} />
        <Stepper
          label="헤어스타일"
          items={HAIR_STYLES}
          value={c.hairStyle}
          onPick={(v) => set({ hairStyle: v })}
        />
        <Stepper
          label="머리색"
          items={colorItems(HAIR_COLORS)}
          value={c.hairColor}
          onPick={(v) => set({ hairColor: v })}
          preview={<ColorDot hex={c.hairColor} />}
        />
        <Stepper
          label="피부톤"
          items={colorItems(SKIN_COLORS)}
          value={c.skinColor}
          onPick={(v) => set({ skinColor: v })}
          preview={<ColorDot hex={c.skinColor} />}
        />
        <Stepper label="눈" items={EYES} value={c.eyes} onPick={(v) => set({ eyes: v })} />
        <Stepper
          label="안경"
          items={GLASSES_OPTIONS}
          value={c.glasses}
          onPick={(v) => set({ glasses: v })}
        />
        <Stepper
          label="눈썹 모양"
          items={BROW_SHAPE_ITEMS}
          value={c.eyebrows}
          onPick={(v) => set({ eyebrows: v })}
        />
        <Stepper
          label="눈썹 두께"
          items={BROW_THICKNESS}
          value={c.browThickness}
          onPick={(v) => set({ browThickness: v })}
        />
        <Stepper label="입" items={MOUTH} value={c.mouth} onPick={(v) => set({ mouth: v })} />
        <Stepper
          label="수염"
          items={[NONE(), ...BEARD]}
          value={c.beard}
          onPick={(v) => set({ beard: v })}
        />
        <Stepper label="옷" items={CLOTHES} value={c.clothes} onPick={(v) => set({ clothes: v })} />
        <Stepper
          label="옷 색"
          items={colorItems(CLOTHES_COLORS)}
          value={c.clothesColor}
          onPick={(v) => set({ clothesColor: v })}
          preview={<ColorDot hex={c.clothesColor} />}
        />
      </div>

      {/*
        CC BY 4.0 이 요구하는 세 가지를 모두 담고 있다. 화면에서 지우지 말 것.
          1) 저작자 표기  2) 라이선스 링크  3) 변경 사실 표시
        3번은 우리가 파츠를 추가/수정할 때만 의무이므로, 커스텀 파츠가 있을 때만 붙인다.
      */}
      <p style={{ fontSize: 10, color: "#999", marginTop: 20 }}>
        아바타 스타일:{" "}
        <a href={TOONHEAD_CREDIT.creatorUrl} target="_blank" rel="noreferrer">
          {TOONHEAD_CREDIT.title} by {TOONHEAD_CREDIT.creator}
        </a>{" "}
        ·{" "}
        <a href={TOONHEAD_CREDIT.licenseUrl} target="_blank" rel="noreferrer">
          {TOONHEAD_CREDIT.license}
        </a>
        {HAS_CUSTOM_PARTS && " · 원저작물에서 일부 파츠를 추가·변경했습니다"}
      </p>
    </div>
  );
}
