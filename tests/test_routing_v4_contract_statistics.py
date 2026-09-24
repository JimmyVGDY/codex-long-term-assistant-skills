"""中文：V4 请求目录和统计边界；合成数据不提供模型资格。

English: Request catalog and statistical boundary tests with synthetic samples.
"""
from __future__ import annotations

import math
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
from cp_runtime.routing_contract import (RoutingError, admitted, phase_key, policy,
    policy_digest, read_document, resolve_request, resource_need)
from cp_runtime.routing_statistics import exact_binomial, paired_quality, paired_ratio


class V4ContractTests(unittest.TestCase):
    def test_catalog_has_eighteen_tuples_but_default_reviewer_pool_has_nine(self):
        data = policy()
        self.assertEqual(18, len(data["profiles"]))
        self.assertEqual(6, len({item["model"] for item in data["profiles"].values()}))
        role = "cp_review_data_contract"
        self.assertEqual(9, len(admitted(role)))
        self.assertEqual(18, len(admitted(role, "EVALUATION")))
        with self.assertRaises(RoutingError):
            resolve_request("gpt-5.6-terra", "low", role)
        self.assertEqual("g56-terra-low", resolve_request("gpt-5.6-terra", "low", role, "EVALUATION"))

    def test_general_roles_never_inherit_reviewer_or_evaluation_admission(self):
        for role in ("worker", "explorer"):
            self.assertEqual(4, len(admitted(role)))
            with self.assertRaises(RoutingError):
                admitted(role, "EVALUATION")
            with self.assertRaises(RoutingError):
                resolve_request("gpt-6-astra", "low", role)
        for effort in ("", "none", "xhigh", "max", "ultra"):
            with self.assertRaises(RoutingError):
                resolve_request("gpt-6-sol", effort, "cp_review_data_contract")

    def test_mutating_return_value_cannot_change_frozen_policy(self):
        before = policy_digest()
        policy()["profiles"]["g6-sol-high"]["model"] = "untrusted"
        self.assertEqual(before, policy_digest())
        self.assertEqual("gpt-6-sol", policy()["profiles"]["g6-sol-high"]["model"])

    def test_duplicate_keys_nonfinite_and_oversized_documents_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            for body in ('{"a":1,"a":2}', '{"x":NaN}', "[]"):
                path.write_text(body, encoding="utf-8")
                with self.assertRaises(RoutingError):
                    read_document(path)
            path.write_text('{"a":"' + "x" * 300 + '"}', encoding="utf-8")
            with self.assertRaisesRegex(RoutingError, "TOO_LARGE"):
                read_document(path, maximum=100)

    def test_repair_normalization_and_resource_categories(self):
        self.assertEqual("repair", phase_key("post", "repair"))
        with self.assertRaises(RoutingError):
            phase_key("pre", "repair")
        self.assertEqual({"units": 12, "attempts": 1, "astra_attempts": 1,
                          "astra_high_attempts": 1}, resource_need("g6-astra-high", 12))
        self.assertEqual(0, resource_need("g6-sol-high", 12)["astra_attempts"])
        with self.assertRaises(RoutingError):
            resource_need("g6-sol-high", True)


class V4StatisticsTests(unittest.TestCase):
    def test_exact_interval_matches_reference_binomial_example(self):
        low, high = exact_binomial(20, 25)
        # 中文：公开参考值是近似值，按其公布精度校验。
        # English: The published reference is approximate; test its displayed precision.
        self.assertAlmostEqual(0.592962, low, delta=0.000001)
        self.assertAlmostEqual(0.9316878, high, delta=0.000001)

    def test_endpoints_satisfy_independent_binomial_equations(self):
        low, high = exact_binomial(20, 25)
        def direct_cdf(k, p):
            return math.fsum(math.comb(25, i) * p ** i * (1 - p) ** (25 - i)
                             for i in range(k + 1))
        self.assertAlmostEqual(0.975, direct_cdf(19, low), places=11)
        self.assertAlmostEqual(0.025, direct_cdf(20, high), places=11)

    def test_zero_failures_does_not_create_zero_width_certainty(self):
        low, high = exact_binomial(0, 30)
        self.assertEqual(0.0, low)
        self.assertAlmostEqual(1 - 0.025 ** (1 / 30), high, places=10)
        paired = paired_quality([True] * 30, [True] * 30, family_intervals=2)
        self.assertLess(paired["lower_delta_bp"], -500)
        self.assertGreater(paired["upper_delta_bp"], 500)

    def test_symmetry_and_multiple_comparison_penalty(self):
        left, right = exact_binomial(4, 30)
        inv_left, inv_right = exact_binomial(26, 30)
        self.assertAlmostEqual(left, 1 - inv_right, places=10)
        self.assertAlmostEqual(right, 1 - inv_left, places=10)
        wider = exact_binomial(4, 30, family_intervals=12)
        self.assertLess(wider[0], left)
        self.assertGreater(wider[1], right)

    def test_paired_direction_is_not_raw_pass_rate_or_finding_count(self):
        result = paired_quality([False] * 100, [True] * 100, family_intervals=2)
        self.assertEqual((100, 0), (result["wins"], result["losses"]))
        self.assertGreater(result["lower_delta_bp"], 9000)
        inverse = paired_quality([True] * 100, [False] * 100, family_intervals=2)
        self.assertEqual(result["lower_delta_bp"], -inverse["upper_delta_bp"])

    def test_invalid_counts_and_boolean_integer_aliases_reject(self):
        for arguments in ((True, 30), (31, 30), (0, 0), (0, 10001)):
            with self.assertRaises(RoutingError):
                exact_binomial(*arguments)
        with self.assertRaises(RoutingError):
            paired_quality([1], [True], family_intervals=2)

    def test_bootstrap_keeps_unknown_for_degenerate_or_underpowered_data(self):
        self.assertEqual("UNCERTAIN", paired_ratio([1] * 30, [2] * 30, family_intervals=1)["status"])
        self.assertEqual("UNCERTAIN", paired_ratio([0] * 30, [1] * 30, family_intervals=1)["status"])
        self.assertEqual("UNCERTAIN", paired_ratio([1] * 29, [2] * 29, family_intervals=1)["status"])

    def test_paired_bootstrap_is_reproducible_and_bounded(self):
        a = [10 + i for i in range(30)]
        b = [5 + i // 3 for i in range(30)]
        first = paired_ratio(a, b, family_intervals=1, resamples=1000)
        self.assertEqual(first, paired_ratio(a, b, family_intervals=1, resamples=1000))
        self.assertEqual("ESTIMATED", first["status"])
        self.assertLess(first["upper_ratio_ppm"], 1_000_000)


if __name__ == "__main__":
    unittest.main()
