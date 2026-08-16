"""실제 예측 파이프라인에 필요한 비공개 데이터·모델 파일을 점검한다."""

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent

REQUIRED_INPUTS = {
    "GOMS 정제 데이터": ROOT / "data/clean/goms_clean.csv",
    "KLIPS 패널": ROOT / "data/raw/klips/klips_base.pkl",
}

MODEL_GROUPS = {
    "KNN 유사인물": ["knn.pkl", "encoders.pkl"],
    "인과효과": ["econml_yp.pkl", "econml_klips.pkl", "econml.pkl"],
    "생존분석": ["lifelines_yp.pkl", "lifelines_klips.pkl", "lifelines.pkl"],
}


def main() -> int:
    artifacts = ROOT / "backend/models/artifacts"
    missing_inputs = []

    print("[학습 입력]")
    for label, path in REQUIRED_INPUTS.items():
        exists = path.is_file()
        print(f"{'OK' if exists else 'MISSING':7} {label}: {path.relative_to(ROOT)}")
        if not exists:
            missing_inputs.append(path)

    print("\n[서빙 모델]")
    missing_groups = []
    for label, alternatives in MODEL_GROUPS.items():
        if label == "KNN 유사인물":
            ready = all((artifacts / name).is_file() for name in alternatives)
        else:
            ready = any((artifacts / name).is_file() for name in alternatives)
        print(f"{'OK' if ready else 'MISSING':7} {label}: {', '.join(alternatives)}")
        if not ready:
            missing_groups.append(label)

    if missing_inputs or missing_groups:
        print("\n실제 모델 모드 준비 안 됨: 원본/정제 데이터 또는 학습 artifact를 팀에서 전달받아야 합니다.")
        return 1

    print("\n실제 모델 모드에 필요한 파일이 준비되었습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
