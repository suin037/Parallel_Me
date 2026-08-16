# -*- coding: utf-8 -*-
"""hybrid.py — 로컬 모델 우선 + 선택적 API 재확인 파이프라인.

검증 결과(로컬 F1 0.636 vs API 0.770): 긍/부정·valence는 로컬이 API만큼 정확하고,
차이는 '상처·당황' 같은 애매한 부정감정 세분류에서만 크게 벌어진다.
그래서 전량 API를 쓰지 않고, 아래 조건일 때만 API로 재확인한다:

  1) 로컬 예측이 애매 구간(상처·당황 등)에 있거나
  2) 로컬 확신도(conf)가 임계값보다 낮을 때

그 외에는 로컬 결과를 그대로 신뢰 → 비용·프라이버시 노출 최소화, 정확도 이득은 대부분 확보.
최종 감정으로 심리 이론 RAG(psych_link)까지 연결한다.

사용:
    from infer import DiaryAnalyzer
    from hybrid import analyze_hybrid
    az = DiaryAnalyzer(ckpt="../model_v3_e6.pt")
    r = analyze_hybrid(az, "이직을 괜히 했나 계속 후회된다.")
    print(r["final_coarse"], r["escalation"], r["psych"]["cards"])

CLI:
    python diary_module/hybrid.py --text "..."
    python diary_module/hybrid.py --index 41           # 검증셋에서 선택
    python diary_module/hybrid.py --index 41 --no-api   # 로컬만(에스컬레이션 끔)
"""

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIARY = ROOT / "diary_module"
sys.path.insert(0, str(DIARY))
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from psych_link import link_psych   # noqa: E402

# ── 에스컬레이션 정책(운영 튜닝 지점) ──────────────────────────────────
ESCALATE_LABELS = {"상처", "당황"}   # API가 크게 앞서는 애매 구간
CONF_THRESHOLD = 0.50                # 로컬 확신도가 이 밑이면 재확인
API_MODEL = "claude-sonnet-5"

LABELS = ["분노", "슬픔", "불안", "상처", "당황", "기쁨"]
TAXONOMY_DESC = """분노: 화, 짜증, 좌절, 분함, 억울
슬픔: 우울, 낙담, 상실, 허무, 눈물
불안: 걱정, 초조, 두려움, 긴장, 막막함
상처: 서운함, 배신감, 소외감, 마음의 상처
당황: 곤란, 열등감, 부끄러움, 예상 밖 혼란
기쁨: 행복, 만족, 즐거움, 설렘, 뿌듯"""
API_SYSTEM = ("너는 한국어 일기의 감정을 분류하는 전문가다. "
              "반드시 지정된 6개 대분류 중 하나로만 답한다.")


def _load_dotenv():
    import os
    envf = ROOT / ".env"
    if not envf.exists():
        return
    for line in envf.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def _closest_label(x):
    x = (x or "").strip()
    for lab in LABELS:
        if lab in x:
            return lab
    return None


_client = None


def _get_client():
    """(client, None) 또는 (None, 사유). 최초 1회만 초기화."""
    global _client
    if _client is not None:
        return _client, None
    import os
    if not os.getenv("ANTHROPIC_API_KEY"):
        return None, "ANTHROPIC_API_KEY 미설정"
    try:
        from anthropic import Anthropic
    except ImportError:
        return None, "anthropic 미설치"
    _client = Anthropic()
    return _client, None


