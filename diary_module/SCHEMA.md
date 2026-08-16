# 일기 감정 분석 모듈 — 인터페이스 명세

## 담당 경계

- **이 모듈**: 일기 텍스트 → 정량 분석 JSON
- **RAG/API 파트**: 이 JSON + 심리학 카드 → 리포트 문장 생성

정량(감정·수치)은 모델이, 정성(해석·문장)은 API가 담당한다.

---

## 0. 설치

```bash
pip install transformers==4.44.2 "tokenizers<0.20" "huggingface_hub<0.25" \
            torch pandas pyarrow scikit-learn kiwipiepy
```

모델 가중치는 HuggingFace Hub (private):

```python
from huggingface_hub import hf_hub_download
ckpt = hf_hub_download("JY0/lifenology-diary-emotion", "best.pt", token="hf_...")
```

토큰은 팀 내부 전달. **저장소에 커밋 금지.**

---

## 1. 일기 1건 분석

```python
from infer import DiaryAnalyzer
az = DiaryAnalyzer(ckpt=ckpt)   # 최초 1회 로드 (GPU 권장)
result = az.analyze(text)
```

### 반환 구조

| 필드 | 타입 | 설명 |
|---|---|---|
| `crisis_level` | int | 0 안전 / 2 주의 / 3 즉시개입 |
| `block_report` | bool | **true면 리포트 생성 금지** |
| `dominant.coarse` | str | 모델 원본 라벨 (6종) |
| `dominant.display` | str | **UI 표시용 (5종, 상처·당황→속상함)** |
| `dominant.fine` | str | 세부 감정 60종 |
| `dominant.conf` | float | 확신도 0~1 |
| `dominant.reliability` | float | 해당 클래스 검증 F1 |
| `situation.name` | str | 상황 12종 |
| `situation.conf` | float | **0.5 미만이면 사용하지 말 것** |
| `valence_mean` | float | -1(부정) ~ +1(긍정) |
| `valence_series` | list | 청크별 valence = 감정 궤적 |
| `valence_std` | float | 문서 내 감정 변동 |
| `mixed_ratio` | float | 혼재 감정 비율 |
| `coarse_dist` | dict | 6종 확률 분포 |
| `linguistic` | dict | 언어지표 원시값 |
| `rag_triggers` | list | 검색할 RAG 카드 id |
| `slang` | dict | 슬랭 검출 결과 |
| `n_chunks` | int | 분할된 청크 수 |
| `chunks` | list | 청크별 원문 + 감정 + valence |

### crisis_level 처리 규칙

| 레벨 | 동작 |
|---|---|
| 0 | 정상 리포트 |
| 2 | 리포트 생성 + 하단에 지원 안내 첨부 |
| 3 | **리포트 생성 중단**, `crisis.support_message(3)` 표시 |

```python
import crisis
if result["block_report"]:
    show(crisis.support_message(result["crisis_level"]))
    return
```

일기 저장과 감정 분석은 레벨과 무관하게 **항상 수행**한다.
바뀌는 것은 사용자에게 보여줄 화면뿐이다.

---

## 2. 주간 집계

```python
from weekly import aggregate, to_prompt_context, ryff_scores

entries = [{"date": "2026-07-13", "result": az.analyze(t1)}, ...]
agg = aggregate(entries)
ctx = to_prompt_context(agg)   # 프롬프트용 텍스트
ryff = ryff_scores(entries)    # Ryff 6축 참고 지표
```

### aggregate() 주요 필드

- `valence.mean / std / trend / negative_days / max_negative_streak / series`
- `emotions.coarse_top / fine_top / mixed_days`
- `situations.negative_context` — 부정 정서가 몰린 맥락
- `linguistic_week.approach_total / avoidant_total / coping_balance_week`
- `crisis.days` — 위기 감지된 날짜
- `quotes.lowest / highest` — 인용용 원문
- `daily[].evidence` — 일별 최고강도 청크 원문
- `daily[].keywords` — 일별 핵심 명사

### ryff_scores() 주의

