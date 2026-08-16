import pandas as pd

from preprocess.preprocess_koweps import build_dictionary, selected_variables


def test_dictionary_maps_all_nine_domains():
    codebook = pd.DataFrame([
        {"variable": "job", "label": "직종", "question": "", "waves": "1~20차", "section": "", "codebook_file": "x"},
        {"variable": "house", "label": "주택유형", "question": "", "waves": "1~20차", "section": "", "codebook_file": "x"},
        {"variable": "satis", "label": "전반적 생활 만족도", "question": "", "waves": "1~20차", "section": "", "codebook_file": "x"},
    ])
    result = build_dictionary(codebook, {"job": "직종", "house": "주택유형", "satis": "전반적 만족도"})
    mapped = result.set_index("variable")["domains"].to_dict()
    assert "career" in mapped["job"]
    assert "housing" in mapped["house"]
    assert "long_term_values" in mapped["satis"]


def test_event_detection_uses_label_not_question_noise():
    codebook = pd.DataFrame([
        {"variable": "noise", "label": "지원사업 만족도", "question": "이사 후 지원", "waves": "1~20차", "section": "", "codebook_file": "x"},
        {"variable": "move", "label": "지난 1년간 이사경험 여부", "question": "", "waves": "2~20차", "section": "", "codebook_file": "x"},
    ])
    result = build_dictionary(codebook, {"noise": "지원사업 만족도", "move": "지난 1년간 이사경험 여부"})
    events = result.set_index("variable")["events"].to_dict()
    assert events["noise"] == ""
    assert events["move"] == "residential_move"


def test_selected_variables_keep_core_and_candidates():
    dictionary = pd.DataFrame([
        {"variable": "h_pid", "domains": "", "events": "", "outcomes": ""},
        {"variable": "wv", "domains": "", "events": "", "outcomes": ""},
        {"variable": "h06_aq1", "domains": "housing", "events": "residential_move", "outcomes": ""},
    ])
    selected = selected_variables(dictionary)
    assert "h_pid" in selected and "wv" in selected and "h06_aq1" in selected
