"""中文：合成样本验证策略/公式/比较对隔离，不是模型收益实测。

English: Synthetic cohort contract tests, not measured model-quality evidence.
"""
from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
from cp_runtime import delegation_budget as budget  # noqa: E402
from cp_runtime.delegation_calibration import (build_pending_sample, compare_scenarios, finalize_sample,
                                              offline_replay_many)  # noqa: E402
from cp_runtime.dispatch_policy import CURRENT_POLICY_ID, LEGACY_POLICY_ID, policy_digest, score_review  # noqa: E402
from test_dispatch_policy import CONTEXT, ROLE, evidence, sha  # noqa: E402


class MatrixCalibrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.ledgers = {}
        self.count = 0

    def tearDown(self):
        self.temp.cleanup()

    def sample(self, profile, *, matrix=True, finalized=True, shared_task=None):
        self.count += 1
        name = "sample-" + str(self.count)
        task = shared_task or "task-" + str(self.count)
        ledger = self.root / (name + ".jsonl")
        context = {**CONTEXT, "task_id": task}
        binding = {"schema_version": "dispatch-root/1", "repo_path": str(self.root),
                   "profile_path": str(self.root / "synthetic-profile.json"), "profile_binding_sha256": "d" * 64,
                   "envelope_identity_ref": sha("synthetic-envelope-" + task), "host_session_ref": sha("synthetic-session-" + task),
                   "reviewer_policy_id": CURRENT_POLICY_ID, "reviewer_policy_digest": policy_digest()}
        budget.initialize_budget(ledger, budget_id=name, task_id=task, project_id=CONTEXT["project_id"],
                                 repo_fingerprint=CONTEXT["repo_fingerprint"], budget_class="STRICT", default_dispatch_profile="luna-low",
                                 policy_id=CURRENT_POLICY_ID if matrix else LEGACY_POLICY_ID,
                                 review_extension=matrix, root_binding=binding if matrix else None)
        extra = {}
        if matrix:
            atoms, proofs = evidence(("semantic", "multi_domain"), ("state", "concurrent"),
                                     ("impact", "critical_irreversible"), ("conflict", "confirmed"))
            for value in proofs.values():
                value["context"] = dict(context)
            selection = score_review(agent_type=ROLE, context=context, reviewer_budget="deep", evidence_items=atoms,
                                     proofs=proofs, requirements=[profile])
            assignment = {"reviewer": "data", "agent_type": ROLE, "boundary_id": "boundary", "phase": "post",
                          "round": 1, "packet_sha256": context["packet_sha256"], "acceptable_profiles": [profile]}
            extra = {"selection_scorecard": selection, "review_assignment": assignment}
        budget.record_decision(ledger, dispatch_key=name, decision="DELEGATE", role="reviewer", approved_profile=profile,
                               reason_code="SEMANTIC_COMPLEXITY", responsibility="data-contract", difficulty="HIGH",
                               risk_domain="DATA", context_size="SMALL", **extra)
        if matrix:
            budget.bind_review_attempt(ledger, dispatch_key=name, review_state_ref=sha("review-" + task), assignment=assignment)
        item = budget.reserve_budget(ledger, dispatch_key=name, host_dispatch_id="synthetic-host-" + name,
                                     approved_profile=profile, approval_basis="explicit-request", role="reviewer")
        if matrix:
            budget.record_host_dispatch_receipt(ledger, dispatch_key=name, host_dispatch_id="synthetic-host-" + name,
                                                agent_id="synthetic-child-" + name)
            budget.record_host_agent_observation(ledger, agent_id="synthetic-child-" + name, phase="start")
            budget.record_host_agent_observation(ledger, agent_id="synthetic-child-" + name, phase="stop", outcome="PASS")
        else:
            budget.mark_started(ledger, reservation_id=item["reservation_id"], agent_id="synthetic-child-" + name)
            budget.mark_completed(ledger, reservation_id=item["reservation_id"], outcome="PASS")
        self.ledgers[name] = ledger
        sample = build_pending_sample(ledger, item["reservation_id"], {
            "accepted_findings": 1, "repaired_findings": 1, "duplicate_findings": 0,
            "missed_findings": 0, "regressions_prevented": 1,
        })
        if not finalized:
            return sample
        return finalize_sample(sample, finalized_by="parent:synthetic", duration_ms=25,
                               evidence_refs=[sample["reservation_completion_ref"], sha("synthetic-validation")])

    def test_matrix_sample_pins_policy_formula_and_declared_pairs(self):
        sample = self.sample("sol-high")
        self.assertEqual("3.0", sample["schema_version"])
        self.assertEqual("review-weight-v2", sample["cost_formula_version"])
        self.assertIn("sol-high--astra-medium", {pair["id"] for pair in sample["comparison_pairs"]})
        report = offline_replay_many([sample], ledger_paths=self.ledgers)
        self.assertEqual("NONE", report["execution_authorization"])
        self.assertFalse(report["automatic_changes_applied"])
        self.assertTrue(all(not row["eligible"] for row in report["comparisons"]))

    def test_declared_cross_family_pair_uses_independent_tasks_and_no_quality_rank(self):
        samples = [self.sample(profile) for profile in ("sol-high", "astra-medium") for _index in range(3)]
        report = offline_replay_many(samples, ledger_paths=self.ledgers)
        pair = next(row for row in report["comparisons"] if row["comparison_pair_id"] == "sol-high--astra-medium")
        self.assertTrue(pair["eligible"])
        self.assertEqual(3, pair["lower_independent_tasks"])
        self.assertEqual(3, pair["higher_independent_tasks"])
        self.assertEqual("sol-high", pair["recommendation"])
        self.assertEqual("declared-policy-pair", pair["comparison_basis"])

    def test_legacy_and_matrix_samples_never_form_one_cohort(self):
        old = self.sample("luna-low", matrix=False)
        new = self.sample("luna-medium")
        rows = compare_scenarios([old, new], minimum_samples_per_profile=1, minimum_tasks_per_profile=1)
        pairs = [row for row in rows if row["comparison_pair_id"] == "luna-low--luna-medium"]
        self.assertEqual(2, len(pairs))
        self.assertEqual({LEGACY_POLICY_ID, CURRENT_POLICY_ID}, {row["policy_id"] for row in pairs})
        self.assertTrue(all(not row["eligible"] for row in pairs))
        self.assertTrue(all(row["lower_samples"] + row["higher_samples"] == 1 for row in pairs))

    def test_unknown_digest_formula_and_pair_reject(self):
        sample = self.sample("astra-low")
        for key, value in (("policy_digest", sha("unknown")), ("cost_formula_version", "future-formula"),
                           ("comparison_pairs", []), ("policy_id", "unknown")):
            changed = {**sample, key: value}
            with self.assertRaises(budget.DelegationBudgetError):
                compare_scenarios([changed])

    def test_pending_and_repeated_same_task_do_not_create_independent_evidence(self):
        pending = self.sample("sol-high", finalized=False)
        self.assertEqual([], compare_scenarios([pending]))
        samples = [self.sample(profile, shared_task="same-task") for profile in ("sol-high", "astra-medium") for _index in range(3)]
        pairs = compare_scenarios(samples)
        self.assertTrue(all(not row["eligible"] for row in pairs))
        pair = next(row for row in pairs if row["comparison_pair_id"] == "sol-high--astra-medium")
        self.assertEqual(1, pair["lower_independent_tasks"])

    def test_direct_comparison_rejects_foreign_project_even_without_ledger_loader(self):
        first = self.sample("sol-high")
        second = copy.deepcopy(self.sample("astra-medium"))
        second["project_id"] = "foreign-project"
        with self.assertRaises(budget.DelegationBudgetError):
            compare_scenarios([first, second])


if __name__ == "__main__":
    unittest.main()
