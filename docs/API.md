# Parallel Me — 예측 엔진 API 계약 (`/predict`)

시뮬레이션 예측 엔진(L1~L5)이 제공하는 HTTP API 스펙입니다.
**사이트(입력·화면)와 일기 모듈이 이 문서만 보고 붙일 수 있도록** 입력/출력/선택지별 동작을 정리했습니다.

레이어 구성:
- **L1** 룰베이스 생활지표(경제·삶의질·건강·창업·진학) · **L2** KNN 유사사례(GOMS+청년 YP) · **L3** EconML 인과효과 · **L4** lifelines 생존 · **L5** 종단 궤적(10년 소득 경로 + 청년 만족도 궤적 + 선택지 평행우주)
- 서버: FastAPI. 로컬 실행 시 기본 `http://localhost:8000`, 자동 문서 `http://localhost:8000/docs`
- 프론트 CORS 허용: `http://localhost:5173`

---

## 1. 엔드포인트

| 메서드 | 경로 | 설명 |
|---|---|---|
| `GET` | `/health` | 상태 확인 |
| `POST` | `/predict` | 현재의 나 + 진로 선택 **1개** → 평행우주 추정 결과(원자료·전 레이어) |
| `POST` | `/compare` | 현재의 나 + 진로 선택 **A/B 2개** → **발표 카드용 비교 뷰**(3지표×1·3·5·10년) |

> **사이트(4번)·일기(2번)는 화면 렌더링에 `/compare` 를 기준으로 붙이세요.** `/predict` 는 단일 선택 원자료가 필요할 때(또는 `/compare` 응답의 `scenarios.*.raw` 로도 동일하게) 사용합니다.

---

## 2. 입력 — `POST /predict` (JSON body)

| 필드 | 타입 | 필수 | 허용값 / 범위 | 설명 |
|---|---|---|---|---|
| `age` | int | ✅ | 18 ~ 70 | 나이 |
| `sex` | string | ✅ | `"1"`=남 / `"2"`=여 | 성별 (**문자열**) |
| `major` | string | ✅ | 전공 계열 (예: `"공학"`,`"사회"`,`"자연"`) | 전공. 계열명이면 KEDI 취업률/진학률 매칭에 사용 |
| `choice` | string | ✅ | 이직 / 창업 / 진학 (자유 텍스트 OK) | 가정할 진로 선택 |
| `gpa` | float | ❌ | 0 ~ 4.5 | 학점 (현재 미사용) |
| `monthly_wage` | float | ❌ | > 0 | 현재 월소득(만원) |
| `satis_overall` | int | ❌ | 1 ~ 5 | 직무 만족도 |
| `life_satis` | int | ❌ | 1 ~ 7 | 삶의 만족도 |
| `happy` | int | ❌ | 1 ~ 7 | 행복감 |
| `is_regular` | int | ❌ | 1=정규직 / 2=비정규직 | 고용형태 (**궤적 매칭에도 사용**) |
| `firm_size` | int | ❌ | 1 ~ 9 | 기업규모 코드 |
| `edu_level` | int | ❌ | 5=고졸 6=전문대 7=대졸 8=석사 9=박사 | **교육수준 — 종단 궤적 개인화에 강력. 사이트 입력에 추가 권장** |

> 선택 항목은 안 보내도 됩니다(학습 데이터 중앙값으로 대체). 특히 **`edu_level`은 궤적을 가장 크게 가르는 변수**라, 받으면 예측 개인화가 크게 좋아집니다.
> `choice` 분류: `창업/사업/자영`→창업, `진학/대학원/유학/석사/박사`→진학, 그 외→이직.

---

## 3. 출력 — `PredictResponse` (JSON)

