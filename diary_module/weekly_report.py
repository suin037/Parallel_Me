# -*- coding: utf-8 -*-
"""weekly_report.py — 일주일치 일기 → 감정 변화 · 웰빙(건강) 리포트.

한 주(기본 7편)의 일기를 하이브리드 분석(로컬 우선 + 애매/저확신만 API 재확인)으로
매일 감정·valence를 뽑고, 주간 추세·변동성·대처 패턴을 집계한 뒤,
Claude API가 이를 통합한 '주간 웰빙 리포트'를 생성한다.

건강/웰빙 관점은 일기에서 실제로 드러난 신호(감정 궤적, 대처 균형, 통찰, 반추, 수면·
피로 언급 등)와 심리 이론 근거에 한정해 서술한다(없는 통계를 지어내지 않음).

입력:
    --sample                 내장 7일 예시(감정 곡선이 있는 현실적 샘플)
    --file <path>            일기 파일. 항목 구분은 '---' 줄 또는 빈 줄.
    --index-range 11:18      diary_eval.EVAL 에서 연속 구간(테스트용)

기타:
    --no-api                 API 없이 집계만(서사 생략, 키 불필요)
    --out report.md          파일로 저장

서사에는 anthropic + <repo>/.env 의 ANTHROPIC_API_KEY 필요(없으면 집계만 출력).
"""

import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DIARY = ROOT / "diary_module"
sys.path.insert(0, str(DIARY))
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from hybrid import analyze_hybrid, _load_dotenv   # noqa: E402

NARR_MODEL = "claude-sonnet-5"
NARR_SYSTEM = (
    "너는 한 주간의 감정 기록을 읽고 웰빙을 돌봐주는 따뜻하고 현실적인 조력자다. "
    "진단하지 않는다. 감정의 타당성을 먼저 인정하고, 일기에서 실제로 드러난 신호와 "
    "제공된 심리학 근거에만 기대어 이야기한다. 없는 사실이나 수치는 지어내지 않는다."
)

SAMPLE_WEEK = [
    ("월", "새 프로젝트가 시작됐다. 할 일이 많아 보여서 벌써부터 마음이 조금 무겁다. 그래도 해봐야지."),
    ("화", "일이 생각보다 훨씬 많다. 뭐부터 해야 할지 막막하고 하루 종일 초조했다. 잠도 설쳤다."),
    ("수", "회의에서 내 의견이 묵살당했다. 화가 나기도 하고 서운하기도 했다. 집에 와서도 계속 곱씹었다."),
    ("목", "몸이 너무 지친다. 아무것도 하기 싫고 자꾸 눈물이 났다. 다 그만두고 싶은 하루였다."),
    ("금", "친구한테 다 털어놨더니 조금 후련해졌다. 여전히 힘들지만 혼자가 아니라는 느낌은 들었다."),
    ("토", "밀린 잠을 자고 나니 좀 살 것 같다. 작은 일 하나를 끝냈더니 성취감이 있었다."),
    ("일", "한 주를 돌아봤다. 힘들었지만 그래도 버텼다. 다음 주는 좀 더 나눠서 해봐야겠다. 마음이 한결 가볍다."),
]


def _sparkline(values):
    bars = "▁▂▃▄▅▆▇█"
    out = []
    for v in values:
        idx = int(round((max(-1.0, min(1.0, v)) + 1) / 2 * (len(bars) - 1)))
        out.append(bars[idx])
    return "".join(out)


def _trend_label(valence_by_day):
    """일별 valence의 선형 기울기 → 개선/악화/유지."""
    if len(valence_by_day) < 2:
        return "판단 불가", 0.0
    x = np.arange(len(valence_by_day))
    slope = float(np.polyfit(x, valence_by_day, 1)[0])
    if slope > 0.03:
        return "개선 추세 ↗", slope
    if slope < -0.03:
        return "악화 추세 ↘", slope
    return "대체로 유지 →", slope


def _split_entries(raw):
    """원문 문자열 → 항목 리스트('---' 줄 우선, 없으면 빈 줄로 분리)."""
    chunks = [c.strip() for c in raw.split("\n---\n")]
    if len(chunks) == 1:
        chunks = [c.strip() for c in raw.split("\n\n")]
    return [c for c in chunks if c]


