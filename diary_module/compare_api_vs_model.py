# -*- coding: utf-8 -*-
"""compare_api_vs_model.py — 로컬 감정모델 vs Claude API 판단 비교.

같은 일기 텍스트에 대해
  (1) 로컬 모델(klue/roberta 기반, diary_module)
  (2) Claude API(같은 6개 대분류로 직접 판단)
의 감정 라벨·valence 를 받아 아래를 계산한다.

  · 정확도 : 각각을 gold 라벨(diary_eval.EVAL) 과 비교 → accuracy, macro F1, 클래스별 F1
  · 일치도 : 모델 vs API 라벨 일치율 + Cohen's κ(우연 보정)
  · valence: 모델 vs API 상관계수 + 부호 일치율
  · 혼동   : 혼동행렬(모델↔gold, API↔gold, 모델↔API) + 불일치 사례

실행:
    pip install anthropic
    (PowerShell)  $env:ANTHROPIC_API_KEY="sk-..."
    (bash)        export ANTHROPIC_API_KEY=sk-...
    python diary_module/compare_api_vs_model.py

옵션:
    --model  claude-sonnet-5    API 판단에 쓸 모델(기본값)
    --limit  N                  앞 N건만(저렴한 시범용)
    --ckpt   PATH               로컬 모델 체크포인트(기본 <repo>/model_v3_e6.pt)
    --out    PATH               결과 JSON 저장 경로
    --no-api                    API 호출 없이 로컬 모델 vs gold 만(키 불필요, 스모크 테스트)

주의: --no-api 가 아니면 일기 원문이 Claude API 로 전송된다(EVAL 전량). 호출당 과금.
      판단 재현성을 위해 temperature=0 고정.
"""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
from sklearn.metrics import (accuracy_score, cohen_kappa_score,
                             confusion_matrix, f1_score)

ROOT = Path(__file__).resolve().parent.parent
DIARY = ROOT / "diary_module"
# diary_module 을 최우선(루트에도 동명 infer.py 가 있어 섀도잉 방지). ROOT 는 diary_eval 용으로 뒤에.
sys.path.insert(0, str(DIARY))
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

LABELS = ["분노", "슬픔", "불안", "상처", "당황", "기쁨"]
POS = "기쁨"

# API 에 제공할 6분류 정의(로컬 모델 taxonomy 와 동일 체계로 맞춤).
TAXONOMY_DESC = """분노: 화, 짜증, 좌절, 분함, 억울
슬픔: 우울, 낙담, 상실, 허무, 눈물
불안: 걱정, 초조, 두려움, 긴장, 막막함
상처: 서운함, 배신감, 소외감, 마음의 상처
당황: 곤란, 열등감, 부끄러움, 예상 밖 혼란
기쁨: 행복, 만족, 즐거움, 설렘, 뿌듯"""

API_SYSTEM = ("너는 한국어 일기의 감정을 분류하는 전문가다. "
              "반드시 지정된 6개 대분류 중 하나로만 답한다.")


def build_prompt(text):
    return (
        "다음 일기의 지배적 감정을 아래 6개 대분류 중 하나로 판단하라.\n\n"
        f"[감정 분류 체계]\n{TAXONOMY_DESC}\n\n"
        f"[일기]\n{text}\n\n"
        '출력은 JSON 한 줄로만: {"label": "<6개 중 하나>", "valence": <-1.0~1.0 실수>}\n'
        "valence 는 감정의 긍정(+)/부정(-) 정도다. 설명·다른 말은 절대 쓰지 말 것."
    )


def _load_dotenv():
    """의존성 없이 <repo>/.env 를 읽어 os.environ 에 채운다(이미 설정된 값은 유지).

    이렇게 하면 키를 명령어에 안 쓰고 .env 에만 두어 채팅·셸 히스토리 노출을 피한다.
    .env 는 .gitignore 처리되어 커밋되지 않는다.
    """
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
    """모델이 규격 밖 라벨을 주면 가장 근접한 6분류로 보정."""
    x = (x or "").strip()
    for lab in LABELS:
        if lab in x:
            return lab
    return "당황"


def call_api(client, model, text, retries=2):
    """(label, valence, raw) 반환. 실패 시 예외."""
    last = None
    for _ in range(retries + 1):
        try:
            # 최신 모델(sonnet-5/opus-4-8/fable-5)은 temperature 등 샘플링 파라미터를
            # 받지 않는다(보내면 400). 결정성은 프롬프트로만 유도.
            resp = client.messages.create(
                model=model, max_tokens=120,
                system=API_SYSTEM,
                messages=[{"role": "user", "content": build_prompt(text)}],
            )
            raw = resp.content[0].text.strip()
            s = raw[raw.find("{"): raw.rfind("}") + 1]   # 코드펜스/잡텍스트 방어
            obj = json.loads(s)
            label = obj.get("label", "").strip()
            if label not in LABELS:
                label = _closest_label(label)
            val = float(obj.get("valence", 0.0))
            return label, max(-1.0, min(1.0, val)), raw
        except Exception as e:      # noqa: BLE001 - 네트워크/파싱 폭넓게 재시도
            last = e
            time.sleep(1.5)
    raise RuntimeError(f"API 실패: {last}")


