# Parallel Me — 전체 기능 명세

> 코드 기준 정리 (2026-08-17). 기획서가 아니라 **지금 실제로 구현돼 있는 것**의 목록이다.
> 각 항목은 실제 파일·엔드포인트를 가리킨다. 구현이 안 됐거나 화면에 연결되지 않은 것은
> §12 에 따로 모았다.

---

## 1. 한눈에

| 항목 | 값 |
|---|---|
| 한 줄 정의 | 두 갈림길(A/B)을 **실제 패널 데이터로 관측된 경로**로 비교하고, 그 과정을 일기·우주로 쌓는 서비스 |
| 화면(라우트) | 16개 |
| 백엔드 | 2개 서버 — 예측 엔진(`backend/`), 일기·LLM(`diary_module/qmode/`) |
| API 엔드포인트 | 예측 10개 + 일기·LLM 30개 = **40개** |
| 예측 레이어 | L1 룰베이스 · L2 유사인물 · L3 인과 · L4 생존 · L5 궤적 |
| 학습 아티팩트 | 28개 (`backend/models/artifacts/`) |
| 원천 데이터 | KLIPS · KOWEPS · YP청년패널 · GOMS · KOSIS 5종 · DART · 커리어넷 |
| 저장 | 전부 브라우저 로컬 (`localStorage`, 키 31개). 서버에 개인 기록 없음 |

**설계 원칙(코드 전반에 반복되는 것)**
- 없는 데이터는 채우지 않고 **비운다.** 표본 미달이면 그 연차·지표를 아예 만들지 않는다.
- 모든 수치에 **표본 수(n)와 출처**를 함께 낸다.
- 예측이 아닌 것(LLM 서사)은 예측이 아니라고 화면에 적는다.

---

## 2. 화면 지도

| 라우트 | 화면 | 역할 | 탭바 | PC 전체폭 |
|---|---|---|:--:|:--:|
| `/` | Landing | 첫 진입. 온보딩 완료 시 `/my` 로 전달 | ✕ | ✕ |
| `/personas` | Personas | 체험용 인물 7명 중 선택 | ✕ | ○ |
| `/onboarding` | Onboarding | 내 프로필 만들기 | ✕ | ○ |
| `/my` | MyUniverseV2 | **홈** — 3D 우주(행성·별자리) | ○ | ○ |
| `/home` | HomeHub | 일기 허브 — 오늘 기록·캘린더 | ○ | ○ |
| `/checkin` | CheckIn | 하루 체크인 (좁게 유지) | ○ | ✕ |
| `/input` | InputScreen | 비교할 두 갈림길 입력 | ○ | ○ |
| `/simulate` | Simulate | 계산 중 연출 화면 | ✕ | ○ |
| `/result` | Result | A/B 비교 결과 | ○ | ○ |
| `/company` | CompanyScreen | 기업 재무·공시 분석 | ○ | ○ |
| `/archive` | Archive | 보관함 — 저장한 결과 | ○ | ○ |
| `/settings` | Settings | 프로필·개인화·보안 | ✕ | ○ |
| `/handoff` | Handoff | 기기 옮기기(내보내는 쪽) | ○ | ✕ |
| `/resume` | Resume | 기기 옮기기(받는 쪽) | ✕ | ✕ |

레이아웃 규칙은 [Layout.jsx](../frontend/src/components/Layout.jsx) 의 `NO_TABBAR` / `WIDE_DESKTOP` / `useFullDesktop` 세 목록이 정한다.

---

## 3. 진입 · 계정

### 3.1 체험하기 — 인물 7명
로그인 대신 쓰는 프로필 선택. 넷플릭스식.

