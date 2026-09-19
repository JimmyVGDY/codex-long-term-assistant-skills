"""中文：合成评分对照与冻结 v1 重放，不使用宿主证据或模型调用。

English: Synthetic scoring oracle and frozen v1 replay; no host evidence or model calls."""
from __future__ import annotations

import hashlib
import itertools
import json
import random
import unittest

from test_dispatch_policy import CONTEXT, ROLE, ROOT, evidence, sha
from cp_runtime.dispatch_policy import (
    CURRENT_POLICY_ID, PREVIOUS_POLICY_ID, DispatchPolicyError, canonical_json,
    policy, policy_digest, score_review, validate_scorecard,
)


def score(atoms, proofs, **kwargs):
    return score_review(agent_type=ROLE, context=CONTEXT, evidence_items=atoms, proofs=proofs, **kwargs)


def exhaustive_oracle(atoms):
    """中文：独立遍历关联图并枚举五个维度的笛卡尔积。

    English: Independent graph traversal and Cartesian enumeration across five dimensions."""
    atoms = [json.loads(item) for item in sorted({canonical_json(atom) for atom in atoms})]
    remaining = set(range(len(atoms)))
    components = {}
    while remaining:
        seed = min(remaining)
        pending = [seed]
        remaining.remove(seed)
        while pending:
            index = pending.pop()
            components[index] = seed
            linked = {other for other in remaining if any(
                atoms[index][key] == atoms[other][key] for key in ("evidence_ref", "correlation_ref"))}
            remaining -= linked
            pending.extend(linked)
    config = policy()["scoring"]
    priority = config["dimension_priority"]

    def atom_key(index):
        atom = atoms[index]
        return (-config["dimensions"][atom["dimension"]][atom["level"]], priority.index(atom["dimension"]),
                atom["level"], atom["evidence_ref"], atom["correlation_ref"])

    choices = [[None] + [index for index, atom in enumerate(atoms) if atom["dimension"] == dimension]
               for dimension in priority]
    best = (0, ())
    best_indices = ()
    for choice in itertools.product(*choices):
        selected = tuple(sorted((index for index in choice if index is not None), key=atom_key))
        if len({components[index] for index in selected}) != len(selected):
            continue
        candidate = (sum(atom_key(index)[0] for index in selected), tuple(atom_key(index) for index in selected))
        if candidate < best:
            best, best_indices = candidate, selected
    return -best[0], sorted((atoms[index] for index in best_indices), key=canonical_json)


