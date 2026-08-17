"""
심리학 이론카드 검색기 (psych_theory 컬렉션).

레이어2 출력(3지표 점수 + 감정 키워드) → 관련 이론카드 top-k retrieve.
레이어3(Claude 서사)이 summary·interventions·source 를 근거로 쓴다.

핵심 설계
- 임계값(낮음/중간/높음 경계)은 '카드'가 아니라 '여기'에 둔다(INDICATOR_THRESHOLDS).
  레이어2가 연속점수를 주든 버킷을 주든, 카드는 손대지 않고 이 설정만 바꾸면 된다.
- 매칭 2단계:
  (1) 메타 게이팅: 쿼리 지표가 카드 indicator 목록에 있고, direction 이 지표 버킷과
      호환되면 후보. (예: 삶의질=낮음 + direction=낮을수록_적용 → 통과)
  (2) 의미 유사도: 감정·상황 쿼리 텍스트와 document 임베딩 유사도로 후보를 정렬.
  코퍼스가 작아(수십 장) 전체를 유사도 정렬 후 파이썬에서 게이팅한다.

사용:
    from backend.rag.psych_retriever import retrieve
    cards = retrieve(indicator="삶의질", score=0.18,
                     emotions=["후회", "자책"], decision_type="이직", k=3)
"""

import json
import threading
from pathlib import Path

# chromadb / sentence-transformers 는 무거운 선택 의존성이라 지연 임포트한다.
# 미설치·벡터DB 미빌드 환경에서는 카드 JSON 기반 폴백으로 자동 전환(아래 _fallback_retrieve).

ROOT = Path(__file__).resolve().parent.parent.parent
DB_DIR = ROOT / "data" / "vectordb"
CARDS_DIR = ROOT / "data" / "lanollab" / "심리학_이론카드"
EXTRA_CARDS_DIR = ROOT / "diary_module" / "qmode" / "cards_new"
COLLECTION = "psych_theory"
EMB_MODEL = "jhgan/ko-sroberta-multitask"  # 로더와 반드시 동일

# ── 임계값 설정(카드 밖으로 분리한 부분) ────────────────────────────────
# score < 낮음 → '낮음', score > 높음 → '높음', 그 사이는 '중간'.
# 지표별로 다르게 두고 싶으면 키를 추가한다. 없으면 _default 사용.
# indicators.py v2 부터 점수가 **같은 나이대 분포의 백분위 순위**라, 이 임계값은
# 그대로 "하위 1/3 / 상위 1/3" 을 뜻하게 됐다(예전 손튜닝 점수에선 의미가 없었다).
INDICATOR_THRESHOLDS = {
    "_default": {"낮음": 0.33, "높음": 0.66},
    # "경제적안정도": {"낮음": 0.30, "높음": 0.70},
}

# 레이어2가 언더스코어 표기를 줄 수도 있어 쿼리도 정규화한다(로더와 동일 규칙).
# 카드 태그는 구지표 3개(경제적안정도·성장가능성·삶의질)로 달려 있다.
# backend 지표가 5축으로 바뀌었으므로 **질의 쪽을 카드 태그 어휘로 되돌린다**
# — 카드를 재태깅하지 않고도 5축 질의가 기존 코퍼스에 걸린다.
# 관계·자기실현·안정은 예전에 '삶의질' 하나로 접혀 있던 축이라 셋 다 삶의질로 간다.
INDICATOR_NORMALIZE = {
    "삶의_질": "삶의질",
    "경제적_안정도": "경제적안정도",
    "성장_가능성": "성장가능성",
    # ── v3 5축 → 카드 태그(구지표) ──
    "경제": "경제적안정도",
    "성장": "성장가능성",
    "관계": "삶의질",
    "자기실현": "삶의질",
    "안정": "삶의질",
}


def bucket(score, indicator=None):
    """연속 점수(0~1) → '낮음'/'중간'/'높음'. 임계값은 INDICATOR_THRESHOLDS."""
    t = INDICATOR_THRESHOLDS.get(indicator, INDICATOR_THRESHOLDS["_default"])
    if score < t["낮음"]:
        return "낮음"
    if score > t["높음"]:
        return "높음"
    return "중간"


