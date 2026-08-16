import { Routes, Route, Navigate } from "react-router-dom";
import { useResult } from "./data/ResultContext.jsx";
import Layout from "./components/Layout.jsx";
import Landing from "./screens/Landing.jsx";
import Personas from "./screens/Personas.jsx";
import Onboarding from "./screens/Onboarding.jsx";
import InputScreen from "./screens/InputScreen.jsx";
import Simulate from "./screens/Simulate.jsx";
import Result from "./screens/Result.jsx";
import Archive from "./screens/Archive.jsx";
import HomeHub from "./screens/HomeHub.jsx";
import MyUniverse from "./screens/MyUniverseV2.jsx";
import CheckIn from "./screens/CheckIn.jsx";
import Settings from "./screens/Settings.jsx";
import CompanyScreen from "./screens/CompanyScreen.jsx";
import Handoff from "./screens/Handoff.jsx";
import Resume from "./screens/Resume.jsx";

// "/" 진입점 — 첫 로그인이면 랜딩, 이미 온보딩했으면 홈으로.
function Entry() {
  const { onboarded } = useResult();
  return onboarded ? <Navigate to="/my" replace /> : <Landing />;
}

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Entry />} />
        <Route path="/personas" element={<Personas />} />
        <Route path="/onboarding" element={<Onboarding />} />
        <Route path="/home" element={<HomeHub />} />
        <Route path="/input" element={<InputScreen />} />
        <Route path="/simulate" element={<Simulate />} />
        <Route path="/result" element={<Result />} />
        <Route path="/company" element={<CompanyScreen />} />
        <Route path="/my" element={<MyUniverse />} />
        <Route path="/checkin" element={<CheckIn />} />
        <Route path="/archive" element={<Archive />} />
        <Route path="/settings" element={<Settings />} />
        {/* 기기 옮기기 — /handoff 는 내보내는 쪽, /resume 은 링크를 받아 여는 쪽.
            /resume 은 온보딩 전에도 열려야 하므로 Entry 를 거치지 않는다. */}
        <Route path="/handoff" element={<Handoff />} />
        <Route path="/resume" element={<Resume />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
