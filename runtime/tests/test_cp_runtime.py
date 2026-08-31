#!/usr/bin/env python3
"""中文：V5.0 项目治理 Runtime 契约测试。

English: V5.0 project-governance runtime contract tests.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RUNTIME_ROOT = Path(__file__).resolve().parents[1]
if str(RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNTIME_ROOT))

from cp_runtime.approval import check_approval, consume_approval, issue_approval
from cp_runtime.common import RuntimeContractError
from cp_runtime.contracts import EvidenceFreshness
from cp_runtime.evidence import check_evidence, record_evidence
from cp_runtime.memory import create_knowledge_candidate, create_projection_candidate, promote_projection
from cp_runtime.project import load_profile, onboard_project, validate_binding


def run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, check=True, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    return result.stdout.strip()


class RuntimeContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="cp-runtime-v50-")
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.context = self.root / "context"
        self.repo.mkdir()
        run_git(self.repo, "init", "-q")
        run_git(self.repo, "config", "user.email", "test@example.invalid")
        run_git(self.repo, "config", "user.name", "V5 Test")
        (self.repo / "pyproject.toml").write_text("[project]\nname='demo'\nversion='0.1.0'\n", encoding="utf-8")
        (self.repo / "app.py").write_text("print('v1')\n", encoding="utf-8")
        run_git(self.repo, "add", ".")
        run_git(self.repo, "commit", "-qm", "initial")
        self.binding = onboard_project(
            self.repo, "PROJECT-DEMO", "Demo", self.context,
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_project_binding_and_integrity_fail_closed(self) -> None:
        validated = validate_binding(
            self.binding.profile_path, self.repo, "PROJECT-DEMO", self.binding.state_path,
        )
        self.assertEqual("PROJECT-DEMO", validated.project_id)
        profile = load_profile(self.binding.profile_path)
        self.assertIn("Python", profile["technology"]["languages"])
        raw = json.loads(self.binding.profile_path.read_text(encoding="utf-8"))
        raw["project_name"] = "tampered"
        self.binding.profile_path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
        with self.assertRaises(RuntimeContractError):
            load_profile(self.binding.profile_path)

    def test_approval_baseline_expiry_and_single_use(self) -> None:
        approval = self.context / "approval.json"
        issue_approval(
            approval, "APR-001", self.binding.profile_path, "TASK-001",
            ["commit"], "local", self.repo, "2099-01-01T00:00:00+00:00",
        )
        current = check_approval(
            approval, "PROJECT-DEMO", "TASK-001", "commit", "local",
            self._snapshot_sha(),
        )
        self.assertTrue(current.valid)

        (self.repo / "app.py").write_text("print('changed')\n", encoding="utf-8")
        stale = check_approval(
            approval, "PROJECT-DEMO", "TASK-001", "commit", "local",
            self._snapshot_sha(),
        )
        self.assertFalse(stale.valid)
        self.assertIn("baseline-mismatch", stale.reasons)
        run_git(self.repo, "checkout", "--", "app.py")

        consume_approval(
            approval, "PROJECT-DEMO", "TASK-001", "commit", "local",
            self._snapshot_sha(),
        )
        consumed = check_approval(
            approval, "PROJECT-DEMO", "TASK-001", "commit", "local",
            self._snapshot_sha(),
        )
        self.assertFalse(consumed.valid)
        self.assertIn("approval-already-consumed", consumed.reasons)

    def test_evidence_becomes_stale_and_needs_repo_readback(self) -> None:
        evidence = self.context / "evidence.json"
        record_evidence(
            evidence, "EV-001", self.binding.profile_path, "TASK-001",
            self.repo, "validation", "unit", "valid", "python test.py",
            "targeted test passed",
        )
        current = check_evidence(evidence, self.repo, "PROJECT-DEMO", "TASK-001")
        self.assertTrue(current.valid)
        self.assertEqual(EvidenceFreshness.CURRENT, current.freshness)

        no_readback = check_evidence(evidence, None, "PROJECT-DEMO", "TASK-001")
        self.assertFalse(no_readback.valid)
        self.assertIn("repository-freshness-not-checked", no_readback.reasons)

        (self.repo / "app.py").write_text("print('v2')\n", encoding="utf-8")
        stale = check_evidence(evidence, self.repo, "PROJECT-DEMO", "TASK-001")
        self.assertFalse(stale.valid)
        self.assertEqual(EvidenceFreshness.STALE, stale.freshness)

    def test_memory_requires_reviewed_promotion(self) -> None:
        source = self.context / "CURRENT_TASK.md"
        source.write_text("# Current Task\nValidated fact.\n", encoding="utf-8")
        projection = self.context / "projection.json"
        create_projection_candidate(
            projection, self.binding.profile_path, "TASK-001", "PROJ-001",
            [source], ["API path is /v1/demo"], ["Keep backward compatibility"],
            ["Legacy clients remain"], ["Production owner unknown"], "Stable project facts",
        )
        memory_path = self.context / "project-memory.md"
        self.assertNotIn("PROJ-001", memory_path.read_text(encoding="utf-8"))
        knowledge = self.context / "knowledge.json"
        with self.assertRaises(RuntimeContractError):
            create_knowledge_candidate(
                knowledge, projection, self.binding.profile_path, "KN-001",
                "pattern", ["Python API projects"], ["Validate framework version"], "candidate",
            )

        promoted = promote_projection(projection, self.binding.profile_path, "human-reviewer")
        self.assertEqual("PROMOTED", promoted["status"])
        self.assertIn("PROJ-001", memory_path.read_text(encoding="utf-8"))
        candidate = create_knowledge_candidate(
            knowledge, projection, self.binding.profile_path, "KN-001",
            "pattern", ["Python API projects"], ["Validate framework version"], "candidate",
        )
        self.assertEqual("CANDIDATE", candidate["status"])
        self.assertFalse(candidate["activation"]["active"])

    def test_approval_rejects_invalid_operation_expiry_and_repo_output(self) -> None:
        with self.assertRaises(RuntimeContractError):
            issue_approval(
                self.context / "bad-operation.json", "APR-BAD-OP", self.binding.profile_path,
                "TASK-001", ["delete-everything"], "local", self.repo,
                "2099-01-01T00:00:00+00:00",
            )
        with self.assertRaises(RuntimeContractError):
            issue_approval(
                self.context / "expired.json", "APR-EXPIRED", self.binding.profile_path,
                "TASK-001", ["commit"], "local", self.repo,
                "2000-01-01T00:00:00+00:00",
            )
        with self.assertRaises(RuntimeContractError):
            issue_approval(
                self.repo / "approval.json", "APR-IN-REPO", self.binding.profile_path,
                "TASK-001", ["commit"], "local", self.repo,
                "2099-01-01T00:00:00+00:00",
            )

    def test_force_onboarding_preserves_project_memory(self) -> None:
        memory_path = self.context / "project-memory.md"
        before = memory_path.read_text(encoding="utf-8")
        memory_path.write_text(before.replace(
            "<!-- project-memory:end -->",
            "## Preserved\n\n- reviewed fact\n\n<!-- project-memory:end -->",
        ), encoding="utf-8")
        onboard_project(
            self.repo, "PROJECT-DEMO", "Demo", self.context, force=True,
        )
        after = memory_path.read_text(encoding="utf-8")
        self.assertIn("## Preserved", after)

    def _snapshot_sha(self) -> str:
        from cp_runtime.common import repo_snapshot
        return str(repo_snapshot(self.repo)["sha256"])


if __name__ == "__main__":
    unittest.main()
