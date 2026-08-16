"""
논문 RAG 전처리 파이프라인
==========================
담당 논문:
  - Connor & Davidson (2003) CD-RISC
  - 백현숙 외 (2010) K-CD-RISC

실행 방법:
  1. pip install pdfplumber scikit-learn
  2. PDF 파일을 data/raw/papers/ 폴더에 복사
     - connor_davidson_2003.pdf
     - baek_2010.pdf
  3. python preprocess/03_paper_rag.py

결과:
  data/vectordb/psychology/psychology_db.pkl 생성
  → backend/diary/rag_psychology.py 에서 retrieve() 로 검색
"""

import os
import re
import pickle
import pdfplumber
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# ─────────────────────────────────────────
# 설정
# ─────────────────────────────────────────
PDF_PATHS = {
    "connor_davidson_2003": "data/raw/paper/connor_davidson_2003.pdf",
    "baek_2010":            "data/raw/paper/baek_2010.pdf",
}

VECTORDB_PATH = "data/vectordb/psychology"
CHUNK_SIZE    = 500   # 청크당 글자 수

PAPER_META = {
    "connor_davidson_2003": {
        "source":      "Connor & Davidson (2003)",
        "title":       "Development of a new resilience scale: The CD-RISC",
        "journal":     "Depression and Anxiety, 18(2), 76-82",
        "doi":         "10.1002/da.10113",
        "concept":     "회복탄력성 측정 척도 (CD-RISC)",
        "when_to_use": "simulation,diary",
        "keywords":    "이직,적응,번아웃,변화,회복,스트레스,인내,유능감,통제",
    },
    "baek_2010": {
        "source":      "백현숙 외 / Baek et al. (2010)",
        "title":       "Korean Version of the Connor-Davidson Resilience Scale",
        "journal":     "Psychiatry Investigation, 7(2), 109-115",
        "doi":         "10.4306/pi.2010.7.2.109",
        "concept":     "한국판 회복탄력성 척도 (K-CD-RISC)",
        "when_to_use": "simulation,diary",
        "keywords":    "한국,적응,번아웃,끈기,낙관,스트레스,우울,자존감",
    },
}


# ─────────────────────────────────────────
# 1단계: PDF → 텍스트 추출 (페이지 단위)
# ─────────────────────────────────────────
def extract_by_page(pdf_path: str) -> list[str]:
    """페이지별 텍스트 추출"""
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t and len(t.strip()) > 50:
                pages.append(t.strip())
    return pages


def clean_page(text: str) -> str:
    """페이지 텍스트 정제"""
    text = re.sub(r'-\n\s*', '', text)    # 하이픈 줄바꿈 연결
    text = re.sub(r'\n+', ' ', text)      # 줄바꿈 → 공백
    text = re.sub(r' +', ' ', text)       # 연속 공백 제거
    return text.strip()


# ─────────────────────────────────────────
# 2단계: 텍스트 → 청크 분리
# ─────────────────────────────────────────
def split_into_sentences(text: str, size: int = CHUNK_SIZE) -> list[str]:
    """문장 단위로 청킹"""
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks, cur = [], ""
    for sent in sentences:
        if len(cur) + len(sent) + 1 <= size:
            cur = (cur + " " + sent).strip()
        else:
            if cur:
                chunks.append(cur)
            cur = sent
    if cur:
        chunks.append(cur)
    return [c for c in chunks if len(c) >= 80]


