"""中文：V8/V5 复审流程与预算唯一归属集成，使用明确的合成生命周期。

English: V8/V5 workflow integration with explicitly synthetic lifecycle fixtures.
"""
from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

import test_dispatch_context as fixtures

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
from cp_runtime.delegation_budget import (bind_review_attempt, read_budget, record_decision, reserve_budget,
                                         record_host_dispatch_receipt, record_host_agent_observation,
                                         native_review_nonce, sha256_ref)  # noqa: E402
from cp_runtime.review_contract import validate_result  # noqa: E402
from cp_runtime.dispatch_policy import DispatchPolicyError  # noqa: E402
from cp_runtime.common import atomic_write_json  # noqa: E402


class MatrixReviewControllerTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.DispatchContextTests(methodName="runTest")
        self.fixture.setUp()
        self.fixture.init()
        self.review = self.fixture.root / "review"
        self.env = {**os.environ, "PYTHONUTF8": "1", "CODEX_THREAD_ID": "synthetic-session",
                    "CP_DELEGATION_ENVELOPE_PATH": str(self.fixture.envelope)}
        self.tool("init", "--boundary-id", "boundary-one", "--task-id", "synthetic-task",
                  "--repo-path", str(self.fixture.repo), "--delegation-ledger", str(self.fixture.ledger))
        self.tool("isolation", "--review-mode", "independent-agent", "--parent-sandbox", "workspace-write")

    def tearDown(self):
        self.fixture.tearDown()

    def tool(self, *args, ok=True, review=None):
        result = subprocess.run([sys.executable, "-B", str(ROOT / "skills" / "multi-agent-independent-review" / "scripts" / "review_controller.py"),
                                 *args, "--review-dir", str(review or self.review)], cwd=self.fixture.repo, env=self.env,
                                text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=30)
        self.assertEqual(result.returncode == 0, ok, result.stdout + result.stderr)
        return result

    def state(self):
        return json.loads((self.review / "review-state.json").read_text(encoding="utf-8"))

    def prepare(self):
        self.tool("route", "--phase", "post", "--decision", "DELEGATE", "--reason-code", "INDEPENDENT_EVIDENCE_GAIN", "--reason", "Synthetic fixture")
        self.tool("plan", "--phase", "post", "--depth", "1", "--reviewers", "review-data", "--purpose", "Synthetic fixture",
                  "--packet-sha256", "b" * 64, "--effort-tier", "deep")
        selection, assignment = self.fixture.issue(self.fixture.evidence_request())
        record_decision(self.fixture.ledger, dispatch_key="review-attempt", decision="DELEGATE", role="reviewer",
                        approved_profile=selection["approved_profile"], reason_code="INDEPENDENT_EVIDENCE_GAIN",
                        selection_scorecard=selection, review_assignment=assignment)
        return selection, assignment

    def dispatch(self):
        return self.tool("dispatch", "--phase", "post", "--round", "1", "--reviewer", "review-data", "--scope", "README.md",
                         "--delegation-dispatch-key", "review-attempt")

    def start(self):
        item = reserve_budget(self.fixture.ledger, dispatch_key="review-attempt", host_dispatch_id="synthetic-host-call",
                              approved_profile="sol-low", approval_basis="explicit-request", role="reviewer")
        record_host_dispatch_receipt(self.fixture.ledger, dispatch_key="review-attempt", host_dispatch_id="synthetic-host-call", agent_id="synthetic-child")
        record_host_agent_observation(self.fixture.ledger, agent_id="synthetic-child", phase="start")
        return item["reservation_id"]

    def result_file(self):
        path = self.fixture.root / "result.json"
        self.tool("result-template", "--phase", "post", "--round", "1", "--reviewer", "review-data", "--output", str(path))
        result = json.loads(path.read_text(encoding="utf-8"))
        result.update(status="pass", isolation_level="logical-readonly", checked_scope=["README.md"], summary="Synthetic review result")
        path.write_text(json.dumps(result), encoding="utf-8")
        return path, result

    def test_scored_dispatch_result_and_close_have_one_consistent_owner(self):
        self.prepare()
        requested = json.loads(self.dispatch().stdout.splitlines()[-1])
        self.assertEqual({"model":"gpt-5.6-sol","reasoning_effort":"low","agent_type":"cp_review_data_contract", "fork_context":False},
                         requested["native_request_parameters"])
        self.assertEqual("review-attempt",requested["request_parameters"]["task_name"])
        nonce = native_review_nonce(requested["native_message_prefix"])
        self.assertEqual(64, len(nonce))
        self.assertNotIn(nonce, self.fixture.ledger.read_text(encoding="utf-8"))
        self.assertNotIn(nonce, (self.review / "review-state.json").read_text(encoding="utf-8"))
        claim = read_budget(self.fixture.ledger)["review_claims"][sha256_ref("review-attempt")]
        self.assertEqual(sha256_ref(nonce), claim["native_dispatch_ref"])
        state = self.state()
        self.assertEqual(8, state["schema_version"])
        self.assertEqual(0, read_budget(self.fixture.ledger)["usage"]["units"])
        reservation = self.start()
        path, result = self.result_file()
        self.assertEqual(5, result["schema_version"])
        self.assertEqual("sol-low", result["dispatch_assignment"]["approved_profile"])
        self.assertNotIn("minimum_acceptable_profile", result["dispatch_assignment"])
        self.tool("result", "--phase", "post", "--round", "1", "--reviewer", "review-data", "--status", "pass",
                  "--summary", "Synthetic pass", "--result-file", str(path), "--delegation-reservation-id", reservation)
        self.tool("merge", "--phase", "post", "--round", "1", "--summary", "No findings")
        self.tool("close", "--conclusion", "逻辑只读复审完成，无阻塞项", ok=False)
        record_host_agent_observation(self.fixture.ledger, agent_id="synthetic-child", phase="stop", outcome="PASS")
        self.tool("close", "--conclusion", "逻辑只读复审完成，无阻塞项")
        self.assertEqual("closed", self.state()["status"])
        self.assertEqual(10, read_budget(self.fixture.ledger)["usage"]["units"])
        self.tool("validate")

    def test_inline_has_no_dispatch_and_no_review_budget_charge(self):
        self.tool("route", "--phase", "post", "--decision", "INLINE", "--reason-code", "INLINE_SUFFICIENT", "--reason", "Synthetic self-check sufficient")
        self.tool("plan", "--phase", "post", "--depth", "1", "--reviewers", "review-data", "--purpose", "Invalid",
                  "--packet-sha256", "b" * 64, ok=False)
        self.assertEqual(0, self.state()["counters"]["total_reviewers"])
        self.assertEqual(0, read_budget(self.fixture.ledger)["usage"]["units"])

    def test_explicit_high_override_and_linear_minimum_are_rejected(self):
        self.prepare()
        base = ("dispatch", "--phase", "post", "--round", "1", "--reviewer", "review-data", "--scope", "README.md", "--delegation-dispatch-key", "review-attempt")
        self.tool(*base, "--model-profile", "astra-high", ok=False)
        self.tool(*base, "--minimum-acceptable-profile", "terra-medium", ok=False)
        self.assertFalse(read_budget(self.fixture.ledger)["review_claims"])
        self.assertEqual(0, self.state()["counters"]["total_reviewers"])

    def test_interrupted_state_write_recovers_authoritative_claim_without_charge(self):
        _score, assignment = self.prepare()
        state = self.state()
        bind_review_attempt(self.fixture.ledger, dispatch_key="review-attempt", review_state_ref=state["review_state_ref"], assignment=assignment)
        self.assertEqual(0, state["counters"]["total_reviewers"])
        self.tool("reconcile")
        self.assertEqual(1, self.state()["counters"]["total_reviewers"])
        self.assertEqual(0, read_budget(self.fixture.ledger)["usage"]["units"])
        self.tool("reconcile")
        self.assertEqual(1, self.state()["counters"]["total_reviewers"])

    def test_result_cannot_change_owner_selection_cost_or_add_identity_fields(self):
        self.prepare()
        self.dispatch()
        _path, result = self.result_file()
        expected = copy.deepcopy(result["dispatch_assignment"])
        for key, value in (("approved_profile", "astra-low"), ("selection_ref", "sha256:" + "0" * 64),
                           ("review_state_ref", "sha256:" + "d" * 64), ("earned_budget", 40)):
            changed = copy.deepcopy(result)
            changed["dispatch_assignment"][key] = value
            with self.assertRaises(DispatchPolicyError):
                validate_result(changed, expected_assignment=expected)
        changed = {**result, "actual_model": "not-accepted"}
        with self.assertRaises(DispatchPolicyError):
            validate_result(changed)

    def test_success_cannot_be_closed_without_real_review_results(self):
        self.tool("close", "--conclusion", "通过，无阻塞项", ok=False)
        self.prepare()
        self.tool("close", "--conclusion", "通过，无阻塞项", ok=False)

    def test_current_packet_generates_bound_v5_and_rejects_legacy_or_stale_input(self):
        packet = self.fixture.root / "packet"
        script = ROOT / "skills/multi-agent-independent-review/scripts/review_packet.py"

        def packet_tool(*args, ok=True):
            result = subprocess.run([sys.executable, "-B", str(script), *args], cwd=self.fixture.repo,
                                    env=self.env, text=True, encoding="utf-8", capture_output=True, timeout=30)
            self.assertEqual(ok, result.returncode == 0, result.stdout + result.stderr)
            return result

        packet_tool("create", "--repo-path", str(self.fixture.repo), "--output-dir", str(packet),
                    "--boundary-id", "boundary-one", "--phase", "post")
        packet_hash = (packet / "PACKET_SHA256").read_text().strip()
        self.fixture.assignment["packet_sha256"] = packet_hash
        self.tool("route", "--phase", "post", "--decision", "DELEGATE", "--reason-code", "INDEPENDENT_EVIDENCE_GAIN", "--reason", "Synthetic fixture")
        self.tool("plan", "--phase", "post", "--depth", "1", "--reviewers", "review-data", "--purpose", "Synthetic fixture",
                  "--packet-sha256", packet_hash, "--effort-tier", "economy")
        selection, assignment = self.fixture.issue({"reviewer_budget": "economy"})
        self.assertEqual("luna-low", selection["approved_profile"])
        record_decision(self.fixture.ledger, dispatch_key="review-attempt", decision="DELEGATE", role="reviewer",
                        approved_profile=selection["approved_profile"], reason_code="INDEPENDENT_EVIDENCE_GAIN",
                        selection_scorecard=selection, review_assignment=assignment)
        self.dispatch()
        path = self.fixture.root / "packet-result.json"
        template_args = ("result-template", "--packet-dir", str(packet), "--reviewer", "review-data", "--output", str(path))
        packet_tool(*template_args, ok=False)
        packet_tool(*template_args, "--review-dir", str(self.review))
        result = json.loads(path.read_text(encoding="utf-8"))
        result.update(status="pass", isolation_level="logical-readonly", checked_scope=["README.md"], summary="Synthetic result")
        path.write_text(json.dumps(result), encoding="utf-8")
        validate_args = ("validate-result", "--packet-dir", str(packet), "--result-file", str(path))
        packet_tool(*validate_args, ok=False)
        packet_tool(*validate_args, "--review-dir", str(self.review))
        packet_tool("freshness", "--packet-dir", str(packet), "--repo-path", str(self.fixture.repo))
        (self.fixture.repo / "README.md").write_text("Changed after packet", encoding="utf-8")
        packet_tool("freshness", "--packet-dir", str(packet), "--repo-path", str(self.fixture.repo), ok=False)


if __name__ == "__main__":
    unittest.main()
