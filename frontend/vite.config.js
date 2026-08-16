import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    // Quick Tunnel이 매번 임의의 *.trycloudflare.com 호스트를 발급한다.
    // 임시 데모 서버에서만 쓰는 설정이며 정식 배포 서버 설정은 아니다.
    allowedHosts: true,
    // 외부 임시공유에서는 브라우저가 백엔드에 직접 접근하지 않고 같은
    // 프론트 주소의 /api 로 호출한다. Vite가 로컬 FastAPI로 전달하므로
    // 백엔드용 터널과 trycloudflare CORS 예외가 따로 필요 없다.
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
