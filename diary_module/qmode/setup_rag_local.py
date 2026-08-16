# -*- coding: utf-8 -*-
"""setup_rag_local.py — minjub 의 이론카드를 내 쪽으로 복사 + 신규 카드 합쳐 재빌드.

원칙 (인수인계 문서 §5): lanollab-data 원본은 복사만, 수정 금지.
                        실험은 전부 diary_module/qmode/rag_local/ 안에서 한다.

원본 빌드 스크립트의 문제
    preprocess/build_psych_cards_db.py 의 load_cards() 는 비재귀 glob 이라
    하위폴더 _handoff_sohyunio/cards_resilience_v1.json (회복탄력성 4장)이 안 실린다.
    현재 벡터DB 적재량 = 대처 3 + 긍정정서 8 = 11장.
    이 스크립트는 rglob 을 써서 그 4장까지 살린다.

적재 결과 (예상)
    대처 3 + 긍정정서 8 + 회복탄력성 4 + [신규] 부러움 2 + 미래자기 1 + 자기자비 2 = 20장

사용:
    # 1) 원본 카드 복사 (lanollab-data 브랜치를 체크아웃한 경로를 지정)
    python diary_module/qmode/setup_rag_local.py copy --from /path/to/lanollab-data-worktree

    # 2) 로컬 벡터DB 빌드 (chromadb + sentence-transformers 필요)
    python diary_module/qmode/setup_rag_local.py build
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOCAL_CARDS = HERE / "rag_local" / "심리학_이론카드"
LOCAL_DB = HERE / "rag_local" / "vectordb"
NEW_CARDS = HERE / "cards_new"          # 이 브랜치에서 새로 쓴 카드
COLLECTION = "psych_theory"
EMB_MODEL = "jhgan/ko-sroberta-multitask"

SRC_REL = Path("data") / "lanollab" / "심리학_이론카드"


def cmd_copy(src_root: Path):
    src = src_root / SRC_REL
    if not src.exists():
        raise SystemExit(f"원본 카드 폴더 없음: {src}\n"
                         f"  lanollab-data 브랜치를 체크아웃한 경로를 --from 으로 주세요.\n"
                         f"  예) git worktree add ../lanollab-data lanollab-data")
    LOCAL_CARDS.mkdir(parents=True, exist_ok=True)
    n = 0
    # rglob — 하위폴더(_handoff_sohyunio)까지 긁는다. _archive_old_schema 는 제외.
    for f in sorted(src.rglob("cards_*_v1.json")):
        if "_archive_old_schema" in f.parts:
            continue
        dst = LOCAL_CARDS / f.name
        shutil.copy2(f, dst)
        d = json.loads(dst.read_text(encoding="utf-8"))
        print(f"  복사 {f.relative_to(src)} → {dst.name} ({len(d.get('cards', []))}장)")
        n += len(d.get("cards", []))
    # 신규 카드 합류
    if NEW_CARDS.exists():
        for f in sorted(NEW_CARDS.glob("cards_*_v1.json")):
            shutil.copy2(f, LOCAL_CARDS / f.name)
            d = json.loads(f.read_text(encoding="utf-8"))
            print(f"  신규 {f.name} ({len(d.get('cards', []))}장)")
            n += len(d.get("cards", []))
    print(f"\n총 {n}장 → {LOCAL_CARDS}")
    print("원본은 건드리지 않았습니다.")


def _load_chunks(src_root: Path):
    """원본 build_psych_cards_db.card_to_chunk 를 재사용(수정 금지 원칙)."""
    sys.path.insert(0, str(src_root / "preprocess"))
    try:
        import build_psych_cards_db as B
    except ImportError:
        raise SystemExit("build_psych_cards_db 를 찾을 수 없습니다. --from 경로를 확인하세요.")
    chunks = []
    for f in sorted(LOCAL_CARDS.glob("cards_*_v1.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        cards = d.get("cards", [])
        for c in cards:
            chunks.append(B.card_to_chunk(c, d.get("theory_ko", ""), d.get("theory_en", "")))
        print(f"  · {f.name}: {len(cards)}장")
    return chunks


def cmd_build(src_root: Path):
    import chromadb
    from chromadb.utils import embedding_functions

    print(f"[1/3] 카드 로드: {LOCAL_CARDS}")
    chunks = _load_chunks(src_root)
    if not chunks:
        raise SystemExit("적재할 카드 없음. 먼저 copy 를 실행하세요.")
    ids = [c[0] for c in chunks]
    dup = {i for i in ids if ids.count(i) > 1}
    if dup:
        raise SystemExit(f"중복 card_id: {sorted(dup)}")

    print(f"[2/3] 임베딩 모델: {EMB_MODEL}")
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMB_MODEL)

    print(f"[3/3] 적재: {LOCAL_DB} / '{COLLECTION}'")
    LOCAL_DB.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(LOCAL_DB))
    try:
        client.delete_collection(COLLECTION)
    except Exception:
        pass
    col = client.create_collection(name=COLLECTION, embedding_function=ef,
                                   metadata={"hnsw:space": "cosine"})
    col.add(ids=ids, documents=[c[1] for c in chunks], metadatas=[c[2] for c in chunks])
    print(f"\n✅ {len(ids)}장 적재 완료 → {LOCAL_DB}")
    print("   psych_link.py 가 이 DB를 보게 하려면 backend/rag 의 DB 경로를 "
          "환경변수/인자로 이 경로로 바꾸세요(원본 수정 금지).")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["copy", "build"])
    ap.add_argument("--from", dest="src", default="../lanollab-data",
                    help="lanollab-data 브랜치 체크아웃 경로")
    a = ap.parse_args()
    root = Path(a.src).resolve()
    (cmd_copy if a.cmd == "copy" else cmd_build)(root)
