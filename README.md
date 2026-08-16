# Parallel Me

> 고민 중인 두 선택을 실제 패널 데이터와 개인 기록을 바탕으로 비교하고, 선택 이후의 가능한 경로를 탐색하는 평행우주 시뮬레이션 서비스

Parallel Me는 미래를 단정하는 예언 서비스가 아닙니다. KLIPS·GOMS·YP·KOWEPS 등의 조사 자료에서 유사 집단의 관측 결과를 찾아 재정 안정도, 성장 가능성, 삶의 질 관점으로 비교하고 근거와 불확실성을 함께 보여주는 프로젝트입니다.

## 주요 기능

- 두 선택지 A/B 입력 및 비교 시뮬레이션
- 이직 유사 집단의 관측 경로와 1·3·5년 결과 표시
- 일기, 30초 체크인, 개인 가치관을 활용한 해석 보조
- 기록을 별과 별자리로 시각화하는 `나의 우주`
- 결과 근거, 표본 수, 분석 가능 범위를 구분해 표시
- 창업·진학·관계 등 추가 영역을 위한 확장형 입력과 근거 라우팅

## 기술 구성

| 영역 | 기술 |
|---|---|
| Frontend | React 18, Vite, Tailwind CSS, Three.js / React Three Fiber |
| Backend | FastAPI, Pydantic, pandas, scikit-learn, EconML, lifelines |
| AI/RAG | Anthropic API, Cloudflare Workers AI, 심리 카드 검색 |
| Data | KLIPS, GOMS, 청년패널(YP), KOWEPS 등 공개 조사 자료 |

## 저장소 구조

```text
backend/          FastAPI API, 예측·비교 로직, 모델 및 RAG
data/             공개·가공 데이터 위치(개인 단위 원자료는 Git 제외)
diary_module/     일기·체크인·챗봇·개인화 기능
docs/             API, 데이터 감사, 모델 검증, UI 기능 문서
frontend/         React 사용자 화면
klips_module/     KLIPS 전처리 및 분석 모듈
preprocess/       데이터셋별 전처리 코드와 테스트
scripts/          보조 실행 스크립트
tests/            저장소 공통 통합·검증 테스트
```

루트의 `build_*`, `train_*`, `evaluate_*`, `validate_*` 파일은 모델 파이프라인을 재현하기 위한 실행 스크립트입니다. 서비스 실행에 매번 필요한 파일은 아닙니다.

## 로컬 실행

### 1. 환경 변수

```powershell
Copy-Item .env.example .env
```

`.env`에 필요한 API 키를 입력합니다. 키가 없어도 일부 통계·데모 기능은 동작하지만 AI 서사와 이미지 생성은 제한될 수 있습니다.

### 2. 백엔드

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
cd backend
python -m uvicorn main:app --reload --port 8000
```

- 상태 확인: <http://127.0.0.1:8000/health>
- API 문서: <http://127.0.0.1:8000/docs>

### 3. 프론트엔드

새 PowerShell 창에서 실행합니다.

```powershell
cd frontend
npm install
npm run dev
```

브라우저에서 <http://127.0.0.1:5173>에 접속합니다.

## 테스트 및 빌드

```powershell
# Python 테스트
python -m pytest tests

# 프론트엔드 프로덕션 빌드
cd frontend
npm run build
```

외부 API를 실제 호출하는 테스트는 키와 네트워크 상태에 따라 별도 실행이 필요할 수 있습니다.

## 데이터 및 모델 주의사항

- 개인 단위 원자료와 로컬 `.env`는 저장소에 커밋하지 않습니다.
- 현재 이직 모델은 개인의 정확한 미래값을 단정하지 않고, 유사 집단에서 관측된 방향과 범위를 제공합니다.
- 회사명 자체는 주요 패널 데이터에 포함되지 않으므로 목표 회사 정보는 별도 기업 데이터 분석용이며 패널 기반 인과효과 입력과 구분합니다.
- 성장 가능성과 삶의 질 지표는 재현성·시간순 검증 결과에 따라 제한적으로 표시될 수 있습니다.

세부 내용은 [API 문서](docs/API.md), [이직 데이터 감사](docs/JOB_CHANGE_DATA_AUDIT.md), [모델 검증](docs/JOB_CHANGE_MODEL_VALIDATION.md), [나의 우주](docs/MY_UNIVERSE.md)를 참고하세요.

## 협업 규칙

1. 기능별 브랜치에서 작업합니다.
2. 생성 로그, 캐시, 원자료, API 키는 커밋하지 않습니다.
3. PR에는 변경 기능, 영향 화면/API, 검증 결과, 알려진 제한을 적습니다.
4. UI와 모델 결과가 함께 바뀌면 API 응답과 화면 표시를 모두 확인합니다.
