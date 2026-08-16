#!/usr/bin/env bash
# 배포 서버 기동 — 아티팩트를 받고 uvicorn 을 띄운다.
#
# 배경: railway.json 의 startCommand 로 `python ...` 을 직접 적었더니 죽었다.
#     /bin/bash: line 1: python: command not found
# 1차 수정(후보 목록 순회)도 실패했고, 그때 찍힌 진단이 이랬다.
#     PATH=/mise/shims:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
#     /app/.venv 없음
#     (command -v python python3 pip pip3 → 아무것도 없음)
# 즉 빌더(Railpack)가 mise 로 파이썬을 깔았지만 실행 컨테이너에서는 shim 도
# 안 걸리고 OS 파이썬도 없다. 그래서 경로를 **찾아낸다**.
#
# 고르는 기준은 "존재"가 아니라 "우리 패키지가 import 되는가" 다.
# OS 기본 python3 은 있어도 pip 로 깐 것이 안 보여서, 경로만 보고 고르면
# 다음 단계에서 ModuleNotFoundError 로 다시 죽는다.

set -uo pipefail
cd "$(dirname "$0")/.."          # 레포 루트

echo "[start] PATH=$PATH"

usable() {                        # $1 이 우리 의존성을 볼 수 있는 인터프리터인가
    [ -n "${1:-}" ] && [ -x "$1" ] || return 1
    "$1" -c 'import fastapi, uvicorn, joblib' >/dev/null 2>&1
}

PY=""
CANDIDATES=(
    /app/.venv/bin/python
    /opt/venv/bin/python
    "$(command -v python  2>/dev/null || true)"
    "$(command -v python3 2>/dev/null || true)"
    /mise/shims/python
    /mise/shims/python3
    /usr/local/bin/python3
    /usr/bin/python3
)
# mise 설치 경로는 버전이 붙어 있어 glob 으로 넓힌다(여러 후보가 나올 수 있다).
for g in /mise/installs/python/*/bin/python \
         /root/.local/share/mise/installs/python/*/bin/python \
         /usr/local/share/mise/installs/python/*/bin/python; do
    [ -e "$g" ] && CANDIDATES+=("$g")
done
# mise 자체가 있으면 물어본다.
if command -v mise >/dev/null 2>&1; then
    CANDIDATES+=("$(mise which python 2>/dev/null || true)")
fi

for cand in "${CANDIDATES[@]}"; do
    [ -n "$cand" ] || continue
    if usable "$cand"; then
        PY="$cand"; echo "[start] python = $cand (의존성 확인됨)"; break
    fi
    [ -x "$cand" ] && echo "[start] 후보 $cand — 의존성 없음, 건너뜀"
done

# 그래도 못 찾으면 파일시스템을 훑는다. 느리지만 기동 실패보다 낫다.
if [ -z "$PY" ]; then
    echo "[start] 후보 목록 실패 — 파일시스템 탐색"
    while IFS= read -r cand; do
        if usable "$cand"; then
            PY="$cand"; echo "[start] python = $cand (탐색으로 찾음)"; break
        fi
    done < <(find / -maxdepth 6 \( -path /proc -o -path /sys -o -path /dev \) -prune -o \
                  -type f -name 'python3*' -perm -u+x -print 2>/dev/null | head -40)
fi

if [ -z "$PY" ]; then
    echo "[start] ** 쓸 수 있는 파이썬이 없다. 진단: **" >&2
    echo "--- which ---";        command -v python python3 pip pip3 mise uvicorn 2>/dev/null || echo "(없음)"
    echo "--- /app ---";         ls -la /app 2>/dev/null | head -20 || echo "(없음)"
    echo "--- /mise ---";        ls -la /mise 2>/dev/null | head -20 || echo "(없음)"
    echo "--- /mise/shims ---";  ls -la /mise/shims 2>/dev/null | head -30 || echo "(없음)"
    echo "--- /mise/installs ---"; ls -R /mise/installs 2>/dev/null | head -40 || echo "(없음)"
    echo "--- find python ---";  find / -maxdepth 6 -name 'python3*' -type f 2>/dev/null | head -20 || true
    exit 1
fi

"$PY" -c 'import sys; print("[start] version", sys.version.split()[0])'

# 모델 아티팩트 수급. 실패해도 서버는 띄운다 — 무엇이 없는지는 로그와
# /health 의 artifacts 로 확인할 수 있다. 여기서 죽이면 원인 파악이 더 어렵다.
"$PY" scripts/fetch_artifacts.py || echo "[start] 아티팩트 수급 실패 — 서버는 계속 띄운다"

# uvicorn 은 콘솔 스크립트가 PATH 에 없을 수 있으므로 -m 으로 부른다.
exec "$PY" -m uvicorn main:app \
    --app-dir backend \
    --host 0.0.0.0 \
    --port "${PORT:-8000}"
