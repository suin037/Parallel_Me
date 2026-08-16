# qmode — 질문형 일기 모드 (A/B 비교용)

기존 자유 일기 모드와 **나란히 두고 고르기 위한** 추가 패키지.
`diary_module/` 의 기존 파일은 **한 줄도 수정하지 않았다.** (`git status` 로 확인 가능)

```
diary_module/
├── infer.py  hybrid.py  metrics.py  crisis.py  weekly.py  ...   ← 그대로. 자유 일기 모드
└── qmode/                                                       ← 신규. 질문형 모드
    ├── questions.json        질문 풀 (v0.2 · 문헌 검토 반영)
    ├── scheduler.py          출제 로직 (고정 2 + 로테이션, 위기 제약)
    ├── aggregate.py          길이 게이트 · 가중평균 · 부러움 분기
    ├── session.py            하루치 세션 → 기존 파이프라인 연결
    ├── setup_rag_local.py    RAG 복사 + 재빌드 (재귀 glob 수정 포함)
    ├── cards_new/            신규 이론카드 5장
    └── rag_local/            복사본 + 로컬 벡터DB (git 제외 권장)
```

---

## 두 모드의 차이

| | 자유 일기 (기존) | 질문형 (qmode) |
|---|---|---|
| 하루 입력 | 텍스트 1덩어리 | {질문, 답변} 4~5쌍 + 자유칸(선택) |
| 진입점 | `analyze_hybrid(az, text)` | `analyze_session(az, date, answers)` |
| 지표 집계 | 전량 동일 가중 | 길이 게이트 + 가중평균 |
| 질문 라벨 | 없음 | 리포트·서사 프롬프트에 부착 |
| 위기 대응 | 사후 탐지 | 사후 탐지 + **사전 출제 제약** |

두 모드 모두 `metrics.py` · `crisis.py` · `psych_link.py` · `hybrid.py` 를 공유한다.
따라서 A/B 비교에서 달라지는 건 **입력 형식과 집계 방식뿐**이고, 모델은 동일하다.

---

## ⚠️ 절대 하면 안 되는 것 — 질문 텍스트를 지표에 넣기

인수인계 문서 §4-5는 `analyze_hybrid(text, question=...)` 로 질문을 파이프라인에
넘기라고 되어 있었는데, **질문을 답변과 합쳐 넣으면 지표가 오염된다.**

`metrics.py` 의 `INSIGHT` 집합에 `생각`·`때문` 이, `ABSOLUTIST` 에 `가장`·`제일` 이
들어 있고, v0.2 질문 문구가 바로 그 단어를 쓴다.

실측 (`metrics.analyze_text` 로 직접 측정):

| 질문 | 입력 | insight_ratio | absolutist_ratio | first_person_ratio |
|---|---|---|---|---|
| R3 | 답변만 | 0.0000 | 0.0000 | 0.0000 |
| R3 | 질문+답변 | **0.0238** | 0.0000 | 0.0000 |
| C2 | 답변만 | 0.0000 | **0.0769** | 0.0000 |
| C2 | 질문+답변 | 0.0000 | **0.0217** | 0.0217 |
| C1 | 답변만 | 0.0000 | 0.0000 | 0.0000 |
| C1 | 질문+답변 | 0.0000 | 0.0000 | **0.0256** |

두 방향으로 다 깨진다.
- **R3**: 질문의 "생각하나요" 때문에 `insight_ratio` 가 0 → 0.0238 로 오르고,
  `rag_triggers()` 의 `liwc_cognitive_reappraisal` 이 **발화한다.**
  유저가 아니라 질문 문구 때문에 심리카드가 검색되는 것.
- **C2**: 질문이 길어 분모가 불어나면서 진짜 절대어 신호가 0.077 → 0.022 로 **희석**.
- **C1**: 질문의 "내 하루" 때문에 1인칭이 0 → 0.026 으로 상승.

→ **답변만 모델·지표에 넣고, 질문은 메타데이터로만 들고 다니다가
리포트·서사 프롬프트 단계에서 합류시킨다.** `session.py` 가 그렇게 되어 있다.

---

## 사용

