import { useEffect, useState } from "react";
import { analyzeCompany, formatWon, growthRate } from "../data/companyAnalysis.js";

// 기업 분석 — 공고에서 뽑힌 회사명으로 OpenDART 공시·재무를 불러와 보여준다.
// 숫자는 공시 원문 그대로, 해석만 AI가 한다. 근거(공시 원문 링크)를 함께 건다.
export default function CompanyAnalysis({ company, auto = false }) {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  // 이름이 정확히 안 맞을 때 후보를 직접 고르게 한다 — 서버가 임의로 고르면
  // '토스'를 물었는데 '비스토스' 공시가 그 회사인 척 나온다.
  const [choices, setChoices] = useState(null);

  // 전용 화면에서는 검색하자마자 바로 불러온다(버튼을 한 번 더 누르게 하지 않는다).
  useEffect(() => {
    if (auto && company) run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auto, company]);

  async function run(corpCode = null, pickedName = null) {
    if (busy) return;
    setBusy(true); setErr(null); setChoices(null);
    try {
      const res = await analyzeCompany(pickedName || company, corpCode);
      if (res.ok) setData(res);
      else if (res.reason === "no_dart_key") setErr("OpenDART 인증키가 아직 설정되지 않았어요.");
      else if (res.reason === "not_found") {
        setErr(`'${company}'을(를) 공시 목록에서 찾지 못했어요. 비상장이거나 이름이 다를 수 있어요.`);
      } else if (res.reason === "ambiguous") {
        setChoices(res.candidates || []);
        setErr(`'${company}'와 이름이 정확히 같은 회사가 공시에 없어요. 아래에서 골라주세요.`);
      } else if (res.reason === "no_data") {
        setErr(`'${res.name}'은 공시에 등록돼 있지만 공개된 재무·공시 자료가 없어요. 지어내지 않으려고 분석을 멈췄어요.`);
      } else setErr("기업 정보를 불러오지 못했어요.");
    } catch {
      setErr("분석 서버에 연결하지 못했어요.");
    } finally {
      setBusy(false);
    }
  }

  if (!company) return null;

  if (!data) {
    return (
      <div className="rounded-xl border border-white/[.07] bg-black/15 px-3 py-2.5">
        <p className="text-[10px] font-bold text-[#8B6CCF]">이 회사도 볼까요</p>
        <p className="mt-1 text-[11px] leading-relaxed text-sub">
          <b className="text-ink">{company}</b>의 공시·재무를 불러와 사업 흐름과 최근 관심사를 정리해요.
        </p>
        <button
          type="button"
          onClick={() => run()}
          disabled={busy}
          className="tap mt-2 w-full rounded-lg bg-white/10 py-2 text-[11px] font-bold text-ink disabled:opacity-50"
        >
          {busy ? "공시를 읽는 중…" : "기업 분석 불러오기"}
        </button>
        {err && <p className="mt-1.5 text-[10px] leading-relaxed text-[#FFB36B]">{err}</p>}
        {/* 비슷한 이름이 여럿일 때 — 서버가 대신 고르지 않고 여기서 사용자가 고른다. */}
        {choices?.length > 0 && (
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {choices.map((c) => (
              <button
                key={c.corp_code}
                type="button"
                onClick={() => run(c.corp_code, c.name)}
                className="tap rounded-full border border-white/[.12] px-2.5 py-1 text-[10px] text-sub hover:border-[#8B6CCF]"
              >
                {c.name}
              </button>
            ))}
          </div>
        )}
      </div>
    );
  }

  const fin = data.financials || [];
  const g = growthRate(fin, "revenue");
  const max = Math.max(...fin.map((r) => Math.abs(r.revenue || 0)), 1);

  return (
    <div className="rounded-xl border border-white/[.07] bg-black/15 px-3 py-2.5">
      <div className="flex items-baseline justify-between">
        <p className="text-[10px] font-bold text-[#8B6CCF]">기업 분석 · {data.name}</p>
        <span className="text-[9px] text-mut">OpenDART 공시</span>
      </div>

      {fin.length > 0 && (
        <>
          <div className="mt-2 flex items-end gap-1.5">
            {fin.map((r) => (
              <div key={r.year} className="flex flex-1 flex-col items-center gap-1">
                <div
                  className="w-full rounded-t bg-[#8B6CCF]/60"
                  style={{ height: `${Math.max(4, (Math.abs(r.revenue || 0) / max) * 46)}px` }}
                />
                <span className="text-[8px] text-mut">{String(r.year).slice(2)}년</span>
              </div>
            ))}
          </div>
          <p className="mt-1.5 text-[10px] text-sub">
            매출 {formatWon(fin[0]?.revenue)} → {formatWon(fin[fin.length - 1]?.revenue)}
            {g != null && <span className={g >= 0 ? "text-[#5DCAA5]" : "text-[#F0736F]"}> ({g >= 0 ? "+" : ""}{g.toFixed(1)}%)</span>}
          </p>
        </>
      )}

      {data.report?.trend && (
        <p className="mt-2 text-[11px] leading-relaxed text-sub">{data.report.trend}</p>
      )}
      {data.report?.focus && (
        <p className="mt-1.5 text-[11px] leading-relaxed text-sub">
          <b className="text-ink">최근 관심사</b> — {data.report.focus}
        </p>
      )}
      {data.report?.talking_points?.length > 0 && (
        <ul className="mt-2 space-y-1">
          {data.report.talking_points.map((t, i) => (
            <li key={i} className="text-[11px] leading-relaxed text-sub">· {t}</li>
          ))}
        </ul>
      )}

      {data.disclosures?.length > 0 && (
        <details className="mt-2">
          <summary className="cursor-pointer text-[10px] text-mut">근거 자료 · 최근 공시 {data.disclosures.length}건</summary>
          <ul className="mt-1.5 space-y-1">
            {data.disclosures.slice(0, 6).map((d, i) => (
              <li key={i} className="text-[10px] leading-relaxed text-mut">
                <span className="tabular-nums">{d.date}</span>{" "}
                {d.url ? (
                  <a href={d.url} target="_blank" rel="noreferrer" className="text-sub underline">{d.title}</a>
                ) : d.title}
              </li>
            ))}
          </ul>
        </details>
      )}

      <p className="mt-2 text-[9px] leading-relaxed text-mut">
        수치는 공시 원문 그대로이고 해석만 정리한 것입니다. 주가·투자 판단이나 합격 가능성을 예측하지 않습니다.
      </p>
    </div>
  );
}
