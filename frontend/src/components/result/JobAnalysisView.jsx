import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useResult } from "../../data/ResultContext.jsx";

// 결과 화면의 '공고 분석' 탭 — 입력에서 분석한 공고를 예측 수치와 나란히 다시 본다.
// 예측은 '비슷한 사람들이 어떻게 됐나'를, 이 탭은 '내가 가려는 그 자리는 어떤가'를 말한다.
export default function JobAnalysisView() {
  const { jobAnalyses, jobBusy, postings, profile, analyzePostings } = useResult();
  const navigate = useNavigate();
  const [at, setAt] = useState(0);
  const list = jobAnalyses || [];

  if (jobBusy && !list.length) {
    return (
      <p className="px-1 py-6 text-center text-[12px] text-mut">
        담아둔 공고 {postings?.length || 0}개를 읽고 있어요…
      </p>
    );
  }
  if (!list.length) {
    return (
      <div className="rounded-2xl border border-dashed border-white/10 px-3.5 py-6 text-center">
        <p className="text-[12px] text-sub">아직 분석한 공고가 없어요.</p>
        <p className="mt-1 text-[10px] leading-relaxed text-mut">
          시뮬레이션 입력 화면에서 공고를 담으면 여기서 요구 역량과 성향 대조를 볼 수 있어요.
        </p>
      </div>
    );
  }

  const j = list[Math.min(at, list.length - 1)];
  if (!j) return null;
  if (!j.ok) {
    return (
      <div className="rounded-2xl border border-white/10 bg-black/15 px-3.5 py-4">
        <p className="text-[12px] text-[#F0736F]">
          {j.label ? `'${j.label}' ` : ""}공고를 분석하지 못했어요
          {j.reason?.includes("529") || j.reason === "network" ? " (일시적인 연결 문제예요)" : ""}.
        </p>
        <button
          onClick={() => analyzePostings()}
          className="tap mt-2 text-[11px] font-bold text-cyan"
        >
          다시 시도하기 →
        </button>
      </div>
    );
  }

  const values = (profile?.career_values || []).slice(0, 3).map((v) => v.name);

  return (
    <div className="space-y-2.5">
      {/* 공고가 둘 이상이면 나란히 두고 오간다 — 같은 성향으로 어디가 더 맞는지 비교. */}
      {list.length > 1 && (
        <div className="flex flex-wrap gap-1.5">
          {list.map((item, i) => (
            <button
              key={i}
              type="button"
              onClick={() => setAt(i)}
              className={`tap rounded-full border px-3 py-1.5 text-[11px] transition-colors ${
                i === at ? "border-[#8B6CCF] bg-[#8B6CCF]/20 text-[#C7B5F2]" : "border-white/10 text-sub"
              }`}
            >
              {item.company || item.role || `공고 ${i + 1}`}
            </button>
          ))}
        </div>
      )}

      <div className="rounded-2xl border border-[#8B6CCF]/25 bg-[#8B6CCF]/[.07] px-3.5 py-3">
        <p className="text-[10px] tracking-[.12em] text-[#9F85DD]">JOB POSTING</p>
        <b className="mt-1 block text-[15px] text-ink">{j.role || "분석한 공고"}</b>
        {j.company && <span className="text-[11px] text-sub">{j.company}</span>}
        {values.length > 0 && (
          <p className="mt-1.5 text-[10px] text-mut">
            가치관 검사 반영: {values.join(" > ")}
          </p>
        )}
      </div>

      {/* 기업 분석은 창을 겹쳐 놓지 않고 전용 화면으로 보낸다(회사명은 들고 간다). */}
      {j.company && (
        <button
          type="button"
          onClick={() => navigate(`/company?name=${encodeURIComponent(j.company)}`)}
          className="tap flex w-full items-center justify-between rounded-2xl border border-white/[.07] bg-black/15 px-3.5 py-2.5 text-left"
        >
          <span className="text-[11px] leading-relaxed text-sub">
            <b className="text-ink">{j.company}</b>의 재무·공시도 볼까요
          </span>
          <span className="shrink-0 text-[11px] font-bold text-[#C7B5F2]">기업 분석 →</span>
        </button>
      )}

      {j.requirements?.length > 0 && (
        <Block title="요구 역량">
          {j.requirements.map((item, i) => (
            <li key={i} className="text-[12px] leading-relaxed text-sub">· {item}</li>
          ))}
        </Block>
      )}

      {j.fit?.length > 0 && (
        <Block title="나와 맞는 지점" tone="#5DCAA5">
          {j.fit.map((item, i) => (
            <li key={i} className="text-[12px] leading-relaxed text-sub">
              <b className="text-ink">{item.point}</b> — {item.why}
            </li>
          ))}
        </Block>
      )}

      {j.friction?.length > 0 && (
        <Block title="부딪힐 수 있는 지점" tone="#F0A45E">
          {j.friction.map((item, i) => (
            <li key={i} className="text-[12px] leading-relaxed text-sub">
              <b className="text-ink">{item.point}</b> — {item.why}
            </li>
          ))}
        </Block>
      )}

      {j.prep?.length > 0 && (
        <Block title="지원 전 준비">
          {j.prep.map((item, i) => (
            <li key={i} className="text-[12px] leading-relaxed text-sub">· {item}</li>
          ))}
        </Block>
      )}

      {j.questions?.length > 0 && (
        <Block title="예상 면접 질문">
          {j.questions.map((item, i) => (
            <li key={i} className="text-[12px] leading-relaxed text-sub">
              <b className="text-ink">Q. {item.q}</b>
              <span className="mt-0.5 block text-[11px] text-mut">→ {item.angle}</span>
            </li>
          ))}
        </Block>
      )}

      <p className="text-[10px] leading-relaxed text-mut">
        왼쪽 수치는 비슷한 사람들의 실측 데이터에서 온 것이고, 이 탭은 공고 원문과 당신의 기록·가치관 검사에서
        정리한 것입니다. 합격 가능성이나 회사 내부 사정을 예측하지 않습니다.
      </p>
    </div>
  );
}

function Block({ title, tone = "#8B6CCF", children }) {
  return (
    <div className="rounded-2xl border border-white/[.07] bg-black/15 px-3.5 py-3">
      <p className="text-[11px] font-bold" style={{ color: tone }}>{title}</p>
      <ul className="mt-2 space-y-1.5">{children}</ul>
    </div>
  );
}
