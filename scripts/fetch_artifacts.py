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
         HF_REPO_ID  = "suinnn/parallel-me-artifacts"
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


def _load_dotenv() -> None:
    """.env 를 환경변수로 올린다 — 없으면 조용히 넘어간다.

    backend/config.py 는 pydantic-settings 로 .env 를 자동으로 읽는데 이 스크립트는
    os.environ 만 봤다. 그래서 .env 에 HF_TOKEN 을 넣어둔 사람이 "서버는 되는데
    받기만 안 되는" 상태에 빠졌다(HF_REPO_ID 가 없다며 즉시 종료). 배포 환경처럼
    이미 환경변수가 있으면 그쪽이 이긴다 — .env 로 덮지 않는다.
    """
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()

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

# 모델이 아니라 **런타임 데이터**. 역시 .gitignore 로 막혀 있어 레포에 없다.
#
# 이게 없어도 서버는 뜨고 인과·생존 수치도 나온다. 대신 조용히 빈다 —
# 첫 배포에서 /compare 의 income 이 [] 로 나온 게 그 증상이었다. 예외가 안 나고
# 화면에서 그래프만 사라지므로 원인을 찾기 어렵다.
#
# 경로는 레포 기준 상대경로 그대로 쓴다. HF 레포에도 같은 경로로 올린다.
DATA_FILES: list[tuple[str, bool, str]] = [
    ("data/raw/klips/klips_base.pkl",      True,  "L5 소득 궤적 (trajectory.py)"),
    ("data/clean/yp_clean.csv",            True,  "청년 만족도 궤적 (YP 패널)"),
    # 2KB 짜리지만 없으면 소득이 **명목으로 표시된다.** trajectory.wage_basis 가 이걸
    # 못 읽으면 "명목(기준연도 미상)" 으로 답하고, 화면은 그 문자열을 보고 사용자에게
    # 주의 문구까지 띄운다 — 실제로는 2024년 기준으로 디플레이트된 값인데 앱이 자기
    # 데이터 품질을 낮춰 말하게 된다. manifest 의 data_vintage 도 이 파일에서 온다.
    ("data/raw/klips/klips_build_report.json", True, "소득 화폐기준(실질/기준연도)·데이터 빈티지"),
    ("data/raw/klips/klips_health26a.pkl", False, "건강 영역 상세 (domain_router)"),
]

# KOWEPS 사건 패널 — 개인화 매칭(유사 조건 집단)에 쓴다.
# 없으면 집단통계로 답하므로 required=False. 14개라 목록은 코드로 만든다.
_KOWEPS = [
    "koweps_life_panel", "koweps_event_outcomes",
    "koweps_business_self_employment_start_first_event_panel",
    "koweps_career_occupation_change_first_event_panel",
    "koweps_education_level_increase_first_event_panel",
    "koweps_finance_debt_start_first_event_panel",
    "koweps_finance_savings_increase_first_event_panel",
    "koweps_housing_homeownership_start_first_event_panel",
    "koweps_housing_move_first_event_panel",
    "koweps_lifestyle_work_hours_decrease_first_event_panel",
    "koweps_relationship_household_decrease_first_event_panel",
    "koweps_relationship_household_increase_first_event_panel",
    "koweps_relationship_marriage_change_first_event_panel",
    "koweps_relationship_marriage_start_first_event_panel",
]
DATA_FILES += [(f"data/clean/koweps/{n}.parquet", False, "KOWEPS 개인화 매칭")
               for n in _KOWEPS]


def _human(n: int) -> str:
    return f"{n / 1_048_576:.1f}MB"


def local_path(name: str) -> Path:
    """HF 레포 안의 이름 → 이 레포에서의 실제 위치.

    모델(.pkl)은 이름만 쓰고 artifacts/ 로 간다. 데이터는 'data/...' 처럼
    경로가 들어 있어 레포 루트 기준으로 그대로 푼다.
    """
    return (ROOT / name) if "/" in name else (ARTIFACTS / name)


