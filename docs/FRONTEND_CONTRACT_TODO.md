# 프론트 ↔ 엔진 연동 체크리스트 (4번 담당)

엔진(suin-model 브랜치) 기준으로 **현재 프론트 스캐폴드가 API 계약과 어긋난 지점**과 할 일을 정리했습니다.
계약 원문은 `docs/API.md`(특히 **5-B절 `/compare`**), 샘플 응답은 `docs/compare_example.json` 참고.
우선순위: 🔴 병합 직결(먼저) · 🟡 화면 품질 · 🟢 정리.

---

## 🔴 1. 성별 코드 불일치 (매칭이 조용히 깨짐)
- **현상**: `InputForm.jsx`가 성별을 `"F"/"M"`로 보냄. 엔진은 **`"1"=남 / "2"=여`**(GOMS/KLIPS/YP 공통 코딩) 기대.
- **영향**: 잘못된 값이라 KNN·궤적·인과 매칭이 엉뚱하게 나옴(에러는 안 나서 **눈치채기 어려움**).
- **할 일**: 제출 시 `F→"2"`, `M→"1"`로 매핑(드롭다운 value를 아예 `"1"/"2"`로).

## 🔴 2. 결과 렌더 null 크래시 (창업/진학 선택 시)
- **현상**: `ResultView.jsx`가 `Math.round(expected_wage)`, `survival_months.toFixed(1)`, `Math.round(causal_effect)`를 무방비로 호출.
- **영향**: 이 필드들은 **이직에서만** 값이 있고 **창업·진학이면 `null`** → 런타임 크래시.
- **할 일**: `coverage`/`kind`를 먼저 보고 조건부 렌더. 개인단위 카드(기대월급·인과·재직기간)는 이직에서만. null 가드 필수.

## 🔴 3. 화면을 `/compare` 기준으로 (핵심 데모 화면)
- **현상**: `api.js`에 `predict()`만 있고 `/compare` 호출 없음. 화면도 단일 결과만 가정.
- **할 일**: `compare(profile, choiceA, choiceB)` 추가. 발표 화면(두 평행우주 + 3지표 카드)은 **`/compare` 응답 하나로** 구성.
  - 요청: `{ profile:{age,sex,major,...,edu_level}, choice_a, choice_b }`
  - 응답: `scenarios.A / scenarios.B` 각각에 아래 카드가 들어옴.

## 🔴 4. 엔진 산출물이 화면에 하나도 안 붙어 있음
- **현상**: 현재 `ResultView`는 기대월급·인과·재직기간·이웃·narrative만. **궤적·평행우주·만족도·후회·facet 전부 미표시.**
- **할 일**: `/compare` 기준 3지표 카드를 A/B 나란히:
  - **만족도** `satisfaction[]`(종합 1~5) + `satisfaction_summary`(3.8→3.6 하락) + `satisfaction_facets[]`(직무·자기발전·소득·고용안정·장래성 각 궤적)
  - **소득** `income[]`(만원, `p25~p75` 밴드로 불확실성)
  - **후회 리스크** `regret[]`(%) + `regret_summary`("5년 폐업확률 65%")
  - 시점은 `snapshots`(1·3·5·10). **`available:false` 칸은 "데이터 없음"으로(회색), 절대 억지로 채우지 말 것.**

---

## 🟡 5. `edu_level`(최종학력) 입력 칸 추가
- **왜**: 궤적·만족도 매칭 개인화의 핵심 변수. 선택 입력.
- **할 일**: 폼에 최종학력 드롭다운 → `edu_level`(KLIPS 코드: 5=고졸 6=전문대 7=대졸 8=석사 9=박사). 안 보내도 되지만 보내면 예측 개인화 크게 좋아짐.

## 🟡 6. 신뢰지표·note 노출 (차별점 "정직한 불확실성")
- **할 일**:
  - `scenarios.*.confidence.survival_c_index`(L4 예측력), `causal_effect_ci`(인과 95% CI) → "신뢰도" 뱃지/툴팁.
  - 소득·만족도는 `sample_n` 작으면 흐리게(불확실 표시).
  - `note`(문자열)는 **배너로 노출**: 만족도 미분기·인과 CI 0포함·동일 유형 경고 등 오독 방지 문구.

## 🟡 7. coverage/kind 기반 조건부 UI
- **할 일**: `scenarios.*.kind`(이직/창업/진학)에 따라 카드 구성 분기.
  - 창업: 후회=폐업확률, `choice_context`=창업 생존율.
  - 진학: 후회 카드 "데이터 없음", `choice_context`=계열 취업률·진학률.
  - 이직: 신뢰지표·인과 반영 소득까지 풀세트.

---

## 🟢 8. 잡정리
- `api.js`의 `BASE_URL = "http://localhost:8000"` 하드코딩 → 환경변수/설정으로.
- `major`는 계열명 텍스트(예: `"공학","사회","자연"`)로 보내면 KEDI 취업률/진학률 매칭됨.
- 단일 원자료가 필요하면 `/predict` 또는 `/compare` 응답의 `scenarios.*.raw`(원본 전체) 사용.

---
_기준: 엔진 suin-model 브랜치 / `docs/API.md`. 문의는 예측엔진 담당(나)._
