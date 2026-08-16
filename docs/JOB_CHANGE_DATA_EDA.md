# 현재 이직 모델 학습 데이터 EDA

> 모델 입력 직전 데이터 기준. KLIPS는 `wage_outlier=0` 필터 후, YP는 연속 연도 전이표 생성 후 분석했다.

## 데이터 구성

| 데이터 | 담당 지표 | 행 | 사람 | 이직 행 | 이직률 | 1인당 전이(중앙값) |
|---|---|---:|---:|---:|---:|---:|
| KLIPS | 경제적 안정도·삶의 질 | 39,261 | 8,930 | 5,756 | 14.7% | 4.0 |
| YP | 성장 가능성 | 35,259 | 12,213 | 3,597 | 10.2% | 3.0 |

## 결과변수 기술통계

| 데이터 | 결과변수 | 유지 n | 이직 n | 유지 평균 | 이직 평균 | 이직 결측률 |
|---|---|---:|---:|---:|---:|---:|
| KLIPS | 실질임금 변화율 | 32,560 | 3,166 | 6.017 | 17.967 | 45.0% |
| KLIPS | 소득 감소 확률 | 32,560 | 3,166 | 0.521 | 0.429 | 45.0% |
| KLIPS | 삶의 만족도 변화 | 27,409 | 4,663 | 0.045 | 0.229 | 19.0% |
| KLIPS | 행복도 변화 | 27,406 | 4,663 | 0.007 | 0.169 | 19.0% |
| KLIPS | 건강점수 변화 | 33,487 | 5,756 | -0.029 | -0.002 | 0.0% |
| KLIPS | 웰빙지수 변화 | 27,410 | 4,663 | 0.026 | 0.199 | 19.0% |
| YP | 자기발전 만족도 변화 | 10,942 | 1,713 | -0.008 | 0.173 | 52.4% |
| YP | 장래성 만족도 변화 | 10,942 | 1,713 | -0.006 | 0.174 | 52.4% |
| YP | 직무 만족도 변화 | 10,942 | 1,713 | 0.001 | 0.112 | 52.4% |

## 주요 품질 경고

- 결측률 20% 이상: YP.growth_change 64.1%, YP.work_change 64.1%, YP.future_change 64.1%, YP.income_t 55.2%, YP.growth_t 54.4%, YP.firm_size_t 54.4%, YP.future_t 54.4%, YP.work_t 54.4%, YP.stability_t 54.4%, YP.emp_status_t 54.4%, KLIPS.firm_size_t 51.1%
- 이직/유지 결측률 차이 ≥10%p: YP.stability_t -56.0%p, YP.growth_t -56.0%p, YP.firm_size_t -56.0%p, YP.future_t -56.0%p, YP.work_t -56.0%p, YP.emp_status_t -56.0%p, YP.income_t -54.7%p, KLIPS.wage_change_pct +42.2%p, KLIPS.wage_down_t1 +42.2%p, KLIPS.tenure_t +41.8%p, KLIPS.jobtype_t +41.8%p, KLIPS.employment_status_t +41.8%p, KLIPS.occupation_group_t +41.8%p, KLIPS.real_wage_t +41.0%p, KLIPS.firm_size_t +22.2%p, YP.growth_change -13.1%p, YP.future_change -13.1%p, YP.work_change -13.1%p
- 이직/유지 간 표준화 차이 |SMD|≥0.1: KLIPS.age_t -0.36, KLIPS.real_wage_t -0.38, KLIPS.firm_size_t -0.22, KLIPS.tenure_t -0.51, YP.income_t -0.55, YP.growth_t -0.27, YP.future_t -0.31, YP.work_t -0.24, YP.stability_t -0.33
- 범주 비율 최대 차이 ≥10%p: KLIPS.sex_t 13.3%, KLIPS.employment_status_t 41.8%, KLIPS.occupation_group_t 41.8%, KLIPS.jobtype_t 41.8%, YP.firm_size_t 56.0%, YP.emp_status_t 56.0%
- KLIPS 연도별 이직률 범위: 12.9%~19.0%
- YP 연도별 이직률 범위: 9.8%~10.7%
- YP의 실제 연령 범위는 20~30세라서 31~45세 성장 예측으로 일반화할 수 없다.

## 모델링 해석

- 동일 인물이 여러 연도에 반복 등장하므로 행 단위 무작위 분리는 누수다. 현재처럼 pid 단위 분리를 유지해야 한다.
- 이직률이 낮고 연도별로 변하므로 정확도보다 ROC-AUC·Brier·overlap과 연도 외부검증을 함께 봐야 한다.
- `*_change`는 결과변수이고 `*_t1`은 미래 정보다. 둘 다 입력 피처로 사용하면 안 된다.
- 이직/유지의 사전 특성 차이가 크면 단순 평균 차이가 아니라 propensity/AIPW 보정이 필요하다.
- 성장·삶의 질은 주관척도 변화량이므로 척도 방향, 천장효과, 회귀-평균 효과를 추가 확인해야 한다.

## EDA 결론과 즉시 조치

1. **KLIPS 타깃 코호트 재정의:** 이직 행 중 약 42%는 t 시점 직업정보가 통째로 없다. 현재 삶의 질 모델에는 실업→취업 전이가 이직과 섞일 수 있으므로, t와 t+1 모두 취업 상태인 직장 간 이동만 별도 추출해야 한다.
2. **YP 분석대상 명시:** 성장 문항은 전체 전이의 약 36%에서만 전후 관측된다. 결과가 있는 취업자 코호트와 전체 코호트를 분리하고, 관측 여부를 만드는 선택편향을 검증해야 한다.
3. **연령 적용범위 제한:** YP 성장 표본은 실제 20~30세뿐이다. 데이터 보강 전까지 성장 결과를 31세 이상에게 일반화하지 않는다.
4. **결측을 단순 대체하지 않기:** 기업규모와 고용 관련 결측은 무작위 결측이 아니다. 고용상태 필터·결측 사유 범주·완전사례 민감도 분석을 비교한다.
5. **그 다음 재학습:** 위 코호트 수정 후 3지표를 다시 학습하고 기존 결과와 표본 수·효과 방향·시간검증을 비교한다.

## 생성 파일

- `data/clean/job_change_eda_summary.json`
- `data/clean/job_change_eda_missingness.csv`
- `data/clean/job_change_eda_group_balance.csv`
- `data/clean/job_change_eda_outcomes.csv`
- `docs/assets/job_change_eda_klips.png`, `docs/assets/job_change_eda_yp.png`
