import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { BookOpen, ChevronRight, LockKeyhole, Sparkles } from "lucide-react";
import DiaryToday from "../components/DiaryToday.jsx";
import PetPeek from "../components/PetPeek.jsx";
import ApiStatus from "../components/ApiStatus.jsx";
import { loadUniverse } from "../data/myUniverse.js";

export default function HomeHub() {
  const navigate = useNavigate();
  const [universeState, setUniverseState] = useState(loadUniverse);

  useEffect(() => {
    const refresh = () => setUniverseState(loadUniverse());
    window.addEventListener("pm:universe", refresh);
    return () => window.removeEventListener("pm:universe", refresh);
  }, []);

  const recentEntries = (universeState.checkins || [])
    .filter((entry) => !entry.empty && (entry.text || entry.note || entry.emotion))
    .sort((a, b) => String(b.date).localeCompare(String(a.date)))
    .slice(0, 5);

  return (
    <div className="pb-4 lg:pb-12">
      {/* 돌보미는 설정 안에 있어 들어가 보지 않으면 상태를 모른다.
          매일 오는 이 화면 맨 위에 세워, 기분이 눈에 띄게 한다. */}
      <header className="flex items-start justify-between gap-3 pb-5 lg:pb-7">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-[11px] font-bold tracking-[.12em] text-violet-300"><BookOpen size={14} /> DIARY</div>
          <h1 className="mt-2 text-[26px] font-black tracking-[-.04em] text-ink lg:text-[38px]">오늘의 기록</h1>
          <p className="mt-1.5 max-w-[650px] text-[11px] leading-5 text-sub lg:text-[13px]">오늘 있었던 일과 마음을 한곳에 남겨보세요.</p>
        </div>
        <PetPeek />
      </header>

      <div className="grid items-start gap-8 border-t border-white/[.08] pt-6 lg:grid-cols-[minmax(0,1.55fr)_minmax(300px,.65fr)] lg:gap-10 lg:pt-8">
        <main data-tour="diary" className="min-w-0 lg:pr-2"><DiaryToday /></main>

        <aside data-tour="recent" className="space-y-4 lg:sticky lg:top-[100px]">
          <section className="rounded-[20px] border border-white/[.08] bg-white/[.025] p-4">
            <div className="flex items-center gap-2 text-[12px] font-bold text-ink"><LockKeyhole size={15} className="text-violet-300" /> 기록은 이렇게 활용돼요</div>
            <ul className="mt-3 space-y-2.5 text-[10px] leading-4 text-sub">
              <li>· 자주 반복되는 고민과 삶의 영역을 찾아요.</li>
              <li>· 시뮬레이션 주제와 결과 설명을 개인화해요.</li>
              <li>· 일기만으로 예측 숫자를 임의로 바꾸지는 않아요.</li>
            </ul>
          </section>

          <section className="overflow-hidden rounded-[20px] border border-white/[.08] bg-white/[.025]">
            <div className="flex items-center justify-between border-b border-white/[.07] px-4 py-3.5">
              <h2 className="text-[12px] font-bold text-ink">최근 기록</h2>
              <button type="button" onClick={() => navigate("/my")} className="tap flex items-center gap-1 text-[9px] text-mut">나의 우주에서 보기 <ChevronRight size={12} /></button>
            </div>
            {recentEntries.length ? recentEntries.map((entry) => (
              <button key={entry.date} type="button" onClick={() => navigate("/my")} className="tap flex w-full items-center gap-3 border-b border-white/[.06] px-4 py-3 text-left last:border-0 hover:bg-white/[.03]">
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-violet-500/10 text-violet-300"><Sparkles size={13} /></span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[11px] font-semibold text-ink">{entry.text || entry.note || entry.emotion || "오늘의 기록"}</span>
                  <span className="mt-0.5 block text-[9px] text-mut">{entry.date}</span>
                </span>
              </button>
            )) : <p className="px-4 py-7 text-center text-[10px] text-mut">첫 기록을 남기면 여기에 모여요.</p>}
          </section>

          <ApiStatus />
        </aside>
      </div>
    </div>
  );
}
