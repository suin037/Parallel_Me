import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, HashRouter } from "react-router-dom";
import App from "./App.jsx";
import ErrorBoundary from "./components/ErrorBoundary.jsx";
import { ResultProvider } from "./data/ResultContext.jsx";
import { DiaryProvider } from "./data/DiaryContext.jsx";
import "./index.css";

/*
 * 라우터를 고른다.
 *
 * BrowserRouter 는 초기화할 때 History API 를 건드린다. 전시관이 iframe 에
 * sandbox 를 걸면서 allow-same-origin 을 빼면 우리 문서의 출처가 사라지고,
 * 그 상태에서 history.replaceState() 는 SecurityError 를 던진다. 부팅 중이라
 * 잡아줄 곳이 없어 그대로 흰 화면이 된다.
 *
 * 그래서 먼저 한 번 찔러보고, 막히면 주소를 안 건드리는 HashRouter 로 간다.
 * 주소가 /my 대신 /#/my 가 되지만 화면은 똑같이 돈다 — 흰 화면보다 낫다.
 */
function pickRouter() {
  try {
    if (typeof window === "undefined" || !window.history) return HashRouter;
    window.history.replaceState(window.history.state, "");
    return BrowserRouter;
  } catch {
    return HashRouter;
  }
}

const Router = pickRouter();

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <ErrorBoundary>
      <Router>
        <ResultProvider>
          <DiaryProvider>
            <App />
          </DiaryProvider>
        </ResultProvider>
      </Router>
    </ErrorBoundary>
  </React.StrictMode>,
);
