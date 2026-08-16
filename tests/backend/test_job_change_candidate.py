import unittest

from models.job_change_candidate import financial_impact, prediction_for_choice


class JobChangeCandidateTest(unittest.TestCase):
    def test_candidate_returns_separated_evidence_and_experiment(self):
        result = financial_impact({
            "age": 29, "sex": "2", "monthly_wage": 320,
            "firm_size": 4, "edu_level": 7, "occupation_group": 3,
            "employment_status": 1, "tenure_years": 2.5,
        })
        self.assertEqual(result["status"], "directional_evidence_not_deployment_approved")
        self.assertEqual(result["population_evidence"]["verdict"], "favorable_association")
        self.assertEqual(result["personalized_estimate"]["status"], "disabled_insufficient_individual_validation")
        self.assertNotIn("difference_pct_points", result["personalized_estimate"])
        self.assertEqual(result["sensitivity_validation"]["decision"], "보류")
        self.assertEqual(result["growth_potential"]["status"], "insufficient_evidence")
        self.assertEqual(result["quality_of_life"]["status"], "insufficient_evidence")
        self.assertEqual(result["input_quality"]["imputed_features"], [])
        self.assertEqual(result["observed_transitions"]["status"], "available")
        self.assertEqual(result["observed_transitions"]["evidence_grade"], "observed")
        self.assertGreater(result["observed_transitions"]["sample_n"], 0)
        self.assertLessEqual(len(result["observed_transitions"]["destinations"]), 5)

    def test_non_job_choice_is_not_applicable(self):
        result = prediction_for_choice("진학", {"age": 29})
        self.assertEqual(result["status"], "not_applicable")

    def test_move_and_stay_receive_separate_observed_outcomes(self):
        profile = {
            "age": 29, "occupation_group": 3, "employment_status": 1,
            "monthly_wage": 320, "tenure_years": 2.5, "firm_size": 5,
        }
        move = prediction_for_choice("이직", profile)
        stay = prediction_for_choice("유지", profile)
        self.assertEqual(move["observed_outcomes"]["scenario"], "move")
        self.assertEqual(stay["observed_outcomes"]["scenario"], "stay")
        self.assertIn("growth", move["observed_outcomes"]["domains"])
        self.assertIn("quality_of_life", move["observed_outcomes"]["domains"])
        self.assertGreaterEqual(move["observed_outcomes"]["matching"]["sample_n"], 40)
        self.assertIn("직종", move["observed_outcomes"]["matching"]["applied_conditions"])
        self.assertEqual([point["year"] for point in move["parallel_trajectory"]["timeline"]], [1, 3, 5])
        self.assertGreater(move["parallel_trajectory"]["timeline"][0]["sample_n"], 0)

    def test_profiles_produce_different_matched_groups(self):
        office = prediction_for_choice("이직", {
            "age": 29, "occupation_group": 3, "employment_status": 1, "monthly_wage": 320,
        })["observed_outcomes"]
        service = prediction_for_choice("이직", {
            "age": 29, "occupation_group": 4, "employment_status": 2, "monthly_wage": 180,
        })["observed_outcomes"]
        self.assertNotEqual(office["matching"]["sample_n"], service["matching"]["sample_n"])


if __name__ == "__main__":
    unittest.main()
