# 로컬 실행 매뉴얼 (Windows / PowerShell)

터미널 **2개**를 띄운다. 1번은 백엔드, 2번은 프론트.

## 1. 백엔드

```powershell
cd "c:\Users\USER\OneDrive\바탕 화면\lifenologylab\-LIFENOLOGY_boiled_egg\backend"
..\.venv\Scripts\Activate.ps1
uvicorn main:app --reload
```

- `..\.venv` (**루트** venv)를 쓴다. 새로 만든다면
  `pip install -r backend/requirements.txt` 로 만들면 된다 — 아래 "함정" 참고.
- 기동 후 워밍업(모델·패널 로딩)에 **약 20초** 걸린다. 그동안 요청하면 느리다.
- 확인: <http://127.0.0.1:8000/health> → `"warmup": {"done": true ...}`, `"artifacts": {"available": true}` 이면 정상.
- API 문서: <http://127.0.0.1:8000/docs>

## 2. 프론트

```powershell
cd "c:\Users\USER\OneDrive\바탕 화면\lifenologylab\-LIFENOLOGY_boiled_egg\frontend"
npm run dev
```

- 접속: <http://localhost:5173>
- `npm install`은 **package.json이 바뀐 pull 직후에만** 하면 된다. 평소엔 생략.

## 3. 종료

각 터미널에서 `Ctrl+C`.

---

## 함정 (겪은 것만)

### sklearn 버전이 어긋나면 모델이 안 붙는다
`backend/models/artifacts/*.pkl`(레포에 없다 — `scripts/fetch_artifacts.py` 가 HF에서
받아온다)은 **scikit-learn 1.6.1**로 학습됐다. 서빙 환경도 같은 버전이어야 한다.

증상: `Can't get attribute '_RemainderColsList'` → artifacts 로딩 실패.
`/health`에서 `"artifacts": "실패: AttributeError"`, 화면에 실수치 대신 폴백이 뜬다.

`backend/requirements.txt`가 예전에 `scikit-learn==1.9.0`을 고정하고 있어서 venv를
새로 만들면 깨졌다. **지금은 고쳐져 있다**(1.6.1 + econml 0.16.0 등 언피클 세트 고정).

주의: 이 세트를 `>=`로 풀면 안 된다. pip 의존성 해결은 **성공하고** `joblib.load`
시점에만 터져서 원인을 찾기 어렵다. 이유는 `backend/requirements.txt` 주석 참고.

### pull 후 vite가 죽는다
```
The following dependencies are imported but could not be resolved:
  @react-three/fiber / @react-three/drei / three
```
→ `npm install` 한 번 실행하면 해결. (2026-08-14 통합본에서 3D 의존성이 추가됨)

### 포트가 이미 쓰이는 중
```powershell
Get-NetTCPConnection -LocalPort 8000 | Select-Object OwningProcess
Stop-Process -Id <PID>
```

### 로그에 뜨지만 정상인 것
- `psych_rag_loaded: false` — chromadb 미설치 시 심리카드 JSON 폴백으로 동작. 선택 의존성이라 정상.
- `enroll(진학) trained: false` — 처치군 178건 < 최소 200건이라 의도적으로 모델을 안 만든 것.

---

## 참고

- `.env`는 프로젝트 루트에 있고 `backend/config.py`가 자동으로 읽는다. 키 없어도 통계 기능은 동작, AI 서사·이미지 생성만 제한.
- 프론트가 보는 백엔드 주소 기본값은 `http://127.0.0.1:8000` (`VITE_API_BASE`로 변경 가능).
- 파이썬 테스트: 루트에서 `python -m pytest tests`
