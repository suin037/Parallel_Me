"""
멀티태스크 감정 분류기 (공식 train/val split 사용)
  head 1: 대분류 6   - 리포트 뼈대
  head 2: 소분류 60  - 계층 마스킹으로 60지선다를 10지선다로
  head 3: 상황 12    - 리포트 트리거 탐지
  head 4: VAD 2      - 감정 시계열 그래프

정확도 장치: 계층마스킹 / logit adjustment / label smoothing / R-Drop / EMA
"""
import json, argparse, os, time
import numpy as np, pandas as pd, torch
import torch.nn as nn, torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
from transformers import AutoTokenizer, AutoModel, get_cosine_schedule_with_warmup
from sklearn.metrics import f1_score, accuracy_score, classification_report

DEV = "cuda" if torch.cuda.is_available() else "cpu"


class DS(Dataset):
    def __init__(self, df, tok, maxlen, maps, tax):
        self.t = df["text"].tolist()
        self.c = [maps["coarse"][x] for x in df["coarse"]]
        self.f = [maps["fine"][x] for x in df["fine"]]
        self.s = [maps["sit"].get(x, 0) for x in df["situation"]]
        self.v = [[tax["fine"][x]["valence"], tax["fine"][x]["arousal"]] for x in df["fine"]]
        self.tok, self.maxlen = tok, maxlen

    def __len__(self):
        return len(self.t)

    def __getitem__(self, i):
        e = self.tok(self.t[i], truncation=True, max_length=self.maxlen,
                     padding="max_length")
        return {
            "input_ids": torch.tensor(e["input_ids"]),
            "attention_mask": torch.tensor(e["attention_mask"]),
            "coarse": torch.tensor(self.c[i]),
            "fine": torch.tensor(self.f[i]),
            "sit": torch.tensor(self.s[i]),
            "vad": torch.tensor(self.v[i], dtype=torch.float),
        }


class Model(nn.Module):
    def __init__(self, backbone, n_c, n_f, n_s, hier):
        super().__init__()
        self.enc = AutoModel.from_pretrained(backbone)
        h = self.enc.config.hidden_size
        self.drop = nn.Dropout(0.1)
        self.h_c = nn.Linear(h, n_c)
        self.h_f = nn.Linear(h + n_c, n_f)   # 대분류 신호를 소분류에 주입
        self.h_s = nn.Linear(h, n_s)
        self.h_v = nn.Linear(h, 2)
        self.register_buffer("hier", hier)   # [n_c, n_f] 0/1

    def forward(self, ids, mask, hard_mask=False):
        out = self.enc(input_ids=ids, attention_mask=mask).last_hidden_state
        m = mask.unsqueeze(-1).float()
        x = (out * m).sum(1) / m.sum(1).clamp(min=1e-9)   # mean pooling
        x = self.drop(x)
        lc = self.h_c(x)
        lf = self.h_f(torch.cat([x, lc.detach()], dim=-1))
        if hard_mask:
            lf = lf.masked_fill(self.hier[lc.argmax(-1)] == 0, -1e4)
        return lc, lf, self.h_s(x), torch.tanh(self.h_v(x))


def prior_from_counts(counts, tau):
    p = np.asarray(counts, dtype=np.float64)
    p = p / p.sum()
    return torch.tensor(np.log(p ** tau + 1e-12), dtype=torch.float)


def evaluate(model, dl, inv_c, inv_f):
    model.eval()
    P = {"c": [], "f": [], "s": []}
    Y = {"c": [], "f": [], "s": []}
    with torch.no_grad():
        for b in dl:
            b = {k: v.to(DEV, non_blocking=True) for k, v in b.items()}
            with torch.autocast("cuda", enabled=DEV == "cuda"):
                lc, lf, ls, _ = model(b["input_ids"], b["attention_mask"], hard_mask=True)
            P["c"] += lc.argmax(-1).cpu().tolist(); Y["c"] += b["coarse"].cpu().tolist()
            P["f"] += lf.argmax(-1).cpu().tolist(); Y["f"] += b["fine"].cpu().tolist()
            P["s"] += ls.argmax(-1).cpu().tolist(); Y["s"] += b["sit"].cpu().tolist()
    return {
        "f1_coarse": f1_score(Y["c"], P["c"], average="macro"),
        "acc_coarse": accuracy_score(Y["c"], P["c"]),
        "f1_fine": f1_score(Y["f"], P["f"], average="macro"),
        "acc_fine": accuracy_score(Y["f"], P["f"]),
        "acc_sit": accuracy_score(Y["s"], P["s"]),
        "_yc": Y["c"], "_pc": P["c"],
    }


