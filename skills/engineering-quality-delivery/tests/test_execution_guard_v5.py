#!/usr/bin/env python3
"""Task Envelope V2, Approval and Finalization integration tests."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[3]
GUARD = Path(__file__).resolve().parents[1] / "scripts" / "execution_guard.py"
RUNTIME_CLI = PACKAGE_ROOT / "scripts" / "cp-runtime.py"


def run(command: list[str], cwd: Path | None = None, expected: int = 0) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command, cwd=str(cwd) if cwd else None, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env={**__import__("os").environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    if result.returncode != expected:
        raise AssertionError(
            f"unexpected rc={result.returncode}, expected={expected}\n"
            f"command={' '.join(command)}\nstdout={result.stdout}\nstderr={result.stderr}"
        )
    return result


def git(repo: Path, *args: str) -> None:
    run(["git", *args], cwd=repo)


class ExecutionGuardV5Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="execution-guard-v5-")
        root = Path(self.temp.name)
        self.repo = root / "repo"
        self.context = root / "context"
        self.state = root / "task-state"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.email", "test@example.invalid")
        git(self.repo, "config", "user.name", "V5 Test")
        (self.repo / "a.txt").write_text("v1\n", encoding="utf-8")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "initial")
        onboard = run([
            sys.executable, "-B", str(RUNTIME_CLI), "project-onboard",
            "--repo-path", str(self.repo), "--project-id", "PROJECT-01",
            "--context-dir", str(self.context),
        ])
        self.assertIn("PROJECT-01", onboard.stdout)
        self.profile = self.context / "project-profile.json"
        self.project_state = self.context / "project-state.json"
        run([
            sys.executable, "-B", str(GUARD), "init",
            "--state-dir", str(self.state), "--task-id", "TASK-01",
            "--profile", "STANDARD", "--repo-path", str(self.repo),
            "--project-profile", str(self.profile), "--project-state", str(self.project_state),
            "--project-id", "PROJECT-01", "--complexity", "L2",
            "--reviewer-budget", "balanced", "--model-profile", "terra-medium",
        ])

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_finalization_blocks_unsupported_external_claims(self) -> None:
        (self.repo / "a.txt").write_text("v2\n", encoding="utf-8")
        run([
            sys.executable, "-B", str(GUARD), "record-validation",
            "--state-dir", str(self.state), "--name", "targeted",
            "--status", "valid", "--command-or-packet", "unit-test",
        ])
        report = self.state / "final.json"
        blocked = run([
            sys.executable, "-B", str(GUARD), "finalize",
            "--state-dir", str(self.state), "--claim", "modified",
            "--claim", "validated", "--claim", "deployed",
            "--output-json", str(report), "--require-all",
        ], expected=2)
        value = json.loads(report.read_text(encoding="utf-8"))
        self.assertEqual("BLOCKED", value["result"])
        self.assertEqual(["deployed"], value["accepted_final_state"]["unsupported_claims"])
        self.assertIn("deployed", blocked.stdout)

    def test_commit_requires_bound_single_use_approval_and_head_readback(self) -> None:
        (self.repo / "a.txt").write_text("v2\n", encoding="utf-8")
        approval = self.context / "approval.json"
        run([
            sys.executable, "-B", str(RUNTIME_CLI), "approval-issue",
            "--output", str(approval), "--approval-id", "APR-01",
            "--profile", str(self.profile), "--task-id", "TASK-01",
            "--operation", "commit", "--environment", "local",
            "--repo-path", str(self.repo), "--ttl-minutes", "30",
        ])
        run([
            sys.executable, "-B", str(GUARD), "authorize-action",
            "--state-dir", str(self.state), "--action", "committed",
            "--approval", str(approval),
        ])
        # No commit yet: readback must fail because HEAD did not advance.
        run([
            sys.executable, "-B", str(GUARD), "record-action",
            "--state-dir", str(self.state), "--action", "committed",
            "--status", "success", "--evidence", "git rev-parse HEAD",
        ], expected=1)
        git(self.repo, "add", "a.txt")
        git(self.repo, "commit", "-qm", "change")
        run([
            sys.executable, "-B", str(GUARD), "record-action",
            "--state-dir", str(self.state), "--action", "committed",
            "--status", "success", "--evidence", "new HEAD read back",
        ])
        report = self.state / "commit-final.json"
        run([
            sys.executable, "-B", str(GUARD), "finalize",
            "--state-dir", str(self.state), "--claim", "committed",
            "--output-json", str(report), "--require-all",
        ])
        value = json.loads(report.read_text(encoding="utf-8"))
        self.assertEqual("PASS", value["result"])

    def test_profile_tamper_blocks_protected_action(self) -> None:
        raw = json.loads(self.profile.read_text(encoding="utf-8"))
        raw["project_name"] = "tampered"
        self.profile.write_text(json.dumps(raw), encoding="utf-8")
        approval = self.context / "approval.json"
        # No valid Approval can be issued from a tampered profile.
        run([
            sys.executable, "-B", str(RUNTIME_CLI), "approval-issue",
            "--output", str(approval), "--approval-id", "APR-02",
            "--profile", str(self.profile), "--task-id", "TASK-01",
            "--operation", "push", "--environment", "local",
            "--repo-path", str(self.repo),
        ], expected=1)


if __name__ == "__main__":
    unittest.main()