def _print_confusion(title, y_true, y_pred):
    cm = confusion_matrix(y_true, y_pred, labels=LABELS)
    print(f"\n[{title}]  (행=실제/기준, 열=예측)")
    head = "        " + "".join(f"{l:>6}" for l in LABELS)
    print(head)
    for i, lab in enumerate(LABELS):
        row = "".join(f"{cm[i][j]:>6}" for j in range(len(LABELS)))
        print(f"{lab:>6}  {row}")


def _report(name, y_true, y_pred):
    acc = accuracy_score(y_true, y_pred)
    f1m = f1_score(y_true, y_pred, labels=LABELS, average="macro", zero_division=0)
    per = f1_score(y_true, y_pred, labels=LABELS, average=None, zero_division=0)
    print(f"\n== {name} vs gold ==")
    print(f"  accuracy = {acc:.3f} | macro F1 = {f1m:.3f}")
    print("  클래스별 F1: " + " · ".join(f"{l} {v:.2f}" for l, v in zip(LABELS, per)))
    # 긍정/부정 2분류
    yb = [1 if y == POS else 0 for y in y_true]
    pb = [1 if p == POS else 0 for p in y_pred]
    print(f"  긍/부정 2분류 F1 = {f1_score(yb, pb, zero_division=0):.3f}")
    return {"accuracy": round(acc, 4), "macro_f1": round(f1m, 4),
            "per_class_f1": {l: round(float(v), 4) for l, v in zip(LABELS, per)}}


