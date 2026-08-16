"""
감성대화말뭉치 JSON -> 학습용 parquet
확인된 구조:
  item["profile"]["emotion"]["type"]       -> "E18"
  item["profile"]["emotion"]["situation"]  -> ["S06", "D02"]
  item["talk"]["content"]["HS01".."HS03"]  -> 사람 발화
"""
import re, json, glob, argparse, random
import pandas as pd

# ---------------------------------------------------------------
# 문체 정규화: 대화체(해요체) -> 일기체(평서형)
# 긴 패턴부터 치환해야 하므로 순서 중요
# ---------------------------------------------------------------
STYLE_RULES = [
    # 1인칭 겸양 -> 평어 (L2 '1인칭 단수 비율' 지표와 직결)
    (r"저는\b", "나는"), (r"저도\b", "나도"), (r"저를\b", "나를"),
    (r"저의\b", "나의"), (r"저한테\b", "나한테"), (r"저에게\b", "나에게"),
    (r"저와\b", "나와"), (r"저랑\b", "나랑"), (r"저희\b", "우리"),
    (r"제가\b", "내가"), (r"제\s", "내 "),

    # 종결어미
    (r"했었어요", "했었다"), (r"하였습니다", "했다"),
    (r"했습니다", "했다"), (r"했어요", "했다"), (r"했네요", "했다"),
    (r"했거든요", "했다"), (r"했잖아요", "했다"), (r"했는데요", "했는데"),
    (r"합니다", "한다"), (r"해요", "한다"), (r"하네요", "한다"),
    (r"됐어요", "됐다"), (r"됩니다", "된다"), (r"돼요", "된다"),
    (r"있어요", "있다"), (r"있습니다", "있다"),
    (r"없어요", "없다"), (r"없습니다", "없다"),
    (r"같아요", "같다"), (r"같습니다", "같다"),
    (r"이에요", "이다"), (r"예요", "다"), (r"입니다", "이다"), (r"이네요", "이다"),
    (r"거예요", "거다"), (r"겁니다", "거다"),
    (r"([가-힣])세요", r"\1다"),
    (r"([가-힣])어요", r"\1어"),
    (r"([가-힣])아요", r"\1아"),
    (r"([가-힣])네요", r"\1네"),
    (r"([가-힣])군요", r"\1군"),
    (r"([가-힣])죠", r"\1지"),
]

DIALOG_NOISE = [
    r"^(음+|아+|어+|그러니까|그게|저기요?|있잖아요?)[,.\s]*",
    r"(그쵸|그죠|맞죠|아시죠)\??",
]


def normalize_style(t: str) -> str:
    if not isinstance(t, str):
        return ""
    t = t.strip()
    for p in DIALOG_NOISE:
        t = re.sub(p, "", t)
    for p, r in STYLE_RULES:
        t = re.sub(p, r, t)
    return re.sub(r"\s+", " ", t).strip()


def load(path):
    rows = []
    for f in sorted(glob.glob(f"{path}/*.json")):
        data = json.load(open(f, encoding="utf-8-sig"))
        print(f"  {f}: {len(data)} items")
        for it in data:
            emo = it.get("profile", {}).get("emotion", {})
            fine = emo.get("type", "")
            situ = emo.get("situation") or []
            content = it.get("talk", {}).get("content", {})
            for k in ("HS01", "HS02", "HS03"):
                s = content.get(k, "")
                if isinstance(s, str) and len(s.strip()) > 3:
                    rows.append({
                        "text": s.strip(),
                        "fine": fine,
                        "situation": situ[0] if situ else "UNK",
                        "dtype": situ[1] if len(situ) > 1 else "UNK",
                        "turn": int(k[-1]),
                    })
    return pd.DataFrame(rows)


def build(df, tax, aug_ratio, seed=42):
    fine2coarse = {k: v["coarse"] for k, v in tax["fine"].items()}
    df = df[df["fine"].isin(fine2coarse)].copy()
    df["coarse"] = df["fine"].map(fine2coarse)

    df["norm"] = df["text"].apply(normalize_style)
    df = df[df["norm"].str.len().between(4, 300)]

    base = df.copy()
    base["final"] = base["norm"]

    # 원문 일부를 문체 증강으로 추가 (문체 불변성 확보)
    if aug_ratio > 0:
        aug = df.sample(frac=aug_ratio, random_state=seed).copy()
        aug["final"] = aug["text"]
        out = pd.concat([base, aug])
    else:
        out = base

    before = len(out)
    out = out.drop_duplicates(subset=["final", "fine"])
    print(f"  dedup: {before} -> {len(out)}")

    out = out[["final", "coarse", "fine", "situation", "dtype", "turn"]]
    return out.rename(columns={"final": "text"})


def main(a):
    tax = json.load(open(a.taxonomy, encoding="utf-8"))
    random.seed(42)

    print("[load train]")
    tr = load(a.train_dir)
    print("[load val]")
    va = load(a.val_dir)
    print(f"raw utterances: train={len(tr)}  val={len(va)}")

    print("[build train]")
    tr = build(tr, tax, a.aug_ratio)
    print("[build val]")
    va = build(va, tax, 0.0)          # 검증셋은 증강 없이 정규화만

    tr = tr.sample(frac=1.0, random_state=42).reset_index(drop=True)
    tr.to_parquet(a.out_train, index=False)
    va.to_parquet(a.out_val, index=False)

    print(f"\nsaved  train={len(tr)}  val={len(va)}")
    print("\n[대분류 분포]")
    print(tr["coarse"].value_counts().to_string())
    vc = tr["fine"].value_counts()
    print(f"\n[소분류] {vc.nunique()}종  min={vc.min()}  max={vc.max()}")
    print("\n[상황]")
    print(tr["situation"].value_counts().to_string())
    print("\n[정규화 예시]")
    for t in tr["text"].head(8):
        print("  ", t[:80])


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--train_dir", default="./rawx/tr")
    p.add_argument("--val_dir", default="./rawx/va")
    p.add_argument("--taxonomy", default="./emotion_taxonomy.json")
    p.add_argument("--out_train", default="./data/train.parquet")
    p.add_argument("--out_val", default="./data/val.parquet")
    p.add_argument("--aug_ratio", type=float, default=0.3,
                   help="원문(대화체)을 몇 비율로 추가 학습할지")
    main(p.parse_args())