| # | 이름 | 나이·성별 | 직종 | 유형 | MBTI | 고민 |
|---|---|---|---|---|---|---|
| 01 | 지원 | 29 · 여 | 예술·디자인·방송 | 이직 | INFJ | 합격한 그 회사로 옮길까 |
| 02 | 도현 | 31 · 남 | 연구·공학기술 | 휴식 | INTP | 번아웃 앞에서 반년 쉴까 |
| 03 | 성민 | 35 · 남 | 설치·정비·생산 | 창업 | ISTJ | 8년 다닌 회사를 나와 카페를 |
| 04 | 지호 | 29 · 남 | 경영·사무·금융·보험 | 이직 | INTJ | 조건 좋은 곳으로 또 옮길까 |
| 05 | 은우 | 32 · 여 | 예술·디자인·방송 | 이직 | INFP | 워라밸을 찾아 떠날까 |
| 06 | 린 | 27 · 여 | 영업·판매·서비스 | 이직 · 해외 | ENFP | 석사 마치고 돌아갈까 |
| 07 | 다운 | 30 · 여 | 경영·사무·금융·보험 | 창업 | ENFJ | 겸업을 접고 독립할까 |

- 인물마다 **1년치 일기 기록**이 들어 있다 (파일당 30~40KB). 카드 목록에는 안 읽고, 고른 순간에만 동적 import.
- 고르면 그 사람의 프로필·기록이 슬롯에 심기고 `/my` 로 이동. **새로고침을 하지 않는다** — iframe·사파리에서 저장소가 메모리라 날아가기 때문.
- 그 인물의 두 갈림길이 시뮬레이션 입력에 자동 추천된다(`personaCompare`).
- 얼굴은 이미지 파일이 아니라 `avatarConfig` → SVG 실시간 렌더.

`data/personas/` · `personaSession.js` · `personaSlots.js`

### 3.2 온보딩 — 내 프로필
나이 · 성별 · 전공계열 · 직종(KSCO) · 소득 · 학력 · 근속 · 종사상지위 · 기업규모 · MBTI · 가치 순위 · 아바타.

- **성별은 기본값을 두지 않는다.** 예전 버전이 입력 없이 `sex="2"` 를 저장했던 이력이 있어, `sexConfirmed` 가 없으면 다시 묻는다.
- 직종도 기본값 없음(예전 기본값이 선택지 목록에 없는 값이었다).
- 아바타: 파츠 조합 빌더 / 사진에서 생성(`/avatar/from-photo`) / 스타일 프리셋 3종.

### 3.3 기기 옮기기
서버 없이 폰 → 노트북. `/handoff` 가 상태를 압축해 링크·QR 로 내보내고, `/resume` 이 받아 연다.

---

## 4. 기록 (일기)

| 기능 | 화면·모듈 | 내용 |
|---|---|---|
| 하루 체크인 | `CheckIn` / `DiaryCheckIn` | 기분 1~5 · 에너지 · 감정 태그 · 오늘 쓴 역량 |
| 오늘 일기 | `DiaryToday` | 자유 서술 |
| 대화형 일기 | `ChatDiary` + `/chat`, `/chat/opener`, `/diary/compose` | 마스코트와 대화 → 일기로 정리 |
| 감정 추론 | `/emotion` | 문장에서 감정 라벨 |
| 영역 자동 태깅 | `/tag`, `domain_tag.py` | 진로/삶의 만족/관계/건강/성장성 5축 분류 |
| 일기 신호 | `/signals`, `diarySignals.js` | 최근 2~4주에서 '이직 고민' 상태·반추 감지 |
| 캘린더 | `HomeCalendar` | 월·주 단위. 주간 별자리 + 12개월 황도 12궁 아카이브 |
| 주간 리포트 | `/report/{uid}/{week_key}` | 그 주 흐름 요약 |
| 위로 한마디 | `/chat/comfort` | 주 1회 |
| 오늘의 한 걸음 | `DailySuggest` + `/suggest/daily` | 하루 크기 제안 |
| 추천곡 | `/media/tracks` | 일기 → Deezer 실재 곡 (LLM 은 고르기만) |

**별자리 규칙** — 기록 7개가 모이면 별자리 하나. 달력 주가 아니라 **쌓인 순서**로 묶는다(띄엄띄엄 쓰는 사람의 '이번 주 별자리'가 계속 비는 문제 때문). 모양은 기분의 평균×진폭으로 이름이 붙고, 기록 5개 미만이면 이름을 안 붙인다.

