import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronRight } from "lucide-react";
import { useResult } from "../../data/ResultContext.jsx";
import {
  computeDiarySignals, valueGap, interpretSignals,
  domainAnalysis, domainReport, detectRelationSubtype, dominantDomain,
} from "../../data/diarySignals.js";
import { domainLabel } from "../../data/choices.js";
import { PLANETS } from "../../data/result.js";

// 입력 분야(LIFE_DOMAINS 9종) → 일기 태깅 행성(5종) 매핑. 일기는 domain_tag 로 5개 키로만 태깅됨.
const LIFE_TO_PLANET = {
  career: "career", finance: "career", business: "career",
  education: "growth", long_term_values: "growth",
  relationship: "relation", health: "health",
  housing: "life", lifestyle: "life",
};

// ── 결과 화면 "내 기록으로 본 이 선택" (3층 중 2층) ──
// 이 카드는 '이 갈림길'이 있어야만 성립하는 것만 다룬다 —
// 입력에서 감지된 분야로 좁힌 신호와, 그걸 이 비교에 대입한 해석.
//
// 기록 자체의 흐름(월별 추이·감정·대표 기록·기분 그래프)은 여기가 아니라 나의 우주(행성)에 있다.
// 예전엔 같은 domainReport/그래프를 두 화면에서 그대로 반복했고, 그래서 기록을 보려면
// 시뮬레이션을 한 번 돌려야 하는 순서가 됐다. 기록은 시뮬과 무관하게 쌓이는 자산이라
// 진입점이 행성이어야 맞다. 여기선 두 줄 요약과 링크만 남긴다.
//
// 정직선: 예측 '숫자'를 바꾸지 않는다. 최근 일기에서 "드러난" 상태만 보여준다.
export default function DiarySignalCard() {
  const navigate = useNavigate();
  const { profile, scenarioDomains, choices, scenarioTexts } = useResult();

  // 입력에서 자동 감지된 분야 → 대표 분야 1개 → 행성 키
  const inputKeys = useMemo(
    () => [...new Set([...(scenarioDomains?.a || []), ...(scenarioDomains?.b || [])])],
    [scenarioDomains],
  );
  const primaryLife = inputKeys[0] || null;
  const detected = primaryLife ? LIFE_TO_PLANET[primaryLife] || null : null;

  // 감지 실패 시 예전엔 무조건 "career" 로 떨어뜨렸다. 관계 고민을 입력해도 이직 신호
  // 막대가 뜨는 오분류였다. 이제는 최근 기록에서 실제로 우세한 영역으로 폴백하고,
  // 폴백일 때는 '이 갈림길 기준 해석'(진로 신호·준비 상태)을 아예 내보내지 않는다 —
  // 그 해석은 입력에서 진로 계열이 확인됐을 때만 근거가 있다.
  const fallback = useMemo(() => (detected ? null : dominantDomain({ windowDays: 28 })), [detected]);
  const planetKey = detected || fallback;

  // 관계면 입력 텍스트에서 하위유형(연인/가족/친구/직장) 감지 → 그 유형만 분석
  const subtype = useMemo(() => {
    if (detected !== "relation") return null;
    const txt = `${choices?.a || ""} ${choices?.b || ""} ${scenarioTexts?.a || ""} ${scenarioTexts?.b || ""}`;
    return detectRelationSubtype(txt);
  }, [detected, choices, scenarioTexts]);

  const planetLabel = PLANETS.find((p) => p.key === planetKey)?.label || null;
  const fieldLabel = subtype
    ? `관계 · ${subtype}`
    : detected
      ? domainLabel(primaryLife)
      : planetLabel;

  const isCareer = detected === "career";
  const sig = useMemo(() => computeDiarySignals({ windowDays: 28 }), []);
  const gap = useMemo(() => valueGap(profile, sig), [profile, sig]);
  const shown = (sig.signals || []).filter((x) => x.days > 0).slice(0, 4);
  const hasJobSignal = sig.ok && (sig.jobChangeDays > 0 || shown.length > 0);
  const interp = useMemo(() => (isCareer && hasJobSignal ? interpretSignals(sig, gap) : null), [isCareer, hasJobSignal, sig, gap]);
  const toneColor = { caution: "#F0C36B", go: "#5DCAA5", mid: "#8B6CCF" };

  const anal = useMemo(
    () => (planetKey ? domainAnalysis(planetKey, undefined, subtype) : { ok: false, n: 0 }),
    [planetKey, subtype],
  );

  // 분야도 못 잡고 기록도 없으면 읽을 게 없다 — 빈 카드를 띄우느니 기록을 권한다.
  if (!planetKey) {
    return (
      <div className="mb-3 rounded-2xl border border-line bg-[#101827] p-3.5">
        <div className="text-[13px] font-bold text-ink">🧭 내 기록으로 본 이 선택</div>
        <p className="mt-1.5 text-[11px] leading-relaxed text-mut">
          아직 이 갈림길과 이어 볼 기록이 없어요. 홈에서 요즘 고민을 남기면 다음 비교부터
          통계 결과를 내 기준으로 읽을 수 있어요.
        </p>
      </div>
    );
  }

  return (
    <div className="mb-3 rounded-2xl border border-line bg-[#101827] p-3.5">
      <div className="flex items-center justify-between">
        <div className="text-[13px] font-bold text-ink">🧭 내 기록으로 본 이 선택</div>
        <span className="text-[10px] text-mut">{fieldLabel}</span>
      </div>
      <p className="mt-1 text-[10.5px] leading-relaxed text-mut">
        {subtype ? (
          <>이 갈림길을 <b className="text-sub">{subtype} 관계</b>로 보고, <b className="text-sub">{subtype}</b> 관련 일기만 골라 읽었어요.</>
        ) : detected ? (
          <>이 갈림길을 <b className="text-sub">{fieldLabel}</b> 분야로 보고, 그 분야 일기를 읽었어요.</>
        ) : (
          <>입력에서 분야가 뚜렷하지 않아, 최근 가장 많이 기록한 <b className="text-sub">{fieldLabel}</b> 영역을 대신 보여드려요.</>
        )}
      </p>

      {!anal.ok ? (
        <p className="mt-2 text-[11px] leading-relaxed text-mut">
          아직 <b className="text-sub">{fieldLabel}</b> 분야 일기가 없어요. 홈에서 이 분야 기록을 남기면
          이 예측을 내 기준으로 읽을 수 있어요.
        </p>
      ) : (
        <>
          {/* ── 이 갈림길 기준 해석 — 입력에서 진로 계열이 감지됐을 때만 ── */}
          {isCareer && hasJobSignal && (
            <>
              {sig.jobChangeDays >= 1 && (
                <p className="mt-2 text-[11.5px] leading-relaxed text-sub">
                  최근 {sig.windowDays}일 동안 <b className="text-cyan">이직 고민이 {sig.jobChangeDays}일</b> 나타났어요.
                  {sig.jobChangeDays >= 3 && " 지금 이 비교가 마침 필요한 시점 같아요."}
                </p>
              )}
              {shown.length > 0 && (
                <div className="mt-2.5 space-y-1.5">
                  {shown.map((s) => (
                    <div key={s.key} className="flex items-center gap-2">
                      <span className="w-[68px] shrink-0 text-[11px] text-sub">{s.label}</span>
                      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-[#223047]">
                        <div className="h-full rounded-full bg-[#8B6CCF]"
                          style={{ width: `${Math.min(100, Math.round(s.intensity * 100))}%` }} />
                      </div>
                      <span className="w-[34px] shrink-0 text-right text-[10px] tabular-nums text-mut">{s.days}일</span>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}

          {isCareer && interp && (
            <div className="mt-3 border-t border-line pt-2.5">
              <div className="text-[11px] font-bold text-ink">🧭 그래서 — 내 기록으로 본 해석</div>
              <p className="mt-1.5 text-[11.5px] leading-relaxed text-sub">
                <b style={{ color: toneColor[interp.readiness.tone] }}>준비 상태 · </b>{interp.readiness.text}
              </p>
              <div className="mt-1.5 text-[11px] text-sub">
                <b className="text-mut">우선 확인할 조건</b>
                <ul className="mt-1 space-y-0.5">
                  {interp.conditions.map((c, i) => (
                    <li key={i} className="flex gap-1.5 leading-relaxed"><span className="text-mut">·</span><span>{c}</span></li>
                  ))}
                </ul>
              </div>
              {interp.valueNote && <p className="mt-1.5 text-[10px] leading-relaxed text-mut">{interp.valueNote}</p>}
            </div>
          )}

          {/* ── 기록 요약 두 줄 + 행성으로 보내는 링크 ──
              그래프·월별 추이·대표 기록은 행성 패널이 더 깊게 보여준다. 여기선 되풀이하지 않는다. */}
          <div className={`${isCareer && (hasJobSignal || interp) ? "mt-3 border-t border-line pt-2.5" : "mt-2.5"}`}>
            <p className="text-[11.5px] leading-relaxed text-sub">{domainReport(anal, fieldLabel)}</p>
            <button
              type="button"
              onClick={() => navigate(`/my?planet=${planetKey}`)}
              className="tap mt-1.5 flex items-center gap-0.5 text-[11px] font-semibold text-cyan"
            >
              나의 우주에서 {fieldLabel} 기록 전체 보기
              <ChevronRight size={13} />
            </button>
          </div>
        </>
      )}

      <p className="mt-2.5 text-[9.5px] leading-relaxed text-mut/80">
        일기에서 드러난 주제예요. 예측 <b>숫자를 바꾸지 않고</b>, 무엇을 비교할지 제안하고 통계 결과를 내 기준으로 읽는 데 씁니다.
      </p>
    </div>
  );
}
