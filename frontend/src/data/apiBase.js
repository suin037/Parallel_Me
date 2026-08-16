// AI 기능이 부를 서버 주소 — 한 곳에서 정한다.
//
// 배포하면 프론트는 정적 파일이라 localhost 를 부를 수 없다. 그러면 챗봇·N년 뒤·
// 기회 찾기·오늘 제안·노래·공고/기업/관계 분석이 전부 죽는다. 그래서 주소를
// 세 경로로 찾는다 — 앞의 것이 이긴다.
//
//   1) window.__QMODE_BASE__      : index.html 이나 콘솔에서 넣는 값(재빌드 없이 교체 가능)
//   2) VITE_QMODE_BASE            : 빌드 시 주입(.env.production 또는 배포 플랫폼 환경변수)
//   3) /api/qmode                 : 로컬·Quick Tunnel 공통(Vite 프록시)
//
// 배포본에서 주소를 잘못 넣었을 때 바로 알아채도록, 로컬이 아닌 곳에서 localhost 로
// 떨어지면 콘솔에 경고를 남긴다.
function resolve() {
  if (typeof window !== "undefined" && window.__QMODE_BASE__) {
    return String(window.__QMODE_BASE__).replace(/\/+$/, "");
  }
  const fromEnv = import.meta.env?.VITE_QMODE_BASE;
  if (fromEnv) return String(fromEnv).replace(/\/+$/, "");

  // Vite가 /api를 FastAPI(:8000)로 넘기고, qmode 앱은 백엔드의 /qmode에
  // 마운트되어 있다. 상대경로라서 로컬 PC와 외부 터널의 휴대폰 모두 동일하게 동작한다.
  return "/api/qmode";
}

export const API_BASE = resolve();

/** 서버가 살아 있는지 — 화면에서 '서버 꺼짐' 안내를 띄울 때 쓴다. */
export async function pingApi(timeoutMs = 4000) {
  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), timeoutMs);
    const res = await fetch(`${API_BASE}/health`, { signal: ctrl.signal });
    clearTimeout(t);
    return res.ok;
  } catch {
    return false;
  }
}