def _direction_matches(direction, level):
    """카드 direction 과 지표 버킷(level)의 호환성.

    낮을수록_적용 → 지표가 '높음'이 아닐 때(낮음/중간) 적용.
    높을수록_적용 → 지표가 '낮음'이 아닐 때(높음/중간) 적용.
    (강한 트리거는 각각 낮음/높음. 중간은 약하게 허용 — 필요시 여기서 조인다.)
    """
    if not direction:
        return True
    if direction == "낮을수록_적용":
        return level != "높음"
    if direction == "높을수록_적용":
        return level != "낮음"
    return True


_client = None
_collection = None
# 임베딩 모델 로딩은 30초 넘게 걸린다. 락이 없으면 서버 기동 워밍업 스레드와
# 때마침 들어온 첫 요청이 **동시에** 모델을 올려 두 배로 기다리게 된다.
_load_lock = threading.Lock()


def _get_collection():
    """chromadb 컬렉션(정본). 미설치/미빌드면 예외 → 호출측이 폴백으로 전환."""
    global _client, _collection
    if _collection is not None:
        return _collection
    with _load_lock:
        if _collection is not None:            # 락 대기 중에 다른 쪽이 끝냈으면 재사용
            return _collection
        import chromadb  # 지연 임포트(무거운 선택 의존성)
        from chromadb.utils import embedding_functions

        if not DB_DIR.exists():
            raise RuntimeError(f"벡터DB 없음: {DB_DIR} (build_psych_cards_db.py 필요)")
        ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMB_MODEL)
        _client = chromadb.PersistentClient(path=str(DB_DIR))
        _collection = _client.get_collection(COLLECTION, embedding_function=ef)
    return _collection


def is_loaded() -> bool:
    """임베딩 모델·벡터DB 가 이미 메모리에 올라와 있는지(워밍업 상태 확인용)."""
    return _collection is not None


# ── 폴백: chromadb/ST/벡터DB 없이도 카드 JSON에서 직접 검색 ─────────────────
# 민주 로직(임계값·direction·정규화)은 그대로, 검색만 키워드 기반으로 대체.
_CARDS_CACHE = None


def _load_cards():
    global _CARDS_CACHE
    if _CARDS_CACHE is not None:
        return _CARDS_CACHE
    cards = []
    for card_dir in (CARDS_DIR, EXTRA_CARDS_DIR):
        if not card_dir.exists():
            continue
        for p in card_dir.glob("**/cards_*.json"):
            try:
                obj = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            theory_ko = obj.get("theory_ko", "")
            for c in obj.get("cards", []):
                appl = c.get("applicable_situations", {}) or {}
                inds = [INDICATOR_NORMALIZE.get(i, i) for i in appl.get("indicator", [])]
                src = c.get("source", {})
                src = src.get("citation", "") if isinstance(src, dict) else str(src)
                cards.append({
                    "card_id": c.get("card_id", ""),
                    "theory_ko": c.get("theory_ko", theory_ko),
                    "concept_ko": c.get("concept_ko", ""),
                    "summary": c.get("summary", ""),
                    "interventions": c.get("interventions", []) or [],
                    "narrative_guidance": c.get("narrative_guidance", ""),
                    "indicator": inds,
                    "direction": appl.get("direction", ""),
                    "emotion_keywords": appl.get("emotion_keywords", []) or [],
                    "decision_types": appl.get("decision_types", []) or [],
                    "evidence_level": c.get("evidence_level", ""),
                    "source": src,
                    "document": f"{c.get('concept_ko','')}. {c.get('summary','')}",
                })
    _CARDS_CACHE = cards
    return cards


def _fallback_retrieve(indicator, level, emotions, decision_type, k, allow_indicator_miss):
    q = set(emotions or []) | ({decision_type} if decision_type else set())
    out = []
    for c in _load_cards():
        ind_ok = indicator in c["indicator"]
        if not ind_ok and not allow_indicator_miss:
            continue
        if ind_ok and not _direction_matches(c["direction"], level):
            continue
        # 키워드 겹침 기반 유사도(감정/선택유형)
        overlap = len(q & (set(c["emotion_keywords"]) | set(c["decision_types"])))
        sim = round(0.4 + 0.15 * overlap + (0.1 if ind_ok else 0), 4)
        out.append({**c, "similarity": sim, "indicator_matched": ind_ok})
    out.sort(key=lambda x: x["similarity"], reverse=True)
    return out[:k]


