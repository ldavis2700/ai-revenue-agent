import unittest
import math
import json
from pathlib import Path
import subprocess
import sys
import tempfile

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

    def test_rejects_non_finite_candidates_without_distorting_selection(self):
        candidates = [
            {"id": "valid", "eligible": True, "pursuit_score": 88,
             "experiment_state": "validate", "effective_evidence_quality": 0},
            {"id": "nan-score", "eligible": True, "pursuit_score": float("nan"),
             "experiment_state": "scale_candidate", "effective_evidence_quality": 1},
            {"id": "infinite-quality", "eligible": True, "pursuit_score": 100,
             "experiment_state": "scale_candidate", "effective_evidence_quality": float("inf")},
        ]
        result = compare_candidates(candidates)
        self.assertIsNone(result["champion"])
        self.assertEqual(result["challenger"]["id"], "valid")
        self.assertEqual(result["rejected_candidate_count"], 2)
        self.assertEqual(result["rejected_candidate_ids"], ["nan-score", "infinite-quality"])
        self.assertTrue(math.isfinite(result["challenger"]["pursuit_score"]))

    def test_rejects_malformed_identity_eligibility_and_quality_range(self):
        candidates = [
            {"id": "", "eligible": True, "pursuit_score": 99},
            {"id": "string-eligible", "eligible": "false", "pursuit_score": 98},
            {"id": "quality-overflow", "eligible": True, "pursuit_score": 97,
             "effective_evidence_quality": 1.01},
            {"id": "valid", "eligible": True, "pursuit_score": "86.5",
             "experiment_state": "continue_validation", "effective_evidence_quality": "0.5"},
        ]
        result = compare_candidates(candidates)
        self.assertEqual(result["champion"]["id"], "valid")
        self.assertIsNone(result["challenger"])
        self.assertEqual(result["rejected_candidate_count"], 3)
        self.assertEqual(result["champion"]["pursuit_score"], 86.5)
        self.assertEqual(result["champion"]["effective_evidence_quality"], 0.5)

    def test_all_corrupt_candidates_fail_closed_without_exception(self):
        result = compare_candidates([
            {"id": "bad-score", "pursuit_score": "not-a-number"},
            "not-a-candidate",
            None,
        ])
        self.assertEqual(result["posture"], "no_viable_candidate")
        self.assertIsNone(result["champion"])
        self.assertIsNone(result["challenger"])
        self.assertEqual(result["rejected_candidate_count"], 3)

    def test_rejects_integer_conversion_overflow_per_candidate(self):
        for field in ("pursuit_score", "effective_evidence_quality"):
            for value in (10 ** 400, -(10 ** 400)):
                with self.subTest(field=field, sign=value > 0):
                    result = compare_candidates([
                        {"id": "overflow", field: value},
                        {"id": "valid", "pursuit_score": 86},
                    ])
                    self.assertEqual(result["challenger"]["id"], "valid")
                    self.assertEqual(result["rejected_candidate_ids"], ["overflow"])
                    json.dumps(result, allow_nan=False)

    def test_rejects_score_gap_overflow_in_both_directions(self):
        for champion_score, challenger_score in ((-1e308, 1e308), (1e308, -1e308)):
            with self.subTest(champion_score=champion_score):
                with self.assertRaisesRegex(ValueError, "score difference must be a finite number"):
                    compare_candidates([
                        {"id": "champion", "pursuit_score": champion_score,
                         "experiment_state": "scale_candidate", "effective_evidence_quality": 1},
                        {"id": "challenger", "pursuit_score": challenger_score},
                    ])

    def test_large_representable_score_gap_remains_valid(self):
        result = compare_candidates([
            {"id": "champion", "pursuit_score": -4e307,
             "experiment_state": "scale_candidate", "effective_evidence_quality": 1},
            {"id": "challenger", "pursuit_score": 4e307},
        ])
        self.assertEqual(result["challenger_minus_champion_score"], 8e307)
        self.assertEqual(result["posture"], "challenger_advantage")
        self.assertEqual(result["execution_gate"], "recommendation_only")
        self.assertTrue(all(value is False for value in result["guardrails"].values()))
        json.dumps(result, allow_nan=False)

    def test_cli_does_not_publish_an_overflowed_recommendation(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory) / "intelligence.json"
            snapshot.write_text(json.dumps({"candidates": [
                {"id": "champion", "pursuit_score": -1e308,
                 "experiment_state": "scale_candidate", "effective_evidence_quality": 1},
                {"id": "challenger", "pursuit_score": 1e308},
            ]}), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(Path(__file__).resolve().parents[1] / "scripts/portfolio_competition.py"),
                 "--intelligence-json", str(snapshot)],
                capture_output=True, text=True, check=False,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("score difference must be a finite number", result.stderr)


if __name__ == "__main__":
    unittest.main()
