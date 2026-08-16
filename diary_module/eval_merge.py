import numpy as np
from sklearn.metrics import classification_report, f1_score, confusion_matrix
from infer import DiaryAnalyzer
from diary_eval import EVAL

# 상처+당황 -> '위축' (자기/관계에서 오는 움츠러듦)
MERGE = {"상처": "위축", "당황": "위축"}
L5 = ["분노", "슬픔", "불안", "위축", "기쁨"]

az = DiaryAnalyzer()
yt, yp = [], []
for sid, text, gold in EVAL:
    r = az.analyze(text)
    p = r["dominant"]["coarse"]
    yt.append(MERGE.get(gold, gold))
    yp.append(MERGE.get(p, p))

print("=" * 60)
print("  5종 병합 (상처+당황 -> 위축)")
print("=" * 60)
print(classification_report(yt, yp, labels=L5, digits=3, zero_division=0))
print(f"macro F1 = {f1_score(yt, yp, average='macro', zero_division=0):.4f}")

cm = confusion_matrix(yt, yp, labels=L5)
print("\n         " + "".join(f"{l:>6s}" for l in L5))
for i, l in enumerate(L5):
    print(f"  {l:6s} " + "".join(f"{v:6d}" for v in cm[i]))
