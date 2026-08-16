"""
psychology_db.pkl 을 사람이 읽을 수 있는 파일로 변환/확인.

실행:
    python preprocess/inspect_db.py

생성물(같은 폴더):
    psychology_db_preview.json  — 청크 텍스트 + 메타 (VSCode에서 열람 가능)
    psychology_db_preview.txt   — 사람이 훑어보기 좋은 형태
"""

import json
import pickle
from pathlib import Path

DB_PATH = Path("data/vectordb/psychology/psychology_db.pkl")
OUT_DIR = DB_PATH.parent


def main():
    if not DB_PATH.exists():
        raise SystemExit(f"파일 없음: {DB_PATH.resolve()}  (먼저 paper_rag.py 실행)")

    with open(DB_PATH, "rb") as f:
        db = pickle.load(f)

    chunks, metas = db["chunks"], db["metas"]

    # -- 콘솔 요약 --------------------------------------------------------
    print(f"총 청크 수 : {len(chunks)}")
    print(f"TF-IDF 행렬: {db['tfidf_matrix'].shape}")
    by_paper = {}
    for m in metas:
        by_paper[m["paper_id"]] = by_paper.get(m["paper_id"], 0) + 1
    print(f"논문별 청크: {by_paper}\n")

    # -- 1) JSON 로 저장 (기계+사람 모두 읽기 좋음) ----------------------
    records = [
        {
            "index": i,
            "paper_id": m["paper_id"],
            "source": m["source"],
            "page": m["page"],
            "text": c,
        }
        for i, (c, m) in enumerate(zip(chunks, metas))
    ]
    json_path = OUT_DIR / "psychology_db_preview.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"저장 → {json_path}")

    # -- 2) TXT 로 저장 (사람이 훑기 좋음) -------------------------------
    txt_path = OUT_DIR / "psychology_db_preview.txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(f"[{r['index']}] {r['source']} (p.{r['page']})\n")
            f.write(r["text"] + "\n")
            f.write("-" * 70 + "\n")
    print(f"저장 → {txt_path}")


if __name__ == "__main__":
    main()
