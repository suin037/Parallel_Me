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
  // 이름을 둘 다 받는다 — data/api.js 는 같은 서버를 VITE_QMODE_API_URL 로 부른다.
  // 한 이름만 설정된 배포에서 이쪽이 조용히 폴백으로 떨어져 AI 기능이 통째로 죽은 적이 있다.
  // (그때 증상: 요청은 200 인데 본문이 index.html 이라 res.json() 만 던졌다)
  const fromEnv = import.meta.env?.VITE_QMODE_BASE || import.meta.env?.VITE_QMODE_API_URL;
  if (fromEnv) return String(fromEnv).replace(/\/+$/, "");

  // Vite가 /api를 FastAPI(:8000)로 넘기고, qmode 앱은 백엔드의 /qmode에
  // 마운트되어 있다. 상대경로라서 로컬 PC와 외부 터널의 휴대폰 모두 동일하게 동작한다.
  return "/api/qmode";
}

export const API_BASE = resolve();

// 위 주석이 약속하던 경고 — 실제로는 구현돼 있지 않아 아무도 못 알아챘다.
//
// 배포본에서 상대경로로 떨어지면 그 경로는 정적 호스팅의 SPA 폴백에 걸려 **index.html 을
// 200 으로** 돌려준다. 그래서 요청은 '성공'하고 res.json() 만 던진다 — 화면에는
// "서버에 연결하지 못했어요" 로 보이고, 네트워크 탭에도 200 이라 정상처럼 찍힌다.
// 원인을 찾을 단서가 없으므로 여기서 크게 알린다.
if (typeof window !== "undefined" && API_BASE.startsWith("/")) {
  const host = window.location.hostname;
  const local = host === "localhost" || host === "127.0.0.1" || host.endsWith(".local");
  if (!local) {
    console.error(
      `[apiBase] AI 서버 주소가 없어 '${API_BASE}' 로 요청합니다. 배포 환경에서 이 경로는 `
      + "index.html 을 돌려주므로 AI 기능(챗봇·공고분석·N년 뒤·기업/관계 분석·주간 리포트)이 "
      + "전부 조용히 실패합니다. VITE_QMODE_BASE 를 설정하고 **다시 빌드**하세요 "
      + "(Vite 는 빌드 시점에 값을 박으므로 환경변수만 바꾸면 반영되지 않습니다).",
    );
  }
}

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