def main(a):
    os.makedirs(a.out, exist_ok=True)
    tax = json.load(open(a.taxonomy, encoding="utf-8"))
    tr = pd.read_parquet(a.train)
    va = pd.read_parquet(a.val)
    print(f"train={len(tr)}  val={len(va)}")

    sits = sorted(set(tr["situation"]) | set(va["situation"]))
    maps = {
        "coarse": {k: i for i, k in enumerate(sorted(tax["coarse"]))},
        "fine": {k: i for i, k in enumerate(sorted(tax["fine"]))},
        "sit": {k: i for i, k in enumerate(sits)},
    }
    inv_c = {v: tax["coarse"][k] for k, v in maps["coarse"].items()}
    inv_f = {v: tax["fine"][k]["name"] for k, v in maps["fine"].items()}
    print(f"classes: coarse={len(maps['coarse'])} fine={len(maps['fine'])} sit={len(maps['sit'])}")

    hier = torch.zeros(len(maps["coarse"]), len(maps["fine"]))
    for code, fi in maps["fine"].items():
        hier[maps["coarse"][tax["fine"][code]["coarse"]], fi] = 1

    cc = tr["coarse"].map(maps["coarse"]).value_counts().reindex(
        range(len(maps["coarse"])), fill_value=1).values
    cf = tr["fine"].map(maps["fine"]).value_counts().reindex(
        range(len(maps["fine"])), fill_value=1).values
    pc = prior_from_counts(cc, a.tau).to(DEV)
    pf = prior_from_counts(cf, a.tau).to(DEV)

    tok = AutoTokenizer.from_pretrained(a.backbone)
    model = Model(a.backbone, len(maps["coarse"]), len(maps["fine"]),
                  len(maps["sit"]), hier).to(DEV)

    dl_tr = DataLoader(DS(tr, tok, a.maxlen, maps, tax), batch_size=a.bs,
                       shuffle=True, num_workers=4, pin_memory=True, drop_last=True)
    dl_va = DataLoader(DS(va, tok, a.maxlen, maps, tax), batch_size=a.bs * 4,
                       num_workers=4, pin_memory=True)

    nd = ["bias", "LayerNorm.weight"]
    opt = torch.optim.AdamW([
        {"params": [p for n, p in model.named_parameters() if not any(d in n for d in nd)],
         "weight_decay": 0.01},
        {"params": [p for n, p in model.named_parameters() if any(d in n for d in nd)],
         "weight_decay": 0.0},
    ], lr=a.lr)
    total = len(dl_tr) * a.epochs
    sch = get_cosine_schedule_with_warmup(opt, int(total * 0.06), total)
    scaler = torch.amp.GradScaler("cuda", enabled=DEV == "cuda")

    ema = {k: v.detach().clone().float() for k, v in model.state_dict().items()
           if v.dtype.is_floating_point}
    best, best_state = -1.0, None

    for ep in range(a.epochs):
        model.train()
        t0, run = time.time(), 0.0
        for step, b in enumerate(dl_tr):
            b = {k: v.to(DEV, non_blocking=True) for k, v in b.items()}
            opt.zero_grad(set_to_none=True)
            with torch.autocast("cuda", enabled=DEV == "cuda"):
                lc1, lf1, ls1, lv1 = model(b["input_ids"], b["attention_mask"])
                loss = F.cross_entropy(lc1 + pc, b["coarse"], label_smoothing=a.ls)
                loss = loss + a.w_fine * F.cross_entropy(lf1 + pf, b["fine"],
                                                         label_smoothing=a.ls)
                loss = loss + a.w_sit * F.cross_entropy(ls1, b["sit"])
                loss = loss + a.w_vad * F.mse_loss(lv1, b["vad"])

                if a.rdrop > 0:
                    lc2, lf2, _, _ = model(b["input_ids"], b["attention_mask"])
                    loss = loss + 0.5 * (
                        F.cross_entropy(lc2 + pc, b["coarse"], label_smoothing=a.ls) +
                        a.w_fine * F.cross_entropy(lf2 + pf, b["fine"], label_smoothing=a.ls))

                    def kl(p, q):
                        return 0.5 * (F.kl_div(F.log_softmax(p, -1), F.softmax(q, -1),
                                               reduction="batchmean") +
                                      F.kl_div(F.log_softmax(q, -1), F.softmax(p, -1),
                                               reduction="batchmean"))
                    loss = loss + a.rdrop * (kl(lc1, lc2) + kl(lf1, lf2))

            scaler.scale(loss).backward()
            scaler.unscale_(opt)
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            scaler.step(opt); scaler.update(); sch.step()

            with torch.no_grad():
                sd = model.state_dict()
                for k in ema:
                    ema[k].mul_(a.ema).add_(sd[k].detach().float(), alpha=1 - a.ema)

            run += loss.item()
            if step % 200 == 0:
                print(f"  ep{ep} step {step}/{len(dl_tr)} loss={run/(step+1):.4f} "
                      f"lr={sch.get_last_lr()[0]:.2e} {time.time()-t0:.0f}s", flush=True)

        # EMA 가중치로 평가
        bak = {k: v.detach().clone() for k, v in model.state_dict().items()}
        model.load_state_dict({**bak, **{k: v.to(bak[k].dtype) for k, v in ema.items()}})
        m = evaluate(model, dl_va, inv_c, inv_f)
        score = 0.6 * m["f1_coarse"] + 0.4 * m["f1_fine"]
        print(f"[ep{ep}] coarseF1={m['f1_coarse']:.4f} acc={m['acc_coarse']:.4f} | "
              f"fineF1={m['f1_fine']:.4f} acc={m['acc_fine']:.4f} | "
              f"sitAcc={m['acc_sit']:.4f} | score={score:.4f}", flush=True)

        if score > best:
            best = score
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
            torch.save({"state": best_state, "maps": maps, "backbone": a.backbone,
                        "metrics": {k: v for k, v in m.items() if not k.startswith("_")}},
                       f"{a.out}/best.pt")
            print(f"  saved best -> {a.out}/best.pt")
        model.load_state_dict(bak)

    # 최종 리포트
    model.load_state_dict(best_state)
    m = evaluate(model, dl_va, inv_c, inv_f)
    print("\n=== FINAL (best ckpt) ===")
    print(f"coarse macroF1={m['f1_coarse']:.4f} acc={m['acc_coarse']:.4f}")
    print(f"fine   macroF1={m['f1_fine']:.4f} acc={m['acc_fine']:.4f}")
    print(f"situation acc={m['acc_sit']:.4f}")
    print("\n[대분류 상세]")
    print(classification_report(m["_yc"], m["_pc"],
                                target_names=[inv_c[i] for i in range(len(inv_c))],
                                digits=3))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--train", default="./data/train.parquet")
    p.add_argument("--val", default="./data/val.parquet")
    p.add_argument("--taxonomy", default="./emotion_taxonomy.json")
    p.add_argument("--backbone", default="klue/roberta-large")
    p.add_argument("--out", default="./ckpt")
    p.add_argument("--maxlen", type=int, default=64)
    p.add_argument("--bs", type=int, default=16)
    p.add_argument("--lr", type=float, default=1.5e-5)
    p.add_argument("--epochs", type=int, default=3)
    p.add_argument("--ls", type=float, default=0.1)
    p.add_argument("--tau", type=float, default=0.5)
    p.add_argument("--rdrop", type=float, default=0.0)
    p.add_argument("--ema", type=float, default=0.999)
    p.add_argument("--w_fine", type=float, default=1.0)
    p.add_argument("--w_sit", type=float, default=0.3)
    p.add_argument("--w_vad", type=float, default=0.3)
    main(p.parse_args())