def fetch_hf(names: list[str]) -> None:
    from huggingface_hub import hf_hub_download

    repo = os.environ.get("HF_REPO_ID")
    token = os.environ.get("HF_TOKEN")
    if not repo:
        raise SystemExit("HF_REPO_ID 가 없다. 예: suinnn/parallel-me-artifacts")

    for name in names:
        dest = local_path(name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        print(f"    받는 중 {name} …", flush=True)
        # local_dir 를 목적지의 기준으로 잡으면 HF 가 경로 구조를 그대로 만들어 준다.
        base = ROOT if "/" in name else ARTIFACTS
        path = hf_hub_download(repo_id=repo, filename=name, token=token,
                               local_dir=str(base), repo_type="model")
        print(f"      → {_human(Path(path).stat().st_size)}")


def fetch_url(names: list[str]) -> None:
    import requests

    base_url = (os.environ.get("ARTIFACT_BASE_URL") or "").rstrip("/")
    if not base_url:
        raise SystemExit("ARTIFACT_BASE_URL 이 없다.")

    for name in names:
        dest = local_path(name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        print(f"    받는 중 {name} …", flush=True)
        with requests.get(f"{base_url}/{name}", stream=True, timeout=600) as r:
            r.raise_for_status()
            tmp = dest.with_suffix(dest.suffix + ".part")
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
            tmp.replace(dest)   # 중간에 끊긴 파일을 진짜로 오해하지 않게
        print(f"      → {_human(dest.stat().st_size)}")


def _report_group(title: str, entries) -> int:
    print(f"\n  {title}")
    print("  " + "-" * 68)
    missing_required = 0
    for name, required, role in entries:
        p = local_path(name)
        if p.exists():
            mark, extra = "OK  ", _human(p.stat().st_size)
        elif required:
            mark, extra = "없음", "** 필수 **"
            missing_required += 1
        else:
            mark, extra = "  - ", "선택"
        print(f"  {mark} {name:52s} {extra:11s} {role}")
    return missing_required


def report() -> int:
    """현황 출력. 필수 파일이 빠진 개수를 돌려준다."""
    n = _report_group("모델 아티팩트", FILES)
    n += _report_group("런타임 데이터", DATA_FILES)
    return n


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
        # 선택 항목까지 받을지: FETCH_OPTIONAL=1 이면 폴백 모델·KOWEPS 패널도 받는다.
        want_optional = bool(os.environ.get("FETCH_OPTIONAL"))
        want = [n for n, req, _ in (FILES + DATA_FILES) if req or want_optional]
        todo = want if args.force else [n for n in want if not local_path(n).exists()]
        if not todo:
            print("  이미 다 있다 — 내려받기 생략")
        else:
            print(f"  {source} 에서 {len(todo)}개를 받는다"
                  f"{' (선택 항목 포함)' if want_optional else ''}")
            # 파일 단위로 감싼다 — 하나가 없어서 전체가 멈추면 안 된다.
            # (예: KOWEPS 패널을 아직 안 올렸는데 모델까지 못 받는 상황을 막는다)
            for name in todo:
                try:
                    (fetch_hf if source == "hf" else fetch_url)([name])
                except Exception as exc:
                    print(f"  ** {name} 실패: {type(exc).__name__}: {exc}", file=sys.stderr)

    missing = report()
    if missing:
        print(f"\n  ** 필수 파일 {missing}개가 없다. **", file=sys.stderr)
        print("     모델이 없으면 /compare 가 수치를 못 내고 프론트에 데모 숫자가 뜬다.",
              file=sys.stderr)
        print("     데이터가 없으면 예외 없이 소득·만족도 그래프만 조용히 빈다.",
              file=sys.stderr)
    else:
        print("\n  필수 파일 전부 준비됨")


if __name__ == "__main__":
    main()
