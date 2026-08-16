"""KLIPS 이직 전후 분석표의 시간 정렬 규칙 테스트."""

import unittest

import pandas as pd


class TransitionRulesTest(unittest.TestCase):
    def test_group_shift_never_crosses_people(self):
        data = pd.DataFrame({
            "pid": [1, 1, 2, 2],
            "wave": [1, 2, 1, 2],
            "이직": [0, 1, 0, 0],
        }).sort_values(["pid", "wave"])
        nxt = data.groupby("pid", sort=False).shift(-1)
        self.assertEqual(nxt.loc[data.index[0], "이직"], 1)
        self.assertTrue(pd.isna(nxt.loc[data.index[1], "이직"]))
        self.assertEqual(nxt.loc[data.index[2], "이직"], 0)

    def test_only_consecutive_years_are_eligible(self):
        transitions = pd.DataFrame({
            "wave_t": [1, 2, 3], "wave_t1": [2, 4, 4],
            "year_t": [2020, 2021, 2022], "year_t1": [2021, 2023, 2023],
        })
        eligible = transitions[
            ((transitions.wave_t1 - transitions.wave_t) == 1)
            & ((transitions.year_t1 - transitions.year_t) == 1)
        ]
        self.assertEqual(list(eligible.index), [0, 2])

    def test_change_uses_future_minus_present(self):
        row = pd.Series({"life_satisfaction_t": 4, "life_satisfaction_t1": 6})
        self.assertEqual(row.life_satisfaction_t1 - row.life_satisfaction_t, 2)


if __name__ == "__main__":
    unittest.main()
