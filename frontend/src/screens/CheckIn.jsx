import { useNavigate } from "react-router-dom";
import DiaryCheckIn from "../components/DiaryCheckIn.jsx";

// 오늘 기록 전용 화면 — 홈 카드와 같은 컴포넌트를 재사용(직접 진입 /checkin 용).
export default function CheckIn() {
  const navigate = useNavigate();
  return (
    <div>
      <div className="mb-1 mt-2 flex items-center justify-between">
        <h1 className="text-[22px] font-bold leading-[1.2]">오늘 기록</h1>
        <button onClick={() => navigate("/my")} className="tap text-[12px] text-mut">
          닫기
        </button>
      </div>
      <p className="mb-3 text-[13px] text-sub">오늘 하루가 별 하나가 됩니다.</p>
      <DiaryCheckIn onSaved={() => navigate("/my")} />
    </div>
  );
}
