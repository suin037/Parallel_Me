/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#09111F",
        card: "#111B2A",
        card2: "#172337",
        line: "#26354A",
        ink: "#F6F8FC",
        sub: "#B8C2D2",
        mut: "#748198",
        cyan: { DEFAULT: "#8B6CCF", deep: "#8B6CCF" }, // single violet accent
        gold: { DEFAULT: "#FF9F32", deep: "#E98418" }, // 선택 B
        danger: "#FF7B7B",
      },
      fontFamily: {
        sans: [
          "Pretendard",
          "Pretendard Variable",
          "-apple-system",
          "BlinkMacSystemFont",
          "system-ui",
          "Roboto",
          "sans-serif",
        ],
      },
      // Desktop preview size. Real mobile screens still use w-full.
      maxWidth: { phone: "450px" },
      keyframes: {
        fade: {
          from: { opacity: "0", transform: "translateY(8px)" },
          to: { opacity: "1", transform: "none" },
        },
        sheetUp: {
          from: { opacity: "0", transform: "translateY(100%)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        backdropIn: {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        spin: { to: { transform: "rotate(360deg)" } },
        driftA: { "50%": { transform: "translateX(-18px)" } },
        driftB: { "50%": { transform: "translateX(18px)" } },
        twinkle: { "50%": { opacity: "0.2" } },
        // 성운이 아주 느리게 부풀었다 줄어든다.
        // opacity는 건드리지 않는다 — 애니메이션이 utility class(opacity-[.13])를 덮어써서
        // 성운이 화면을 통째로 보라색으로 씌워버린다.
        nebulaDrift: {
          "0%, 100%": { transform: "scale(1)" },
          "50%": { transform: "scale(1.18)" },
        },
        orbit: {
          from: { transform: "rotate(0deg)" },
          to: { transform: "rotate(360deg)" },
        },
        // 궤도를 도는 동안 A/B 글자가 뒤집히지 않도록 같은 주기로 역회전시킨다.
        orbitCounter: {
          from: { transform: "rotate(0deg)" },
          to: { transform: "rotate(-360deg)" },
        },
        cometGlow: {
          "0%, 100%": { opacity: ".7", transform: "scale(.88)" },
          "50%": { opacity: "1", transform: "scale(1.14)" },
        },
      },
      animation: {
        fade: "fade .35s ease",
        "sheet-up": "sheetUp .28s cubic-bezier(.22,.8,.25,1)",
        "backdrop-in": "backdropIn .2s ease-out",
        "spin-slow": "spin 3s linear infinite",
        // 주기·지연은 별마다 인라인으로 덮어써서 흩뜨린다(Stars.jsx).
        twinkle: "twinkle 3s ease-in-out infinite",
        "nebula-drift": "nebulaDrift 14s ease-in-out infinite",
        driftA: "driftA 3s ease-in-out infinite",
        driftB: "driftB 3s ease-in-out infinite",
        orbit: "orbit 5s linear infinite",
        "orbit-counter": "orbitCounter 5s linear infinite",
        "comet-glow": "cometGlow 1.15s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
