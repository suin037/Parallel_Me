import { useEffect, useState } from "react";
import { AlertTriangle } from "lucide-react";
import { API_BASE, pingApi } from "../data/apiBase.js";

// AI 서버가 안 잡히면 알려준다.
//
// 이게 없으면 챗봇·N년 뒤·기회 찾기·오늘 제안·노래·공고/기업/관계 분석이 그냥
// '안 뜨는' 상태가 된다 — 고장인지 원래 그런 건지 알 수가 없다.
// 기록·별자리·나의 우주·탐험은 서버 없이도 도니까, 그 점도 같이 밝힌다.
export default function ApiStatus() {
  const [down, setDown] = useState(false);
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    let alive = true;
    pingApi().then((ok) => {
      if (!alive) return;
      setDown(!ok);
      setChecked(true);
    });
    return () => { alive = false; };
  }, []);

  if (!checked || !down) return null;

  const local = /localhost|127\.0\.0\.1/.test(API_BASE);
  return (
    <div className="mt-3 flex items-start gap-2 rounded-[14px] border border-[#EDA100]/35 bg-[#2A2110] px-3 py-2.5">
      <AlertTriangle size={14} className="mt-0.5 shrink-0 text-[#EDA100]" />
      <div className="min-w-0">
        <p className="text-[11.5px] font-semibold text-[#F0C468]">AI 기능이 지금 꺼져 있어요</p>
        <p className="mt-0.5 text-[10px] leading-relaxed text-sub">
          {local
            ? "분석 서버(localhost:8000)에 연결하지 못했어요. 서버를 켜면 챗봇·미래 서사·기회 찾기·노래 추천이 살아나요."
            : "분석 서버에 연결하지 못했어요. 잠시 뒤 새로고침해 주세요."}
          {" "}기록·별자리·나의 우주·탐험은 그대로 쓸 수 있어요.
        </p>
      </div>
    </div>
  );
}