- `score`는 0~10, **근거 2건 미만이면 None**
- `confidence`: 충분(3+) / 참고(2) / 근거부족(1) / 관찰없음(0)
- **정식 Ryff PWBS 척도 측정이 아님.** 일기 감정을 6요인 틀로 분류한 참고 지표
- UI 표기 필수: "Ryff 6요인 틀 기반 참고 지표 (정식 척도 측정 아님)"

---

## 3. 검증 결과

### 실제 일기 검증셋 (n=58, 직접 구축)

| 지표 | 값 | 신뢰 |
|---|---|---|
| **감정 극성 (긍/부정) F1** | **0.971** | 높음 |
| **valence 부호 일치율** | **94.8%** | 높음 |
| 5종 분류 (display 기준) | F1 0.737 / acc 0.724 | 보통 |
| 6종 분류 (coarse 기준) | F1 0.636 | 낮음 |
| **위기 감지** | **8/8, 미탐 0** | — |

### AIHub 공식 검증셋 (대화, n=6,640)

| 지표 | 값 |
|---|---|
| 6종 macro F1 | 0.804 / acc 0.810 |
| 세부 60종 macro F1 | 0.576 |
| 상황 12종 acc | 0.698 |

클래스별 F1(대화): 분노 .825 / 슬픔 .760 / 불안 .787 / 상처 .714 / 당황 .765 / 기쁨 .974

### 하락 원인

대화 0.804 → 일기 0.636. 도메인 갭 및 **라벨 체계상 중복 정의**가 원인.
원 데이터에서 `E43 고립된`(상처)과 `E51 고립된`(당황),
`E34 혼란스러운`(불안)과 `E59 혼란스러운`(당황)이 같은 이름으로 두 대분류에 존재.
상처·당황 병합 시 0.737로 회복.

---

## 4. AI 프롬프트 표현 규칙 ★필수★

**신뢰도에 따라 단정 강도를 다르게 할 것.**

| 신뢰도 | 대상 | 허용 표현 |
|---|---|---|
| 0.9+ | valence 시계열, 긍/부정 | "목요일 감정이 가장 낮았습니다" — 단정 가능 |
| 0.7~0.9 | `dominant.display` (5종) | "슬픔에 가까웠던 것 같습니다" |
| 0.7 미만 | `dominant.fine`, 낮은 conf | "혹시 ~에 가까웠나요?" 질문형 |
| — | `situation.conf < 0.5` | **언급 금지** |

추가 규칙:

1. `to_prompt_context()` 출력 근거만 사용
2. RAG 카드는 `rag_triggers` 기반 검색 + 안전장치 카드 항상 주입
3. **근거에 없는 심리학적 주장 생성 금지**
4. **진단 표현 금지** (우울증, 불안장애, ADHD 등)
5. `crisis_level >= 3`이면 리포트 생성하지 말 것
6. `dominant.conf < 0.5`면 감정 라벨을 단정하지 말고 사용자에게 확인
7. 세부 감정(fine)은 확정이 아닌 **제안**으로 표시, 수정 허용

---

## 5. UI 권장 구조

```
[층 1] 감정 흐름 그래프        신뢰 0.97  ← 주인공
       valence 시계열, 주간 추세, 반등 지점

[층 2] 오늘의 감정             신뢰 0.74
       "슬픔에 가까웠어요"  [아니에요 ▾]

[층 3] 세부 감정               참고
       "낙담한?"  [직접 고르기]
```

사용자 수정 로그는 재학습 데이터로 축적할 것.

---

## 6. 파일 구성

| 파일 | 역할 |
|---|---|
| `infer.py` | 통합 분석 (진입점) |
| `weekly.py` | 주간 집계 + Ryff 참고지표 |
| `metrics.py` | 언어지표 (Kiwi 형태소 기반) |
| `slang.py` | 신조어 정규화 |
| `crisis.py` | 위기 신호 탐지 |
| `train_v2.py` | 모델 정의 + 학습 (infer가 import) |
| `preprocess_v2.py` | AIHub 데이터 전처리 |
| `emotion_taxonomy.json` | 60감정 + VAD + 상황 + 병합 매핑 |
| `run_eval.py` / `eval_merge.py` | 검증 스크립트 |