| 필드 | 타입 | 설명 |
|---|---|---|
| `choice` | string | 적용된 선택지 (이직/창업/진학) |
| `coverage` | string | **이 선택지에 어떤 레이어가 제공됐는지 사람이 읽는 설명** (4절) |
| `expected_wage` | float \| **null** | 유사집단 기대 월소득(L2). 이직만 |
| `causal_effect` | float \| **null** | 선택→소득 인과효과(L3, 만원). 이직만 |
| `survival_months` | float \| **null** | 평균 재직기간(L4, 개월). 이직만 |
| `neighbors` | `NeighborCase[]` | 유사 사례(L2). 이직만 채워짐 |
| `neighbor_changed_ratio` | float \| **null** | 유사집단 중 실제 이직 비율. 이직만 |
| `risk_timeline` | `{연차: 확률}` | 이직=이직확률(L4) / 창업=폐업확률 / 진학=`{}` |
| `life_indicators` | `LifeIndicator[]` | Layer1 생활지표 패널 — **선택지 무관 항상 제공** |
| `trajectory` | `TrajectoryPoint[]` | **L5 종단 소득 궤적** — 비슷한 사람들의 향후 N년(≈10년, KLIPS) 소득·이직 실제 분포 |
| `wellbeing_trajectory` | `WellbeingPoint[]` | **만족도 궤적** — 종합 만족도(1~5)의 시간 변화(청년·YP, ≈4년). 소득 궤적과 짝지어 해석. **청년 범위 밖이면 `[]`** |
| `scenario_trajectories` | `{시나리오: TrajectoryPoint[]}` | **선택지 평행우주** — `{"유지":…, "이직":…}`. **이직 choice에서만** |
| `narrative` | string | 설명 문장 (**3번 팀원 RAG가 생성**. 미설정 시 `""`) |

### `NeighborCase` (유사 사례 1건 — L2)

| 필드 | 타입 | 설명 |
|---|---|---|
| `source` | string | `"GOMS"`(전공 매칭) / `"YP"`(청년패널). **점수는 출처끼리만 비교** |
| `similarity` | float | 유사도(1에 가까울수록 유사) |
| `monthly_wage` | float \| null | 월소득(만원) |
| `job_category` | string \| null | 직종/전공 (YP는 null) |
| `satis_overall` | float \| null | 직무 만족도 |
| `life_satis` | float \| null | 삶의 만족도 (YP는 null) |
| `job_changed` | int \| null | 이직 경험(0/1) |

### `LifeIndicator` (생활지표 1건 — L1)

| 필드 | 타입 | 설명 |
|---|---|---|
| `dimension` | string | 경제 / 삶의질 / 삶의질(청년) / 정신건강 / 신체건강 / 직업환경 / 진학·취업 / 창업 |
| `indicator` / `value` / `unit` | | 지표명 / 값 / 단위 |
| `group` | string | 기준 집단 (예: "성별×연령대", "29세이하·2025") |
| `source` | string | 출처 조사명 |

### `TrajectoryPoint` (궤적 한 시점 — L5)

| 필드 | 타입 | 설명 |
|---|---|---|
| `year` | int | 시작 기준 경과 연수(0=현재) |
| `age` | int | 그 시점 나이 |
| `sample_n` | int | **이 시점까지 추적된 유사인 수 (작을수록 불확실 — 그래프에 표시 권장)** |
| `income_p25` / `income_p50` / `income_p75` | float | 월소득 하위25% / 중앙값 / 상위25% (만원) |
| `job_change_cum` | float \| null | 시작 이후 누적 이직 경험 비율 |

### `WellbeingPoint` (만족도 궤적 한 시점 — L5)

| 필드 | 타입 | 설명 |
|---|---|---|
| `year` / `age` / `sample_n` | int | 경과 연수 / 나이 / 추적 표본 수 |
| `satis_p25` / `satis_p50` / `satis_p75` | float | 종합 만족도 하위25% / 중앙값 / 상위25% (**1~5**) |

---

## 4. 선택지별 동작 (⚠️ 연동 핵심)

개인단위 레이어(L2/L3/L4)와 평행우주는 **'이직'에만** 데이터가 있어 제공됩니다. **`coverage`를 보고 판단하세요.**