def _run_hybrid(data, az, args):
    """하이브리드 평가: 로컬 우선 + 애매/저확신만 API 재확인 → gold 대비 정확도 + 호출률."""
    from hybrid import should_escalate, api_classify

    gold, loc_pred, hyb_pred, rows = [], [], [], []
    n_api = 0
    for i, (sid, text, g) in enumerate(data, 1):
        r = az.analyze(text)
        loc = r["dominant"]["coarse"]
        esc, reason = should_escalate(r, conf_threshold=args.conf)
        final, used, api_lab = loc, False, None
        if esc and not args.no_api:
            api_lab, _ = api_classify(text, model=args.model)
            if api_lab:
                final, used = api_lab, True
                n_api += 1
        gold.append(g); loc_pred.append(loc); hyb_pred.append(final)
        arrow = f"→ API={api_lab} " if used else ""
        print(f"  [{i}/{len(data)}] gold={g:>2} loc={loc:>2} {arrow}final={final:>2} "
              f"[{'API' if used else 'loc'}]")
        rows.append({"sid": sid, "gold": g, "local": loc, "api": api_lab,
                     "final": final, "escalated": used, "text": text[:60]})

    print("\n" + "=" * 68)
    result = {"n": len(data), "mode": "hybrid", "conf_threshold": args.conf}
    result["local"] = _report("로컬 단독", gold, loc_pred)
    result["hybrid"] = _report(f"하이브리드(로컬+API 재확인)", gold, hyb_pred)
    _print_confusion("하이브리드 ↔ gold", gold, hyb_pred)

    rate = n_api / len(data) if data else 0
    print("\n" + "=" * 68)
    print("== 에스컬레이션(API 호출) ==")
    print(f"  API 호출 {n_api}/{len(data)}건 ({rate:.0%}) — 나머지는 로컬로 처리")
    fixed = sum(1 for row in rows if row["escalated"]
                and row["local"] != row["gold"] and row["final"] == row["gold"])
    broke = sum(1 for row in rows if row["escalated"]
                and row["local"] == row["gold"] and row["final"] != row["gold"])
    print(f"  API가 정정한 오답: +{fixed}건 | API가 망친 정답: -{broke}건 "
          f"| 순이득 {fixed - broke:+d}건")
    result["escalation"] = {"n_api": n_api, "rate": round(rate, 4),
                            "fixed": fixed, "broke": broke}

    result["rows"] = rows
    out = args.out.replace(".json", "_hybrid.json") if args.out.endswith(".json") else args.out
    Path(out).write_text(json.dumps(result, ensure_ascii=False, indent=2),
                         encoding="utf-8")
    print(f"\n결과 저장: {out}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="claude-sonnet-5")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--ckpt", default=str(ROOT / "model_v3_e6.pt"))
    ap.add_argument("--out", default=str(DIARY / "compare_result.json"))
    ap.add_argument("--no-api", action="store_true")
    ap.add_argument("--hybrid", action="store_true",
                    help="하이브리드 모드: 로컬 우선 + 애매/저확신만 API 재확인")
    ap.add_argument("--conf", type=float, default=0.50,
                    help="하이브리드 에스컬레이션 확신도 임계값")
    args = ap.parse_args()
    _load_dotenv()          # <repo>/.env 에 ANTHROPIC_API_KEY 가 있으면 자동 로드

    from diary_eval import EVAL
    data = EVAL[: args.limit] if args.limit else EVAL
    print(f"검증셋: {len(data)}건 | 로컬 모델: {Path(args.ckpt).name} | "
          f"API: {'(생략)' if args.no_api else args.model}")

    # ── 로컬 모델 로드 & 추론 ────────────────────────────────
    from infer import DiaryAnalyzer
    az = DiaryAnalyzer(ckpt=args.ckpt,
                       taxonomy=str(DIARY / "emotion_taxonomy.json"))

    if args.hybrid:
        _run_hybrid(data, az, args)
        return

    # ── API 클라이언트(선택) ────────────────────────────────
    client = None
    if not args.no_api:
        try:
            from anthropic import Anthropic
        except ImportError:
            print("\n[오류] anthropic 미설치 → `pip install anthropic` 후 재실행 "
                  "(또는 --no-api 로 로컬만 평가).")
            sys.exit(1)
        import os
        if not os.getenv("ANTHROPIC_API_KEY"):
            print("\n[오류] ANTHROPIC_API_KEY 미설정. "
                  "<repo>/.env 에 ANTHROPIC_API_KEY=sk-... 한 줄을 넣거나(.gitignore됨), "
                  '$env:ANTHROPIC_API_KEY="sk-..." 로 지정 후 재실행.')
            sys.exit(1)
        client = Anthropic()

    gold, m_pred, a_pred, m_val, a_val, rows = [], [], [], [], [], []
    for i, (sid, text, g) in enumerate(data, 1):
        r = az.analyze(text)
        mp = r["dominant"]["coarse"]
        mv = r["valence_mean"]
        ap_lab, av = None, None
        if client is not None:
            ap_lab, av, _ = call_api(client, args.model, text)
            print(f"  [{i}/{len(data)}] gold={g:>2} | 모델={mp:>2} | API={ap_lab:>2}")
        else:
            print(f"  [{i}/{len(data)}] gold={g:>2} | 모델={mp:>2}")
        gold.append(g); m_pred.append(mp); m_val.append(mv)
        if ap_lab is not None:
            a_pred.append(ap_lab); a_val.append(av)
        rows.append({"sid": sid, "gold": g, "model": mp, "model_valence": mv,
                     "api": ap_lab, "api_valence": av, "text": text[:60]})

    # ── 리포트 ───────────────────────────────────────────────
    print("\n" + "=" * 68)
    result = {"n": len(data), "model_ckpt": Path(args.ckpt).name}
    result["model"] = _report("로컬 모델", gold, m_pred)
    _print_confusion("모델 ↔ gold", gold, m_pred)

    if client is not None:
        result["api"] = _report(f"API({args.model})", gold, a_pred)
        _print_confusion("API ↔ gold", gold, a_pred)

        # 모델 vs API 일치도
        agree = np.mean([1 if a == b else 0 for a, b in zip(m_pred, a_pred)])
        kappa = cohen_kappa_score(m_pred, a_pred, labels=LABELS)
        print("\n" + "=" * 68)
        print("== 모델 ↔ API 일치도 ==")
        print(f"  라벨 일치율 = {agree:.3f} | Cohen's κ = {kappa:.3f}  "
              f"({_kappa_verdict(kappa)})")
        _print_confusion("모델(행) ↔ API(열)", m_pred, a_pred)

        # valence 상관
        mv_a, av_a = np.array(m_val), np.array(a_val)
        corr = float(np.corrcoef(mv_a, av_a)[0, 1]) if len(mv_a) > 1 else float("nan")
        sign = float(np.mean(np.sign(mv_a) == np.sign(av_a)))
        print("\n== valence 비교 (모델 ↔ API) ==")
        print(f"  피어슨 상관 = {corr:.3f} | 부호 일치율 = {sign:.3f}")

        result["agreement"] = {"label_agree": round(float(agree), 4),
                               "cohen_kappa": round(float(kappa), 4),
                               "valence_corr": round(corr, 4),
                               "valence_sign_agree": round(sign, 4)}

        # 불일치 사례(최대 12건)
        print("\n== 모델 ≠ API 불일치 사례 ==")
        n_dis = 0
        for row in rows:
            if row["api"] and row["model"] != row["api"]:
                mark = []
                if row["model"] == row["gold"]:
                    mark.append("모델○")
                if row["api"] == row["gold"]:
                    mark.append("API○")
                tag = f" [{'/'.join(mark)}]" if mark else " [둘다✗]"
                print(f"  gold={row['gold']:>2} 모델={row['model']:>2} "
                      f"API={row['api']:>2}{tag}  {row['text']}")
                n_dis += 1
                if n_dis >= 12:
                    break

    result["rows"] = rows
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2),
                              encoding="utf-8")
    print(f"\n결과 저장: {args.out}")


def _kappa_verdict(k):
    if k < 0.20: return "미약"
    if k < 0.40: return "약함"
    if k < 0.60: return "보통"
    if k < 0.80: return "상당함"
    return "거의 완전"


if __name__ == "__main__":
    main()
