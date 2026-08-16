import unittest

from robustness_validate_job_change_models import classify_stability


class RobustnessValidationTest(unittest.TestCase):
    def test_stability_gate(self):
        self.assertEqual(classify_stability(1.0, 0.8, 0.9), "안정 후보")
        self.assertEqual(classify_stability(0.8, 0.4, 0.9), "방향 후보")
        self.assertEqual(classify_stability(1.0, 1.0, 0.79), "overlap 부족")
        self.assertEqual(classify_stability(0.6, 0.8, 0.9), "근거 불충분")


if __name__ == "__main__":
    unittest.main()
