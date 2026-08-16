"""일기모듈(2번) 브리지.

일기 텍스트 → 감정/언어 신호 → (1) 엔진 입력(satis_*) 개인화 보강,
(2) 서사(Claude) 컨텍스트. 위기(L3) 감지 시 서사 대신 상담 안내(모듈 안전 규칙 준수).

감정 모델(DiaryAnalyzer: HF 비공개 ckpt + torch)이 있으면 그것을,
없으면 규칙기반(metrics·crisis·slang, 모델 불필요)으로 폴백한다.
  · 모델 체크포인트 경로는 환경변수 DIARY_CKPT 로 지정(없으면 규칙기반).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIARY_DIR = ROOT / "diary_module"
if DIARY_DIR.exists() and str(DIARY_DIR) not in sys.path:
    sys.path.insert(0, str(DIARY_DIR))

# 규칙기반 3종(모델 불필요) — crisis 는 stdlib, metrics/slang 은 kiwipiepy
_RULE_OK = True
try:
    import crisis as _crisis  # type: ignore
    import metrics as _metrics  # type: ignore
    import slang as _slang  # type: ignore
except Exception:
    _RULE_OK = False

_analyzer = None
_analyzer_tried = False


def _try_model():
    """감정 모델 로드 시도(1회). ckpt/torch 없으면 None."""
    global _analyzer, _analyzer_tried
    if _analyzer_tried:
        return _analyzer
    _analyzer_tried = True
    try:
        ckpt = os.environ.get("DIARY_CKPT")
        if not ckpt or not Path(ckpt).exists():
            return None
        from infer import DiaryAnalyzer  # torch 필요

        _analyzer = DiaryAnalyzer(ckpt=ckpt, taxonomy=str(DIARY_DIR / "emotion_taxonomy.json"))
    except Exception:
        _analyzer = None
    return _analyzer


def _v_to(v: float, lo: int, hi: int) -> int:
    """valence(-1~1) → [lo,hi] 정수 척도."""
    return int(round((v + 1) / 2 * (hi - lo) + lo))


def analyze_diary(text: str) -> dict:
    if not text or not text.strip():
        return {"available": False}

    # 위기 판정(항상, 규칙기반)
    crisis_level, block = 0, False
    if _RULE_OK:
        try:
            cr = _crisis.detect(text)
            crisis_level, block = cr.level, cr.block_report
        except Exception:
            pass

    # 1) 감정 모델 우선
    az = _try_model()
    if az is not None:
        try:
            r = az.analyze(text)
            return {
                "available": True,
                "source": "model",
                "crisis_level": r.get("crisis_level", crisis_level),
                "block_report": r.get("block_report", block),
                "dominant": r.get("dominant"),
                "situation": r.get("situation"),
                "valence": r.get("valence_mean"),
                "valence_std": r.get("valence_std"),
                "interpret": r.get("interpret"),
                "rag_triggers": r.get("rag_triggers", []),
                "slang": r.get("slang"),
            }
        except Exception:
            pass

    # 2) 규칙기반 폴백
    if not _RULE_OK:
        return {"available": False, "reason": "diary 의존성(kiwipiepy 등) 미설치"}
    m = _metrics.analyze_text(text)
    sp = _slang.slang_polarity(text)
    v = float(m.get("emotion_valence", 0.0))
    if sp["slang_pos"] or sp["slang_neg"]:
        sv = (sp["slang_pos"] - sp["slang_neg"]) / max(sp["slang_pos"] + sp["slang_neg"], 1)
        v = round((v + sv) / 2, 3)
    return {
        "available": True,
        "source": "rule",
        "crisis_level": crisis_level,
        "block_report": block,
        "valence": v,
        "interpret": _metrics.interpret(m),
        "linguistic": m,
        "rag_triggers": _metrics.rag_triggers(m),
        "slang": sp,
        "note": "감정 모델 미탑재 — 규칙기반(언어지표·슬랭·위기) 신호. valence는 근사치, "
        "정식 감정분류는 DIARY_CKPT 지정 시 활성화.",
    }


def to_profile_signals(diary: dict) -> dict:
    """일기 valence → satis 근사. 호출측이 profile 의 None 필드만 채우는 데 사용."""
    if not diary.get("available") or diary.get("valence") is None:
        return {}
    v = float(diary["valence"])
    return {
        "satis_overall": _v_to(v, 1, 5),  # 직무만족 1~5
        "life_satis": _v_to(v, 1, 7),  # 삶의만족 1~7
        "happy": _v_to(v, 1, 7),  # 행복감 1~7
    }


def diary_context_line(diary: dict) -> str:
    """서사 프롬프트에 넣을 한 줄 요약."""
    if not diary.get("available"):
        return ""
    parts = [f"valence {diary.get('valence')}"]
    if diary.get("interpret"):
        parts.append(str(diary["interpret"]))
    dom = diary.get("dominant") or {}
    if dom:
        parts.append(f"주정서 {dom.get('display') or dom.get('coarse')}")
    if diary.get("crisis_level"):
        parts.append(f"위기레벨 {diary['crisis_level']}")
    trig = diary.get("rag_triggers") or []
    if trig:
        parts.append("신호:" + ",".join(trig[:3]))
    return " · ".join(str(p) for p in parts)


def crisis_message(level: int) -> str:
    if _RULE_OK:
        try:
            return _crisis.support_message(level)
        except Exception:
            pass
    return "지금 많이 힘드시다면 자살예방 상담전화 109(24시간)로 연락해 주세요. 혼자 견디지 않으셔도 됩니다."
