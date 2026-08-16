import unittest

from sensitivity_validate_job_change_financial import nonlinear_preprocessor


class FinancialSensitivityTest(unittest.TestCase):
    def test_nonlinear_preprocessor_is_dense_and_handles_unknown_categories(self):
        import pandas as pd

        pre = nonlinear_preprocessor(["age"], ["job"])
        train = pd.DataFrame({"age": [20, 30, None], "job": ["a", "b", "a"]})
        test = pd.DataFrame({"age": [25], "job": ["unseen"]})
        pre.fit(train)
        transformed = pre.transform(test)
        self.assertEqual(transformed.shape[0], 1)
        self.assertEqual(transformed.ndim, 2)


if __name__ == "__main__":
    unittest.main()
