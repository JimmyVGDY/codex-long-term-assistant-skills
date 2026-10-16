"""中文：独立样例准备、规则保护及原生 Git 快照的契约回归。
English: Contract regressions for independent fixture preparation, rule protection, and native Git snapshots.
"""
import copy
import importlib.util
import json
import subprocess
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("skill_fixture", ROOT / "scripts/skill_eval_fixture.py")
FIXTURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FIXTURE)
EVAL = FIXTURE.EVAL


def suite():
    return {
        "schema": "skill-eval-suite/1", "suite_id": "fixture-contract",
        "data_classification": "public-synthetic",
        "cases": [{
            "id": "answer", "task": "Create result.json containing the answer from facts.json.",
            "skills": ["backend-engineering"], "files": {"facts.json": '{"answer":42}\n'},
            "allowed_changes": ["result.json"], "artifacts": ["result.json"],
            "checks": [{"id": "answer", "kind": "json_equal", "path": "result.json",
                        "expected": {"answer": 42}}],
        }],
    }


def environment():
    return {"platform": "windows", "runtime": "python-3.11", "requested_model": "fixed-request",
            "requested_effort": "medium", "permissions_digest": "e" * 64, "cache_condition": "cold"}


class FixturePreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_real_git_snapshot_independent_runs_and_protected_rules(self):
        target = self.root / "study"
        result = FIXTURE.prepare(suite(), "answer", target, "HEAD", environment(), candidate="HEAD")
        self.assertEqual("NOT_STARTED", result["model_execution"])
        records = {}
        for variant, answer in (("baseline", 0), ("candidate", 42)):
            run = target / variant
            workspace = run / "workspace"
            self.assertTrue((workspace / ".agents/skills/backend-engineering/SKILL.md").is_file())
            self.assertFalse((workspace / "input.json").exists())
            self.assertFalse((workspace / "prompt.txt").exists())
            (workspace / "result.json").write_text(json.dumps({"answer": answer}), encoding="utf-8")
            records[variant] = EVAL.capture(EVAL.read_json(run / "input.json"), workspace)
        comparison = EVAL.compare(records["baseline"], records["candidate"])
        self.assertEqual("FAILED", comparison["baseline"]["outcome"])
        self.assertEqual("PASS", comparison["candidate"]["outcome"])
        self.assertEqual("UNKNOWN", comparison["benefit"])
        protected = target / "candidate/workspace/.agents/skills/backend-engineering/SKILL.md"
        protected.write_text("changed", encoding="utf-8")
        changed = EVAL.capture(EVAL.read_json(target / "candidate/input.json"),
                               target / "candidate/workspace")
        self.assertEqual("FAILED", changed["outcome"])
        self.assertIn(".agents/skills/backend-engineering/SKILL.md", changed["forbidden_changes"])

    def test_existing_output_is_not_overwritten(self):
        target = self.root / "existing"
        target.mkdir()
        marker = target / "keep"
        marker.write_text("original", encoding="utf-8")
        with self.assertRaisesRegex(EVAL.EvalError, "OUTPUT_ALREADY_EXISTS"):
            FIXTURE.prepare(suite(), "answer", target, "HEAD", environment())
        self.assertEqual("original", marker.read_text(encoding="utf-8"))

    def test_historical_rules_are_read_from_a_deep_checkout(self):
        repo = self.root / ("deep-" + "x" * max(20, 155 - len(str(self.root)) - 6))
        relative = "skills/engineering-quality-delivery/assets/templates/TASK_EXECUTION_ENVELOPE.template.yaml"
        paths = {"global/AGENTS.md": "# Synthetic rules\n",
                 "skills/engineering-quality-delivery/SKILL.md": "# Synthetic skill\n",
                 relative: "fixture: public\n"}
        for name, content in paths.items():
            target = repo / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8", newline="\n")
        for args in (("init", "-q"), ("config", "core.longpaths", "false"),
                     ("add", "."), ("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                                    "commit", "-qm", "Public fixture")):
            subprocess.run(["git", "-C", str(repo), "-c", "core.autocrlf=false", *args],
                           check=True, capture_output=True, timeout=10)
        with mock.patch.object(FIXTURE, "ROOT", repo):
            commit = FIXTURE.resolve_commit("HEAD")
            self.assertGreater(len(str(repo)) + len(commit) + len(relative) + 2, 260)
            result = FIXTURE.rules_snapshot(["engineering-quality-delivery"], commit)
        self.assertEqual(result[".agents/" + relative], b"fixture: public\n")

    def test_invalid_suite_cannot_write_output(self):
        for mutation in ("classification", "case", "path", "skill", "rules"):
            value = suite()
            if mutation == "classification":
                value["data_classification"] = "business-conversation"
            elif mutation == "case":
                value["cases"].append(copy.deepcopy(value["cases"][0]))
            elif mutation == "path":
                value["cases"][0]["files"]["../escape"] = "bad"
            elif mutation == "skill":
                value["cases"][0]["skills"] = ["not-installed"]
            else:
                value["cases"][0]["allowed_changes"].append("AGENTS.md")
            target = self.root / mutation
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                FIXTURE.prepare(value, "answer", target, "HEAD", environment())
            self.assertFalse(target.exists())

    def test_rule_digest_and_override_contracts_are_validated(self):
        target = self.root / "study"
        FIXTURE.prepare(suite(), "answer", target, "HEAD", environment(), candidate="HEAD")
        value = EVAL.read_json(target / "baseline/input.json")
        value["rule_digest"] = "0" * 64
        with self.assertRaisesRegex(EVAL.EvalError, "RULE_DIGEST"):
            EVAL.validate_input(value)
        value = EVAL.read_json(target / "baseline/input.json")
        value["allowed_changes"].append("AGENTS.md")
        with self.assertRaisesRegex(EVAL.EvalError, "RULE_MUTATION"):
            EVAL.validate_input(value)

    def test_incomplete_fixture_cannot_be_reported_as_success(self):
        target = self.root / "study"
        FIXTURE.prepare(suite(), "answer", target, "HEAD", environment(), candidate="HEAD")
        record = EVAL.capture(EVAL.read_json(target / "baseline/input.json"), target / "baseline/workspace")
        self.assertEqual("FAILED", record["outcome"])
        self.assertTrue(any(row["reason"] == "ARTIFACT_MISSING" for row in record["checks"]))


if __name__ == "__main__":
    unittest.main()