# ─────────────────────────────────────────
# 3단계: TF-IDF 벡터화 후 저장
# ─────────────────────────────────────────
def build_db(pdf_paths: dict) -> dict:
    """
    PDF → 청킹 → TF-IDF 벡터화 → pickle 저장

    ChromaDB 대신 TF-IDF + cosine similarity 사용
    이유: 외부 임베딩 모델 다운로드 없이 작동, 빠름, 가볍다
    논문 수가 30편 이상으로 늘어나면 ChromaDB + 임베딩으로 전환 추천
    """
    all_chunks, all_metas = [], []

    for paper_id, pdf_path in pdf_paths.items():
        if not os.path.exists(pdf_path):
            print(f"⚠️  파일 없음: {pdf_path}")
            print(f"   해당 경로에 PDF를 복사하세요\n")
            continue

        meta  = PAPER_META[paper_id]
        pages = extract_by_page(pdf_path)

        # 참고문헌 페이지 제거
        pages = [
            p for p in pages
            if "REFERENCES" not in p[:50] and "References" not in p[:50]
        ]

        paper_chunks = 0
        for page_num, page_text in enumerate(pages):
            clean  = clean_page(page_text)
            chunks = split_into_sentences(clean)
            for i, chunk in enumerate(chunks):
                all_chunks.append(chunk)
                all_metas.append({
                    **meta,
                    "page":        page_num + 1,
                    "chunk_index": i,
                    "paper_id":    paper_id,
                })
                paper_chunks += 1

        print(f"✅ {paper_id}: {len(pages)}페이지 → {paper_chunks}개 청크")

    # 청크가 하나도 없으면 벡터화 단계에서 'empty vocabulary' 에러가 나므로
    # 여기서 원인을 명확히 알려주고 중단한다.
    if not all_chunks:
        raise SystemExit(
            "청크가 0개입니다. PDF를 하나도 읽지 못했습니다.\n"
            f"  - PDF 경로 확인: {list(pdf_paths.values())}\n"
            "  - 파일이 있는데도 비었다면 스캔본(이미지) PDF라 텍스트 추출이 안 될 수 있습니다."
        )

    # TF-IDF 벡터화
    # char_wb + ngram(2,4): 영어/한국어 모두 처리 가능
    vectorizer = TfidfVectorizer(
        analyzer='char_wb',
        ngram_range=(2, 4),
        max_features=8000,
        sublinear_tf=True,
    )
    tfidf_matrix = vectorizer.fit_transform(all_chunks)

    db = {
        "chunks":       all_chunks,
        "metas":        all_metas,
        "vectorizer":   vectorizer,
        "tfidf_matrix": tfidf_matrix,
    }

    os.makedirs(VECTORDB_PATH, exist_ok=True)
    save_path = f"{VECTORDB_PATH}/psychology_db.pkl"
    with open(save_path, "wb") as f:
        pickle.dump(db, f)

    print(f"\n총 {len(all_chunks)}개 청크 저장 → {save_path}")
    return db


# ─────────────────────────────────────────
# 4단계: 검색 함수 (서비스에서 import하여 사용)
# ─────────────────────────────────────────
_db_cache = None  # 서버 시작 시 한 번만 로드

def retrieve(query: str, top_k: int = 2) -> str:
    """
    쿼리와 관련된 논문 청크 검색 → Claude 프롬프트에 삽입

    사용법:
        from preprocess.paper_rag import retrieve
        context = retrieve("이직 후 적응이 힘들다")
        # Claude 프롬프트의 [심리학 근거] 섹션에 삽입

    Args:
        query:  검색 쿼리 (한국어/영어 모두 가능)
        top_k:  반환할 청크 수

    Returns:
        "[출처]\n관련 내용" 형식의 문자열
        Claude 프롬프트에 바로 삽입 가능
    """
    global _db_cache

    db_path = f"{VECTORDB_PATH}/psychology_db.pkl"
    if not os.path.exists(db_path):
        return ""

    if _db_cache is None:
        with open(db_path, "rb") as f:
            _db_cache = pickle.load(f)

    q_vec = _db_cache["vectorizer"].transform([query])
    sims  = cosine_similarity(q_vec, _db_cache["tfidf_matrix"])[0]
    top   = np.argsort(sims)[::-1][:top_k]

    lines = []
    for idx in top:
        if sims[idx] > 0.01:
            m = _db_cache["metas"][idx]
            lines.append(
                f"[{m['source']} — {m['concept']}]\n{_db_cache['chunks'][idx]}"
            )

    return "\n\n".join(lines)


# ─────────────────────────────────────────
# 실행
# ─────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 55)
    print("논문 RAG 전처리")
    print("=" * 55 + "\n")

    build_db(PDF_PATHS)

    print("\n=== 검색 테스트 ===")
    tests = [
        "resilience coping stress adaptation after job change",
        "factor analysis hardiness persistence optimism Korean",
        "CD-RISC five factors personal competence tenacity",
        "burnout career transition change acceptance",
    ]
    for q in tests:
        print(f"\n쿼리: '{q}'")
        r = retrieve(q, top_k=1)
        if r:
            print(r[:300] + "...")
        else:
            print("결과 없음")

    print("\n✅ 전처리 완료. 서비스에서 retrieve() 를 import하여 사용하세요.")