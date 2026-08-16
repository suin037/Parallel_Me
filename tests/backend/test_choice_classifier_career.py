from choice_classifier import classify


def test_generic_career_change_phrases_are_job_change():
    for text in ("진로 변경", "진로변경", "커리어 변경", "커리어 전환", "직업 변경", "직종 변경"):
        assert classify(text, record=False).kind == "이직"


def test_current_career_maintenance_is_stay():
    assert classify("현재 진로 유지", record=False).kind == "유지"
