"""compare_keywords 회귀 테스트.

추출이 결정적(LLM 없음)이라 이 테스트가 계속 유효하다 — 모듈 docstring 의
'정직선' 세 번째 항목이 지켜지는지도 여기서 같이 잡는다.
"""

import sys
from pathlib import Path

import pytest

DIARY = Path(__file__).resolve().parents[2] / "diary_module"
if str(DIARY) not in sys.path:
    sys.path.insert(0, str(DIARY))

pytest.importorskip("kiwipiepy", reason="형태소 분석기가 없으면 추출 자체가 없다")

from qmode import compare_keywords as CK  # noqa: E402


def _records(days, text, month="08"):
    return [{"date": f"2026-{month}-{d:02d}", "text": text} for d in days]


def test_recent_spike_beats_habitual_word():
    """평소 늘 쓰던 말은 밀리고, 최근에 튄 말이 올라온다.

    빈도순이면 '운동'(19일)이 '팀장'(9일)을 이긴다. lift 로 골라야 뒤집힌다 —
    이게 이 모듈이 단순 빈도 카운트와 갈리는 지점이다.
    """
    records = _records(range(1, 20), "운동을 했다. 날씨가 좋다.", month="05")
    records += _records(range(1, 10), "팀장 눈치에 야근까지 했다.")

    out = CK.extract(records)
    words = [k["word"] for k in out["keywords"]]

    assert out["ok"] is True
    assert out["baseline_used"] is True
    assert "팀장" in words and "야근" in words
    assert "운동" not in words          # 최근 창에 없다 → 후보가 아니다


def test_baseline_is_skipped_when_history_is_short():
    """평소가 없으면 lift 를 만들지 않는다. 없는 근거를 지어내지 않기 위해서다."""
    out = CK.extract(_records(range(1, 6), "팀장 때문에 야근이 반복된다."))

    assert out["ok"] is True
    assert out["baseline_used"] is False
    assert all(k["lift"] == 1.0 for k in out["keywords"])


def test_stopwords_and_single_chars_are_dropped():
    records = _records(range(1, 10), "오늘 요즘 생각이 많다. 시간 부분 상황 마음.")
    words = [k["word"] for k in CK.extract(records)["keywords"]]

    assert not ({"오늘", "요즘", "생각", "시간", "부분", "상황", "마음"} & set(words))


def test_min_days_filters_one_off_events():
    """하루만 나온 말은 후보가 아니다 — 단발 사건이 전부 올라오는 걸 막는다."""
    records = _records(range(1, 10), "팀장 때문에 야근이 반복된다.")
    records.append({"date": "2026-08-11", "text": "치과에 다녀왔다."})

    words = [k["word"] for k in CK.extract(records)["keywords"]]
    assert "치과" not in words


def test_malformed_input_never_raises():
    """호출부가 이 실패로 막히면 안 된다 — 빈 목록이면 고정 사전이 그대로 답이다."""
    for bad in ([], None, [{"no": "date"}], [{"date": "bad", "text": "x"}], [None, 3, "x"]):
        out = CK.extract(bad)
        assert out["ok"] is False
        assert out["keywords"] == []


def test_samples_carry_evidence_for_domain_routing():
    """단어만으로는 영역을 못 정한다('팀장'은 어느 사전에도 없다).

    그래서 프론트(choices.js)가 영역을 판정할 근거 문장을 함께 돌려줘야 한다.
    이게 비면 키워드 칩이 통째로 안 만들어진다.
    """
    out = CK.extract(_records(range(1, 10), "팀장 눈치에 야근까지 했다. 회사가 버겁다."))
    top = {k["word"]: k for k in out["keywords"]}

    assert "팀장" in top
    assert top["팀장"]["samples"], "근거 문장이 없으면 영역 판정이 불가능하다"
    assert any("회사" in s for s in top["팀장"]["samples"])
