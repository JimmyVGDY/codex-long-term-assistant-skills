"""中文：策略与评分契约测试；来源快照是明确的合成夹具。

English: Policy/scorecard contract tests using synthetic provenance, not host evidence.
"""
from __future__ import annotations

import copy
import hashlib
import itertools
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
from cp_runtime.dispatch_policy import (  # noqa: E402
    CURRENT_POLICY_ID, LEGACY_POLICY_ID, DispatchPolicyError, allowed_profiles,
    canonical_json, legacy_minimum_profiles, policy, policy_digest, profile_spec,
    profile_weights, requirement_profiles, resolve_request, score_review, validate_scorecard,
)

ROLE = "cp_review_data_contract"
CONTEXT = {
    "project_id": "synthetic-project", "task_id": "synthetic-task",
    "repo_fingerprint": "sha256:" + "a" * 64,
    "packet_sha256": "b" * 64, "baseline_sha256": "c" * 64,
}


def sha(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode()).hexdigest()


def evidence(*pairs: tuple[str, str]) -> tuple[list[dict], dict]:
    atoms, proofs = [], {}
    for index, (dimension, level) in enumerate(pairs):
        ref = sha("synthetic-evidence-" + str(index))
        atoms.append({"dimension": dimension, "level": level, "evidence_ref": ref,
                      "correlation_ref": sha("synthetic-cause-" + str(index))})
        proofs[ref] = {
            "evidence_ref": ref, "context": dict(CONTEXT), "status": "valid",
            "source": "verified-evidence-record",
            "prior_result_ref": sha("synthetic-prior-result") if dimension == "prior_inconclusive" else "",
            "prior_attempt_ref": sha("synthetic-prior-attempt") if dimension == "prior_inconclusive" else "",
        }
    return atoms, proofs


def scored(*pairs: tuple[str, str], **kwargs) -> dict:
    atoms, proofs = evidence(*pairs)
    return score_review(agent_type=kwargs.pop("agent_type", ROLE), context=CONTEXT,
                        evidence_items=atoms, proofs=proofs, **kwargs)