**별 색 규칙** — 색상 계열은 브랜드 보라 하나로 고정, **밝기만** 1→5로 오른다. 색·투명도·크기·헤일로가 같은 방향. 어두운 별 = 힘들었던 날. [moodColors.js](../frontend/src/data/moodColors.js) 단일 출처.

---

## 5. 비교 · 예측 (핵심)

### 5.1 흐름
```
/input  두 갈림길 입력
   │  ├ 자유 서술 → 영역 자동 감지 (detectPrimaryLifeDomain)
   │  ├ 선택지 분류 (/choices/classify-pair, LLM 보강)
   │  ├ 조건 질문 (scenarioIntake — 영역별 1~3개)
   │  ├ 기준 시점 선택 (1~10년)
   │  └ 보조 입력: 공고 분석 · 관계 대화 · 가치관 검사
   ▼
/simulate  → POST /simulate
   ▼
/result  A/B 비교
```

### 5.2 입력 보조

| 기능 | 엔드포인트 | 내용 |
|---|---|---|
| 채용공고 분석 | `/job/extract-url`, `/job/extract-pdf`, `/job/analyze` | URL·PDF → 조건 추출 → 나와 맞는 지점 |
| 기업 분석 | `/company/search`, `/company/summary`, `/company/analyze` | DART 공시 → 재무·안정성 |
| 관계 상담 | `/relationship/analyze`, `/relationship/{uid}/{tag}` | 대화 전문 → 관계 진단 (**전송 전 마스킹 적용**) |
| 직업가치관 검사 | `/career/value-test`, `/career/value-report` | 커리어넷 기반 |
| 가치 카드 순위 | `ValueRankingInput` + `value_ranking.py` | 8종 강제 순위 → 축 가중치 |
| 성향 심층 검사 | `ValueDeepTest`, `psychQuestions.js` | 서술형 → `disposition_block` |
| 제3의 길 | `/third-path` | A도 B도 아닌 선택지 제안 |
| 비교 키워드 제안 | `/suggest/compare-keywords` | 일기에서 요즘 튄 말 |

### 5.3 예측 엔진 5레이어

| 레이어 | 모듈 | 하는 일 | 데이터 |
|---|---|---|---|
| **L1** 룰베이스 | `rulebase.py` | 생활지표 조회. 선택 무관 항상 제공 | KOSIS · 지표누리 |
| **L2** 유사인물 | `models/knn_model.py` | '평행우주의 나' 탐색. 청년은 GOMS+YP 혼합, 그 외 GOMS | GOMS · YP |
| **L3** 인과효과 | `models/econml_model.py` | 선택 → 소득 인과효과 (treatment별) | KLIPS |
| **L3-t** 시간 프로파일 | `models/dynamic_effect.py` | 연차별 효과 + CI 밴드 | KLIPS |
| **L4** 생존분석 | `models/lifelines_model.py` | 후회 리스크 타임라인 (재직/자영 스펠) | KLIPS · YP |
| **L5** 종단 궤적 | `trajectory.py` | 비슷한 사람 300명을 **실제로 추적**한 소득·이직 분포(p25/50/75) | KLIPS |

**선택 유형별 커버리지**

| 유형 | L1 | L2 | L3 인과 | L4 생존 | 만족도 분기 |
|---|:--:|:--:|:--:|:--:|:--:|
| 이직 (`move`) | ○ | ○ | ○ | ○ | ○ |
| 창업 (`startup`) | ○ | ○ | ○ | ○ | ○ |
| 휴식 (`break`) | ○ | ○ | ○ | ○ | — |
| 진학 (`enroll`) | ○ | ○ | △ 대리사건 | ✕ | ○ |
| 유지 (`stay`) | ○ | ○ | — | — | ○ |
| 결혼·주택·이사 | ○ | ○ | KOWEPS | ✕ | ✕ |

△ 진학은 실제 입학이 아니라 **학력코드 상승**을 대리사건으로 쓴다. 유효 표본·게이트 결과는 `artifacts/treatment_report.json`.

### 5.4 결과 화면 구성