```python
from infer import DiaryAnalyzer
from qmode.scheduler import Scheduler
from qmode.session import analyze_session, build_diary_metrics, to_prompt_block

# 1) 오늘 문항 뽑기
sch = Scheduler()
qs = sch.pick("2026-07-27", history=hist, crisis_recent=False, user_day=12)

# 2) 하루치 분석
az = DiaryAnalyzer(ckpt="../model_v3_e6.pt")
s = analyze_session(az, "2026-07-27", [
    {"question_id": "C1", "text": "..."},
    {"question_id": "C2", "text": "..."},
], free_text=None)

# 3) 누적 → backend 전달값
agg = build_diary_metrics(sessions)      # 5개 미만이면 diary_metrics=None
print(to_prompt_block(sessions, agg))    # 서사 프롬프트에 붙일 블록
```

의존성은 기존과 동일 (`kiwipiepy`, `torch`, `transformers==4.44.2`).
`scheduler.py` 와 `aggregate.py` 는 모델 없이도 단독 실행·검증 가능:

```bash
python qmode/scheduler.py     # 14일 출제 시뮬레이션 + 위기 주간 동작
python qmode/aggregate.py     # 길이 게이트·5개 보류·부러움 분기 검증
```

---

## RAG 로컬 실험

```bash
git worktree add ../lanollab-data lanollab-data
python qmode/setup_rag_local.py copy  --from ../lanollab-data
python qmode/setup_rag_local.py build --from ../lanollab-data
```

- 원본(`lanollab-data`)은 **복사만, 수정 안 함.** 실험은 `qmode/rag_local/` 안에서만.
- 원본 `build_psych_cards_db.py` 의 `card_to_chunk` 를 그대로 재사용한다(스키마 호환 검증 완료).
- **원본 빌드의 비재귀 glob 버그를 우회한다.** `_handoff_sohyunio/` 하위의
  회복탄력성 4장이 원래는 안 실려 벡터DB에 11장만 있었다. `rglob` 으로 20장이 된다.

| 이론파일 | 장수 | 출처 |
|---|---|---|
| cards_coping_v1 | 3 | minjub (Lazarus & Folkman 1984) |
| cards_positive_emotion_v1 | 8 | minjub (Fredrickson 2001) |
| cards_resilience_v1 | 4 | sohyun — **원래 미적재분** (Connor & Davidson 2003) |
| cards_envy_v1 | 2 | 신규 (Van de Ven et al. 2009) |
| cards_future_self_v1 | 1 | 신규 (King 2001) |
| cards_self_compassion_v1 | 2 | 신규 (Leary et al. 2007 / Kross et al. 2005) |
| **합계** | **20** | |

신규 5장은 v0.2 질문의 근거 논문과 1:1 대응한다 — D4→envy, D5→future_self,
D6→self_compassion, C2·R5→self_distancing.

---

## A/B 비교에서 볼 것

두 모드를 같은 기간 돌려 비교할 지표:

1. **응답률** — 질문형이 자유 일기보다 기록일수가 많은가
2. **답변 길이 분포** — 게이트(15/40 형태소) 임계값이 실제 분포에 맞는가
3. **지표 분산** — 질문형이 문체 편차를 줄여 지표가 안정적인가 (이게 전환의 원래 근거)
4. **위기 탐지** — 심층 문항이 위기 신호를 더 끌어내는가, 그 대응이 적절한가

3번이 핵심이다. 질문형의 존재 이유가 "신호 안정화"이므로, 분산이 안 줄면
전환 근거가 사라진다.

---

## 미해결

- `persona.py`(값→지시문 매핑)는 아직 없음. `aggregate.py` 출력이 그 입력이 된다.
- `backend/schemas.py` 의 `PredictRequest` 에 `diary_metrics` 필드 추가 필요 — backend 담당 조율.
- 로테이션 풀 부족: 심층(D) 6개라 3주면 한 바퀴. 4개 추가 필요.
  추가 시 거리두기 규칙(질문풀_설계.md §1-1) 적용 필수.
- `emotion_taxonomy.json` 상황 개수 문서 오기(12→13) 미반영.