def load_entries(args):
    """[(label, text), ...] 반환."""
    if args.file:
        entries = _split_entries(Path(args.file).read_text(encoding="utf-8"))
        return [(f"D{i+1}", t) for i, t in enumerate(entries)]
    if args.stdin:
        print("일기를 붙여넣으세요. 항목은 빈 줄 또는 '---'로 구분. 끝나면 Ctrl+Z 후 Enter:\n")
        entries = _split_entries(sys.stdin.read())
        return [(f"D{i+1}", t) for i, t in enumerate(entries)]
    if args.index_range:
        a, b = args.index_range.split(":")
        from diary_eval import EVAL
        return [(f"#{i}", EVAL[i][1]) for i in range(int(a), int(b))]
    return list(SAMPLE_WEEK)   # 기본: 내장 샘플


def load_metrics(path, n):
    """건강지표 JSON → 길이 n 리스트(부족분 None). 리스트/라벨딕셔너리 모두 허용.

    예시: [{"sleep_score":72,"sleep_hours":5.5,"exercise_min":0}, ...]
    """
    if not path:
        return [None] * n
    import json
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):        # {"월": {...}, ...} 형태면 값만 순서대로
        data = list(data.values())
    out = list(data)[:n]
    return out + [None] * (n - len(out))


def _health_summary(days):
    """일별 건강지표 → (요약 텍스트 or '', 집계 dict). 지표 없으면 빈 문자열."""
    m = [d.get("metrics") for d in days]
    if not any(m):
        return "", {}
    def col(key):
        return [(d["label"], d["metrics"].get(key)) for d in days
                if d.get("metrics") and d["metrics"].get(key) is not None]
    sleep_h = col("sleep_hours")
    sleep_s = col("sleep_score")
    exer = col("exercise_min")
    agg = {}
    lines = ["[건강 지표]"]
    if sleep_h:
        vals = [v for _, v in sleep_h]
        agg["avg_sleep_hours"] = round(float(np.mean(vals)), 1)
        lines.append(f"  수면시간: 평균 {agg['avg_sleep_hours']}h · "
                     + " ".join(f"{l}:{v}h" for l, v in sleep_h))
        # 수면-기분 관계(≥3일)
        pair = [(d["metrics"]["sleep_hours"], d["valence"]) for d in days
                if d.get("metrics") and d["metrics"].get("sleep_hours") is not None]
        if len(pair) >= 3:
            xs, ys = zip(*pair)
            if np.std(xs) > 0 and np.std(ys) > 0:
                r = float(np.corrcoef(xs, ys)[0, 1])
                agg["sleep_valence_corr"] = round(r, 2)
                lines.append(f"  (수면시간↔기분 상관 {r:+.2f})")
    if sleep_s:
        vals = [v for _, v in sleep_s]
        agg["avg_sleep_score"] = round(float(np.mean(vals)), 1)
        lines.append(f"  수면점수: 평균 {agg['avg_sleep_score']} · "
                     + " ".join(f"{l}:{v}" for l, v in sleep_s))
    if exer:
        total = sum(v for _, v in exer)
        active = sum(1 for _, v in exer if v > 0)
        agg["exercise_total_min"] = total
        agg["exercise_days"] = active
        lines.append(f"  운동: 주 {active}일 · 총 {total}분 · "
                     + " ".join(f"{l}:{v}분" for l, v in exer))
    return "\n".join(lines), agg


