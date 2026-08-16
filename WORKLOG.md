# parallel-me 작업 로그 / 이어서 하기 핸드오프

> 최종 갱신: 2026-07-19 · 4-레이어 파이프라인 **실데이터 학습 완료** 상태
> 이 문서만 보고 이어서 작업할 수 있도록 환경·데이터·코드·결과·다음할일을 정리.

---

## 0. 한 줄 상태
GOMS·YP2021·KLIPS 3개 실데이터로 **L1~L4 전 레이어 학습 완료.** 단, 코드가 여러 브랜치 + 신규 파일에 흩어져 있고 **아직 미커밋**. 서빙(`/predict`) 연결은 미완.

---

## 1. 환경 (중요)
- **반드시 `knhanes` conda 환경 사용** (Python 3.11.15)
  - 경로: `C:/Users/USER/anaconda3/envs/knhanes/python.exe`
  - ⚠️ 시스템 Python 3.14로는 `econml` 설치 불가(소스빌드 실패). 반드시 knhanes.
- 설치 완료 패키지: `scikit-learn 1.6.1`, `joblib`, `lifelines 0.30`, `econml 0.16`, `python-calamine`, `pyreadstat`
  - numpy 2.4.6 유지 / pandas 3.0.3 → **2.3.3 다운그레이드**됨(lifelines 요구)
- 실행 예: `KPY="C:/Users/USER/anaconda3/envs/knhanes/python.exe"; "$KPY" train_models.py`

---

## 2. 원본 데이터 위치 (repo 밖, 상위 `lifenologylab/` 폴더)
| 데이터 | 위치 | 상태 |
|---|---|---|
| GOMS | `../goms/goms_clean.csv` | 전처리 완료본(11,498행, 팀 표준 스키마) |
| KLIPS | `../klips/klips{01~10}{p,h,a}.sav` | 원본(SPSS), 1998~2007 |
| YP2021 | `../yp2021/YP2021_w{01~04}.xlsx` | 원본(엑셀) |

---

## 3. Git 브랜치 지도 (remote: github.com/suin037/-LIFENOLOGY_boiled_egg)
| 브랜치 | 담당 | 핵심 내용 |
|---|---|---|
| `main` | jiyunjung0 | 기본 구조 |
| `lanollab-data` (현재 체크아웃) | **minjub423(나)** | 건강지표(KNHANES/KWCS/CHS) RAG + 심리학 이론카드 |
| `sohyun` | thgusdl, sohyunio | `preprocess_goms.py`, `preprocess_yp.py`, `paper_rag.py`, `eda.ipynb` |
| `suin-model` | suin | `train_models.py`(L2/L3 GOMS), `klips_train.py`(L3/L4 KLIPS) |

**브랜치들이 서로 갈라져 있고 통합(merge) 안 됨.** 전처리(sohyun)·학습(suin-model)이 다른 브랜치라 한 곳에 모아야 함.

---

## 4. 이번에 한 작업

### 4-1. 팀 코드 가져와 실행 (작업 트리에 존재, 미커밋)
- `train_models.py` ← suin-model 에서 추출
- `klips_train.py` ← suin-model 에서 추출
- `preprocess/preprocess_yp.py` ← sohyun 에서 추출

### 4-2. 없던 코드 신규 작성 (⭐ 커밋 대상)
| 파일 | 역할 |
|---|---|
| `preprocess/preprocess_klips.py` | **KLIPS 원본→가공** (klips_train이 요구하던 `klips_base.pkl`/`생존.csv` 생성). 없던 구멍을 메움 |
| `yp_train.py` | YP L4 생존분석 학습 (팀에 없던 부분) |
| `build_layer1.py` | L1 룰베이스 조회 레이어 |

> 참고: `training/` 폴더(features.py, train_*.py, make_synthetic.py)는 **초기 합성데이터 프로토타입**. 실데이터는 위 팀 코드로 대체됨. 스키마가 달라(major/gpa vs major_cat/income_now) 실데이터엔 안 씀. 참고용으로만 유지.

