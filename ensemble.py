# ensemble.py — 3모델 softmax 평균 + 가중치 탐색
import json, torch, numpy as np, pandas as pd
import torch.nn.functional as F
from train_v2 import Model, DS
from transformers import AutoTokenizer
from torch.utils.data import DataLoader
from sklearn.metrics import f1_score
from itertools import product

DEV = "cuda"
CKPTS = ["./ckpt_e6/best.pt", "./ckpt_kc/best.pt", "./ckpt_kf/best.pt"]

tax = json.load(open("emotion_taxonomy.json", encoding="utf-8"))
va = pd.read_parquet("./data/val_c.parquet")

def load(p):
    ck = torch.load(p, map_location=DEV)
    maps = ck["maps"]
    hier = torch.zeros(len(maps["coarse"]), len(maps["fine"]))
    for c, i in maps["fine"].items():
        hier[maps["coarse"][tax["fine"][c]["coarse"]], i] = 1
    m = Model(ck["backbone"], len(maps["coarse"]), len(maps["fine"]),
              len(maps["sit"]), hier.to(DEV))
    m.load_state_dict(ck["state"]); m.to(DEV).eval()
    return m, AutoTokenizer.from_pretrained(ck["backbone"]), maps

models = [load(p) for p in CKPTS]
maps0 = models[0][2]
y_true = [maps0["coarse"][x] for x in va["coarse"]]

# 각 모델의 대분류 확률 수집
all_probs = []
for m, tok, maps in models:
    dl = DataLoader(DS(va, tok, 128, maps, tax), batch_size=128)
    probs = []
    with torch.no_grad():
        for b in dl:
            b = {k: v.to(DEV) for k, v in b.items()}
            with torch.cuda.amp.autocast():
                lc, _, _, _ = m(b["input_ids"], b["attention_mask"], hard_mask=True)
            probs.append(F.softmax(lc, -1).float().cpu().numpy())
    all_probs.append(np.concatenate(probs))

# 단독 성능
for i, p in enumerate(all_probs):
    f1 = f1_score(y_true, p.argmax(1), average="macro")
    print(f"model{i} ({CKPTS[i].split('/')[1]}): macroF1={f1:.4f}")

# 가중치 grid search
best_f1, best_w = 0, None
for w in product(np.arange(0, 1.05, 0.1), repeat=len(all_probs)):
    if abs(sum(w) - 1) > 0.01:
        continue
    ens = sum(wi * pi for wi, pi in zip(w, all_probs))
    f1 = f1_score(y_true, ens.argmax(1), average="macro")
    if f1 > best_f1:
        best_f1, best_w = f1, w
print(f"\n최적 앙상블: F1={best_f1:.4f}  weights={[round(x,2) for x in best_w]}")