def retrieve(indicator, score=None, level=None, emotions=None,
             decision_type=None, k=3, allow_indicator_miss=False):
    """관련 이론카드 top-k.

    indicator : 지표 이름('삶의질' 등). 언더스코어 표기도 자동 정규화.
    score     : 지표 연속점수(0~1). level 미지정 시 임계값으로 버킷팅.
    level     : '낮음'/'중간'/'높음'. 주어지면 score 대신 사용.
    emotions  : 감정 키워드 리스트(의미검색 쿼리에 사용).
    decision_type : 선택 유형('이직' 등). 있으면 쿼리 텍스트에 가중.
    k         : 반환 개수.
    allow_indicator_miss : True면 지표 불일치 카드도 유사도만으로 후보에 포함.
    """
    indicator = INDICATOR_NORMALIZE.get(indicator, indicator)
    emotions = emotions or []
    if level is None:
        if score is None:
            raise ValueError("score 또는 level 중 하나는 필요합니다.")
        level = bucket(score, indicator)

    # chromadb(정본) 시도 → 미설치/미빌드면 카드 JSON 폴백으로 전환
    try:
        col = _get_collection()
    except BaseException:
        return _fallback_retrieve(indicator, level, emotions, decision_type, k, allow_indicator_miss)

    # 의미검색 쿼리 텍스트: 감정 + 선택맥락(+지표상태)로 구성
    q_parts = list(emotions)
    if decision_type:
        q_parts.append(decision_type)
    q_parts.append(f"{indicator} {level}")
    query_text = " ".join(q_parts) if q_parts else indicator

    # 전체를 유사도 순으로 받아서 파이썬에서 게이팅(코퍼스가 작음)
    total = col.count()
    res = col.query(query_texts=[query_text], n_results=total,
                    include=["metadatas", "documents", "distances"])
    metas = res["metadatas"][0]
    docs = res["documents"][0]
    dists = res["distances"][0]

    out = []
    for meta, doc, dist in zip(metas, docs, dists):
        card_inds = [x for x in meta.get("indicator", "").split(",") if x]
        ind_ok = indicator in card_inds
        if not ind_ok and not allow_indicator_miss:
            continue
        if ind_ok and not _direction_matches(meta.get("direction", ""), level):
            continue
        out.append({
            "card_id": meta["card_id"],
            "theory_ko": meta.get("theory_ko", ""),
            "concept_ko": meta.get("concept_ko", ""),
            "summary": meta.get("summary", ""),
            "interventions": [x for x in meta.get("interventions", "").split(" || ") if x],
            "narrative_guidance": meta.get("narrative_guidance", ""),
            "indicator": card_inds,
            "direction": meta.get("direction", ""),
            "emotion_keywords": [x for x in meta.get("emotion_keywords", "").split(",") if x],
            "decision_types": [x for x in meta.get("decision_types", "").split(",") if x],
            "evidence_level": meta.get("evidence_level", ""),
            "source": meta.get("source", ""),
            "document": doc,
            "similarity": round(1 - dist, 4),   # cosine distance → 유사도
            "indicator_matched": ind_ok,
        })
        if len(out) >= k:
            break
    return out


if __name__ == "__main__":
    # 데모: 삶의 질 낮음 + 후회/자책 + 이직 맥락
    print("데모 쿼리: indicator=삶의질, score=0.18(→낮음), emotions=[후회,자책], decision=이직\n")
    for i, c in enumerate(retrieve(indicator="삶의질", score=0.18,
                                   emotions=["후회", "자책"], decision_type="이직", k=3), 1):
        print(f"[{i}] {c['card_id']}  (유사도 {c['similarity']}, 지표일치={c['indicator_matched']})")
        print(f"    이론: {c['theory_ko']} · 개념: {c['concept_ko']}")
        print(f"    direction={c['direction']} · 감정={c['emotion_keywords']}")
        print(f"    출처: {c['source'][:70]}...")
        print()
