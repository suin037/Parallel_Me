import { useEffect, useMemo, useState } from "react";
import { Sparkles, Search } from "lucide-react";
import { fetchSuggestion, getTodaySuggestion, suggestMaterials, fetchTracks, getTodayTracks } from "../data/suggestApi.js";
import { loadSpeech } from "../data/dispositionApi.js";

// 오늘 해볼 만한 것 — 최근 2주 기록을 보고 작게 권한다.
//  · 몸 / 듣기 / 해보기 / 쉬기 / 사람 으로 결을 나눠 세 개.
//  · 기록이 많이 무거운 날엔 권하지 않고, 아무것도 안 해도 된다고만 말한다.
const KIND_STYLE = {
  move: { color: "#5DCAA5", icon: "🏃" },
  listen: { color: "#8FB4F0", icon: "🎧" },
  try: { color: "#EDA100", icon: "✦" },
  rest: { color: "#B79BF0", icon: "🌙" },
  meet: { color: "#F0918D", icon: "🫂" },
};

// 기분을 어느 쪽으로 옮기려는지 — 가라앉은 날 갑자기 신나는 쪽으로 밀지 않는다.
const SHIFT_LABEL = {
  stay: "지금 마음 곁에",
  lift: "천천히 끌어올리기",
  energize: "기운 내는 쪽으로",
};