### 4-3. repo 내 데이터/산출물 생성
- `data/goms_clean.csv` (../goms 에서 복사)
- `data/raw/yp/YP2021_w0*.xlsx` (복사)
- `data/clean/yp_clean.csv`, `data/clean/yp_spells.csv` (preprocess_yp 산출)
- `data/raw/klips/klips_base.pkl`, `data/raw/klips/klips_base_생존.csv` (preprocess_klips 산출)
- `data/clean/layer1_rulebase.csv` (build_layer1 산출)

---

## 5. 처음부터 재현하는 법
```bash
KPY="C:/Users/USER/anaconda3/envs/knhanes/python.exe"
cd -LIFENOLOGY_boiled_egg

# (1) 데이터 배치
mkdir -p data/raw/yp data/raw/klips data/clean
cp ../goms/goms_clean.csv data/goms_clean.csv
cp ../yp2021/YP2021_w0*.xlsx data/raw/yp/

# (2) 전처리
"$KPY" preprocess/preprocess_yp.py      # → data/clean/yp_clean.csv, yp_spells.csv
"$KPY" preprocess/preprocess_klips.py   # ../klips 읽어 → data/raw/klips/klips_base*.  (원본은 복사 안 함)

# (3) 학습
"$KPY" build_layer1.py     # L1 룰베이스   → layer1_lookup.pkl
"$KPY" train_models.py     # L2 KNN + L3 EconML(GOMS) → knn.pkl, econml.pkl, encoders.pkl
"$KPY" yp_train.py         # L4 생존(YP)   → lifelines_yp.pkl
"$KPY" klips_train.py      # L3+L4(KLIPS)  → econml_klips.pkl, lifelines_klips.pkl
```

---

## 6. 학습 결과 (실데이터)
| 레이어 | 방법/데이터 | 아티팩트 | 핵심 수치 |
|---|---|---|---|
| **L1** 룰베이스 | GOMS 집계 | `layer1_lookup.pkl` | 이직자 소득변화: 보건의료 +30.4% / 경영사무 +29.3% / **IT(연구공학) +28.5%** / … 미용여행 +2.0% |
| **L2** KNN | GOMS 11,318명 | `knn.pkl`, `encoders.pkl` | 이직 비율 22.5%, 피처 9개 |
| **L3** EconML | KLIPS 종단(정본) | `econml_klips.pkl` | ATE 이직→익년임금 **+1~2만원 (비유의)** (CausalForest +1.1 / LinearDML +2.0) |
| L3(참고) | GOMS 단면 | `econml.pkl` | ATE **-16.2만원** (CI -53~+21) |
| **L4** lifelines | KLIPS 종단 | `lifelines_klips.pkl` | 이직 누적확률 **1년 27% / 3년 41% / 5년 50%** |
| L4(추가) | YP 스펠 | `lifelines_yp.pkl` | 근속 중앙값 72개월, Cox concordance 0.76 |

**핵심 관찰:** L1의 "이직자 소득 +28%"는 선택편향. L3의 순수 인과효과는 ≈0 → 인과추론이 필요한 이유를 실데이터가 입증.

> 폐기 대상: `backend/models/artifacts/lifelines.pkl` (초기 합성 산출물, 이제 `_yp`/`_klips`가 대체).

---