| 블록 | 컴포넌트 | 내용 |
|---|---|---|
| 아바타 비교 | `AvatarComparison` | A/B 미래 이미지 (`/visualize`) |
| 핵심 수치 | `ResultQuickStats` | 소득·만족도·후회 — 요청 연차 기준, 없으면 최근접 + 배지 |
| 데이터 주석 | `ResultDataNotes` | **관측 안 된 지표를 명시** |
| 변화 궤적 | `ChangeView` | 1·3·5년 평행 경로 |
| KOWEPS 근거 | `KowepsEvidenceCard`, `KowepsTrajectoryView` | 1·3·5·10년 관측 변화 |
| 관계 인과 | `RelationshipEffectCard` | 관계 선택의 효과 |
| 삶의 질 | `LifeView` | 만족도 궤적 |
| 정성 비교 | `SoftCompareView` + `/compare/soft` | 수치 없는 영역(관계·건강·일상) |
| 일기 신호 | `DiarySignalCard` | 내 기록이 가리키는 방향 |
| 상세 인사이트 | `DetailedInsights` | 차이·분산·표본 해설 |
| 행동 | `ActionView` | 결정 후 할 일 → 알람으로 연결 |

3지표(경제적안정도 · 성장가능성 · 삶의질)는 `indicators.py` 가 0~1 로 산출하고, 그 점수로 `rag/psych_narrative` 가 심리 이론카드를 검색해 서사에 붙인다.

---

## 6. 나의 우주 (`/my`)

3D 캔버스. 드래그 회전 · 휠 확대.

| 요소 | 내용 |
|---|---|
| **행성 5개** | 진로(가스) · 삶의 만족(암석) · 관계(암석) · 건강(얼음) · 성장성(바다) |
| **별자리** | 행성 둘레를 도는 = 그 영역의 일기. 누르면 펼쳐 봄 |
| **시나리오 표식** | 그 영역에서 돌린 시뮬레이션 |

**행성 패널** (누르면 오른쪽에 열림)

1. **상태 한 줄** — 영역마다 재는 방법이 다르다
   - 점수를 내는 영역: 삶의 만족 · 건강 → 0~10 점수 (기록 N일 이상일 때만)
   - 점수를 안 내는 영역: 진로 · 관계 · 성장성 → 대신 '얼마나 자주 떠올랐나'
2. **흐름 그래프** — 점수 영역은 기분 추이, 그 외는 주별 언급 빈도(롤리팝)
3. **관계 전용** — 연인·가족·친구·직장으로 나눈 분포
4. **성장성 전용** — 역량 믹스(무엇을 쌓았나)
5. **아직 안 가본 길** — `/opportunity/scan`. 기록에서 아직 저울에 올린 적 없는 갈림길 2~4개. 누르면 그 선택지가 채워진 채 시뮬레이션이 열림
6. **이 영역의 N년 뒤** — `/future/scenario`. 관측 거리 해금제:

   | 시점 | 필요 조건 |
   |---|---|
   | 1년 | 일기 3개 |
   | 3년 | 일기 10개 |
   | 5년 | 일기 10개 + 작은 탐험 1회 |
   | 10년 | + 탐험 기록 1개 |

7. **미래 보기** — 그 영역 중심으로 시뮬레이션 시작

**작은 탐험(`expeditions.js`)** — 인생 결정과 일상 사이를 메우는 한 걸음. "다녀오기"로 시작해 기록을 남기면 관측 거리가 열린다.

---

## 7. 보관함 · 알람

- **보관함** (`/archive`) — 시뮬 결과 스냅샷 저장. 저장한 우주 목록
- **결정 기록** — A/B 중 무엇을 골랐는지 + 회고
- **알람** (`reminders.js`) — 결정한 미래를 향한 **아직 안 한 행동**을 모아 알림. 종 아이콘 + 하루 한 번 토스트

---

## 8. 게임화

| 요소 | 규칙 |
|---|---|
| XP | 기록·시뮬레이션으로 획득 |
| 코인 | `floor(총XP / 100) − 사용량` (100 XP당 1코인) |
| 레벨 해금 | 꾸미기 전용 — 예측 결과와 무관 |
| 마스코트 | 쓰다듬기 · 간식으로 친밀도. **간식은 기록으로 번다** |
| 상점 | 소품 · 간식 · 배경 · 가구 · 행성 스킨 |