| 항목 | 이직 | 창업 | 진학 |
|---|---|---|---|
| `expected_wage`/`causal_effect`/`survival_months` | ✅ | null | null |
| `neighbors` | ✅ (GOMS+YP) | `[]` | `[]` |
| `risk_timeline` | 이직확률 | 폐업확률 | `{}` |
| `life_indicators` | ✅ | ✅(+창업 생존율) | ✅(+계열 취업률·진학률) |
| `trajectory` (소득) | ✅ | ✅ | ✅ (연령대만 맞으면 항상) |
| `wellbeing_trajectory` (만족도) | 청년만 ✅ | 청년만 ✅ | 청년만 ✅ (그 외 `[]`) |
| `scenario_trajectories` | ✅ `{유지, 이직}` | `{}` | `{}` |

---

## 5. 예시 (이직, `age 27·사회·250만원`)

**요청**
```json
{ "age": 27, "sex": "2", "major": "사회", "choice": "이직", "monthly_wage": 250, "edu_level": 7 }
```
**응답** (핵심 발췌)
```json
{
  "choice": "이직",
  "coverage": "이직: 개인단위 매칭(L2)·인과(L3)·생존(L4) + 생활지표(L1)",
  "expected_wage": 246.0,
  "causal_effect": 7.9,
  "survival_months": 86.0,
  "risk_timeline": { "1": 0.028, "3": 0.18, "5": 0.336 },
  "trajectory": [
    { "year": 0, "age": 27, "sample_n": 300, "income_p25": 228, "income_p50": 240, "income_p75": 256, "job_change_cum": null },
    { "year": 3, "age": 30, "sample_n": 131, "income_p25": 228, "income_p50": 256, "income_p75": 286, "job_change_cum": 0.185 }
  ],
  "scenario_trajectories": {
    "유지": [ { "year": 0, "income_p50": 240 }, { "year": 3, "income_p50": 256 } ],
    "이직": [ { "year": 0, "income_p50": 248 }, { "year": 3, "income_p50": 264 } ]
  },
  "life_indicators": [ { "dimension": "경제", "indicator": "또래 평균 월임금(전체근로자)", "value": 269.1, "unit": "만원", "group": "29세이하·2025", "source": "고용형태별근로실태조사(KOSIS)" } ],
  "narrative": ""
}
```
> 창업/진학은 `expected_wage`·`causal_effect`·`neighbors`·`scenario_trajectories`가 비고, `life_indicators`(+창업 생존율/계열 취업률)와 `trajectory`가 채워집니다.

---

## 5-B. `/compare` — A vs B 평행우주 비교 (⭐ 발표 화면 표준)

핵심 서사 = **"너와 데이터가 비슷한 사람들이 이 길(A/B)을 갔을 때"**. 주인공 3지표는 **만족도 · 소득 · 후회**.
선택 A·B를 나란히, 각 지표를 1·3·5·10년 스냅샷으로(데이터 없는 시점은 정직하게 비움) 보여줍니다.
`/predict` 를 A/B 두 번 호출해 정규화한 얇은 계층이라 **엔진(L1~L5)·`/predict` 계약은 그대로**입니다.
형태 예시 파일: `docs/compare_example.json` (숫자는 placeholder, 필드 구조는 실제와 동일).

> **시점은 데이터가 지지하는 데까지만.** 우리 패널은 방대하지 않아 만족도(YP)는 약 4년, 소득(KLIPS)·후회도
> 관측범위까지만 값이 있고 나머지 시점은 `available:false`. "10년 그리드를 강제로 채우지 않는다"가 원칙입니다.

### 입력 — `POST /compare`
```json
{
  "profile": { "age": 27, "sex": "2", "major": "사회", "monthly_wage": 250, "edu_level": 7 },
  "choice_a": "이직",
  "choice_b": "대학원 진학"
}
```
`profile` 필드는 `/predict` 입력에서 `choice` 만 뺀 것과 동일(2절 참고). `choice_a`/`choice_b` 는 자유 텍스트(이직/창업/진학으로 자동 분류).

### 출력 — `CompareResponse`
| 필드 | 타입 | 설명 |
|---|---|---|
| `profile` | Profile | 입력 프로필 에코 |
| `snapshots` | int[] | 지표 카드 시점 = `[1,3,5,10]` |
| `choice_a` / `choice_b` | string | 입력 선택 에코 |
| `scenarios` | `{ "A": ScenarioView, "B": ScenarioView }` | 두 평행우주 |
| `note` | string | 비교 주의사항(동일 유형 경고·인과 적용 범위 등). 빈 문자열이면 없음 |

