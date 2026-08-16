# -*- coding: utf-8 -*-
"""disposition_model.py — 개인 성향 파악 모델 (단일 진입점).

온보딩 가치순위 + 질문형 일기 → 성향 프로파일 + 이직 서사용 재료.
흩어진 파이프라인(value_ranking·aggregate·disposition_llm·disposition)을 하나의
호출 가능한 '모델'로 묶는다. 로직은 각 모듈에 있고 여기선 오케스트레이션만(중복 없음).

엔진(정확성 우선): 가치=온보딩 강제순위(주) · 대처/스타일/이직렌즈=LLM 구조화 추출.
신뢰성 가드: 스키마 검증 · 전이오류 재시도 · 갱신 블렌딩(가치는 온보딩 종속) ·
            confidence(데이터량×추출확신) · robust(2회 추출 교차확인).

로컬 모델 증류(API 뗌)는 후속 — 이 모델의 출력이 그 학습 라벨이 된다.

사용:
    from qmode.disposition_model import DispositionModel
    m = DispositionModel()
    prof = m.analyze(ranked_card_ids, sessions)     # sessions: analyze_session 결과들
    prof["jobchange_material"]   # ← suin 예측서사에 끼울 재료
    prof["confidence"]           # 얼마나 믿을지
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DIARY = HERE.parent
if str(DIARY) not in sys.path:
    sys.path.insert(0, str(DIARY))

import metrics                                                   # noqa: E402
from qmode import value_ranking, disposition                    # noqa: E402
from qmode import disposition_llm as _llm                        # noqa: E402
from qmode import mbti as _mbti                                  # noqa: E402
from qmode.aggregate import accumulate, classify_envy           # noqa: E402


def _merge_mbti(extract, mprior):
    """LLM 추출에 MBTI prior 병합. 결정방식·위험감수는 LLM 우선(일기>MBTI),
    LLM에 없으면(콜드스타트) MBTI로 채운다. MBTI 전달 톤은 항상 얹는다."""
    if not mprior:
        return extract
    eff = dict(extract or {})
    eff["coping"] = (extract or {}).get("coping", {}) or {}
    eff["value_axes"] = (extract or {}).get("value_axes", {}) or {}
    jc = dict((extract or {}).get("job_change") or {})
    if not jc.get("decision_style"):
        jc["decision_style"] = mprior["decision_style"]
    if jc.get("risk_tolerance") is None:
        jc["risk_tolerance"] = mprior["risk_tolerance"]
    if not jc.get("protect_most") and (extract or {}).get("job_change", {}).get("protect_most"):
        jc["protect_most"] = extract["job_change"]["protect_most"]
    eff["job_change"] = jc
    eff["delivery_flags"] = list((extract or {}).get("delivery_flags") or []) + mprior["delivery_flavor"]
    return eff


def _rows_from_sessions(sessions):
    """세션들 → accumulate 입력. metrics 없으면 답변에서 계산(자체완결)."""
    rows = []
    for s in sessions:
        for it in s.get("items", []):
            if it.get("skipped"):
                continue
            text = it.get("answer", "")
            m = it.get("metrics") or metrics.analyze_text(text)
            rows.append({"date": s.get("date"), "question_id": it.get("question_id"),
                         "source": "question", "text": text, "metrics": m})
        f = s.get("free")
        if f and f.get("answer"):
            m = f.get("metrics") or metrics.analyze_text(f["answer"])
            rows.append({"date": s.get("date"), "question_id": None, "source": "free",
                         "text": f["answer"], "metrics": m})
    return rows


def _core_agree(a, b):
    """두 추출의 핵심 3차원 일치 여부(대처·결정·위험감수도±0.15)."""
    if not a or not b:
        return False
    ja, jb = a.get("job_change", {}), b.get("job_change", {})
    rt_a, rt_b = ja.get("risk_tolerance"), jb.get("risk_tolerance")
    return (a["coping"]["direction"] == b["coping"]["direction"]
            and ja.get("decision_style") == jb.get("decision_style")
            and rt_a is not None and rt_b is not None and abs(rt_a - rt_b) <= 0.15)


class DispositionModel:
    """개인 성향 파악 모델. analyze()가 성향 프로파일 + 이직 재료를 돌려준다."""

    def __init__(self, model: str = "claude-sonnet-5"):
        self.model = model

    # ── 메인 ────────────────────────────────────────────────────────
    def analyze(self, ranked_cards, sessions, *, mbti: str | None = None,
                use_llm: bool = True, robust: bool = False, span_label: str = "") -> dict:
        """
        ranked_cards : 온보딩 가치순위(카드 id 리스트). 없으면(None) 균등 prior.
        sessions     : session.analyze_session 결과 리스트(items[].answer/metrics 포함).
        mbti         : 'INTJ' 등(선택). 스타일 차원(결정·위험·톤)의 초기 prior — 일기가 갱신.
        use_llm      : False면 온보딩·지표만(오프라인 폴백, 대처/이직렌즈 없음).
        robust       : True면 추출 2회 → 핵심차원 불일치 시 confidence 강등.
        """
        # 1) 가치 = 온보딩 강제순위(주). 없으면 균등.
        if ranked_cards:
            vw = value_ranking.axis_weights(ranked_cards)
        else:
            vw = {a: 1 / len(value_ranking.AXES) for a in value_ranking.AXES}

        # 2) 일기 누적(길이게이트·부러움 분기)
        agg = accumulate(_rows_from_sessions(sessions))
        n = agg.get("n_answers", 0)

        # 3) LLM 구조화 추출(대처·스타일·이직렌즈) — 정확성의 핵심
        extract, err, stable = None, None, None
        if use_llm:
            extract, err = _llm.extract(sessions, model=self.model, span_label=span_label)
            if robust and extract:
                second, _ = _llm.extract(sessions, model=self.model, span_label=span_label)
                stable = _core_agree(extract, second)

        # 4) 갱신 블렌딩(가치는 온보딩 종속, α상한)
        blended = _llm.blend_weights(vw, extract, n_answers=n)
        weights = blended["weights"]

        # 5) MBTI 스타일 prior 병합 (일기>MBTI: 있으면 LLM 우선, 없으면 MBTI로 채움)
        mprior = _mbti.prior(mbti)
        effective = _merge_mbti(extract, mprior)

        # 6) confidence — 데이터량 × 추출확신 (robust면 불일치 시 감점)
        conf = self._confidence(n, extract, stable)

        # 7) 이직 서사용 재료(personalize/suin에 넘길 블록) — MBTI 병합본 사용
        material = disposition.build_jobchange_material(
            weights, effective, decided_by=blended["note"])

        jc = (effective or {}).get("job_change", {})
        cop = (effective or {}).get("coping", {})
        return {
            "value_weights": weights,
            "value_order": value_ranking.narrate_order(weights),
            "coping": cop.get("direction"),
            "risk_tolerance": jc.get("risk_tolerance"),
            "decision_style": jc.get("decision_style"),
            "protect_most": jc.get("protect_most"),
            "delivery": disposition.delivery_from_llm(effective),
            "summary": (extract or {}).get("summary"),
            "mbti": (mprior or {}).get("mbti"),
            "mbti_note": (mprior or {}).get("note"),
            "n_answers": n,
            "confidence": conf,
            "consistency_ok": stable,
            "envy": agg.get("envy"),
            "jobchange_material": material,
            "blend_note": blended["note"],
            "raw_extract": extract,
            "extract_error": err,
        }

    @staticmethod
    def to_personalize_inputs(prof: dict) -> dict:
        """analyze() 결과 → 팀원 personalize.build_personalization 입력(정본 어댑터).

        가치는 내 쪽에서 이미 온보딩⊕일기 블렌딩(α≤0.3)했으므로 value_weights로 넘기고
        diary_weights=None (personalize 재블렌딩 방지 — 화제빈도 오독 재발 차단).
        스타일·이직렌즈·MBTI는 disposition_block에 이미 녹아 있다.
        """
        return {
            "value_weights": prof.get("value_weights"),
            "diary_weights": None,
            "n_answers": prof.get("n_answers", 0),
            "disposition_block": prof.get("jobchange_material", ""),
        }

    # ── confidence ─────────────────────────────────────────────────
    @staticmethod
    def _confidence(n_answers, extract, stable):
        """0~1. 데이터 적거나·추출 확신 낮거나·재현 불일치면 낮춘다."""
        data = min(1.0, n_answers / 40.0)                 # ~40답변이면 충분
        if not extract:
            return round(0.3 * data, 2)                    # 온보딩만 → 낮게
        jc = extract.get("job_change", {})
        cop = extract.get("coping", {})
        c = [cop.get("confidence", 0.5), jc.get("confidence", 0.5)]
        ext_conf = sum(c) / len(c)
        score = data * ext_conf
        if stable is False:                                # robust 검사 불일치
            score *= 0.7
        level = "높음" if score >= 0.6 else "보통" if score >= 0.35 else "낮음"
        return {"score": round(score, 2), "level": level,
                "note": f"데이터 {n_answers}답변 · 추출확신 {ext_conf:.2f}"
                        + ("" if stable is None else f" · 재현 {'일치' if stable else '불일치'}")}


if __name__ == "__main__":
    import argparse, importlib.util, json
    ap = argparse.ArgumentParser()
    ap.add_argument("persona", nargs="?", default="P1_stability")
    ap.add_argument("--mbti", default=None, help="예: INTJ (스타일 prior)")
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--robust", action="store_true")
    args = ap.parse_args()

    ds = HERE / "dataset"
    spec = importlib.util.spec_from_file_location("build", ds / "build.py")
    build = importlib.util.module_from_spec(spec); spec.loader.exec_module(build)

    diary = build.load_diary(args.persona)
    sessions, _ = build.to_sessions_and_rows(diary)
    ranked = build.personas.PERSONAS[args.persona]["ranked"]

    m = DispositionModel()
    prof = m.analyze(ranked, sessions, mbti=args.mbti, use_llm=not args.no_llm,
                     robust=args.robust,
                     span_label=f"({build.personas.PERSONAS[args.persona]['label']})")
    print(f"=== 성향 프로파일 · {args.persona}"
          + (f" · MBTI {prof['mbti']}" if prof.get("mbti") else "") + " ===")
    for k in ("coping", "risk_tolerance", "decision_style", "protect_most",
              "summary", "n_answers"):
        print(f"  {k}: {prof[k]}")
    print(f"  confidence: {prof['confidence']}")
    print(f"  value_order: {' > '.join(prof['value_order'])}")
    print("\n--- 이직 재료(suin에 넘길 것) ---")
    print(prof["jobchange_material"])
