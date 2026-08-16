import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Eyebrow } from "../components/ui.jsx";
import CompanyAnalysis from "../components/CompanyAnalysis.jsx";

// 기업 분석 — 검색해서 보는 독립 화면.
// 공고 분석 카드 안에 끼워 넣으니 창이 겹쳐 답답해서, 따로 뺐다.
// 공고에서 회사명이 잡혔으면 그 이름을 들고 들어온다(?name=).
export default function CompanyScreen() {
  const navigate = useNavigate();
  const location = useLocation();
  const preset = new URLSearchParams(location.search).get("name") || "";
  const [query, setQuery] = useState(preset);
  const [target, setTarget] = useState(preset);

  useEffect(() => {
    setQuery(preset);
    setTarget(preset);
  }, [preset]);

  function search(event) {
    event?.preventDefault();
    const q = query.trim();
    if (q) setTarget(q);
  }

  return (
    <div className="pb-8">
      <Eyebrow>기업 분석 · DART</Eyebrow>
      <h1 className="text-[21px] font-bold leading-[1.2] lg:text-[26px]">
        지원할 회사, 숫자로 먼저 보기
      </h1>
      <p className="mt-1 text-[12px] leading-relaxed text-sub">
        금융감독원 전자공시(DART)의 재무·공시를 그대로 불러옵니다. 해석만 정리하고, 수치는 지어내지 않아요.
      </p>

      <form onSubmit={search} className="mt-4 flex gap-1.5">
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="회사명 (예: 삼성전자, 카카오, 토스뱅크)"
          className="min-w-0 flex-1 rounded-xl border border-line bg-[#0E1424] px-3.5 py-2.5 text-[13px] text-ink outline-none placeholder:text-mut focus:border-[#8B6CCF]"
        />
        <button
          type="submit"
          disabled={!query.trim()}
          className="tap shrink-0 rounded-xl bg-[#8B6CCF] px-4 text-[12px] font-bold text-white disabled:opacity-40"
        >
          검색
        </button>
      </form>

      <div className="mt-2 flex flex-wrap gap-1.5">
        {["삼성전자", "카카오", "NAVER", "SK하이닉스", "현대자동차"].map((name) => (
          <button
            key={name}
            type="button"
            onClick={() => { setQuery(name); setTarget(name); }}
            className="tap rounded-full border border-white/10 px-2.5 py-1 text-[10px] text-sub hover:border-[#8B6CCF]/50"
          >
            {name}
          </button>
        ))}
      </div>

      <div className="mt-4">
        {target ? (
          <CompanyAnalysis key={target} company={target} auto />
        ) : (
          <p className="rounded-2xl border border-dashed border-white/10 px-3.5 py-8 text-center text-[12px] leading-relaxed text-mut">
            회사명을 검색하면 매출·영업이익 추이와 최근 공시를 볼 수 있어요.
            <br />
            상장사는 대부분 조회되고, 비상장은 공시 의무가 있는 곳만 나옵니다.
          </p>
        )}
      </div>

      <button
        onClick={() => navigate(-1)}
        className="tap mt-5 w-full rounded-2xl border border-white/10 py-3 text-[12px] text-sub"
      >
        ← 돌아가기
      </button>
    </div>
  );
}