### `ScenarioView` (선택지 하나의 카드 묶음)
| 필드 | 타입 | 설명 |
|---|---|---|
| `choice` / `kind` | string | 입력 선택 / 정규화 유형(이직·창업·진학) |
| `coverage` | string | 어떤 레이어가 적용됐는지(사람이 읽는 설명) |
| `satisfaction` | `IndicatorPoint[]` | ⭐ **만족도(종합)** — 삶의 만족도 궤적(1~5, 청년·YP). "이 길 간 사람 만족도가 이렇게 변함" |
| `satisfaction_summary` | object \| null | 종합 만족도 변화 한 줄 요약 `{start, latest, delta, direction(상승/하락/유지), span_years, sample_n, scale, source}` |
| `satisfaction_facets` | `FacetTrajectory[]` | ⭐ **만족도 세부 5축** — 직무·자기발전·소득·고용안정·장래성 각각의 궤적. "소득 만족은 낮은데 직무는 높더라" |
| `income` | `IndicatorPoint[]` | ⭐ **소득** — 비슷한 사람들의 월소득 중앙값·분포(만원, L5). 이직은 L3 인과 반영 |
| `regret` | `IndicatorPoint[]` | ⭐ **후회 리스크** — 이직=이탈확률(L4)/창업=폐업확률(생멸)/진학=미제공 |
| `regret_summary` | object \| null | 후회 리스크 요약 `{label, worst_year, worst_value, unit, source}`. 진학=null |
| `growth_potential` | `IndicatorPoint[]` | (보조) 성장 가능성 — 현재(0년) 대비 소득 상승률 |
| `health_context` | `LifeIndicator[]` | 건강 맥락(정신·신체·직업환경). **집단 기준이라 선택 A/B로 안 갈림 — 참고값** |
| `choice_context` | `LifeIndicator[]` | 선택 맥락(창업=생존율 / 진학=계열 취업률·진학률 / 이직=`[]`) |
| `confidence` | object | 신뢰지표(아래). 이직에서 채워짐 |
| `raw` | `PredictResponse` | 원본 `/predict` 응답 전체(만족도 원자료 등 포함, 프론트 자유 사용) |

세 주인공 카드(`satisfaction`·`income`·`regret`)는 각각 `snapshots`(1·3·5·10) 4개 시점의 `IndicatorPoint` 배열입니다.

> ⚠️ **만족도는 아직 선택 A/B로 분기되지 않습니다**(현재는 프로필 기준 궤적이라 A·B가 동일). "비슷한 사람들의
> 전반적 만족도 변화" 배경으로 해석하세요. 선택별(대학원 간 사람 vs 취업한 사람) 만족도 분기는 **데이터 확장 과제**이며,
> 해당 상황이면 `note` 에 안내가 실립니다.

### `IndicatorPoint` (카드 한 시점)
| 필드 | 타입 | 설명 |
|---|---|---|
| `year` | int | 시점(1·3·5·10) |
| `available` | bool | **데이터 있으면 true.** false면 그 시점 값 없음(값을 지어내지 않음) |
| `value` | float \| null | 대표값(소득 중앙값 / 상승률% / 확률%) |
| `p25` / `p75` | float \| null | 분포 밴드(경제 카드에서 소득 하위·상위 25%) |
| `unit` | string \| null | 예: `만원`, `%(현재 대비 소득)`, `%(이탈확률)` |
| `sample_n` | int \| null | 추적 표본 수(작을수록 불확실 — 흐리게 표시 권장) |
| `source` | string \| null | 출처 레이어/조사 |
| `note` | string \| null | `available=false` 사유 등 |

### `FacetTrajectory` (만족도 세부 축 1개 — `satisfaction_facets[]`)
| 필드 | 타입 | 설명 |
|---|---|---|
| `key` | string | 원변수(`satis_work`·`satis_growth`·`satis_income`·`satis_stability`·`satis_future`) |
| `label` / `dimension` | string | 표시 이름(예: "소득 만족") / 묶음(직무·성장·소득·안정·미래) |
| `points` | `{year, value(1~5), sample_n}[]` | facet 궤적(값은 매칭집단 **평균** — 1~5 정수라 중앙값은 4로 뭉개져 평균 사용) |
| `start` / `latest` / `delta` / `direction` | float / string | 시작·최근 값, 변화량, 방향(상승/하락/유지) |
| `scale` / `source` | string | `"1~5"` / 출처 |

