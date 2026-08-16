"""
심리학 지식 카드 → 검색용 벡터DB 빌드
=====================================
입력:  data/knowledge/*.json   (개념별 지식 카드. 사람이 구조화)
출력:  data/vectordb/psychology/psychology_db.pkl
       + preview.json / preview.txt (사람 확인용)

[카드 JSON 규칙]
  - 최상위 "metadata" : 개념/출처/용도 등 (파일 전체 공통)
  - 그 외 최상위의 '리스트[dict]' 필드는 모두 '카드 묶음'으로 간주
    (positive_emotion_cards, mechanism_cards ... 이름은 자유)
  - 각 카드 dict 는 자유 필드. 검색에는 '신호어 + 정의 + 개념'을 사용.

[검색 방식]  TF-IDF(char_wb) + cosine. 임베딩 모델 불필요, 가볍고 빠름.

실행:  python preprocess/build_knowledge_db.py   (repo 루트에서)
필요:  pip install scikit-learn
"""

import json
import pickle
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

KNOWLEDGE_DIR = Path("data/knowledge")
OUT_DIR = Path("data/vectordb/psychology")
OUT_PKL = OUT_DIR / "psychology_db.pkl"


# ---------------------------------------------------------------------------
# 카드에서 값 뽑기 (한국어 키가 파일마다 조금씩 달라도 견디게)
# ---------------------------------------------------------------------------
def signal_words(card: dict) -> list[str]:
    """'신호어'가 포함된 키의 리스트 값을 모두 모은다."""
    words = []
    for k, v in card.items():
        if "신호어" in k and isinstance(v, list):
            words += [str(x) for x in v]
    return words


def card_label(card: dict) -> str:
    """카드의 대표 이름 (긍정정서/원리/개념 ...)."""
    for k in ("긍정정서", "원리", "개념", "이름", "name"):
        if card.get(k):
            return str(card[k])
    return card.get("id", "")


def build_search_text(card: dict, concept: str) -> str:
    """★검색 대상 텍스트 = 신호어 + 정의 중심 (+ 개념/라벨 문맥)."""
    parts = [concept, card_label(card), card.get("정의", "")]
    parts += signal_words(card)
    return " ".join(p for p in parts if p).strip()


# ---------------------------------------------------------------------------
def load_cards():
    """data/knowledge/*.json 을 전부 읽어 카드 레코드 리스트로 평탄화."""
    files = sorted(KNOWLEDGE_DIR.glob("*.json"))
    if not files:
        raise SystemExit(f"카드 JSON 없음: {KNOWLEDGE_DIR.resolve()}/*.json")

    cards, search_texts = [], []
    for path in files:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        meta = data.get("metadata", {})
        concept = meta.get("개념", path.stem)
        n_before = len(cards)

        for key, value in data.items():
            if key == "metadata":
                continue
            # '리스트[dict]' 필드만 카드 묶음으로 인정
            if not (isinstance(value, list) and value and isinstance(value[0], dict)):
                continue
            for card in value:
                search_texts.append(build_search_text(card, concept))
                cards.append({
                    "id": card.get("id", ""),
                    "concept": concept,
                    "label": card_label(card),
                    "source": meta.get("출처", ""),
                    "용도": meta.get("용도", []),
                    "card_type": key,          # 어느 카드 묶음이었는지
                    "source_file": path.name,
                    "card": card,              # 원본 카드 전체(조언_방향 등 포함)
                })
        print(f"  {path.name}: +{len(cards) - n_before}장  (개념: {concept})")

    return cards, search_texts


def main():
    print("[1] 카드 로딩")
    cards, search_texts = load_cards()
    print(f"    총 {len(cards)}장")

    print("[2] TF-IDF 벡터화")
    vectorizer = TfidfVectorizer(
        analyzer="char_wb", ngram_range=(2, 4),
        max_features=8000, sublinear_tf=True,
    )
    tfidf = vectorizer.fit_transform(search_texts)

    db = {
        "cards": cards,
        "search_texts": search_texts,
        "vectorizer": vectorizer,
        "tfidf_matrix": tfidf,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_PKL, "wb") as f:
        pickle.dump(db, f)
    print(f"[3] 저장 → {OUT_PKL}  ({len(cards)}장 × {tfidf.shape[1]} feature)")

    # -- 사람 확인용 preview --------------------------------------------
    preview = [
        {"index": i, "concept": c["concept"], "label": c["label"],
         "id": c["id"], "조언_방향": c["card"].get("조언_방향", ""),
         "search_text": t}
        for i, (c, t) in enumerate(zip(cards, search_texts))
    ]
    (OUT_DIR / "psychology_db_preview.json").write_text(
        json.dumps(preview, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"    preview → {OUT_DIR / 'psychology_db_preview.json'}")


# ---------------------------------------------------------------------------
# 검색 (백엔드에서 import)
# ---------------------------------------------------------------------------
_cache = None


def retrieve(query: str, top_k: int = 3, min_sim: float = 0.02) -> list[dict]:
    """일기 문장 등으로 관련 지식 카드 검색 → 구조화된 조언 반환."""
    global _cache
    if _cache is None:
        if not OUT_PKL.exists():
            return []
        with open(OUT_PKL, "rb") as f:
            _cache = pickle.load(f)

    q = _cache["vectorizer"].transform([query])
    sims = cosine_similarity(q, _cache["tfidf_matrix"])[0]
    order = sims.argsort()[::-1][:top_k]

    out = []
    for i in order:
        if sims[i] < min_sim:
            continue
        c = _cache["cards"][i]
        out.append({
            "concept": c["concept"],
            "label": c["label"],
            "정의": c["card"].get("정의", ""),
            "조언_방향": c["card"].get("조언_방향", ""),
            "source": c["source"],
            "score": round(float(sims[i]), 3),
        })
    return out


if __name__ == "__main__":
    main()

    print("\n=== 검색 테스트 ===")
    for q in ["오늘 새로운 걸 배워서 더 알고 싶어졌다",
              "불안했는데 친구랑 있으니 좀 편안해졌다",
              "요즘 계속 무기력하고 막막하다"]:
        print(f"\n[쿼리] {q}")
        for r in retrieve(q, top_k=2):
            print(f"  ({r['score']}) {r['concept']} · {r['label']}")
            print(f"      조언: {r['조언_방향'][:60]}...")