class ScoringMonotonicityTests(unittest.TestCase):
    def test_added_alternative_preserves_existing_feasible_seventeen(self):
        atoms, proofs = evidence(("semantic", "multi_domain"), ("state", "concurrent"), ("state", "concurrent"))
        atoms[2]["correlation_ref"] = atoms[0]["correlation_ref"]
        before = score(atoms[:2], {atom["evidence_ref"]: proofs[atom["evidence_ref"]] for atom in atoms[:2]})
        after = score(atoms, proofs)
        self.assertEqual((17, 17), (before["earned_budget"], after["earned_budget"]))
        self.assertEqual("sol-medium", after["approved_profile"])
        self.assertEqual(9, score(atoms, proofs, policy_id=PREVIOUS_POLICY_ID)["earned_budget"])

    def test_lower_local_choice_wins_globally_and_satisfies_quality_requirement(self):
        atoms, proofs = evidence(("semantic", "multi_domain"), ("impact", "high"), ("semantic", "multi_domain"))
        atoms[1]["correlation_ref"] = atoms[0]["correlation_ref"]
        selected = score(atoms, proofs, requirements=["sol-low"])
        self.assertEqual(13, selected["earned_budget"])
        self.assertEqual({"semantic", "impact"}, {item["dimension"] for item in selected["awards"]})
        with self.assertRaisesRegex(DispatchPolicyError, "SCORE_BELOW_QUALITY_REQUIREMENT"):
            score(atoms, proofs, requirements=["sol-low"], policy_id=PREVIOUS_POLICY_ID)

    def test_bounded_generated_inputs_match_exhaustive_oracle_and_canonical_output(self):
        rng = random.Random(781231)
        config = policy()["scoring"]
        levels = [(dimension, level) for dimension, values in config["dimensions"].items() for level in values]
        for number in range(240):
            count = number % 25  # 中文：包含零项及 24 项上限。 English: Includes zero and the exact 24-atom limit.
            atoms, proofs = evidence(*(rng.choice(levels) for _ in range(count)))
            for index, atom in enumerate(atoms):
                atom["correlation_ref"] = sha("group-" + str(rng.randrange(max(1, count // 2))))
                if index and rng.random() < 0.25:
                    atom["evidence_ref"] = atoms[rng.randrange(index)]["evidence_ref"]
            proofs = {atom["evidence_ref"]: {**proofs[atom["evidence_ref"]],
                      "prior_result_ref": sha("prior-result"), "prior_attempt_ref": sha("prior-attempt")}
                      for atom in atoms}
            with self.subTest(number=number, count=count):
                expected_total, expected_atoms = exhaustive_oracle(atoms)
                result = score(atoms, proofs)
                self.assertEqual(expected_total, sum(item["points"] for item in result["awards"]))
                self.assertEqual(expected_atoms, [{key: value for key, value in item.items() if key != "points"}
                                                 for item in result["awards"]])
                self.assertEqual(min(40, 1 + expected_total), result["earned_budget"])
                self.assertEqual(len({canonical_json(item) for item in atoms}),
                                 len(result["awards"]) + len(result["exclusions"]))
                rng.shuffle(atoms)
                self.assertEqual(canonical_json(result), canonical_json(score(atoms, dict(reversed(list(proofs.items()))))))
                if atoms and count < 24:
                    self.assertEqual(result, score(atoms + [atoms[0]], proofs))
                self.assertEqual(result, validate_scorecard(result))

    def test_nonmerging_additions_cannot_reduce_optimum(self):
        rng = random.Random(8831)
        levels = [(dimension, level) for dimension, values in policy()["scoring"]["dimensions"].items() for level in values]
        for run in range(30):
            atoms, proofs = evidence(*(rng.choice(levels) for _ in range(24)))
            previous = 1
            for index, atom in enumerate(atoms):
                # 中文：新证据最多关联一个现有根因。 English: New evidence identity, attaching to at most one existing root.
                atom["correlation_ref"] = sha("root-" + str(rng.randrange(index + 1)))
                prefix = atoms[:index + 1]
                value = score(prefix, {item["evidence_ref"]: proofs[item["evidence_ref"]] for item in prefix})
                with self.subTest(run=run, prefix=index + 1):
                    self.assertGreaterEqual(value["earned_budget"], previous)
                previous = value["earned_budget"]

    def test_valid_group_merge_can_reduce_score_but_stale_bridge_cannot(self):
        atoms, proofs = evidence(("semantic", "multi_domain"), ("state", "concurrent"), ("impact", "high"))
        bridge = atoms.pop()
        bridges = [{**bridge, "correlation_ref": atom["correlation_ref"]} for atom in atoms]
        self.assertEqual(9, score(atoms + bridges, proofs)["earned_budget"])
        proofs[bridge["evidence_ref"]]["status"] = "stale"
        self.assertEqual(17, score(atoms + bridges, proofs)["earned_budget"])

    def test_cap_is_applied_after_raw_optimum_and_input_limit_before_deduplication(self):
        atoms, proofs = evidence(("semantic", "multi_domain"), ("state", "concurrent"),
                                 ("impact", "critical_irreversible"), ("conflict", "confirmed"),
                                 ("prior_inconclusive", "confirmed"))
        result = score(atoms, proofs, reviewer_budget="deep")
        self.assertEqual(42, sum(item["points"] for item in result["awards"]))
        self.assertEqual(40, result["earned_budget"])
        with self.assertRaisesRegex(DispatchPolicyError, "SCORE_EVIDENCE_LIMIT"):
            score(atoms * 5, proofs)

    def test_frozen_scorecards_and_resource_bytes_are_unchanged(self):
        cases = json.loads((ROOT / "tests/fixtures/scoring-v1-scorecards.json").read_text(encoding="utf-8"))
        for case in cases:
            with self.subTest(case=case["name"]):
                self.assertEqual(case["scorecard"], validate_scorecard(case["scorecard"]))
        old = (ROOT / "runtime/cp_runtime/data/dispatch-policy-v2.json").read_bytes()
        self.assertEqual("8ceb5ade807e40fd926290652c9a3d6170930e4830363feca01e6ba0755289a1", hashlib.sha256(old).hexdigest())
        self.assertEqual("sha256:bbb7c1fc54f38bd02b07ff9bb00ce73437f180f36a7464b8f9a9dc8f4dbeca62", policy_digest(PREVIOUS_POLICY_ID))
        self.assertNotEqual(policy_digest(PREVIOUS_POLICY_ID), policy_digest(CURRENT_POLICY_ID))
        old_contract, new_contract = policy(PREVIOUS_POLICY_ID), policy()
        new_contract["policy_id"] = old_contract["policy_id"]
        new_contract["scoring"]["formula_version"] = old_contract["scoring"]["formula_version"]
        self.assertEqual(old_contract, new_contract)

    def test_all_tied_permutations_have_same_awards_and_exclusions(self):
        atoms, proofs = evidence(("semantic", "multi_domain"), ("state", "concurrent"),
                                 ("semantic", "multi_domain"), ("state", "concurrent"))
        atoms[1]["correlation_ref"] = atoms[0]["correlation_ref"]
        atoms[3]["correlation_ref"] = atoms[2]["correlation_ref"]
        encodings = {canonical_json(score(order, proofs)) for order in itertools.permutations(atoms)}
        self.assertEqual(1, len(encodings))
        self.assertEqual(17, score(atoms, proofs)["earned_budget"])


if __name__ == "__main__":
    unittest.main()
