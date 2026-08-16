import json
import sys


def test_artifact_manifest_checks_runtime_files(monkeypatch, tmp_path):
    # tests/test_tier1.py가 수집 단계에서 최소 claude_api stub을 전역 등록한다.
    # main이 요구하는 나머지 두 진입점도 채워 테스트 순서와 무관하게 만든다.
    claude_api = sys.modules.get("utils.claude_api")
    if claude_api is not None:
        monkeypatch.setattr(claude_api, "generate_scenarios", lambda *a, **k: {}, raising=False)
        monkeypatch.setattr(claude_api, "warm_narrative_schema", lambda: None, raising=False)
    import main

    (tmp_path / "present.pkl").write_bytes(b"model")
    (tmp_path / "manifest.json").write_text(json.dumps({
        "generated_at": "test",
        "git": "deadbee",
        "missing": [],
        "artifacts": {
            "present.pkl": {"layer": "L2", "present": True},
            "missing.pkl": {"layer": "L3", "present": True},
            "deprecated.pkl": {"layer": "L4", "present": True},
        },
    }), encoding="utf-8")

    # 필수는 missing.pkl 뿐 — deprecated.pkl 은 폐기 대상이라 빠져도 degraded 가 아니다.
    monkeypatch.setattr(main, "_required_artifacts",
                        lambda: frozenset({"present.pkl", "missing.pkl"}))
    monkeypatch.setattr(type(main.settings), "artifacts_abspath", property(lambda _: tmp_path))
    main._artifact_manifest.cache_clear()
    try:
        state = main._artifact_manifest()
    finally:
        main._artifact_manifest.cache_clear()

    assert state["manifest_missing"] == []
    assert state["missing"] == ["missing.pkl"]
    assert state["missing_optional"] == ["deprecated.pkl"]
    assert state["required_known"] is True
    assert state["artifacts"]["present.pkl"]["present"] is True
    assert state["artifacts"]["missing.pkl"]["present"] is False


def test_optional_artifact_missing_does_not_degrade(monkeypatch, tmp_path):
    """폐기·폴백 아티팩트만 빠졌으면 degraded 가 아니어야 한다.

    전에는 manifest 에 이름이 있는데 파일이 없으면 무조건 degraded 라, 필수가 전부
    멀쩡해도 /health 가 계속 degraded 였다. 늘 degraded 면 진짜 고장을 못 알아본다.
    """
    import main

    (tmp_path / "present.pkl").write_bytes(b"model")
    (tmp_path / "manifest.json").write_text(json.dumps({
        "generated_at": "test",
        "git": "deadbee",
        "missing": ["lifelines.pkl"],
        "artifacts": {
            "present.pkl": {"layer": "L2", "present": True},
            "lifelines.pkl": {"layer": "L4", "present": False},
        },
    }), encoding="utf-8")

    monkeypatch.setattr(main, "_required_artifacts", lambda: frozenset({"present.pkl"}))
    monkeypatch.setattr(type(main.settings), "artifacts_abspath", property(lambda _: tmp_path))
    main._artifact_manifest.cache_clear()
    try:
        state = main._artifact_manifest()
    finally:
        main._artifact_manifest.cache_clear()

    assert state["missing"] == []                      # degraded 판정 근거는 비어야 한다
    assert state["missing_optional"] == ["lifelines.pkl"]   # 다만 숨기지는 않는다


def test_required_list_reads_fetch_artifacts_table():
    """필수 목록이 scripts/fetch_artifacts.py 에서 실제로 읽히는지.

    못 읽으면 None 으로 떨어져 '빠진 건 전부 필수' 라는 보수적 동작으로 되돌아간다.
    조용히 그렇게 되면 이 수정이 무의미해지므로 여기서 잡는다.
    """
    import main

    main._required_artifacts.cache_clear()
    try:
        required = main._required_artifacts()
    finally:
        main._required_artifacts.cache_clear()

    assert required is not None, "scripts/fetch_artifacts.py 의 FILES 를 못 읽었다"
    assert "knn.pkl" in required
    assert "lifelines_klips.pkl" in required
    assert "lifelines.pkl" not in required      # 폐기 대상
    assert "knn_yp.pkl" not in required         # 선택 폴백
