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
        },
    }), encoding="utf-8")

    monkeypatch.setattr(type(main.settings), "artifacts_abspath", property(lambda _: tmp_path))
    main._artifact_manifest.cache_clear()
    try:
        state = main._artifact_manifest()
    finally:
        main._artifact_manifest.cache_clear()

    assert state["manifest_missing"] == []
    assert state["missing"] == ["missing.pkl"]
    assert state["artifacts"]["present.pkl"]["present"] is True
    assert state["artifacts"]["missing.pkl"]["present"] is False
