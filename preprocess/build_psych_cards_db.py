"""
심리학 이론카드(cards_*_v1.json) → ChromaDB 'psych_theory' 컬렉션 적재.

사용법:
    KPY="C:/Users/USER/anaconda3/envs/knhanes/python.exe"
    "$KPY" preprocess/build_psych_cards_db.py

입력:  data/lanollab/심리학_이론카드/cards_*_v1.json
       (하위 _archive_old_schema/ 및 top-level _authoring_note 는 자동 스킵)
출력:  data/vectordb/  (ChromaDB PersistentClient, 컬렉션 'psych_theory')

설계 메모
- 리치 카드(JSON)는 원본(source of truth). 이 로더가 팀표준 {id, document, metadata}
  청크로 평탄화해 적재한다. 카드를 직접 고치지 말고 이 스크립트를 다시 돌린다.
- ChromaDB 메타데이터는 스칼라만 허용 → 리스트(indicator/emotion/decision/tags)는
  콤마 문자열로 평탄화한다.
- 지표 표기 정규화: 카드는 '삶의_질', 팀표준 통계청크는 '삶의질'(언더스코어 없음).
  레이어2 쿼리 문자열과 저장값이 일치해야 필터가 걸리므로 여기서 통일한다.
- 통계 RAG(stats_kr)와 컬렉션을 분리한다. 이 스크립트는 psych_theory만 다룬다.
- 임계값(낮음/중간/높음 경계)은 카드가 아니라 '검색' 단계(psych_retriever)에 둔다.
  로더는 지표 이름과 direction 만 저장한다.
"""

import json
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

ROOT = Path(__file__).resolve().parent.parent
CARDS_DIR = ROOT / "data" / "lanollab" / "심리학_이론카드"
DB_DIR = ROOT / "data" / "vectordb"
COLLECTION = "psych_theory"

# 로컬 multilingual 임베딩(한국어 강함, 무료·오프라인). 첫 실행 시 모델 자동 다운로드.
# 교체 가능: intfloat/multilingual-e5-base 등. e5 계열은 query:/passage: 프리픽스 필요.
EMB_MODEL = "jhgan/ko-sroberta-multitask"

# 카드 표기 → 팀표준(통계청크) 표기. 레이어2 쿼리도 이 값과 맞춰야 한다.
INDICATOR_NORMALIZE = {
    "삶의_질": "삶의질",
    "경제적_안정도": "경제적안정도",
    "성장_가능성": "성장가능성",
}


def _flatten(xs):
    """리스트 → 콤마 문자열(ChromaDB 스칼라 제약). None/빈 값은 빈 문자열."""
    return ",".join(xs) if xs else ""


def card_to_chunk(card, theory_ko, theory_en):
    """리치 카드 1장 → (id, document, metadata) 팀표준 청크."""
    appl = card.get("applicable_situations", {})
    indicators = [INDICATOR_NORMALIZE.get(i, i) for i in appl.get("indicator", [])]

    # document = 임베딩(검색) 대상 텍스트. concept + summary 를 중심으로,
    # 개입방법도 넣어 '행동 제안' 매칭을 강화한다.
    document = card.get("embedding_text") or f"{card.get('concept_ko','')}. {card.get('summary','')}"
    if card.get("interventions"):
        document += " 개입: " + " ".join(card["interventions"])

    source = card.get("source", {})
    metadata = {
        "card_id": card["card_id"],
        "theory_ko": theory_ko,
        "theory_en": theory_en,
        "concept_ko": card.get("concept_ko", ""),
        # 근거 블록 구성을 위해 원문도 스칼라로 보관(레이어3이 그대로 주입)
        "summary": card.get("summary", ""),
        "interventions": " || ".join(card.get("interventions", [])),
        "narrative_guidance": card.get("narrative_guidance", ""),
        "indicator": _flatten(indicators),
        "direction": appl.get("direction", ""),
        "emotion_keywords": _flatten(appl.get("emotion_keywords", [])),
        "decision_types": _flatten(appl.get("decision_types", [])),
        "evidence_level": source.get("evidence_level", ""),
        "source": source.get("citation", ""),
        "doi_or_url": source.get("doi_or_url", ""),
        "tags": _flatten(card.get("tags", [])),
        "doc_type": "이론카드",
        "version": card.get("version", "v1"),
    }
    return card["card_id"], document, metadata


def load_cards():
    """CARDS_DIR 직속의 cards_*_v1.json 만 읽는다(_archive 하위폴더는 glob 비재귀라 자동 제외)."""
    chunks = []
    files = sorted(CARDS_DIR.glob("cards_*_v1.json"))
    for f in files:
        data = json.loads(f.read_text(encoding="utf-8"))
        theory_ko = data.get("theory_ko", "")
        theory_en = data.get("theory_en", "")
        # top-level _authoring_note 등은 cards 배열이 아니므로 자연히 무시됨
        for card in data.get("cards", []):
            chunks.append(card_to_chunk(card, theory_ko, theory_en))
        print(f"  · {f.name}: {len(data.get('cards', []))}장")
    return chunks, files


def main():
    if not CARDS_DIR.exists():
        raise SystemExit(f"카드 폴더 없음: {CARDS_DIR}")

    print(f"[1/3] 카드 로드: {CARDS_DIR}")
    chunks, files = load_cards()
    if not chunks:
        raise SystemExit("적재할 카드가 없습니다.")
    ids = [c[0] for c in chunks]
    docs = [c[1] for c in chunks]
    metas = [c[2] for c in chunks]

    # card_id 중복 검사(전역 고유해야 함)
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise SystemExit(f"중복 card_id: {sorted(dupes)}")

    print(f"[2/3] 임베딩 모델 로드: {EMB_MODEL} (첫 실행 시 다운로드)")
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMB_MODEL)

    print(f"[3/3] ChromaDB 적재: {DB_DIR} / 컬렉션 '{COLLECTION}'")
    DB_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(DB_DIR))
    # 재적재 시 기존 컬렉션 초기화(멱등)
    try:
        client.delete_collection(COLLECTION)
    except Exception:
        pass
    col = client.create_collection(
        name=COLLECTION,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )
    col.add(ids=ids, documents=docs, metadatas=metas)

    print(f"\n✅ 적재 완료: {len(ids)}개 카드 · 이론파일 {len(files)}개 → '{COLLECTION}'")
    print(f"   DB 경로: {DB_DIR}")


if __name__ == "__main__":
    main()
