# -*- coding: utf-8 -*-
"""
run_eval.py — 실제 일기 기준 성능 측정
사용법: python3 run_eval.py
"""
from collections import Counter
from sklearn.metrics import (classification_report, confusion_matrix,
                             f1_score, accuracy_score)
from infer import DiaryAnalyzer
from diary_eval import EVAL, CRISIS_EVAL

LABELS = ["분노", "슬픔", "불안", "상처", "당황", "기쁨"]
POS = "기쁨"

az = DiaryAnalyzer()

y_true, y_pred, val_pred, wrong = [], [], [], []
for sid, text, gold in EVAL:
    r = az.analyze(text)
    pred = r["dominant"]["coarse"]
    y_true.append(gold)
    y_pred.append(pred)
    val_pred.append(r["valence_mean"])
    if pred != gold:
        wrong.append((gold, pred, r["dominant"]["conf"], text[:45]))

print("=" * 66)
print(f"  실제 일기 검증셋 (n={len(EVAL)}) — 6종 감정 분류")
print("=" * 66)
print(classification_report(y_true, y_pred, labels=LABELS,
                            digits=3, zero_division=0))
print(f"macro F1 = {f1_score(y_true, y_pred, average='macro', zero_division=0):.4f}")
print(f"accuracy = {accuracy_score(y_true, y_pred):.4f}")

# ---- 긍정/부정 2분류 ----
yb = [1 if y == POS else 0 for y in y_true]
pb = [1 if p == POS else 0 for p in y_pred]
print("\n" + "=" * 66)
print("  긍정/부정 2분류")
print("=" * 66)
print(classification_report(yb, pb, target_names=["부정", "긍정"],
                            digits=3, zero_division=0))

# ---- valence 방향 일치 ----
ok = sum(1 for g, v in zip(y_true, val_pred)
         if (g == POS and v > 0) or (g != POS and v < 0))
print(f"valence 부호 일치율 = {ok}/{len(EVAL)} ({ok/len(EVAL)*100:.1f}%)")

# ---- 혼동 행렬 ----
print("\n" + "=" * 66)
print("  혼동 행렬 (행=정답, 열=예측)")
print("=" * 66)
cm = confusion_matrix(y_true, y_pred, labels=LABELS)
print("         " + "".join(f"{l:>6s}" for l in LABELS))
for i, l in enumerate(LABELS):
    print(f"  {l:6s} " + "".join(f"{v:6d}" for v in cm[i]))

# ---- 오답 목록 ----
print("\n" + "=" * 66)
print(f"  오분류 {len(wrong)}건")
print("=" * 66)
for g, p, c, t in wrong:
    print(f"  {g} → {p} ({c:.2f})  {t}...")

# ---- 위기 감지 ----
print("\n" + "=" * 66)
print("  위기 감지 모듈")
print("=" * 66)
try:
    import crisis
    hit = miss = fp = 0
    for text, gold in CRISIS_EVAL:
        lv = crisis.detect(text).level
        mark = "OK " if lv == gold else "XX "
        if lv == gold:
            hit += 1
        elif lv < gold:
            miss += 1
        else:
            fp += 1
        print(f"  {mark} 정답L{gold} 예측L{lv}  {text[:42]}")
    print(f"\n  정확 {hit}/{len(CRISIS_EVAL)} | 미탐 {miss} (치명) | 오탐 {fp} (허용)")
except ImportError:
    print("  crisis.py 없음")
