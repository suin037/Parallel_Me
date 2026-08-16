# -*- coding: utf-8 -*-
"""report_one.py — 일기 한 편 → 감정 리포트 한 장.

일기 텍스트를 받아
  1) 로컬 모델 감정 분석 (대분류/세부/valence 궤적/상황/언어지표)
  2) 심리 이론 RAG 근거 (관련 이론카드 + 행동 제안 + 출처)
  3) (선택) Claude API가 1·2를 통합한 따뜻한 서사
를 하나의 읽을 수 있는 리포트로 출력한다.

실행:
    # 자유 텍스트로
    python diary_module/report_one.py --text "오늘 발표를 망쳤다. 계속 후회된다."

    # gold 검증셋(diary_eval.EVAL)에서 index로 골라
    python diary_module/report_one.py --index 12

    # 서사(Claude) 없이 분석·근거만 (키 불필요)
    python diary_module/report_one.py --text "..." --no-narrative

    # 파일로 저장
    python diary_module/report_one.py --index 20 --out report.md

서사에는 anthropic 패키지 + <repo>/.env 의 ANTHROPIC_API_KEY 가 필요하다(없으면 자동 생략).
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIARY = ROOT / "diary_module"
sys.path.insert(0, str(DIARY))            # infer / slang / metrics / psych_link 우선
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))            # diary_eval(루트)

NARR_MODEL = "claude-sonnet-5"
NARR_SYSTEM = (
    "너는 일기를 읽고 마음을 헤아려주는 따뜻하고 현실적인 조력자다. "
    "진단하지 말고, 감정의 타당성을 먼저 인정한 뒤, 제공된 심리학 근거에 기대어 "
    "부드럽게 관점을 넓혀준다. 단정적 위로나 지시는 피한다."
)


def _load_dotenv():
    """<repo>/.env → os.environ (이미 설정된 값은 유지)."""
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


def _sparkline(values):
    """valence 궤적(-1~1)을 유니코드 막대로. 감정 흐름을 한눈에."""
    if not values:
        return ""
    bars = "▁▂▃▄▅▆▇█"
    out = []
    for v in values:
        idx = int(round((max(-1.0, min(1.0, v)) + 1) / 2 * (len(bars) - 1)))
        out.append(bars[idx])
    return "".join(out)


def build_narrative_prompt(diary, psych):
    dom = diary["dominant"]
    lines = [
        "다음은 한 사람의 일기와, 그에 대한 감정 분석·심리학 근거다. "
        "이를 바탕으로 3~4문장의 따뜻하고 현실적인 리포트를 써라. "
        "감정을 먼저 인정하고, 근거 카드 중 하나의 관점과 행동 제안을 자연스럽게 녹이되 "
        "반드시 그 출처를 문장 안에 짧게 인용하라.\n",
        f"[감정] 대분류={dom['coarse']}, 세부={dom['fine']}, "
        f"긍·부정도(valence)={diary['valence_mean']}",
        f"[상황] {diary['situation']['name']}",
        f"[언어 패턴] {diary['interpret']}",
        "",
        psych.get("prompt_block", "(근거 카드 없음)"),
    ]
    return "\n".join(lines)


def generate_narrative(diary, psych, model=NARR_MODEL):
    """Claude로 서사 통합. 실패/미설정 시 (None, 사유) 반환."""
    import os
    if not os.getenv("ANTHROPIC_API_KEY"):
        return None, "ANTHROPIC_API_KEY 미설정(.env 확인)"
    try:
        from anthropic import Anthropic
    except ImportError:
        return None, "anthropic 미설치 (pip install anthropic)"
    try:
        client = Anthropic()
        resp = client.messages.create(
            model=model, max_tokens=400,
            system=NARR_SYSTEM,
            thinking={"type": "disabled"},   # 짧은 생성 → 생각 끔(본문 잘림 방지 + 비용↓)
            messages=[{"role": "user",
                       "content": build_narrative_prompt(diary, psych)}],
        )
        return "".join(b.text for b in resp.content if b.type == "text").strip(), None
    except Exception as e:      # noqa: BLE001
        return None, f"API 오류: {e}"


def render(diary, psych, narrative, source_label):
    L = []
    add = L.append
    add("=" * 60)
    add("　　　　　　　일 기 감 정 리 포 트")
    add("=" * 60)
    if source_label:
        add(f"대상: {source_label}")
    add("")

    # 안전 분기 — 위기면 리포트 대신 지지 메시지.
    if psych.get("safety_level") == "crisis":
        add("⚠️  안전 안내")
        add("-" * 60)
        add(psych.get("crisis_message", ""))
        return "\n".join(L)

    dom = diary["dominant"]
    sit = diary["situation"]
    add("■ 감정 요약")
    add("-" * 60)
    add(f"  주 감정 : {dom['coarse']} › {dom['fine']}  "
        f"(확신도 {dom['conf']}, 신뢰도 F1 {dom['reliability']})")
    add(f"  상황    : {sit['name']}")
    add(f"  긍·부정도: 평균 {diary['valence_mean']}  "
        f"(변동 {diary['valence_std']})")
    add(f"  감정 궤적: {_sparkline(diary['valence_series'])}  "
        f"{diary['valence_series']}")
    add(f"  언어 패턴: {diary['interpret']}")
    if psych.get("safety_level") == "high_distress":
        add(f"  ※ 고통 신호 감지: {psych.get('safety_hits')} — 톤을 낮춰 다룸")
    add("")

    dist = diary.get("coarse_dist", {})
    top = sorted(dist.items(), key=lambda x: -x[1])[:3]
    add("  감정 분포: " + " · ".join(f"{k} {v:.0%}" for k, v in top))
    add("")

    add(f"■ 심리 해석 근거  (초점: {psych.get('focus_indicator')} "
        f"= {psych.get('level')})")
    add("-" * 60)
    cards = psych.get("cards", [])
    if not cards:
        add("  (매칭된 이론카드 없음)")
    for i, c in enumerate(cards, 1):
        add(f"  {i}) {c['theory_ko']} — {c['concept_ko']}  "
            f"(유사도 {c.get('similarity')})")
        add(f"     해석: {c.get('summary', '')}")
        acts = c.get("interventions", [])
        if acts:
            add(f"     행동 제안: {acts[0]}")
        add(f"     출처: {c.get('source', '')}")
        add("")

    add("■ 통합 리포트" + ("  (Claude 서사)" if narrative else ""))
    add("-" * 60)
    if narrative:
        for para in narrative.split("\n"):
            add("  " + para)
    else:
        add("  (서사 생략 — 아래 사유)")
    add("")
    add("=" * 60)
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--text", help="분석할 일기 텍스트")
    g.add_argument("--index", type=int, help="diary_eval.EVAL 에서 index 로 선택")
    g.add_argument("--stdin", action="store_true",
                   help="표준입력(붙여넣기)으로 일기 받기 — 입력 후 Ctrl+Z, Enter")
    ap.add_argument("--ckpt", default=str(ROOT / "model_v3_e6.pt"))
    ap.add_argument("--model", default=NARR_MODEL, help="서사 생성 모델")
    ap.add_argument("--no-narrative", action="store_true", help="Claude 서사 생략")
    ap.add_argument("--out", help="리포트를 저장할 파일 경로")
    args = ap.parse_args()

    _load_dotenv()

    # 입력 텍스트 결정
    source_label = ""
    if args.index is not None:
        from diary_eval import EVAL
        sid, text, gold = EVAL[args.index]
        source_label = f"검증셋 #{args.index} (출처 {sid}, gold={gold})"
    elif args.text:
        text = args.text
    else:
        text = ("오늘 발표를 망쳤다. 손이 떨려서 말이 자꾸 꼬였다. "
                "끝나고 화장실에 한참 있었다. 그래도 저녁에 친구가 밥 사줘서 조금 풀렸다.")
        source_label = "(예시 일기)"

    from infer import DiaryAnalyzer
    from psych_link import analyze_and_link
    az = DiaryAnalyzer(ckpt=args.ckpt,
                       taxonomy=str(DIARY / "emotion_taxonomy.json"))
    diary = analyze_and_link(az, text)
    if "error" in diary:
        print("분석 실패:", diary)
        return
    psych = diary["psych"]

    narrative, reason = (None, "생략됨")
    if not args.no_narrative and psych.get("safety_level") != "crisis":
        narrative, reason = generate_narrative(diary, psych, model=args.model)

    report = render(diary, psych, narrative, source_label)
    if narrative is None and not args.no_narrative and psych.get("safety_level") != "crisis":
        report += f"\n(서사 미생성 사유: {reason})\n"

    print("\n" + report)
    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
        print(f"\n저장: {args.out}")


if __name__ == "__main__":
    main()