def build_prompt(days, long=False):
    """일별 집계 dict 리스트 → 주간 웰빙 리포트 프롬프트. long=True면 상세본."""
    vals = [d["valence"] for d in days]
    trend, slope = _trend_label(vals)
    vol = float(np.std(vals))
    worst = min(days, key=lambda d: d["valence"])
    best = max(days, key=lambda d: d["valence"])
    from collections import Counter
    emo_ct = Counter(d["emotion"] for d in days)
    avg_cop = np.mean([d["coping"] for d in days if d["coping"] is not None] or [0])
    avg_ins = np.mean([d["insight"] for d in days if d["insight"] is not None] or [0])

    traj = " · ".join(f"{d['label']}:{d['emotion']}({d['valence']:+.2f})" for d in days)
    health_text, health_agg = _health_summary(days)
    health_note = (" 건강 지표가 주어졌으면 수면·운동을 감정 흐름과 연결해 해석하되, "
                   "주어지지 않은 지표는 언급하지 말 것.") if health_text else ""

    if long:
        intro = [
            "아래는 한 사람의 일주일치 감정 기록 요약이다. 이를 바탕으로 '주간 웰빙 리포트'를 써라.",
            "구성: (1) 이번 주 한 줄 요약  (2) 감정 흐름 서술  (3) 웰빙·건강 관점  "
            "(4) 다음 주 제안 1~2개. 각 항목 2~3문장, 따뜻하고 현실적으로. "
            "웰빙·건강 관점과 제안은 아래 '심리 근거'의 이론과 출처를 문장 안에 짧게 인용해 뒷받침하라. "
            "일기에 없는 통계·수치는 지어내지 말 것." + health_note + "\n",
        ]
    else:
        intro = [
            "아래는 한 사람의 일주일치 감정 기록 요약이다. 이를 바탕으로 '주간 웰빙 리포트'를 간결하게 써라.",
            "형식(각 항목 딱 1~2문장, 핵심만. 마크다운 제목·굵은 글씨 등 장식 금지):",
            "  · 요약: 이번 주 한 줄",
            "  · 흐름: 감정 변화 핵심만",
            "  · 웰빙: 근거 이론 1개 + 출처 짧게 인용",
            "  · 제안: 다음 주 행동 1개",
            "따뜻하되 군더더기 없이. 일기에 없는 통계·수치는 지어내지 말 것." + health_note + "\n",
        ]
    lines = [
        *intro,
        f"[감정 궤적] {traj}",
        f"[추세] {trend} (기울기 {slope:+.3f}) · [변동성] {vol:.2f}",
        f"[가장 힘든 날] {worst['label']}({worst['emotion']}, {worst['valence']:+.2f})",
        f"[가장 나은 날] {best['label']}({best['emotion']}, {best['valence']:+.2f})",
        f"[감정 분포] {dict(emo_ct)}",
        f"[대처 균형 평균] {avg_cop:+.2f} (양수=접근형, 음수=회피형) · [통찰 평균] {avg_ins:.3f}",
    ]
    if health_text:
        lines += ["", health_text]
    lines += [
        "",
        "[심리 근거 — 가장 힘든 날 기준]",
        worst.get("prompt_block") or "(근거 카드 없음)",
    ]
    meta = {"trend": trend, "slope": slope, "volatility": vol,
            "worst": worst["label"], "best": best["label"], "emo_ct": dict(emo_ct),
            "health": health_agg}
    return "\n".join(lines), meta