## 7. ⚠️ 검증/주의 필요
1. **KLIPS 전처리는 코드북 없이 라벨 기반 작성.** 이직=취업시점(년/월) 변화로 파생, 월임금은 **명목값**(컬럼명 `월임금_실질`이나 디플레이트 안 함, 1998~2007 혼재). → 담당자 코드북 검증 + 실질임금 환산 필요.
2. **경로 불일치:** `preprocess_goms.py`(sohyun)는 `data/clean/goms_clean.csv`에 저장하는데, `train_models.py`는 `data/goms_clean.csv`를 읽음. (지금은 GOMS 완료본을 후자 경로에 직접 복사해 우회)
3. **YP→학습 연결이 팀 코드엔 없었음.** `yp_train.py`(신규)로 L4만 연결. YP 패널 기반 L3는 미구현.
4. **서빙 미연결:** `/predict` 붙이려면 backend 의존성(fastapi/uvicorn/pydantic-settings/anthropic) 설치 + suin-model 의 backend 모델 파일 필요. 아티팩트 형식이 팀(suin-model) 기준이라, `lanollab-data`의 backend 모듈(초기 내 편집본)과는 계약이 다름.
5. **아티팩트가 두 sklearn 환경에서 섞여 나왔다.** (2026-08-17 확인)
   HF(`suinnn/parallel-me-artifacts`)에서 12개를 받아 `sklearn 1.6.1`로 열어보니:

   | 아티팩트 | 저장된 sklearn |
   |---|---|
   | `knn.pkl` (필수) | **1.9.0** |
   | `econml_klips.pkl` (필수) | **1.9.0** |
   | `econml.pkl` (선택) | **1.9.0** |
   | 나머지 9개 | 경고 없음 |

   서빙(`requirements-prediction.txt`)은 `1.6.1`이라 필수 2개가 cross-version 언피클이다.
   `InconsistentVersionWarning: might lead to breaking code or invalid results` 가 뜬다.
   **다만 12개 전부 예외 없이 로드되고 프로덕션도 정상 동작 중이다**(`/health` ok).

   깔끔한 해가 없다 — 어느 쪽으로 맞춰도 반대쪽이 어긋난다:
   - `1.6.1` 유지 → `knn`·`econml_klips` 가 계속 cross-version (현재 상태)
   - `1.9.0` 으로 올림 → econml 0.16.0 을 못 씀(`<1.7` 요구). 0.17.0 으로 올리면
     0.16.0 으로 저장된 `*_break`·`*_startup`·`*_yp` 가 반대로 어긋남

   → **진짜 해결은 한 환경에서 전부 재학습.** 그전까지는 `1.6.1` 고정을 유지한다
   (배포와 일치하고, 바꾸면 econml 이 깨진다).

   참고: `requirements-prediction.txt` 주석과 RUN.md 는 "아티팩트가 1.6.1 로 저장돼
   있다"고 적고 있으나 위 3개는 사실이 아니다. 재학습 전까지 그 문구를 근거로 삼지 말 것.

---

## 8. 참고: 심리학 이론카드 (minjub423 작업, 별개)
전처리한 논문 2편 → 카드 파일:
- **Lazarus & Folkman (1984)** 대처이론 → `data/lanollab/심리학_이론카드/cards_coping_v1.json` (원본 `../coping_cards.json`)
- **Fredrickson (2001)** broaden-and-build → `data/lanollab/심리학_이론카드/cards_positive_emotion_v1.json` (원본 `../positive_emotion_cards.json`)
- (CD-RISC 회복탄력성 논문 `paper_rag.py`는 sohyunio 작업 — 별개)

---

## 9. 다음 할 일 (TODO)
- [ ] 신규 파일(`preprocess/preprocess_klips.py`, `yp_train.py`, `build_layer1.py`) 커밋 + PR
- [ ] `sohyun` + `suin-model` + 신규 작업을 `main`으로 **통합(merge)**
- [ ] KLIPS 전처리 **코드북 검증** + **실질임금 디플레이트**
- [ ] 경로 정합성 통일(`data/clean/goms_clean.csv` vs `data/goms_clean.csv`)
- [ ] 서빙 연결: backend 의존성 설치 → 아티팩트를 `/predict`에 배선(L1~L4 통합, KLIPS판 우선)
- [ ] 폐기: 합성 `lifelines.pkl` 제거
- [ ] **`knn.pkl`·`econml_klips.pkl`·`econml.pkl` 을 sklearn 1.6.1 + econml 0.16.0 환경에서 재학습** (7-5 참고)
- [ ] (선택) YP 패널 기반 L3 인과추론 추가
