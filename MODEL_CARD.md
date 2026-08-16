---
language: ko
license: cc-by-nc-4.0
tags:
  - emotion-classification
  - korean
  - diary
base_model: klue/roberta-large
---

# LIFENOLOGY 일기 감정 분석 모델

한국어 일기 텍스트의 감정을 분석하는 멀티태스크 분류기.
`klue/roberta-large` 기반, AIHub 감성대화말뭉치로 파인튜닝.

## 출력

| 헤드 | 클래스 수 | 용도 |
|---|---|---|
| 대분류 | 6 (분노/슬픔/불안/상처/당황/기쁨) | 리포트 뼈대 |
| 세부 감정 | 60 | 제안용 |
| 상황 | 12 (직장·학업·가족 등) | 맥락 탐지 |
| VAD 회귀 | 2 (valence, arousal) | 감정 시계열 그래프 |

소분류는 계층 마스킹으로 예측 대분류 내부로 제한됨.

## 성능

### 실제 일기 검증셋 (n=58, 자체 구축)

| 지표 | 값 |
|---|---|
| **감정 극성(긍/부정) F1** | **0.971** |
| **valence 부호 일치율** | **94.8%** |
| 5종 분류 (상처+당황 병합) | F1 0.737 |
| 6종 분류 | F1 0.636 |

### AIHub 공식 검증셋 (대화, n=6,640)

| 지표 | 값 |
|---|---|
| 대분류 6종 macro F1 | 0.804 |
| 대분류 accuracy | 0.810 |
| 세부 60종 macro F1 | 0.576 |
| 상황 12종 accuracy | 0.698 |

클래스별 F1: 분노 .825 / 슬픔 .760 / 불안 .787 / 상처 .714 / 당황 .765 / 기쁨 .974

## 학습 설정

- 데이터: AIHub 감성대화말뭉치 (dataSetSn=86), 대화 단위 합본 54,142건
- 백본: klue/roberta-large
- 6 epochs, batch 24, maxlen 128, lr 1.2e-5
- R-Drop 0.5, label smoothing 0.1, logit adjustment (τ=0.5), EMA 0.999

### 라벨 단위 실험

발화 단위(150k) 대비 대화 단위(54k)로 라벨링을 바꾼 결과 F1이 0.60 → 0.78로 상승.
데이터 양보다 라벨 품질이 결정적이었음.

## 한계

- **상처·당황 구분 정확도 낮음.** 원 데이터에서 `고립된`, `혼란스러운`이
  두 대분류에 중복 정의되어 있어 인간 라벨러도 구분이 어려움. 병합 사용 권장.
- 대화체 학습 데이터 → 일기체 추론의 도메인 갭 존재 (0.804 → 0.636)
- 신조어·슬랭은 별도 정규화 사전 필요
- **진단 도구가 아님.** 세부 감정은 확정이 아닌 제안으로 사용할 것.

## 사용

```python
from huggingface_hub import hf_hub_download
ckpt = hf_hub_download("JY0/lifenology-diary-emotion", "best.pt", token="hf_...")

from infer import DiaryAnalyzer   # GitHub diary_module/
az = DiaryAnalyzer(ckpt=ckpt)
result = az.analyze("오늘 발표를 망쳤다. 그래도 저녁에 친구가 밥 사줘서 좀 풀렸다.")
print(result["valence_series"])   # 감정 궤적
```

추론 코드 및 명세: https://github.com/suin037/-LIFENOLOGY_boiled_egg (`diary_module/`)

## 라이선스

학습 데이터(AIHub)의 이용약관을 따름. 비상업적 연구 목적으로만 사용.