def generate(prompt, model=NARR_MODEL, long=False):
    import os
    if not os.getenv("ANTHROPIC_API_KEY"):
        return None, "ANTHROPIC_API_KEY 미설정"
    try:
        from anthropic import Anthropic
    except ImportError:
        return None, "anthropic 미설치"
    try:
        # thinking 끔: 짧은 생성엔 불필요하고, 켜두면 max_tokens를 생각에 소진해
        # 본문이 잘린다(sonnet-5는 기본 thinking on). 끄면 토큰 전량이 본문 + 비용↓.
        resp = Anthropic().messages.create(
            model=model, max_tokens=1600 if long else 350, system=NARR_SYSTEM,
            thinking={"type": "disabled"},
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(b.text for b in resp.content if b.type == "text").strip(), None
    except Exception as e:      # noqa: BLE001
        return None, f"API 오류: {e}"


def render(days, meta, narrative):
    L = ["=" * 62, "　　　　　　　주 간 감 정 · 웰 빙 리 포 트", "=" * 62, ""]
    vals = [d["valence"] for d in days]
    L.append("■ 감정 궤적")
    L.append("-" * 62)
    L.append(f"  {_sparkline(vals)}   (요일: {' '.join(d['label'] for d in days)})")
    for d in days:
        crisis = "  ⚠️위기" if d.get("safety") == "crisis" else (
            "  ·고통" if d.get("safety") == "high_distress" else "")
        esc = "  (API재확인)" if d.get("escalated") else ""
        L.append(f"  {d['label']}  {d['emotion']:>3}  valence {d['valence']:+.2f}"
                 f"{esc}{crisis}")
    L.append("")
    L.append(f"  추세: {meta['trend']}  |  변동성: {meta['volatility']:.2f}  |  "
             f"최저 {meta['worst']} · 최고 {meta['best']}")
    L.append(f"  감정 분포: {meta['emo_ct']}")
    h = meta.get("health") or {}
    if h:
        parts = []
        if "avg_sleep_hours" in h:
            parts.append(f"평균수면 {h['avg_sleep_hours']}h")
        if "avg_sleep_score" in h:
            parts.append(f"수면점수 {h['avg_sleep_score']}")
        if "exercise_days" in h:
            parts.append(f"운동 {h['exercise_days']}일/{h['exercise_total_min']}분")
        if "sleep_valence_corr" in h:
            parts.append(f"수면↔기분 {h['sleep_valence_corr']:+.2f}")
        L.append("  건강지표: " + " · ".join(parts))
    L.append("")
    L.append("■ 웰빙 리포트" + ("  (Claude 통합)" if narrative else ""))
    L.append("-" * 62)
    if narrative:
        for line in narrative.split("\n"):
            L.append("  " + line)
    else:
        L.append("  (서사 생략)")
    L.append("")
    L.append("=" * 62)
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--sample", action="store_true", help="내장 7일 예시 사용(기본)")
    g.add_argument("--file", help="일기 파일(항목 구분: '---' 줄 또는 빈 줄)")
    g.add_argument("--stdin", action="store_true",
                   help="표준입력(붙여넣기)으로 일기 받기 — 항목 구분 '---' 또는 빈 줄, 끝에 Ctrl+Z Enter")
    g.add_argument("--index-range", help="diary_eval.EVAL 연속구간, 예: 11:18")
    ap.add_argument("--metrics", help="건강지표 JSON(일별 sleep_score/sleep_hours/exercise_min). "
                    "삼성헬스 등에서 내보낸 값을 넣으면 웰빙 평가에 반영")
    ap.add_argument("--ckpt", default=str(ROOT / "model_v3_e6.pt"))
    ap.add_argument("--model", default=NARR_MODEL)
    ap.add_argument("--no-api", action="store_true", help="집계만(서사·에스컬레이션 생략)")
    ap.add_argument("--long", action="store_true",
                    help="상세본(토큰 많이 씀). 기본은 짧은 요약본")
    ap.add_argument("--out", help="리포트 저장 경로")
    args = ap.parse_args()
    _load_dotenv()

    entries = load_entries(args)

    from infer import DiaryAnalyzer
    az = DiaryAnalyzer(ckpt=args.ckpt, taxonomy=str(DIARY / "emotion_taxonomy.json"))

    metrics = load_metrics(args.metrics, len(entries))
    days = []
    for i, (label, text) in enumerate(entries):
        r = analyze_hybrid(az, text, allow_api=not args.no_api)
        ling = r.get("linguistic", {})
        days.append({
            "label": label,
            "text": text,
            "emotion": r["final_coarse"],
            "valence": r["valence_mean"],
            "coping": ling.get("coping_balance"),
            "insight": ling.get("insight_ratio"),
            "safety": r["psych"].get("safety_level"),
            "escalated": r["escalation"]["used"],
            "prompt_block": r["psych"].get("prompt_block", ""),
            "metrics": metrics[i],
        })

    prompt, meta = build_prompt(days, long=args.long)
    narrative, reason = (None, "생략")
    if not args.no_api:
        narrative, reason = generate(prompt, model=args.model, long=args.long)

    report = render(days, meta, narrative)
    if narrative is None and not args.no_api:
        report += f"\n(서사 미생성: {reason})\n"

    print("\n" + report)
    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
        print(f"\n저장: {args.out}")


if __name__ == "__main__":
    main()
