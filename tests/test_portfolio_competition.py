import unittest

from scripts.portfolio_competition import candidates_from_intelligence, compare_candidates


class PortfolioCompetitionTests(unittest.TestCase):
    def test_measured_winner_faces_strongest_distinct_challenger(self):
        candidates = [
            {"id": "winner", "eligible": True, "pursuit_score": 92.0,
             "experiment_state": "scale_candidate", "effective_evidence_quality": 0.9},
            {"id": "challenger", "eligible": True, "pursuit_score": 94.5,
             "experiment_state": "validate", "effective_evidence_quality": 0},
            {"id": "retired", "eligible": True, "pursuit_score": 99.0,
             "experiment_state": "deprioritize", "effective_evidence_quality": 1},
        ]
        result = compare_candidates(candidates)
        self.assertEqual(result["champion"]["id"], "winner")
        self.assertEqual(result["challenger"]["id"], "challenger")
        self.assertEqual(result["posture"], "challenger_advantage")
        self.assertEqual(result["recommended_action"], "run_bounded_head_to_head_validation")
        self.assertEqual(result["execution_gate"], "recommendation_only")
        self.assertFalse(result["guardrails"]["automatic_spend"])

    def test_unmeasured_portfolio_starts_with_validation(self):
        result = compare_candidates([
            {"id": "a", "eligible": True, "pursuit_score": 90,
             "experiment_state": "validate", "effective_evidence_quality": 0},
            {"id": "b", "eligible": True, "pursuit_score": 88,
             "experiment_state": "validate", "effective_evidence_quality": 0},
        ])
        self.assertIsNone(result["champion"])
        self.assertEqual(result["challenger"]["id"], "a")
        self.assertEqual(result["recommended_action"], "validate_challenger")

    def test_prefers_evidence_enriched_pursuit_candidates(self):
        pursuit = [{"id": "evidence", "pursuit_score": 91, "experiment_state": "validate"}]
        snapshot = {"pursuit_plan": {"pursue": pursuit}, "candidates": [{"id": "static"}]}
        self.assertEqual(candidates_from_intelligence(snapshot), pursuit)

    def test_falls_back_to_candidate_list(self):
        candidates = [{"id": "static"}]
        self.assertEqual(candidates_from_intelligence({"candidates": candidates}), candidates)


if __name__ == "__main__":
    unittest.main()