export default function DailySuggest() {
  const [data, setData] = useState(getTodaySuggestion);
  const [tracks, setTracks] = useState(getTodayTracks);
  const [busy, setBusy] = useState(false);
  // 렌더마다 localStorage 를 다시 파싱하지 않도록 — 1년치면 그것만으로도 눈에 띈다.
  const mat = useMemo(() => suggestMaterials(), []);

  // 오늘 것이 없으면 한 번만 만든다(하루 1회 — 들어올 때마다 부르면 말이 계속 바뀐다).
  useEffect(() => {
    if (data || !mat.ready) return;
    let alive = true;
    setBusy(true);
    fetchSuggestion({ speech: loadSpeech() })
      .then((r) => { if (alive) setData(r); })
      .finally(() => { if (alive) setBusy(false); });
    return () => { alive = false; };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // 노래는 따로 불러온다 — Deezer 왕복이 있어 느리고, 실패해도 위 제안은 살아야 한다.
  useEffect(() => {
    if (tracks || !mat.ready) return;
    let alive = true;
    fetchTracks({ speech: loadSpeech() }).then((r) => { if (alive && r?.ok) setTracks(r); });
    return () => { alive = false; };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (!mat.ready) return null;          // 기록이 없으면 아예 띄우지 않는다
  if (busy && !data) {
    return (
      <div className="mt-4 rounded-[18px] border border-line bg-[#141b2e] px-4 py-3 text-[11px] text-mut">
        최근 기록을 보고 오늘 해볼 만한 걸 고르는 중…
      </div>
    );
  }
  if (!data) return null;

  // 무거운 날 — 할 일 대신 그 말만 남긴다.
  if (data.care) {
    return (
      <div className="mt-4 rounded-[18px] border border-[#8B6CCF]/30 bg-[#161029] px-4 py-3.5">
        <p className="text-[12px] leading-relaxed text-sub">{data.reason}</p>
      </div>
    );
  }
  if (!data.ok) return null;

  return (
    <div data-tour="daily-suggest" className="mt-4 rounded-[18px] border border-line bg-[#141b2e] p-4">
      <div className="mb-2 flex items-center gap-1.5">
        <Sparkles size={14} className="text-[#EDA100]" />
        <span className="text-[12.5px] font-semibold text-ink">오늘 이런 건 어때요</span>
      </div>

      <div className="space-y-2">
        {data.items.map((it, i) => {
          const st = KIND_STYLE[it.kind] || KIND_STYLE.try;
          return (
            <div key={i} className="rounded-xl border border-white/[.06] bg-black/20 p-3">
              <div className="flex items-start justify-between gap-2">
                <p className="text-[12px] font-semibold text-ink">
                  <span className="mr-1.5">{st.icon}</span>{it.title}
                </p>
                <span
                  className="shrink-0 rounded-full px-2 py-0.5 text-[9px]"
                  style={{ color: st.color, background: `${st.color}1A` }}
                >
                  {it.kindLabel}
                </span>
              </div>
              {it.why && <p className="mt-1 text-[10.5px] leading-relaxed text-sub">{it.why}</p>}
              {it.how && <p className="mt-1 text-[10.5px] leading-relaxed text-mut">→ {it.how}</p>}
              {it.search && (
                <a
                  href={`https://www.google.com/search?q=${encodeURIComponent(it.search)}`}
                  target="_blank"
                  rel="noreferrer"
                  className="tap mt-1.5 inline-flex items-center gap-1 text-[10px] text-cyan"
                >
                  <Search size={11} /> {it.search}
                </a>
              )}
            </div>
          );
        })}
      </div>

      {/* 기분 전환용 노래 — 곡은 Deezer 에서 온 실재하는 값이라 링크가 바로 열린다. */}
      {tracks?.ok && tracks.items?.length > 0 && (
        <div className="mt-3 border-t border-white/[.06] pt-3">
          <div className="mb-1.5 flex items-center justify-between">
            <span className="text-[11.5px] font-semibold text-ink">🎧 지금 들을 만한 노래</span>
            {tracks.shift && (
              <span className="text-[9px] text-[#8FB4F0]">{SHIFT_LABEL[tracks.shift] || ""}</span>
            )}
          </div>
          {/* 일기에 음악 이야기가 없으면 기분 방향으로 고른다(seedFrom==="mood").
              그때도 "내가 적은 곡의 결"이라고 하면 거짓말이 된다. */}
          {tracks.seedFrom === "mood" ? (
            <p className="mb-1 text-[9.5px] text-mut">일기에 음악 이야기가 없어 지금 기분에 맞춰 골랐어요</p>
          ) : tracks.genres?.length > 0 ? (
            <p className="mb-1 text-[9.5px] text-mut">내가 적은 곡의 결 · {tracks.genres.join(", ")}</p>
          ) : null}
          {tracks.seedWhy && (
            <p className="mb-1.5 text-[9.5px] leading-relaxed text-mut">{tracks.seedWhy}</p>
          )}
          <div className="space-y-1.5">
            {tracks.items.map((t, i) => (
              <a
                key={i}
                href={t.link}
                target="_blank"
                rel="noreferrer"
                className="tap flex items-start gap-2.5 rounded-xl border border-white/[.06] bg-black/20 p-2.5 hover:border-[#8FB4F0]/40"
              >
                {t.cover
                  ? <img src={t.cover} alt="" className="h-9 w-9 shrink-0 rounded-md object-cover" />
                  : <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-white/5 text-[13px]">♪</span>}
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[11.5px] font-semibold text-ink">{t.title}</span>
                  <span className="block truncate text-[10px] text-sub">
                    {t.artist}{t.year ? ` · ${t.year}` : ""}{t.kind ? ` · ${t.kind}` : ""}
                  </span>
                  {/* 장르는 Deezer 가 준 사실값 — 판단(why)과 갈라 보이게 칩으로 둔다. */}
                  {t.genres?.length > 0 && (
                    <span className="mt-0.5 flex flex-wrap gap-1">
                      {t.genres.slice(0, 2).map((g) => (
                        <span key={g} className="rounded-full bg-[#8FB4F0]/15 px-1.5 py-px text-[8.5px] text-[#8FB4F0]">{g}</span>
                      ))}
                    </span>
                  )}
                  {t.why && <span className="mt-0.5 block text-[9.5px] leading-relaxed text-mut">{t.why}</span>}
                </span>
              </a>
            ))}
          </div>
        </div>
      )}

    </div>
  );
}
