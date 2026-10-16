"""中文：反馈绑定、验收桥接与失败证据保留的回归验证。
English: Regression checks for feedback binding, verifier adapters, and preservation of failed evidence.
"""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location("skill_review_tests", ROOT / "scripts/skill_eval_review.py")
REVIEW = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REVIEW)
EVAL = REVIEW.module("eval")


def environment():
    return {"platform": "windows", "runtime": "python-3.11", "requested_model": "fixed-request",
            "requested_effort": "medium", "permissions_digest": "e" * 64, "cache_condition": "cold"}


def inputs(variant):
    return {
        "schema": "skill-eval-input/1", "study_id": "feedback", "case_id": "output",
        "sample_id": "one", "variant": variant, "fixture_digest": "a" * 64,
        "rule_digest": EVAL.digest(EVAL.canonical({})), "rule_files": {}, "source_sha": "b" * 40,
        "environment": environment(), "initial_files": {}, "allowed_changes": ["result.txt"],
        "artifacts": ["result.txt"],
        "checks": [{"id": "answer", "kind": "contains", "path": "result.txt", "expected": "42"}],
        "metrics": {},
    }


class EvaluationReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def comparison(self):
        rows = {}
        for variant in ("baseline", "candidate"):
            output = self.root / variant
            output.mkdir()
            (output / "result.txt").write_text("42", encoding="utf-8")
            rows[variant] = EVAL.capture(inputs(variant), output)
        return EVAL.compare(rows["baseline"], rows["candidate"])

    def feedback(self, comparison):
        value = REVIEW.feedback_template(comparison)
        value.update(reviewer_id="maintainer", verdict="tie",
                     notes="Both outputs contain the requested answer; general quality is not established.")
        criterion = value["criteria"][0]
        criterion.update(baseline="PASS", candidate="PASS", reason="Compared both actual output files.")
        criterion["evidence"] = [
            {"variant": side, "path": "result.txt",
             "sha256": comparison[side]["files"]["result.txt"]["sha256"]}
            for side in ("baseline", "candidate")
        ]
        return value

    def test_feedback_is_bound_and_does_not_grant_authority_or_prove_benefit(self):
        comparison = self.comparison()
        record = REVIEW.record_feedback(comparison, self.feedback(comparison))
        self.assertEqual("NONE", record["execution_authorization"])
        self.assertEqual("UNKNOWN", record["benefit"])
        self.assertEqual("NOT_PROVIDED", record["identity_attestation"])
        self.assertEqual(record, REVIEW.verify_feedback(comparison, record))

    def test_unfilled_template_is_not_accepted_as_review(self):
        comparison = self.comparison()
        with self.assertRaises(ValueError):
            REVIEW.record_feedback(comparison, REVIEW.feedback_template(comparison))

    def test_wrong_digest_missing_evidence_and_foreign_artifact_are_rejected(self):
        comparison = self.comparison()
        for mutation in ("digest", "missing", "foreign", "empty-review"):
            value = self.feedback(comparison)
            if mutation == "digest":
                value["comparison_digest"] = "0" * 64
            elif mutation == "missing":
                value["criteria"][0]["evidence"] = []
            elif mutation == "foreign":
                value["criteria"][0]["evidence"][0]["path"] = "../foreign"
            else:
                value["criteria"][0].update(baseline="UNKNOWN", candidate="UNKNOWN", evidence=[])
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                REVIEW.record_feedback(comparison, value)

    def test_feedback_no_longer_verifies_after_artifact_mutation(self):
        comparison = self.comparison()
        record = REVIEW.record_feedback(comparison, self.feedback(comparison))
        (self.root / "candidate/result.txt").write_text("wrong", encoding="utf-8")
        with self.assertRaises(ValueError):
            REVIEW.verify_feedback(comparison, record)

    def test_evaluator_can_record_non_discriminating_checks(self):
        comparison = self.comparison()
        value = self.feedback(comparison)
        value["evaluation_gaps"] = [{
            "check_id": "answer", "issue": "Substring presence does not verify the whole answer.",
            "evidence": "An output saying 42 is wrong would satisfy the current predicate.",
        }]
        record = REVIEW.record_feedback(comparison, value)
        self.assertEqual(value["evaluation_gaps"], record["feedback"]["evaluation_gaps"])

    def test_rendered_review_is_escaped(self):
        comparison = self.comparison()
        value = self.feedback(comparison)
        value["notes"] = "<script>not executable</script>"
        page = EVAL.render(comparison, REVIEW.record_feedback(comparison, value))
        self.assertIn("&lt;script&gt;not executable", page)
        self.assertNotIn("<script>", page)
        self.assertIn("reviewer identity is not attested", page)

    def test_existing_hidden_oracle_and_failed_result_are_preserved(self):
        target = self.root / "reuse"
        REVIEW.prepare_reuse("local-fix", target, "HEAD", environment(), ["pagination.py"], candidate="HEAD")
        original = REVIEW.verify_reuse(target / "baseline")
        self.assertFalse(original["oracle"]["behavior_passed"])
        source = target / "candidate/workspace/pagination.py"
        source.write_text(source.read_text(encoding="utf-8").replace("max(1,", "max(0,"), encoding="utf-8")
        repaired = REVIEW.verify_reuse(target / "candidate")
        self.assertTrue(repaired["oracle"]["behavior_passed"])
        rows = {
            side: EVAL.capture(EVAL.read_json(target / side / "input.json"), target / side / "workspace")
            for side in ("baseline", "candidate")
        }
        compared = EVAL.compare(rows["baseline"], rows["candidate"])
        self.assertEqual("FAILED", compared["baseline"]["outcome"])
        self.assertEqual("PASS", compared["candidate"]["outcome"])
        with self.assertRaisesRegex(ValueError, "REUSE_ALREADY_VERIFIED"):
            REVIEW.verify_reuse(target / "baseline")
        self.assertEqual(original, EVAL.read_json(target / "baseline/oracle-receipt.json"))

    def test_modified_old_tests_block_execution_before_oracle_is_created(self):
        target = self.root / "reuse"
        REVIEW.prepare_reuse("local-fix", target, "HEAD", environment(), ["pagination.py"], candidate="HEAD")
        (target / "candidate/workspace/test_old.py").write_text("", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "PROTECTED_INPUT_CHANGED"):
            REVIEW.verify_reuse(target / "candidate")
        self.assertFalse((target / "candidate/workspace/oracle.json").exists())

    def test_fake_old_test_digest_cannot_redefine_the_catalog(self):
        target = self.root / "reuse"
        REVIEW.prepare_reuse("local-fix", target, "HEAD", environment(), ["pagination.py"], candidate="HEAD")
        run = target / "candidate"
        (run / "workspace/test_old.py").write_text("", encoding="utf-8")
        current = EVAL.read_json(run / "input.json")
        legacy = EVAL.read_json(run / "input-manifest.json")
        for value in (current, legacy):
            value["initial_files"]["test_old.py"] = EVAL.digest(b"")
        (run / "input.json").write_bytes(EVAL.canonical(current))
        (run / "input-manifest.json").write_bytes(EVAL.canonical(legacy))
        with self.assertRaisesRegex(ValueError, "CATALOG_INPUT_CHANGED"):
            REVIEW.verify_reuse(run)

    def test_protected_test_cannot_be_declared_mutable(self):
        with self.assertRaisesRegex(ValueError, "REUSE_PROTECTED_INPUT"):
            REVIEW.prepare_reuse("local-fix", self.root / "bad", "HEAD", environment(),
                                 ["test_old.py"], candidate="HEAD")
        self.assertFalse((self.root / "bad").exists())


if __name__ == "__main__":
    unittest.main()
