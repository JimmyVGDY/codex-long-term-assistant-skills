"""中文：隔离临时仓库中的信封、Evidence 与评分 CLI 集成；非真实宿主验收。

English: Envelope/Evidence/CLI integration in temporary repos, not live host acceptance.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
from cp_runtime.dispatch_context import build_root_binding, prepare_review_selection, verify_root_binding  # noqa: E402
from cp_runtime.dispatch_policy import CURRENT_POLICY_ID, PREVIOUS_POLICY_ID, DispatchPolicyError, policy_digest  # noqa: E402
from cp_runtime.delegation_budget import initialize_budget, read_budget  # noqa: E402
from cp_runtime.evidence import record_evidence  # noqa: E402
from cp_runtime.project import onboard_project  # noqa: E402


class DispatchContextTests(unittest.TestCase):
    def setUp(self):
        self.policy_id = getattr(self, "policy_id", CURRENT_POLICY_ID)
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True, capture_output=True)
        (self.repo / "README.md").write_text("Synthetic integration fixture\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.repo), "add", "README.md"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(self.repo), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                        "-c", "commit.gpgsign=false", "commit", "-qm", "Fixture"], check=True, capture_output=True)
        self.project = onboard_project(self.repo, "synthetic-project", "Synthetic", self.root / "context")
        self.envelope = self.root / "execution-state.json"
        self.envelope.write_text(json.dumps({
            "schema_version": 5, "task_id": "synthetic-task", "repo_path": str(self.repo),
            "routing": {"reviewer_policy": {"policy_id": self.policy_id, "policy_digest": policy_digest(self.policy_id)}},
            "project": {"binding_status": "BOUND", "project_id": self.project.project_id,
                        "profile_path": str(self.project.profile_path), "profile_sha256": self.project.profile_sha256,
                        "state_path": str(self.project.state_path)},
        }), encoding="utf-8")
        self.identity, self.binding = build_root_binding(self.envelope, "synthetic-session")
        self.ledger = self.root / "budget.jsonl"
        self.assignment = {"reviewer": "review-data", "agent_type": "cp_review_data_contract",
                           "boundary_id": "boundary-one", "phase": "post", "round": 1,
                           "packet_sha256": "b" * 64}

    def tearDown(self):
        self.temp.cleanup()

    def init(self):
        return initialize_budget(self.ledger, budget_id="budget-one", **self.identity,
                                 budget_class="STRICT", default_dispatch_profile="luna-low",
                                 policy_id=self.policy_id, root_binding=self.binding, review_extension=True)

    def evidence_request(self):
        path = self.root / "evidence.json"
        record_evidence(path, "evidence-one", self.project.profile_path, "synthetic-task", self.repo,
                        "review", "Synthetic concurrency fact", "valid", "synthetic-fixture",
                        "Synthetic fixture, not live host evidence", ["packet:" + "b" * 64])
        ref = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        return {"reviewer_budget": "balanced", "evidence_items": [{
            "dimension": "state", "level": "concurrent", "evidence_ref": ref,
            "correlation_ref": "sha256:" + "a" * 64,
        }], "evidence_paths": {ref: str(path)}}

    def issue(self, request):
        return prepare_review_selection(read_budget(self.ledger), request, self.assignment,
                                        envelope_path=self.envelope, cwd=str(self.repo), host_session_id="synthetic-session")

    def cli(self, *args, ok=True):
        result = subprocess.run([sys.executable, "-B", str(ROOT / "scripts" / "delegation-budget.py"), *args],
                                cwd=self.repo, env={**os.environ, "PYTHONUTF8": "1"}, text=True,
                                encoding="utf-8", errors="replace", capture_output=True, timeout=20)
        self.assertEqual(result.returncode == 0, ok, result.stdout + result.stderr)
        return result

    def test_live_profile_envelope_and_host_identity_are_independently_compared(self):
        self.init()
        verify_root_binding(self.binding, self.identity, envelope_path=self.envelope,
                            cwd=str(self.repo), host_session_id="synthetic-session")
        for identity, cwd, session in (({**self.identity, "task_id": "other-task"}, str(self.repo), "synthetic-session"),
                                       (self.identity, str(self.root), "synthetic-session"),
                                       (self.identity, str(self.repo), "another-session")):
            with self.assertRaises(DispatchPolicyError):
                verify_root_binding(self.binding, identity, envelope_path=self.envelope, cwd=cwd, host_session_id=session)
        with self.assertRaises(DispatchPolicyError):
            build_root_binding(self.envelope, "")

    def test_verified_evidence_drives_one_luna_first_selection(self):
        self.init()
        selected, assignment = self.issue(self.evidence_request())
        self.assertEqual(1, selected["base_units"])
        self.assertEqual(10, selected["earned_budget"])
        self.assertEqual("sol-low", selected["approved_profile"])
        self.assertEqual(["sol-low"], assignment["acceptable_profiles"])

    def test_stale_evidence_adds_zero_and_submitted_proofs_or_totals_reject(self):
        self.init()
        request = self.evidence_request()
        (self.repo / "README.md").write_text("Changed baseline\n", encoding="utf-8")
        selected, _ = self.issue(request)
        self.assertEqual("luna-medium", selected["approved_profile"])
        self.assertEqual(2, selected["earned_budget"])
        for key, value in (("earned_budget", 40), ("proofs", {}), ("approved_profile", "astra-high")):
            with self.assertRaises(DispatchPolicyError):
                self.issue({**request, key: value})

    def test_tampered_evidence_bytes_cannot_be_accepted_as_valid_provenance(self):
        self.init()
        request = self.evidence_request()
        path = Path(next(iter(request["evidence_paths"].values())))
        path.write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(DispatchPolicyError, "HASH_MISMATCH"):
            self.issue(request)

    def test_cli_new_default_is_v3_and_computes_profile_instead_of_trusting_override(self):
        self.cli("init", "--ledger", str(self.ledger), "--budget-id", "cli-budget",
                 "--task-id", self.identity["task_id"], "--project-id", self.identity["project_id"],
                 "--repo-fingerprint", self.identity["repo_fingerprint"], "--budget-class", "STRICT",
                 "--review-extension", "--root-envelope", str(self.envelope), "--host-session-id", "synthetic-session")
        self.assertEqual("3.0", read_budget(self.ledger)["schema_version"])
        request = self.root / "selection-input.json"
        request.write_text(json.dumps(self.evidence_request()), encoding="utf-8")
        assignment = self.root / "assignment.json"
        assignment.write_text(json.dumps(self.assignment), encoding="utf-8")
        args = ("decide", "--ledger", str(self.ledger), "--dispatch-key", "scored-attempt",
                "--decision", "DELEGATE", "--role", "reviewer", "--reason-code", "INDEPENDENT_EVIDENCE_GAIN",
                "--root-envelope", str(self.envelope), "--host-session-id", "synthetic-session",
                "--selection-input", str(request), "--review-assignment", str(assignment))
        before = self.ledger.read_bytes()
        self.cli(*args, "--approved-profile", "astra-high", ok=False)
        self.assertEqual(before, self.ledger.read_bytes())
        result = json.loads(self.cli(*args).stdout)
        self.assertEqual("sol-low", result["approved_profile"])
        self.assertEqual(10, result["selection_scorecard"]["earned_budget"])

    def test_explicit_previous_matrix_init_verifies_root_and_preserves_policy(self):
        document = json.loads(self.envelope.read_text(encoding="utf-8"))
        document["routing"]["reviewer_policy"] = {
            "policy_id": PREVIOUS_POLICY_ID, "policy_digest": policy_digest(PREVIOUS_POLICY_ID)}
        self.envelope.write_text(json.dumps(document), encoding="utf-8")
        args = ("init", "--ledger", str(self.ledger), "--budget-id", "previous-matrix",
                "--task-id", self.identity["task_id"], "--project-id", self.identity["project_id"],
                "--repo-fingerprint", self.identity["repo_fingerprint"], "--budget-class", "STRICT")
        self.cli(*args, "--policy-id", PREVIOUS_POLICY_ID, ok=False)  # 中文：无任务信封。 English: No envelope.
        self.cli(*args, "--policy-id", PREVIOUS_POLICY_ID, "--root-envelope", str(self.envelope),
                 "--host-session-id", "", ok=False)
        self.cli(*args, "--root-envelope", str(self.envelope), "--host-session-id", "synthetic-session", ok=False)
        self.assertFalse(self.ledger.exists())  # 中文：默认 v3 不能绑定 v2 信封。 English: Default v3 cannot bind a v2 envelope.
        self.cli(*args, "--policy-id", PREVIOUS_POLICY_ID, "--root-envelope", str(self.envelope),
                 "--host-session-id", "synthetic-session")
        state = read_budget(self.ledger)
        self.assertEqual("3.0", state["schema_version"])
        self.assertEqual(PREVIOUS_POLICY_ID, state["policy_id"])
        self.assertEqual(policy_digest(PREVIOUS_POLICY_ID), state["policy_digest"])
        selection, _assignment = self.issue(self.evidence_request())
        self.assertEqual("luna-evidence-v1", selection["formula_version"])

    def test_execution_envelope_pins_default_and_explicit_scored_policies(self):
        for selected in (CURRENT_POLICY_ID, PREVIOUS_POLICY_ID):
            directory = self.root / ("execution-" + selected)
            command = [sys.executable, "-B", str(ROOT / "skills/engineering-quality-delivery/scripts/execution_guard.py"),
                       "init", "--state-dir", str(directory), "--task-id", "synthetic-task",
                       "--repo-path", str(self.repo), "--project-profile", str(self.project.profile_path),
                       "--project-id", self.project.project_id]
            if selected == PREVIOUS_POLICY_ID:
                command += ["--reviewer-policy", selected]
            completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                                       env={**os.environ, "PYTHONUTF8": "1"}, timeout=20)
            self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
            document = json.loads((directory / "execution-state.json").read_text(encoding="utf-8"))
            self.assertEqual(selected, document["routing"]["reviewer_policy"]["policy_id"])
            self.assertEqual(policy_digest(selected), document["routing"]["reviewer_policy"]["policy_digest"])
            self.assertEqual("luna-first-evidence-score", document["routing"]["reviewer_policy"]["selection_mode"])


if __name__ == "__main__":
    unittest.main()
