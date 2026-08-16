import unittest

import pandas as pd

from evaluate_job_change_indicators import clustered_bootstrap_difference, summarize_metric


class IndicatorValidationTest(unittest.TestCase):
    def test_summary_reports_move_minus_stay(self):
        df = pd.DataFrame({
            "pid": range(8), "moved_t1": [0, 0, 0, 0, 1, 1, 1, 1],
            "change": [0, 0, 1, 1, 2, 2, 3, 3],
        })
        result = summarize_metric(df, "change", "test", "point")
        self.assertEqual(result["unadjusted_mean_difference_move_minus_stay"], 2.0)
        self.assertFalse(result["causal"])

    def test_bootstrap_requires_both_groups(self):
        df = pd.DataFrame({"pid": [1, 2], "moved_t1": [0, 0], "change": [1, 2]})
        self.assertEqual(clustered_bootstrap_difference(df, "change"), (None, None))


if __name__ == "__main__":
    unittest.main()
