import unittest

import pandas as pd

from train_validate_job_change_models import _cluster_ci, split_people


class JobChangeModelValidationTest(unittest.TestCase):
    def test_split_is_person_disjoint_and_reproducible(self):
        df = pd.DataFrame({
            "pid": [pid for pid in range(20) for _ in range(2)],
            "moved_t1": [0, 1] * 20,
        })
        train_a, test_a = split_people(df)
        train_b, test_b = split_people(df)
        self.assertFalse(set(train_a.pid) & set(test_a.pid))
        self.assertEqual(set(train_a.pid), set(train_b.pid))
        self.assertEqual(set(test_a.pid), set(test_b.pid))

    def test_cluster_ci_contains_row_weighted_mean(self):
        pseudo = pd.Series([1.0, 1.0, 1.0, 5.0]).to_numpy()
        pid = pd.Series([1, 1, 1, 2]).to_numpy()
        low, high = _cluster_ci(pseudo, pid, iterations=2000)
        self.assertLess(low, pseudo.mean())
        self.assertGreater(high, pseudo.mean())


if __name__ == "__main__":
    unittest.main()