class DispatchPolicyTests(unittest.TestCase):
    def test_registered_reviewers_accept_ten_exact_tuples_and_general_roles_keep_four(self):
        for role in policy()["reviewer_roles"]:
            self.assertEqual(10, len(allowed_profiles(role)))
            for name in allowed_profiles(role):
                spec = profile_spec(name)
                self.assertEqual((name, "explicit-request"), resolve_request(
                    spec["model"], spec["effort"], "luna-low", role))
        for role in ("worker", "explorer", "default", ""):
            self.assertEqual(4, len(allowed_profiles(role)))
            for family, effort in itertools.product(("sol", "astra"), ("low", "medium", "high")):
                model = "gpt-6-astra" if family == "astra" else "gpt-5.6-sol"
                with self.assertRaises(DispatchPolicyError):
                    resolve_request(model, effort, "luna-low", role)

    def test_unknown_roles_partial_requests_implicit_premium_and_excess_effort_reject(self):
        for role in ("cp_review_fake", "reviewer", "review", "cp_review_data_contract_extra"):
            with self.assertRaises(DispatchPolicyError):
                resolve_request("gpt-5.6-sol", "low", "luna-low", role)
        for model, effort, default in (("", "", "sol-low"), ("gpt-5.6-sol", "", "luna-low"),
                                       ("", "high", "luna-low"), ("gpt-6-other", "high", "luna-low")):
            with self.assertRaises(DispatchPolicyError):
                resolve_request(model, effort, default, ROLE)
        for effort in ("xhigh", "max", "ultra", "none"):
            with self.assertRaises(DispatchPolicyError):
                resolve_request("gpt-6-astra", effort, "luna-low", ROLE)

    def test_policy_is_pinned_and_returns_no_mutable_global_state(self):
        before = policy_digest()
        mutable = policy()
        mutable["profiles"]["astra-high"]["units"] = 1
        self.assertEqual(40, profile_weights()["astra-high"])
        self.assertEqual(before, policy_digest())
        with self.assertRaises(DispatchPolicyError):
            policy(CURRENT_POLICY_ID, sha("not-the-policy"))
        with self.assertRaises(DispatchPolicyError):
            policy("future-version")
        self.assertEqual({"luna-low": 1, "luna-medium": 2, "terra-medium": 4, "terra-high": 8},
                         profile_weights(LEGACY_POLICY_ID))
        self.assertEqual(["terra-medium", "terra-high"], legacy_minimum_profiles("terra-medium"))
        with self.assertRaises(DispatchPolicyError):
            legacy_minimum_profiles("sol-low")

    def test_luna_base_and_all_ten_evidence_budget_boundaries(self):
        cases = [
            ("economy", (), "luna-low", 1),
            ("balanced", (), "luna-medium", 2),
            ("deep", (), "terra-medium", 4),
            ("deep", (("state", "multi_step"),), "terra-high", 8),
            ("balanced", (("state", "concurrent"),), "sol-low", 10),
            ("deep", (("semantic", "bounded"), ("state", "concurrent")), "sol-medium", 14),
            ("deep", (("state", "concurrent"), ("conflict", "confirmed")), "sol-high", 18),
            ("deep", (("semantic", "multi_domain"), ("state", "concurrent"), ("impact", "high")), "astra-low", 24),
            ("deep", (("semantic", "multi_domain"), ("state", "concurrent"), ("conflict", "confirmed"),
                      ("prior_inconclusive", "confirmed")), "astra-medium", 32),
            ("deep", (("semantic", "multi_domain"), ("state", "concurrent"),
                      ("impact", "critical_irreversible"), ("conflict", "confirmed")), "astra-high", 40),
        ]
        for mode, items, expected, units in cases:
            with self.subTest(profile=expected):
                result = scored(*items, reviewer_budget=mode)
                self.assertEqual(1, result["base_units"])
                self.assertEqual(expected, result["approved_profile"])
                self.assertEqual(units, result["earned_budget"])
                self.assertEqual(result, validate_scorecard(result))

    def test_missing_stale_and_cross_context_evidence_add_no_points(self):
        atoms, proofs = evidence(("impact", "critical_irreversible"))
        ref = atoms[0]["evidence_ref"]
        for field in CONTEXT:
            changed = copy.deepcopy(proofs)
            changed[ref]["context"][field] = "different" if field in {"project_id", "task_id"} else (
                "sha256:" + "d" * 64 if field == "repo_fingerprint" else "d" * 64)
            result = score_review(agent_type=ROLE, context=CONTEXT, evidence_items=atoms, proofs=changed)
            self.assertEqual("luna-low", result["approved_profile"])
            self.assertEqual(0, sum(row["points"] for row in result["awards"]))
        for status in ("stale", "unknown", "failed", "blocked"):
            changed = copy.deepcopy(proofs)
            changed[ref]["status"] = status
            self.assertEqual(1, score_review(agent_type=ROLE, context=CONTEXT,
                                           evidence_items=atoms, proofs=changed)["earned_budget"])
        self.assertEqual(1, score_review(agent_type=ROLE, context=CONTEXT, evidence_items=atoms)["earned_budget"])

    def test_transitive_correlation_and_permutation_cannot_inflate_score(self):
        atoms, proofs = evidence(("semantic", "multi_domain"), ("state", "concurrent"),
                                 ("impact", "critical_irreversible"))
        atoms[1]["evidence_ref"] = atoms[0]["evidence_ref"]
        atoms[2]["correlation_ref"] = atoms[1]["correlation_ref"]
        proofs.pop(sha("synthetic-evidence-1"))
        encodings = set()
        for order in itertools.permutations(atoms):
            result = score_review(agent_type=ROLE, context=CONTEXT, evidence_items=order, proofs=proofs)
            self.assertEqual(15, result["earned_budget"])
            self.assertEqual(1, len(result["awards"]))
            self.assertEqual("impact", result["awards"][0]["dimension"])
            encodings.add(canonical_json(result))
        self.assertEqual(1, len(encodings))

    def test_exact_duplicates_dimension_caps_and_fixed_ties(self):
        atoms, proofs = evidence(("semantic", "multi_domain"), ("state", "concurrent"))
        atoms[1]["correlation_ref"] = atoms[0]["correlation_ref"]
        result = score_review(agent_type=ROLE, context=CONTEXT, evidence_items=atoms + atoms, proofs=proofs)
        self.assertEqual(9, result["earned_budget"])
        self.assertEqual("state", result["awards"][0]["dimension"])
        atoms, proofs = evidence(("semantic", "bounded"), ("semantic", "cross_module"), ("semantic", "multi_domain"))
        result = score_review(agent_type=ROLE, context=CONTEXT, evidence_items=atoms, proofs=proofs)
        self.assertEqual(9, result["earned_budget"])
        self.assertEqual(2, len(result["exclusions"]))

    def test_invalid_evidence_cannot_join_valid_groups_and_reduce_their_score(self):
        atoms, proofs = evidence(("semantic", "multi_domain"), ("state", "concurrent"), ("impact", "high"))
        invalid = atoms.pop()
        proofs[invalid["evidence_ref"]]["status"] = "stale"
        bridges = [{**invalid, "correlation_ref": atom["correlation_ref"]} for atom in atoms]
        result = score_review(agent_type=ROLE, context=CONTEXT, evidence_items=atoms + bridges, proofs=proofs)
        self.assertEqual(17, result["earned_budget"])
        self.assertEqual(2, len(result["awards"]))

    def test_quality_requirements_do_not_use_a_cross_model_rank(self):
        with self.assertRaisesRegex(DispatchPolicyError, "SCORE_BELOW_QUALITY_REQUIREMENT"):
            scored(requirements=["astra-low"])
        result = scored(("impact", "critical_irreversible"), ("state", "concurrent"),
                        ("semantic", "multi_domain"), ("conflict", "confirmed"),
                        reviewer_budget="deep", requirements=["sol-medium", "sol-high"])
        self.assertEqual("sol-high", result["approved_profile"])
        self.assertNotIn("astra-high", result["requirement_profiles"])
        for requested in ([], ["sol-low", "sol-low"], ["not-known"]):
            with self.assertRaises(DispatchPolicyError):
                requirement_profiles(ROLE, requested)

    def test_general_role_cannot_gain_premium_by_high_scoring(self):
        result = scored(("impact", "critical_irreversible"), ("state", "concurrent"),
                        ("semantic", "multi_domain"), ("conflict", "confirmed"),
                        reviewer_budget="deep", agent_type="worker")
        self.assertEqual(40, result["earned_budget"])
        self.assertEqual("terra-high", result["approved_profile"])

    def test_previous_inconclusive_requires_both_references(self):
        atoms, proofs = evidence(("prior_inconclusive", "confirmed"))
        proofs[atoms[0]["evidence_ref"]]["prior_attempt_ref"] = ""
        self.assertEqual(1, score_review(agent_type=ROLE, context=CONTEXT,
                                       evidence_items=atoms, proofs=proofs)["earned_budget"])

    def test_tampered_totals_candidates_or_exclusions_are_rejected(self):
        valid = scored(("state", "multi_step"), reviewer_budget="deep")
        for key, value in (("earned_budget", 40), ("approved_profile", "astra-high"),
                           ("cost_basis_units", 1), ("requirement_profiles", ["sol-high"]),
                           ("extra", "untrusted")):
            changed = {**valid, key: value}
            with self.assertRaises(DispatchPolicyError):
                validate_scorecard(changed)
        for role in ("", "default", "cp_review_unregistered"):
            with self.assertRaises(DispatchPolicyError):
                scored(agent_type=role)


if __name__ == "__main__":
    unittest.main()
