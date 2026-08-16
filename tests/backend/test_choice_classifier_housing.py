from choice_classifier import classify


def test_housing_inflections_are_classified_as_housing():
    for text in ("집을 산다", "집을 판다", "집을 살까", "아파트를 산다"):
        assert classify(text, record=False).kind == "주택"

