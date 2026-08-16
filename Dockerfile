# 예측 서버(backend/main.py) 실행 이미지.
#
# 왜 Dockerfile 인가: Railway 기본 빌더(Railpack)로 세 번 시도했는데 전부
# 실행 컨테이너에서 파이썬을 못 찾아 죽었다. 진단을 찍어보니
#     PATH=/mise/shims:...   ← 경로는 잡혀 있는데
#     /mise 없음 / /mise/shims 없음 / /mise/installs 없음
#     find / -name 'python3*' → 없음
# 빌드 이미지와 실행 이미지가 갈리면서 mise 로 설치한 파이썬이 안 넘어왔다.
# 위치를 맞히는 대신 베이스 이미지를 우리가 정한다 — 파이썬 경로가 확정된다.
#
# 3.11 인 이유: backend/models/artifacts/*.pkl 을 만든 로컬 환경과 같게 맞춘다.
# joblib.load 는 pickle 이라 인터프리터·라이브러리가 어긋나면 조용히 깨진다.
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

# 의존성을 코드보다 먼저 깐다 — 코드만 바뀌면 이 레이어가 캐시돼 재빌드가 빠르다.
#
# numpy·scipy·scikit-learn·econml·pyarrow 는 cp311 manylinux wheel 이 있어
# 보통 컴파일이 없다. 다만 wheel 이 없는 패키지가 하나라도 끼면 빌드가 통째로
# 깨지고 그때마다 배포 한 사이클(5~10분)을 버린다 — 이미 세 번 버렸다.
# 그래서 빌드 도구를 깔고, 설치가 끝나면 **같은 레이어에서 지운다**.
# (다른 레이어에서 지우면 이미지 크기가 안 줄어든다)
COPY requirements-prediction.txt .
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends build-essential; \
    pip install --no-cache-dir -r requirements-prediction.txt; \
    apt-get purge -y --auto-remove build-essential; \
    rm -rf /var/lib/apt/lists/*

COPY . .

# 기동은 scripts/start.sh 가 맡는다 — 아티팩트를 받고 uvicorn 을 띄운다.
# 이 이미지에서는 /usr/local/bin/python 이 확정이라 탐색이 첫 후보에서 끝난다.
CMD ["bash", "scripts/start.sh"]