def api_classify(text, model=API_MODEL, retries=2):
    """일기 → (label, valence). 실패 시 (None, None)."""
    client, reason = _get_client()
    if client is None:
        return None, None
    prompt = (
        "다음 일기의 지배적 감정을 아래 6개 대분류 중 하나로 판단하라.\n\n"
        f"[감정 분류 체계]\n{TAXONOMY_DESC}\n\n"
        f"[일기]\n{text}\n\n"
        '출력은 JSON 한 줄로만: {"label": "<6개 중 하나>", "valence": <-1.0~1.0 실수>}\n'
        "설명·다른 말은 절대 쓰지 말 것."
    )
    for _ in range(retries + 1):
        try:
            resp = client.messages.create(
                model=model, max_tokens=120,
                system=API_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = resp.content[0].text.strip()
            obj = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
            label = obj.get("label", "").strip()
            if label not in LABELS:
                label = _closest_label(label)
            val = float(obj.get("valence", 0.0))
            return label, max(-1.0, min(1.0, val))
        except Exception:      # noqa: BLE001
            time.sleep(1.0)
    return None, None


def should_escalate(diary, conf_threshold=CONF_THRESHOLD,
                    escalate_labels=ESCALATE_LABELS):
    """로컬 결과 → (에스컬레이션 여부, 사유)."""
    dom = diary.get("dominant", {})
    coarse = dom.get("coarse")
    conf = dom.get("conf", 1.0)
    if coarse in escalate_labels:
        return True, f"애매 구간({coarse})"
    if conf < conf_threshold:
        return True, f"낮은 확신도({conf} < {conf_threshold})"
    return False, "로컬 신뢰"


def analyze_hybrid(analyzer, text, *, allow_api=True,
                   conf_threshold=CONF_THRESHOLD,
                   escalate_labels=ESCALATE_LABELS, model=API_MODEL, k=3):
    """로컬 분석 → (조건부)API 재확인 → 최종 감정으로 심리 RAG.

    반환 diary dict 에 추가되는 키:
      final_coarse : 최종 채택 감정(대분류)
      escalation   : {used, reason, local_coarse, api_coarse, api_valence, model, source}
      psych        : link_psych 결과(최종 감정 기준)
    """
    diary = analyzer.analyze(text)
    if "error" in diary:
        return diary

    local_coarse = diary["dominant"]["coarse"]
    esc_needed, reason = should_escalate(diary, conf_threshold, escalate_labels)

    final_coarse = local_coarse
    api_coarse, api_val, source = None, None, "local"
    if allow_api and esc_needed:
        api_coarse, api_val = api_classify(text, model=model)
        if api_coarse:
            final_coarse = api_coarse       # 애매 구간에선 API를 채택
            source = "api"
        else:
            reason += " · API 미응답→로컬 유지"

    diary["final_coarse"] = final_coarse
    diary["escalation"] = {
        "used": source == "api",
        "reason": reason if esc_needed else "로컬 신뢰(조건 미충족)",
        "local_coarse": local_coarse,
        "api_coarse": api_coarse,
        "api_valence": api_val,
        "model": model if source == "api" else None,
        "source": source,
    }

    # 최종 감정으로 심리 RAG 연결(dominant.coarse 를 최종값으로 반영).
    diary["dominant"]["coarse"] = final_coarse
    diary["psych"] = link_psych(diary, text=text, k=k)
    diary["dominant"]["coarse"] = local_coarse   # 원 예측 보존
    return diary


def _demo_line(diary):
    e = diary["escalation"]
    tag = f"API채택({e['api_coarse']})" if e["used"] else f"로컬유지"
    return (f"로컬={e['local_coarse']} → 최종={diary['final_coarse']} "
            f"[{tag}] · {e['reason']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--text")
    g.add_argument("--index", type=int)
    ap.add_argument("--ckpt", default=str(ROOT / "model_v3_e6.pt"))
    ap.add_argument("--conf", type=float, default=CONF_THRESHOLD)
    ap.add_argument("--no-api", action="store_true", help="에스컬레이션 끔(로컬만)")
    args = ap.parse_args()
    _load_dotenv()

    src = ""
    if args.index is not None:
        from diary_eval import EVAL
        sid, text, gold = EVAL[args.index]
        src = f"검증셋 #{args.index} (gold={gold})"
    else:
        text = args.text or "이직을 괜히 했나 계속 후회된다. 다 내 잘못 같고 자책만 하게 된다."

    from infer import DiaryAnalyzer
    az = DiaryAnalyzer(ckpt=args.ckpt, taxonomy=str(DIARY / "emotion_taxonomy.json"))
    r = analyze_hybrid(az, text, allow_api=not args.no_api, conf_threshold=args.conf)

    print("\n" + "=" * 60)
    if src:
        print(src)
    print(text[:70])
    print("-" * 60)
    print(_demo_line(r))
    p = r["psych"]
    print(f"심리 초점: {p['focus_indicator']}={p['level']} | "
          f"안전: {p['safety_level']}")
    print(f"이론카드: {[c['card_id'] for c in p['cards']]}")