> 만족도 세부 축은 **선택 A/B로는 안 갈리지만**(YP 직무만족은 취업자만 관측), 입력 프로필에 따라 값이 달라져
> "너와 비슷한 사람들은 소득 만족이 낮고 직무 만족은 높더라"처럼 개인화된 결을 준다. `satisfaction`(종합)과 짝지어 해석.

### `confidence` (신뢰지표 — '정직한 불확실성' 차별점)
```json
"confidence": {
  "survival_c_index": { "metric": "5-fold C-index", "c_index_test": 0.754, "c_index_train": 0.755,
                        "overfit_gap": 0.001, "n_spells": 10173, "treatment": "move",
                        "event_label": "일자리 이탈(이직)", "source": "YP2021 스펠", "max_horizon_years": 5 },
  "causal_effect_ci": { "ate": 27.9, "ci95_low": 20.9, "ci95_high": 34.8, "unit": "만원",
                        "method": "LinearDML (analytic 95% CI)", "treatment": "move",
                        "n": null, "n_treated": null, "source": "YP2021 청년패널 종단", "caveat": null },
  "causal_effect_by_year": {
    "by_year": { "1": { "ate": 5.8,  "ci_low": 0.52, "ci_high": 11.08, "n_treated": 5498 },
                 "3": { "ate": 10.58, "ci_low": 3.89, "ci_high": 17.28, "n_treated": 3894 } }
  },
  "choice_classification": { "kind": "이직", "confidence": 0.91 }
}
```
> 값은 **런타임에 아티팩트 매니페스트에서 그대로 읽어 내보낸다** — 여기 적힌 숫자는 하드코딩이 아니라
> `backend/models/artifacts/manifest.json` 기준 예시다(`choice_classification.confidence` 는 입력마다 달라지는 예시값).
> 재학습하면 응답도 같이 바뀐다. `n`/`n_treated` 는 아티팩트가 들고 있을 때만 채워진다 —
> YP 이직 모델은 없어서 `null` 이고, KLIPS 로 학습한 창업(703)·쉬어가기(1,344)에는 값이 들어간다.

| 필드 | 의미 |
|---|---|
| `survival_c_index` | 이 입력에 **실제로 쓰인** L4 모델의 5-fold C-index. 모델마다 다르다 — 청년(YP) 이직 0.754 / KLIPS 이직 0.58 / 창업 0.638 / 쉬어가기 0.565 |
| `causal_effect_ci` | L3 인과효과 ATE 와 95% CI. `treatment`·`n_treated` 로 어느 모델·표본인지 식별 |
| `causal_effect_ci.caveat` | 결과변수 개념이 대조군과 다른 경우 채워진다(창업=임금 vs 사업소득·생존편의, 쉬어가기=복귀자만 관측). **채워져 있으면 UI 에 반드시 함께 띄울 것** |
| `causal_effect_by_year` | 상대시간별 동적 처치효과. `{by_year: {h: {ate, ci_low, ci_high, n_treated}}}` 형태(t+1~t+5). 궤적 밴드를 연차별 CI 폭으로 벌리는 데 쓴다 |
| `choice_classification` | 선택 유형 분류 결과와 확신도. 0.6 미만이면 `notes` 에 경고가 붙는다 |

> `causal_effect_ci` 는 **LinearDML 의 analytic 95% CI** 를 노출한다. (같은 YP 데이터에서 CausalForestDML 은
> ATE +27.5·CI −21.2~+76.2 로 0을 포함할 만큼 넓지만, LinearDML CI 는 +20.9~+34.8 로 정밀하고 점추정은 사실상 동일.)
> 소득 격차를 "확실한 효과"로 말할 수 있는지는 이 CI 로 판단 — YP 이직 효과는 **0을 넘어 유의**.
> `ci95_low` 는 원값 20.95 를 소수 1자리로 반올림한 20.9 다(발표 자료의 +21.0 과 같은 값).

