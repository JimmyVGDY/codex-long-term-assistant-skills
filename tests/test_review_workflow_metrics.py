"""中文：交付失败不能从端到端评测分母消失。

English: Failed delivery must not disappear from end-to-end evaluation denominators.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime"))
from cp_runtime.review_workflow_metrics import summarize_trials


def trial(number, **changes):
    return {"trial_id": f"trial-{number}", "case_id": f"case-{number}", "profile_id": "g6-sol-medium",
            "excluded": False, "material_delivered": True, "protocol_valid": True,
            "boundary_compliant": True, "semantic_correct": True, "duration_ms": 100, "cost_proxy": 2,
            **changes}


class WorkflowMetricTests(unittest.TestCase):
    def test_delivery_failures_remain_in_primary_denominator(self):
        result = summarize_trials([trial(1), trial(2, material_delivered=False, protocol_valid=False,
                                    semantic_correct=None), trial(3, semantic_correct=False)])
        stats = result["all"]
        self.assertEqual({"numerator": 1, "denominator": 3, "rate": 1 / 3}, stats["complete_workflow"])
        self.assertEqual(2, stats["material_delivery"]["numerator"])
        self.assertEqual(0.5, stats["semantic_accuracy_conditional_on_scored"]["rate"])
        self.assertEqual(3, stats["semantic_scoring_coverage"]["denominator"])
        self.assertEqual("NOT_EVALUATED", result["production_qualification"])

    def test_good_analysis_with_bad_receipt_or_forbidden_retry_is_not_workflow_pass(self):
        stats = summarize_trials([trial(1, protocol_valid=False), trial(2, boundary_compliant=False)])["all"]
        self.assertEqual(1, stats["semantic_accuracy_conditional_on_scored"]["rate"])
        self.assertEqual(0, stats["complete_workflow"]["numerator"])

    def test_retry_and_exclusion_costs_are_never_refunded_or_hidden(self):
        stats = summarize_trials([trial(1, excluded=True), trial(2, material_delivered=False,
                    semantic_correct=None, duration_ms=None, cost_proxy=None), trial(3, case_id="case-2")])["all"]
        self.assertEqual(3, stats["actual_attempts"])
        self.assertEqual(2, stats["eligible_attempts"])
        self.assertEqual(1, stats["independent_cases"])
        self.assertEqual({"known_sum": 4, "known_attempts": 2, "unknown_attempts": 1}, stats["cost_proxy"])

    def test_missing_and_empty_evidence_is_unknown_not_zero_quality(self):
        stats = summarize_trials([])["all"]
        self.assertIsNone(stats["complete_workflow"]["rate"])
        stats = summarize_trials([trial(1, semantic_correct=None)])["all"]
        self.assertIsNone(stats["semantic_accuracy_conditional_on_scored"]["rate"])
        self.assertEqual(0, stats["complete_workflow"]["rate"])

    def test_duplicate_or_invented_semantic_evidence_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "DUPLICATE_TRIAL"):
            summarize_trials([trial(1), trial(1)])
        with self.assertRaisesRegex(ValueError, "GRADE_WITHOUT_MATERIAL"):
            summarize_trials([trial(1, material_delivered=False)])
        for changes in ({"semantic_correct": "pass"}, {"cost_proxy": float("nan")},
                        {"duration_ms": -1}, {"protocol_valid": 1}, {"cost_proxy": True}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                summarize_trials([trial(1, **changes)])

    def test_profiles_remain_separate_with_same_paired_case(self):
        report = summarize_trials([trial(1), trial(2, case_id="case-1", profile_id="g56-sol-medium")])
        self.assertEqual(1, report["all"]["independent_cases"])
        self.assertEqual(2, len(report["profiles"]))


if __name__ == "__main__":
    unittest.main()
