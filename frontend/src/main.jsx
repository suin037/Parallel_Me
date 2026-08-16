import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App.jsx";
import { ResultProvider } from "./data/ResultContext.jsx";
import { DiaryProvider } from "./data/DiaryContext.jsx";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <ResultProvider>
        <DiaryProvider>
          <App />
        </DiaryProvider>
      </ResultProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