### 선택 유형별로 채워지는 것
| 카드/필드 | 이직 | 창업 | 진학 |
|---|---|---|---|
| `satisfaction` | 관측범위(≈4년)까지 ✅ | 〃 | 〃 (선택 무관 공통 궤적) |
| `income` | ✅ (L3 인과 반영) | ✅ (관측 궤적) | ✅ (관측 궤적) |
| `regret` | ✅ 이탈확률 | ✅ 폐업확률 | ❌ 전부 `available:false` |
| `choice_context` | `[]` | 창업 생존율 | 계열 취업률·진학률 |
| `confidence` | ✅ (C-index·인과 CI) | `{}` | `{}` |

> **화면 렌더 팁**: 세 카드(만족도·소득·후회)를 A/B 나란히, 각 카드 안에 시점 스냅샷. `available:false` 칸은 "데이터 없음"으로(회색, 강제로 채우지 않기). 소득·만족도는 `p25~p75` 밴드로 불확실성 표시. 만족도는 `satisfaction_summary` 로 "3.5→3.3 (하락)" 같은 한 줄도 가능. `note` 는 배너로 노출(만족도 미분기·인과 CI 0 포함·동일 유형 경고 등 — 오독 방지).

---

## 6. 연동 노트

### 사이트 담당 (입력·화면)
- **화면(두 행성·3지표 카드·타임라인)은 `/compare` 하나로 렌더** (5-B절). 단일 선택 원자료가 필요하면 `/predict` 또는 `/compare` 응답의 `scenarios.*.raw`.
- 필수 입력 `age·sex·major·choice`(단일) 또는 `profile + choice_a/b`(비교). **`edu_level`(최종학력) 한 칸 추가 강력 권장** — 궤적 개인화의 핵심.
- ⚠️ 현재 프론트 스캐폴드는 성별을 `"F"/"M"` 로 보냄 → API 는 `"1"(남)/"2"(여)` 기대. **입력 폼에서 `"1"/"2"` 로 매핑 필요.**
- **`coverage` 먼저 읽고** 화면 구성. 창업/진학이면 개인단위 카드는 숨기거나 "통계 기반" 안내로.
- **`trajectory`** → 소득 궤적 곡선(p25~p75 밴드 포함). `sample_n`이 작아지는 뒤 연차는 흐리게/불확실 표시.
- **`scenario_trajectories`** → 유지 vs 이직 **두 곡선 겹쳐** 평행우주 시각화. 두 선의 격차 = L3 인과효과.
- `neighbors[].source`로 "비슷한 졸업자(GOMS)/청년(YP)" 구분. similarity는 source 다르면 직접 비교 금지.

### 일기 모듈 담당
- 일기에서 추출한 신호(만족도·감정 등)를 **선택 입력**(`satis_overall`·`life_satis`·`happy`)으로 채워 개인화.
- 새 입력이 필요하면 이 문서 기준으로 스키마 확장 협의.

### narrative 경계
- `narrative`는 엔진이 아니라 **심리 RAG(3번)** 담당. 엔진은 위 수치(특히 `life_indicators`·`trajectory`)를 근거로 제공.

---

## 7. 실행
```bash
cd backend
uvicorn main:app --reload         # http://localhost:8000/docs
```
> 산출물 pkl(`backend/models/artifacts/*.pkl`)·`data/` lookup·`data/raw/klips/klips_base.pkl`(궤적용)이 있어야 각 레이어가 동작합니다. 없는 소스는 자동 skip. 서버 첫 요청 시 KLIPS 로드로 잠깐 느릴 수 있음(이후 캐시).

## 8. 확장 예정
- 진학: 개인단위 추적 모델 (현재는 계열 취업률·진학률 집계)
- 궤적: 소득 외 차원(만족도·삶의질) 시간 변화
- 입력: 일기 모듈 연동에 따른 스키마 확장

---
_예측 엔진(suin-model 브랜치) 기준. 스키마 변경 시 함께 갱신._
