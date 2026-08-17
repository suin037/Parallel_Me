"""데이터 파일이 없을 때 **없는 부분만** 비는지 확인한다.

배포 서버에는 `data/clean/` 이 통째로 없다(.gitignore). 그런데 예전엔
`job_change_trajectory._cluster_artifact()` 가 존재 확인 없이 파일을 읽어
FileNotFoundError 를 던졌고, `main._validated_prediction` 의 except 가 그걸 잡아
`validated_predictions` 를 통째로 unavailable 로 만들었다.

같이 죽은 것이 문제였다 — 재정 영향(`financial_impact`)은 `.joblib` 하나만
있으면 되고 그 파일은 배포에 **있다.** 배포본 7개 페르소나 응답이 전부
`"reason": "선택 보조 관측경로를 불러오지 못했습니다(FileNotFoundError)"` 였다.
"""

import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

pd = pytest.importorskip("pandas", reason="엔진 의존성이 있는 환경에서만 의미가 있다")

from models import job_change_trajectory as traj  # noqa: E402


def test_데이터가_없으면_예외_대신_상태로_알린다(monkeypatch):
    """예외를 던지면 호출부가 살아 있는 것까지 버린다."""
    monkeypatch.setattr(traj, "data_available", lambda: False)

    got = traj.trajectory_for_choice("이직", {"age": 32, "monthly_wage": 310})

    assert got["status"] == "unavailable"
    assert "배포에 포함되지 않아" in got["reason"]


@pytest.mark.parametrize("kind", ["창업", "휴식", "진학", "기타"])
def test_이직_유지가_아니면_해당없음이다(kind):
    """'못 쟀다' 와 '해당 없다' 는 다른 말이다."""
    assert traj.trajectory_for_choice(kind, {})["status"] == "not_applicable"


def test_data_available_는_두_파일을_모두_본다(monkeypatch, tmp_path):
    """하나만 있어도 읽다가 터진다 — 둘 다 있어야 한다."""
    missing, existing = tmp_path / "없음.json", tmp_path / "있음.parquet"
    existing.write_bytes(b"")

    monkeypatch.setattr(traj, "CLUSTERS", missing)
    monkeypatch.setattr(traj, "FUTURE_PANEL", existing)
    assert traj.data_available() is False

    monkeypatch.setattr(traj, "CLUSTERS", existing)
    monkeypatch.setattr(traj, "FUTURE_PANEL", missing)
    assert traj.data_available() is False

    monkeypatch.setattr(traj, "CLUSTERS", existing)
    monkeypatch.setattr(traj, "FUTURE_PANEL", existing)
    assert traj.data_available() is True


def test_관측결과는_패널_CSV_가_없으면_그_부분만_비운다(monkeypatch, tmp_path):
    """리포트만 보고 통과시키면 그다음 패널 CSV 를 읽다 터진다."""
    from models import job_change_candidate as cand

    monkeypatch.setattr(cand, "KLIPS_PANEL", tmp_path / "없음.csv")
    monkeypatch.setattr(cand, "_observed_outcomes_report", lambda: {"metrics": []})

    got = cand._observed_outcomes("이직", {"age": 32})
    assert got["status"] == "unavailable"
    assert "reason" in got


def test_이직_전체_결과에서_궤적만_비고_나머지는_남는다(monkeypatch):
    """핵심 회귀 테스트 — 하나가 없다고 전부 버리면 안 된다."""
    from models import job_change_candidate as cand

    monkeypatch.setattr(cand, "trajectory_for_choice",
                        lambda *a, **k: {"status": "unavailable", "reason": "테스트"})
    monkeypatch.setattr(cand, "_observed_outcomes",
                        lambda *a, **k: {"status": "unavailable"})
    monkeypatch.setattr(cand, "financial_impact",
                        lambda profile: {"status": "available", "growth_potential": {}})

    got = cand.prediction_for_choice("이직", {"age": 32, "monthly_wage": 310})

    assert got["status"] == "available"                 # 살아 있는 부분은 남는다
    assert got["selected_scenario"] == "move"
    assert got["parallel_trajectory"]["status"] == "unavailable"
    assert got["observed_outcomes"]["status"] == "unavailable"
