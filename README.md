# Parallel Me

> **선택 이후의 가능성을 미리 탐험하는 AI 인생 경로 시뮬레이터**

**AI가 선택하지 않습니다. 선택할 수 있게 보여줍니다.**

LIFENOLOGY LAB · 삼성생명
Category: **예측 (PREDICT)**
Team **삶은계란** — 변민주 · 정지윤 · 최수인 · 황소현

[🌌 서비스 체험하기](https://parallel--me.vercel.app)

---

## About

취업, 이직, 대학원, 창업처럼 인생의 방향을 바꾸는 선택 앞에서
우리는 종종 주변의 의견이나 막연한 직감에 의존합니다.

**Parallel Me**는 사용자의 기록과 실제 사회 데이터를 바탕으로
두 선택 이후의 가능성을 **1년 · 3년 · 5년 · 10년** 단위로 비교해 보여주는 서비스입니다.

미래를 하나의 정답으로 예측하지 않고,
**각 선택에서 무엇을 얻고 잃을 수 있는지 판단할 근거를 제공합니다.**

---

## Main Features

### 🌌 A/B 평행우주 시뮬레이션

고민 중인 두 선택지를 자연어로 입력하면
두 경로의 미래를 같은 기준에서 비교합니다.

* 경제적 안정도
* 성장 가능성
* 삶의 질
* 유사 조건 집단의 실제 관측 경로
* 선택 이후의 **‘미래의 나’** 장면

### ⭐ 기록 · 나의 우주

매일의 체크인과 일기를 기록하면 하나의 별이 생성됩니다.
기록이 쌓일수록 별자리와 **나만의 우주**가 만들어집니다.

### 🔭 새로운 기회 발견

최근 기록을 바탕으로
사용자가 아직 생각하지 못했던 새로운 선택지를 발견해 제안합니다.

### 🌱 Action Bridge

시뮬레이션 결과를 보는 데서 끝나지 않고
오늘 바로 해볼 수 있는 작은 행동으로 연결합니다.

---

## How It Works

```text
온보딩 · 아바타
        ↓
매일 기록 · 나의 우주
        ↓
A/B 선택 입력
        ↓
평행우주 시뮬레이션
        ↓
새로운 기회 발견
        ↓
Action Bridge
```

---

## Prediction Engine

Parallel Me는 한국의 공개 패널 데이터를 기반으로
여러 분석 방법을 결합해 결과를 계산합니다.

* **Rule-based** — 실제 생활 지표 통계
* **KNN** — 나와 유사한 사례 탐색
* **EconML** — 선택 효과 추정
* **lifelines** — 생존·이탈 리스크 분석
* **Longitudinal Analysis** — 장기 경로 분석

> **LLM이 예측 숫자를 만들지 않습니다.**
> 데이터 기반 엔진이 계산한 결과를 LLM이 이해하기 쉬운 이야기로 전달합니다.

---

## Tech Stack

**Frontend**
React · Vite · Tailwind CSS · Three.js · Recharts

**Backend / Prediction**
FastAPI · scikit-learn · EconML · lifelines · pandas

**AI**
Claude API · `klue/roberta-large` · Cloudflare Workers AI

**Data**
KLIPS · YP · GOMS · KOWEPS 등 한국 정부·공공 패널 데이터

---

## Project Structure

```text
backend/        # 예측 API
diary_module/   # 일기 · 감정분석
frontend/       # React UI
data/           # 가공 데이터
docs/           # 모델 · 데이터 검증 문서
preprocess/     # 데이터 전처리
tests/          # 테스트
```

---

## Run

### Backend

```bash
pip install -r backend/requirements.txt

cd backend
python -m uvicorn main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

---

## Our Principle

Parallel Me는 미래를 단정하지 않습니다.

**근거가 있는 것은 보여주고,
근거가 부족한 것은 억지로 채우지 않습니다.**

> **정답을 대신 고르지 않습니다. 다만, 혼자 고르지 않게 합니다.**

---

### Team 삶은계란

변민주 · 정지윤 · 최수인 · 황소현
