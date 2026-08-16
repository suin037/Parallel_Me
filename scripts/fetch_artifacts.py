"""배포 서버가 기동할 때 모델 아티팩트(.pkl)를 내려받는다.

왜 필요한가
    backend/models/artifacts/*.pkl 은 9개 187MB 다. .gitignore 가 막고 있어서
    (그리고 막는 게 맞아서) 레포에 없다. 로컬에서는 각자 갖고 있으면 되지만
    배포 서버에는 아무도 넣어줄 사람이 없다 — 그래서 기동 시 받아온다.

    안 받으면 서버는 뜨지만 /compare 가 숫자를 못 낸다. 그리고 **조용히** 못 낸다:
    econml_model._load_all() 이 파일이 없으면 그냥 건너뛰므로 예외도 안 난다.
    그래서 이 스크립트는 끝에 검증을 붙여 빠진 게 있으면 크게 알린다.

받는 곳 — ARTIFACT_SOURCE 로 고른다
    hf   HuggingFace 비공개 레포 (기본). 카드 등록이 없고 모델 파일에 맞는 용도.
         HF_REPO_ID  = "suin037/parallel-me-artifacts"
         HF_TOKEN    = 읽기 권한 토큰
    url  아무 HTTPS 베이스 주소 (R2 공개 버킷·S3 서명 URL 등)
         ARTIFACT_BASE_URL = "https://.../artifacts"
    none 받지 않는다. 로컬 개발이나 이미 파일이 있는 환경.

사용
    python scripts/fetch_artifacts.py          # 없는 것만 받는다
    python scripts/fetch_artifacts.py --force  # 있어도 다시 받는다
    python scripts/fetch_artifacts.py --check  # 받지 않고 현황만 본다
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS = ROOT / "backend/models/artifacts"

# 서빙 코드가 실제로 여는 파일. backend/models/*.py 의 TREATMENT_FILES 와 같은 목록이다.
#   required=True  없으면 그 기능이 통째로 죽는다
#   required=False 라우팅 폴백. 없어도 다른 소스로 답한다
FILES: list[tuple[str, bool, str]] = [
    ("knn.pkl",                    True,  "L2 유사인물 매칭 (GOMS)"),
    ("encoders.pkl",               True,  "GOMS 인코더/중앙값"),
    ("econml_klips.pkl",           True,  "L3 이직 인과효과"),
    ("econml_klips_startup.pkl",   True,  "L3 창업 인과효과"),
    ("econml_klips_break.pkl",     True,  "L3 쉬어가기 인과효과"),
    ("lifelines_klips.pkl",        True,  "L4 재직 생존"),
    ("lifelines_klips_startup.pkl", True, "L4 자영 이탈 생존"),
    ("lifelines_klips_break.pkl",  True,  "L4 복귀기간"),
    ("econml.pkl",                 False, "L3 GOMS 폴백"),
    ("knn_yp.pkl",                 False, "L2 청년패널"),
    ("econml_yp.pkl",              False, "L3 청년패널"),
    ("lifelines_yp.pkl",           False, "L4 청년패널"),
]


def _human(n: int) -> str:
    return f"{n / 1_048_576:.1f}MB"


def fetch_hf(names: list[str]) -> None:
    from huggingface_hub import hf_hub_download

    repo = os.environ.get("HF_REPO_ID")
    token = os.environ.get("HF_TOKEN")
    if not repo:
        raise SystemExit("HF_REPO_ID 가 없다. 예: suin037/parallel-me-artifacts")

    for name in names:
        print(f"    받는 중 {name} …", flush=True)
        path = hf_hub_download(repo_id=repo, filename=name, token=token,
                               local_dir=str(ARTIFACTS), repo_type="model")
        print(f"      → {_human(Path(path).stat().st_size)}")


def fetch_url(names: list[str]) -> None:
    import requests

    base = (os.environ.get("ARTIFACT_BASE_URL") or "").rstrip("/")
    if not base:
        raise SystemExit("ARTIFACT_BASE_URL 이 없다.")

    for name in names:
        print(f"    받는 중 {name} …", flush=True)
        with requests.get(f"{base}/{name}", stream=True, timeout=300) as r:
            r.raise_for_status()
            tmp = ARTIFACTS / (name + ".part")
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
            tmp.replace(ARTIFACTS / name)   # 중간에 끊긴 파일을 진짜로 오해하지 않게
        print(f"      → {_human((ARTIFACTS / name).stat().st_size)}")


def report() -> int:
    """현황 출력. 필수 파일이 빠진 개수를 돌려준다."""
    print("\n  아티팩트 현황")
    print("  " + "-" * 62)
    missing_required = 0
    for name, required, role in FILES:
        p = ARTIFACTS / name
        if p.exists():
            mark, extra = "OK  ", _human(p.stat().st_size)
        elif required:
            mark, extra = "없음", "** 필수 **"
            missing_required += 1
        else:
            mark, extra = "  - ", "선택(폴백)"
        print(f"  {mark} {name:30s} {extra:12s} {role}")
    return missing_required


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="이미 있어도 다시 받는다")
    ap.add_argument("--check", action="store_true", help="받지 않고 현황만 본다")
    args = ap.parse_args()

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    source = (os.environ.get("ARTIFACT_SOURCE") or "hf").lower()

    if args.check:
        missing = report()
        sys.exit(1 if missing else 0)

    if source == "none":
        print("  ARTIFACT_SOURCE=none — 내려받기를 건너뛴다")
    else:
        want = [n for n, req, _ in FILES if req or os.environ.get("FETCH_OPTIONAL")]
        todo = want if args.force else [n for n in want if not (ARTIFACTS / n).exists()]
        if not todo:
            print("  이미 다 있다 — 내려받기 생략")
        else:
            print(f"  {source} 에서 {len(todo)}개를 받는다")
            try:
                (fetch_hf if source == "hf" else fetch_url)(todo)
            except Exception as exc:
                # 여기서 죽이지 않는다 — 서버는 뜨고, 아래 검증이 무엇이 빠졌는지 알린다.
                print(f"  ** 내려받기 실패: {type(exc).__name__}: {exc}", file=sys.stderr)

    missing = report()
    if missing:
        print(f"\n  ** 필수 아티팩트 {missing}개가 없다. /compare 가 수치를 내지 못한다. **",
              file=sys.stderr)
        print("     서버는 뜨지만 프론트에는 데모 숫자가 표시된다.", file=sys.stderr)
    else:
        print("\n  필수 아티팩트 전부 준비됨")


if __name__ == "__main__":
    main()
