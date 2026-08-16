import { useMemo, useState } from "react";
import { createAvatar } from "@dicebear/core";
import {
  adventurer,
  avataaars,
  bigSmile,
  croodles,
  dylan,
  lorelei,
  micah,
  miniavs,
  notionists,
  openPeeps,
  personas,
  toonHead,
} from "@dicebear/collection";

// 스타일 고르기용 비교 화면. 말로 설명하는 대신 실제로 보고 고르라고 만든 것.
// 라이선스는 내가 외워 적지 않고 패키지가 들고 있는 meta 에서 그대로 읽는다.
const CANDIDATES = [
  { key: "lorelei", style: lorelei, note: "애니/일러스트 느낌이 제일 강함" },
  { key: "adventurer", style: adventurer, note: "애니풍, 캐주얼" },
  { key: "toonHead", style: toonHead, note: "카툰 얼굴" },
  { key: "bigSmile", style: bigSmile, note: "밝은 카툰" },
  { key: "micah", style: micah, note: "깔끔한 벡터 일러스트" },
  { key: "avataaars", style: avataaars, note: "클래식 카툰(가장 옵션 많음)" },
  { key: "notionists", style: notionists, note: "노션풍 손그림" },
  { key: "openPeeps", style: openPeeps, note: "손그림" },
  { key: "personas", style: personas, note: "플랫 일러스트" },
  { key: "miniavs", style: miniavs, note: "미니멀" },
  { key: "croodles", style: croodles, note: "낙서풍" },
  { key: "dylan", style: dylan, note: "굵은 선 카툰" },
];

// 같은 인물을 여러 스타일로 비교하려고 시드를 고정해 둔다.
const SEEDS = ["Aria", "Jiyun", "Minho", "Sora"];

function svgDataUri(style, seed) {
  return createAvatar(style, { seed, size: 96 }).toDataUri();
}

function licenseOf(style) {
  const meta = style?.meta || {};
  const lic = meta.license || {};
  return {
    title: meta.title || "",
    creator: meta.creator || "",
    name: lic.name || "라이선스 정보 없음",
    url: lic.url || "",
    // CC0 는 저작자 표시 의무가 없다. 그 외(CC BY 등)는 표기 필요.
    attributionFree: /cc0/i.test(lic.name || ""),
  };
}

export default function AvatarStylePicker({ value, onChange }) {
  const [seed, setSeed] = useState(SEEDS[0]);

  const rows = useMemo(
    () =>
      CANDIDATES.map((c) => ({
        ...c,
        uri: svgDataUri(c.style, seed),
        license: licenseOf(c.style),
      })),
    [seed]
  );

  return (
    <div>
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 12 }}>
        <span style={{ fontSize: 12, color: "#666" }}>다른 사람으로 보기:</span>
        {SEEDS.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => setSeed(s)}
            style={{
              borderRadius: 999,
              padding: "4px 10px",
              fontSize: 12,
              cursor: "pointer",
              border: seed === s ? "1px solid #7FD4FF" : "1px solid #ccc",
              background: seed === s ? "#12203a" : "#fff",
              color: seed === s ? "#7FD4FF" : "#333",
            }}
          >
            {s}
          </button>
        ))}
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))",
          gap: 12,
        }}
      >
        {rows.map((r) => {
          const on = value === r.key;
          return (
            <button
              key={r.key}
              type="button"
              onClick={() => onChange(r.key)}
              style={{
                display: "block",
                textAlign: "center",
                padding: 10,
                borderRadius: 10,
                cursor: "pointer",
                background: on ? "#12203a" : "#fff",
                border: on ? "2px solid #7FD4FF" : "1px solid #ddd",
              }}
            >
              <img
                src={r.uri}
                alt={r.key}
                width={96}
                height={96}
                style={{ display: "block", margin: "0 auto", borderRadius: 8 }}
              />
              <div
                style={{
                  marginTop: 6,
                  fontSize: 13,
                  fontWeight: 600,
                  color: on ? "#7FD4FF" : "#222",
                }}
              >
                {r.key}
              </div>
              <div style={{ fontSize: 11, color: "#666", marginTop: 2 }}>{r.note}</div>
              <div
                style={{
                  fontSize: 10,
                  marginTop: 4,
                  color: r.license.attributionFree ? "#2b8a3e" : "#b06000",
                }}
              >
                {r.license.name}
                {r.license.attributionFree ? " · 표기 불필요" : " · 저작자 표기 필요"}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
