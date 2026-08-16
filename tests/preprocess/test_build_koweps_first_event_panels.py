import pandas as pd

from preprocess.build_koweps_first_event_panels import first_baselines, make_event


def test_first_event_and_never_event_control_are_one_row_per_person():
    frame = pd.DataFrame({
        "h_pid": [1, 1, 1, 2, 2, 2], "wv": [1, 2, 3, 1, 2, 3],
        "age": [25, 26, 27, 25, 26, 27], "move": [2, 1, 1, 2, 2, 2],
    })
    event = make_event(frame, {"source": "move", "mode": "yes", "yes_value": 1})
    result = first_baselines(frame, event, [25, 35])
    assert result.groupby("h_pid").size().max() == 1
    assert result.set_index("h_pid")["treatment"].to_dict() == {1: 1, 2: 0}


def test_change_requires_consecutive_known_waves():
    frame = pd.DataFrame({
        "h_pid": [1, 1, 2, 2], "wv": [1, 3, 1, 2],
        "age": [25, 27, 25, 26], "state": [1, 2, 1, 2],
    })
    event = make_event(frame, {"source": "state", "mode": "change"})
    assert pd.isna(event.iloc[1])
    assert event.iloc[3] == 1


def test_transition_keeps_direction_separate():
    frame = pd.DataFrame({
        "h_pid": [1, 1, 2, 2], "wv": [1, 2, 1, 2],
        "age": [25, 26, 25, 26], "state": [5, 1, 1, 3],
    })
    event = make_event(frame, {
        "source": "state", "mode": "transition", "from_values": [5], "to_values": [1],
    })
    assert event.iloc[1] == 1
    assert pd.isna(event.iloc[3])


def test_increase_excludes_decrease_from_control():
    frame = pd.DataFrame({
        "h_pid": [1, 1, 2, 2, 3, 3], "wv": [1, 2, 1, 2, 1, 2],
        "age": [25, 26] * 3, "level": [5, 6, 5, 4, 5, 5],
    })
    event = make_event(frame, {"source": "level", "mode": "increase"})
    assert event.iloc[1] == 1
    assert pd.isna(event.iloc[3])
    assert event.iloc[5] == 0


def test_positive_entry_compares_zero_to_positive_with_zero_stayers():
    frame = pd.DataFrame({
        "h_pid": [1, 1, 2, 2, 3, 3], "wv": [1, 2, 1, 2, 1, 2],
        "age": [25, 26] * 3, "debt": [0, 500, 0, 0, 100, 50],
    })
    event = make_event(frame, {"source": "debt", "mode": "positive_entry"})
    assert event.iloc[1] == 1
    assert event.iloc[3] == 0
    assert pd.isna(event.iloc[5])
