"""통계 근거 검색기 (기업생멸·청년삶의질·건강 등 rag_*_chunks).

심리학 이론카드는 rag/psych_retriever(민주, 정본)가 담당하고,
여기선 **통계 근거 청크만** 다룬다(경계 분리). 서사에 '숫자 근거'로 주입된다.
언어 무관 char n-gram TF-IDF, 데이터 없으면 조용히 빈 결과.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

STAT_SOURCE_HINTS = (
    "통계", "조사", "패널", "행정", "KOSIS", "KLIPS", "GOMS", "YP",
    "국가데이터처", "통계청", "고용노동부", "교육부", "KEDI", "기업생멸",
    "KNHANES", "KWCS", "지역사회건강",
)
PSYCH_SOURCE_HINTS = (
    "JPSP", "Journal of Personality", "Psychology", "심리학", "Ryff",
    "Fredrickson", "Lazarus", "Carver", "Bandura",
)


def _is_statistical_source(source: str, text: str = "") -> bool:
    """심리 논문이 통계 RAG로 새는 것을 막고 조사·행정통계만 허용한다."""
    haystack = f"{source} {text[:300]}"
    if any(hint.lower() in haystack.lower() for hint in PSYCH_SOURCE_HINTS):
        return False
    return any(hint.lower() in haystack.lower() for hint in STAT_SOURCE_HINTS)


def _safe_load(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _load_docs() -> list[dict]:
    docs: list[dict] = []
    seen: set[str] = set()

    def add(text, source, indicator, kind, _id=""):
        text = (text or "").strip()
        if not text or text[:120] in seen:
            return
        seen.add(text[:120])
        docs.append({"text": text, "source": source or "", "indicator": indicator or "", "kind": kind, "id": _id or ""})

    # 통계 근거 청크만 (rag_*chunks*.json) — 카드(cards_*)는 제외
    for p in DATA.glob("**/rag_*chunks*.json"):
        obj = _safe_load(p)
        if obj is None:
            continue
        items = obj.get("chunks") or obj.get("documents") or [] if isinstance(obj, dict) else obj
        if not isinstance(items, list):
            continue
        for it in items:
            if not isinstance(it, dict):
                continue
            text = it.get("document") or it.get("text") or it.get("content") or ""
            meta = it.get("metadata", {}) if isinstance(it.get("metadata"), dict) else {}
            source = meta.get("source") or ""
            if _is_statistical_source(source, text):
                add(text, source, meta.get("indicator") or meta.get("topic") or "", "stat", it.get("id", ""))
    return docs


class StatIndex:
    def __init__(self) -> None:
        self.docs: list[dict] = []
        self._vec = self._mat = self._cos = None
        try:
            self.docs = _load_docs()
            if self.docs:
                from sklearn.feature_extraction.text import TfidfVectorizer
                from sklearn.metrics.pairwise import cosine_similarity

                self._cos = cosine_similarity
                self._vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=1)
                self._mat = self._vec.fit_transform(d["text"] for d in self.docs)
        except Exception:
            self.docs = self.docs or []

    @property
    def n_docs(self) -> int:
        return len(self.docs)

    def retrieve(self, query: str, k: int = 4) -> list[dict]:
        if not query or self._vec is None:
            return []
        try:
            sims = self._cos(self._vec.transform([query]), self._mat)[0]
        except Exception:
            return []
        out = []
        for i in sims.argsort()[::-1]:
            if sims[i] <= 0:
                break
            out.append({**self.docs[int(i)], "score": round(float(sims[i]), 4)})
            if len(out) >= k:
                break
        return out


_INDEX: Optional[StatIndex] = None


def get_index() -> StatIndex:
    global _INDEX
    if _INDEX is None:
        _INDEX = StatIndex()
    return _INDEX


_CHOICE_HINTS = {
    "이직": "이직 소득 임금 고용안정 근속 이탈",
    "창업": "창업 자영업 생존율 폐업 소득 위험",
    "진학": "대학원 진학 취업률 학력 소득 장래성",
}


def evidence_for_choice(choice: str, k: int = 3) -> list[dict]:
    """선택지에 맞는 통계 근거 청크 top-k."""
    idx = get_index()
    if idx.n_docs == 0:
        return []
    normalized = (choice or "").strip()
    base = _CHOICE_HINTS.get(normalized, normalized)
    ranked = idx.retrieve(base, k=min(idx.n_docs, max(k * 12, 30)))
    if normalized == "이직":
        # 이직 근거에서 일반 심리·삶의 질 보고서가 임금/고용 자료를 밀어내지 않게 한다.
        job_hints = ("고용", "근로", "임금", "KLIPS", "노동")
        focused = [d for d in ranked if any(h in f"{d['source']} {d['text']}" for h in job_hints)]
        if focused:
            return focused[:k]
    return ranked[:k]
