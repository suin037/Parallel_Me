#!/usr/bin/env bash
# 배포 서버 기동 — 아티팩트를 받고 uvicorn 을 띄운다.
#
# 왜 스크립트로 빼냈나: railway.json 에 startCommand 로
#     python scripts/fetch_artifacts.py && uvicorn main:app ...
# 를 직접 적었더니 실행 컨테이너에서 이렇게 죽었다.
#     /bin/bash: line 1: python: command not found
# 빌더(Railpack)가 mise 로 파이썬을 설치하는데 그 경로가 실행 시점 PATH 에
# 안 잡히는 경우가 있다. 위치를 찍어 맞히는 대신, 후보를 돌며 **의존성이
# 실제로 import 되는 인터프리터**를 고른다 — OS 기본 python3 은 존재해도
# 우리 패키지가 없어서, 경로만 보고 고르면 그 함정에 빠진다.

set -uo pipefail
cd "$(dirname "$0")/.."          # 레포 루트

echo "[start] PATH=$PATH"

PY=""
for cand in \
    /app/.venv/bin/python \
    "$(command -v python  2>/dev/null || true)" \
    "$(command -v python3 2>/dev/null || true)" \
    /usr/local/bin/python3 \
    /usr/bin/python3
do
    [ -n "$cand" ] && [ -x "$cand" ] || continue
    # 존재만으로는 부족하다 — 우리가 설치한 패키지가 보이는 인터프리터여야 한다.
    if "$cand" -c 'import fastapi, uvicorn, joblib' >/dev/null 2>&1; then
        PY="$cand"
        echo "[start] python = $cand (의존성 확인됨)"
        break
    fi
    echo "[start] 후보 $cand — 의존성 없음, 건너뜀"
done

if [ -z "$PY" ]; then
    echo "[start] ** 쓸 수 있는 파이썬을 못 찾았다. 진단 정보: **" >&2
    command -v python python3 pip pip3 2>/dev/null || true
    ls -la /app/.venv/bin 2>/dev/null || echo "  /app/.venv 없음"
    exit 1
fi

"$PY" -c 'import sys; print("[start] version", sys.version.split()[0])'

# 모델 아티팩트 수급. 실패해도 서버는 띄운다 — 무엇이 없는지는 아래 로그에 남고,
# /health 의 artifacts 로도 확인할 수 있다. 여기서 죽이면 원인 파악이 더 어렵다.
"$PY" scripts/fetch_artifacts.py || echo "[start] 아티팩트 수급 실패 — 서버는 계속 띄운다"

# uvicorn 은 콘솔 스크립트가 PATH 에 없을 수 있으므로 -m 으로 부른다.
exec "$PY" -m uvicorn main:app \
    --app-dir backend \
    --host 0.0.0.0 \
    --port "${PORT:-8000}"