설계 의도: 게임화가 **데이터 축적을 굴리도록** 묶었다.

---

## 9. 안내

- **UserGuide** — 첫 진입 소개 (5단계)
- **Tour** — 마스코트가 화면을 하나씩 짚으며 해설. 라우트를 넘나들며 이어짐
- **GuideAdvice** — 화면마다 담당 마스코트가 나와 그 화면을 설명 (켜 둔 사람에게만)

---

## 10. 개인정보 · 보안

| 구간 | 상태 | 실제 동작 |
|---|:--:|---|
| 저장 (at rest) | **평문** | `localStorage` 에 그대로. 서버 전송 없음 |
| 전송 마스킹 | **부분 적용** | 관계 대화 전문([RelationshipInput.jsx:52](../frontend/src/components/RelationshipInput.jsx#L52)) · 비교 선택지 2줄([Result.jsx:346](../frontend/src/screens/Result.jsx#L346)) |
| 암호화 모듈 | **미연결** | PBKDF2(210k)+AES-256-GCM 구현은 정상. 저장 경로에 안 물려 있음 (§12 참조) |
| 저장소 폴백 | ○ | iframe·사파리에서 차단되면 메모리로 전환하고 그 사실을 화면에 알림 |

---

## 11. 백엔드 API 전체

### 11.1 예측 엔진 (`backend/main.py`) — 10개

| 메서드 | 경로 | 역할 |
|---|---|---|
| POST | `/simulate` | **메인** — A/B 비교 전체 |
| POST | `/compare` | A/B 비교 (엔진 계층) |
| POST | `/predict` | 단일 시나리오 예측 |
| POST | `/evidence/koweps` | KOWEPS 관측 근거 |
| POST | `/choices/classify-pair` | 두 선택지 유형 분류 |
| POST | `/models/job-change/financial-impact` | 이직 재정 영향 |
| POST | `/visualize` | A/B 미래 이미지 생성 |
| POST | `/avatar/generate` | 아바타 이미지 |
| POST | `/avatar/from-photo` | 사진 → 아바타 파츠 |
| GET | `/health` | 상태 |

### 11.2 일기 · LLM (`diary_module/qmode/api.py`) — 30개

| 묶음 | 경로 |
|---|---|
| 기록 | `/analyze` `/save` `/signals` `/tag` `/emotion` |
| 조회 | `/persona/{uid}` `/users/{uid}` `/report/{uid}/{week}` `/reports/{uid}`(DELETE) |
| 대화 | `/chat` `/chat/opener`(GET·POST) `/chat/comfort` `/diary/compose` |
| 미래 | `/scenario` `/third-path` `/future/scenario` `/opportunity/scan` |
| 기업 | `/company/search` `/company/summary` `/company/analyze` |
| 커리어 | `/career/value-test` `/career/value-report` |
| 관계 | `/relationship/analyze` `/relationship/{uid}/{tag}`(GET·DELETE) |
| 공고 | `/job/extract-url` `/job/extract-pdf` `/job/analyze` |
| 제안 | `/suggest/daily` `/suggest/compare-keywords` `/compare/soft` `/media/tracks` |
| 상태 | `/health` |

---

## 12. 관측 한계 (정직선)

| 지표 | 관측 천장 | 근거 |
|---|---|---|
| 소득 · 이직 궤적 | **15년 가능** (현재 10으로 제한) | KLIPS 12~27차 = 16웨이브. 15년 추적 2,375명 |
| L3 인과효과 | **5년** | `dynamic_effects.json` horizons 1~5. 이후는 `extrapolated=True` |
| 삶의 만족 | **3년** | YP 청년패널 4웨이브 |
| 창업 생존율 | 5년 | KOSIS 기업생멸 고정 구간 |
| KOWEPS 관측 변화 | 10년 | registry horizons 고정 |

표본은 뒤로 갈수록 마른다 — 29세 코호트 300명 기준 **5년차 118명 → 10년차 60명 → 15년차 20명**. `min_n=15` 미달 연차는 응답에서 아예 빠진다.

`future_years` 는 **모델 계층에 도달하지 않는다.** 서사·이미지 프롬프트 전용이며, 화면이 이미 만들어진 궤적에서 어느 점을 강조할지의 문제다.

---

## 13. 구현됐으나 화면에 연결 안 된 것

> 코드·API·백엔드는 있는데 렌더 호출이 없거나 부분만 연결된 것들.

| 항목 | 상태 | 위치 |
|---|---|---|
| `DomainRecords` | 정의만 있고 미렌더 (행성 패널과 내용 중복) | `MyUniverseV2.jsx` |
| `FutureScenarioPanel` · `WeekModal` · `ReportModal` · `ArchiveModal` · `RecordModal` | 정의만 있고 미렌더 | `MyUniverseV2.jsx` |
| `CurveView` · `RadarView` · `SummaryView` | 어디서도 import 안 됨 | `components/result/` |
| `MyUniverse.jsx` (v1) | 라우팅은 V2 만 씀 | `screens/` |
| `secureStore` 저장 암호화 | 모듈은 완성, 저장 경로에 미연결 | `data/secureStore.js` |
| `redactPII` 전면 적용 | `api.js` 의 fetch 7곳에 공통 마스킹 없음 | `data/piiRedact.js` |
| `crypto_at_rest.py` | 백엔드 쪽 암호화 모듈 | `diary_module/qmode/` |

---

## 14. 데이터 원천

| 데이터 | 범위 | 쓰이는 곳 |
|---|---|---|
| **KLIPS** 한국노동패널 | 12~27차 (2009~2024), 32,364명 / 289,154행 | L3 인과 · L4 생존 · L5 궤적 |
| **KOWEPS** 한국복지패널 | 최초 사건 패널 | 생활사건(결혼·주택·이사) 관측 근거 |
| **YP** 청년패널 | 4웨이브 | 만족도 궤적 · 청년 L2/L4 |
| **GOMS** 대졸자직업이동 | — | L2 유사인물 (전공 매칭) |
| **KOSIS** | 고용형태별근로실태조사(고용형태·산업·연령) · 기업생멸행정통계 · 사회통합실태조사 | L1 생활지표 · 창업 생존율 |
| 지표누리 국민삶의질 · 청년삶의질2025 | — | L1 |
| 보건복지부 정신건강실태조사 | — | L1 건강 |
| 한국교육개발원 졸업자 학과별 | — | 진학 영역 |
| **DART** | 실시간 | 기업 재무·공시 |
| **커리어넷** | — | 직업가치관검사 |

소득은 CPI 로 디플레이트한 **2024년 기준 실질** (`klips_build_report.json`).

---

## 15. 로컬 저장 키

```
pm.profile.v1        프로필            pm.myuniverse.v1     우주(체크인·XP·행성)
pm.slots.v1          프로필 슬롯        pm.universes.v1      보관함
pm.prefs.v1          환경설정          pm.reminders.v1      알람
pm.petCare.v1        마스코트 친밀도    pm.petShop.v1        상점·인벤토리
pm.expedition.v1     작은 탐험         pm.highestLevel.v1   최고 레벨
pm.future.v1         N년 뒤 캐시       pm.opportunity.v1    아직 안 가본 길 캐시
pm.softCompare.v1    정성 비교 캐시    pm.compareKeywords.v1 비교 키워드 캐시
pm.suggest.v1        오늘의 제안       pm.comfort.v1        위로 한마디
pm.tracks.v1         추천곡            pm.chatDraft.v1      대화 임시저장
pm.tour.v1/.want.v1  투어             pm.guide.seen/ask.v1 안내
pm.advice.on.v1      화면별 조언 on/off pm.nudge.off.v1      넛지 off
pm.speech.v1         말투             pm.activeGoal.v1     활성 목표
pm.anonId.v1         익명 ID          pm.contribConsent.v1 데이터 기여 동의
pm.sec.salt.v1       암호화 salt       pm.sec.verify.v1     암호문구 검증 토큰
pm.cosmoDecisionPrompt.v1  결정 프롬프트
```
