"""中文：真实项目绑定/磁盘 Evidence 的 V4 适配；宿主为合成夹具。

English: Real temporary Project/Evidence integration; host observations are fixtures.
"""
from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
from cp_runtime import budget_v4 as budget
from cp_runtime.common import repo_snapshot
from cp_runtime.evidence import record_evidence
from cp_runtime.project import onboard_project
from cp_runtime.routing_cards import protocol_reference
from cp_runtime.routing_context_v4 import add_current_evidence, build_root_binding, loader, load_snapshot
from cp_runtime.routing_contract import RoutingError, policy_digest, ref, resource_need
from cp_runtime.routing_v4 import snapshot_references
from test_routing_v4_selection_phase import plan, slot, capacity
import v4_fixtures as fx


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True), encoding="utf-8")


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True, capture_output=True)
        (self.repo / "README.md").write_text("Synthetic V4 integration\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.repo), "add", "README.md"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(self.repo), "-c", "user.name=Fixture",
                        "-c", "user.email=fixture@example.invalid", "-c", "commit.gpgsign=false",
                        "commit", "-qm", "fixture"], check=True, capture_output=True)
        self.project = onboard_project(self.repo, "synthetic-v4-context", "Synthetic", self.root / "context")
        self.envelope = self.root / "envelope.json"
        write(self.envelope, {
            "schema_version": 5, "task_id": "evaluation-root", "repo_path": str(self.repo),
            "routing": {"reviewer_policy": {"policy_id": "reviewer-matrix-v4", "policy_digest": policy_digest()}},
            "project": {"binding_status": "BOUND", "project_id": self.project.project_id,
                        "profile_path": str(self.project.profile_path),
                        "profile_sha256": self.project.profile_sha256, "state_path": str(self.project.state_path)},
        })
        self.identity, self.binding = build_root_binding(self.envelope, "desktop-session")
        pair_identity = {key: self.identity[key] for key in ("project_id", "repo_fingerprint")}
        exp = fx.experiment(2)
        exp["identity"] = pair_identity
        exp["protocol_ref"] = protocol_reference(exp)
        case_rows = []
        for sample in exp["samples"][:2]:
            case_rows.append({key: sample[key] for key in
                              ("case_id", "cluster_id", "prompt_ref", "gold_ref", "clean", "critical", "case_ref")})
        self.evaluation = {
            "schema_version": "routing-evaluation/1",
            **{key: exp[key] for key in ("identity", "scenario", "rubric_ref", "minimum_pass_bp",
                                         "baseline_profile", "comparisons", "family_intervals",
                                         "case_plan", "repetitions", "protocol_ref")},
            "cases": case_rows, "costs": fx.costs(exp),
        }
        self.eval_path = self.root / "evaluation.json"
        write(self.eval_path, self.evaluation)
        self.cap_path = self.root / "capability.json"
        self.capability = {
            "schema_version": "desktop-capability/1", "host_surface": "codex-desktop",
            "source": "host-tool-metadata", "root_session_ref": ref("desktop-session"),
            "revision": 1, "available_profiles": ["g6-sol-medium", "g6-sol-high"],
            "created_at": fx.NOW, "expires_at": fx.EXPIRES, "wallclock_enforced": False,
        }
        write(self.cap_path, self.capability)
        evidence_path = self.root / "scope-evidence.json"
        record_evidence(evidence_path, "scope-one", self.project.profile_path, self.identity["task_id"],
                        self.repo, "review", "Synthetic evaluation scope", "valid",
                        "parent-reviewed-v4-requirements", "Fixture only",
                        ["scenario:" + ref(exp["scenario"]), "protocol:" + exp["protocol_ref"],
                         "independent-review-required"])
        evidence_ref = "sha256:" + hashlib.sha256(evidence_path.read_bytes()).hexdigest()
        sources = {
            "root_envelope": str(self.envelope), "capability": str(self.cap_path), "card_sets": [],
            "evaluation_costs": str(self.eval_path), "evaluation_ref": ref(self.evaluation),
            "evidence_paths": {evidence_ref: str(evidence_path)},
        }
        cost = next(item for item in self.evaluation["costs"] if item["profile_id"] == "g6-sol-medium")
        option = {"profile_id": cost["profile_id"], "qualification_ref": ref("evaluation-only"),
                  "cost_ref": ref(cost), "resources": resource_need(cost["profile_id"], cost["reserve_units"])}
        phase_plan = plan([slot("evaluation", [option])])
        phase_plan["identity"] = pair_identity
        self.path = self.root / "budget.jsonl"
        budget.initialize(self.path, declared_identity={**self.identity, "budget_id": "eval-budget"},
                          root_binding=self.binding, sources=sources, execution_mode="EVALUATION",
                          capacity=capacity(), role_capacity={"reviewer": 100, "worker": 0, "explorer": 0},
                          phase_capacity={"pre": 0, "post": 100, "repair": 0}, phase_plan=phase_plan)
        self.request = {
            "schema_version": "routing-request/1", "task_id": self.identity["task_id"],
            "identity": pair_identity, "policy_digest": policy_digest(), "scenario": exp["scenario"],
            "execution_mode": "EVALUATION", "mode": "economy", "slot_id": "evaluation",
            "baseline_sha256": repo_snapshot(self.repo)["sha256"], "packet_sha256": "c" * 64,
            "message_sha256": case_rows[0]["prompt_ref"][7:], "evaluation_case_ref": case_rows[0]["case_ref"],
            "constraints": {"allowed_profiles": ["g6-sol-medium"], "deadline_ms": None, "strict_wallclock": False},
            "evidence": {"ready": True, "independence_required": True, "inline_sufficient": False,
                         "refs": [evidence_ref]}, "expected": {},
        }
        self.loader = loader(cwd=str(self.repo), host_session_id="desktop-session")

    def tearDown(self):
        self.temp.cleanup()

    def test_live_envelope_scope_and_evaluation_plan_drive_preparation(self):
        output = budget.prepare(self.path, self.request, dispatch_key="eval-one", depth=1,
                                snapshot_loader=self.loader)
        self.assertEqual("EVALUATION_SELECTED", output["status"])
        self.assertEqual("g6-sol-medium", output["approved_profile"])

    def test_forged_scope_flags_or_foreign_session_cannot_prepare(self):
        request = copy.deepcopy(self.request)
        request["evidence"]["inline_sufficient"] = True
        with self.assertRaisesRegex(RoutingError, "FLAGS_NOT_VERIFIED"):
            budget.prepare(self.path, request, dispatch_key="forged", depth=1, snapshot_loader=self.loader)
        wrong = loader(cwd=str(self.repo), host_session_id="other-session")
        with self.assertRaisesRegex(RoutingError, "ROOT_BINDING"):
            budget.prepare(self.path, self.request, dispatch_key="foreign", depth=1, snapshot_loader=wrong)
        self.assertFalse(budget.read_budget(self.path)["permits"])

    def test_evaluation_document_cannot_be_changed_after_root_binding(self):
        changed = copy.deepcopy(self.evaluation)
        changed["costs"][0]["reserve_units"] = 1
        write(self.eval_path, changed)
        with self.assertRaisesRegex(RoutingError, "PROTOCOL_BINDING"):
            budget.prepare(self.path, self.request, dispatch_key="changed", depth=1, snapshot_loader=self.loader)

    def test_actual_message_hash_is_bound_to_reserved_case(self):
        output = budget.prepare(self.path, self.request, dispatch_key="eval-one", depth=1,
                                snapshot_loader=self.loader)
        params = output["request_parameters"]
        with self.assertRaisesRegex(RoutingError, "MESSAGE_MISMATCH"):
            budget.approve_and_reserve(self.path, permit_id=output["permit_id"], host_dispatch_id="host-one",
                model=params["model"], effort=params["reasoning_effort"], agent_type=params["agent_type"],
                message_sha256="f" * 64, snapshot_loader=self.loader)
        self.assertFalse(budget.read_budget(self.path)["reservations"])

    def test_new_baseline_evidence_can_be_added_without_reopening_or_refunding_root(self):
        from cp_runtime.routing_evaluation_v4 import make_request
        selected = budget.prepare(self.path, self.request, dispatch_key="before-change", depth=1,
                                    snapshot_loader=self.loader)
        before = budget.read_budget(self.path)
        (self.repo / "README.md").write_text("Changed implementation\n", encoding="utf-8")
        evidence_path = self.root / "new-scope-evidence.json"
        record_evidence(evidence_path, "scope-new", self.project.profile_path, self.identity["task_id"],
            self.repo, "review", "Updated scope", "valid", "parent-reviewed-v4-requirements", "Fixture only",
            ["scenario:" + ref(self.evaluation["scenario"]), "protocol:" + self.evaluation["protocol_ref"],
             "independent-review-required"])
        after = add_current_evidence(self.path, [evidence_path], cwd=str(self.repo), host_session_id="desktop-session")
        self.assertEqual(before["_usage_cache"], after["_usage_cache"])
        self.assertGreater(after["resource_revision"], before["resource_revision"])
        self.assertEqual(2, len(after["sources"]["evidence_paths"]))
        budget.revoke_prepare(self.path, permit_id=selected["permit_id"], reason_ref=ref("new-baseline"))
        prompt = self.root / "prompt.txt"
        prompt.write_text(json.dumps("synthetic-prompt-0"), encoding="utf-8")
        request = make_request(self.path, cwd=str(self.repo), host_session_id="desktop-session", slot_id="evaluation",
            case_id="case-0", profile_id="g6-sol-medium", repetition=1, prompt_path=prompt)
        self.assertEqual(1, len(request["evidence"]["refs"]))
        self.assertNotEqual(self.request["evidence"]["refs"], request["evidence"]["refs"])
        result = budget.prepare(self.path, request, dispatch_key="after-change", depth=1, snapshot_loader=self.loader)
        self.assertEqual("EVALUATION_SELECTED", result["status"])

    def test_evidence_addition_rejects_foreign_scope_and_replacement(self):
        old_ref = self.request["evidence"]["refs"][0]
        with self.assertRaisesRegex(RoutingError, "SOURCE_REPLACEMENT"):
            budget.add_evidence_paths(self.path, {old_ref: str(self.root / "other-file.json")})
        with self.assertRaisesRegex(RoutingError, "ROOT_BINDING"):
            add_current_evidence(self.path, [self.root / "scope-evidence.json"],
                                  cwd=str(self.repo), host_session_id="foreign-session")

    def test_stale_repository_and_capability_root_fail_before_charge(self):
        output = budget.prepare(self.path, self.request, dispatch_key="eval-one", depth=1,
                                snapshot_loader=self.loader)
        (self.repo / "README.md").write_text("Changed scope\n", encoding="utf-8")
        with self.assertRaisesRegex(RoutingError, "BASELINE_CHANGED"):
            budget.prepare(self.path, self.request, dispatch_key="eval-two", depth=1,
                           snapshot_loader=self.loader)
        self.assertFalse(budget.read_budget(self.path)["reservations"])

    def test_finalized_native_shaped_trace_binds_prompt_case_and_protocol(self):
        output = budget.prepare(self.path, self.request, dispatch_key="eval-one", depth=1,
                                snapshot_loader=self.loader)
        params = output["request_parameters"]
        attempt = budget.approve_and_reserve(
            self.path, permit_id=output["permit_id"], host_dispatch_id="host-one",
            model=params["model"], effort=params["reasoning_effort"], agent_type=params["agent_type"],
            message_sha256=self.request["message_sha256"], snapshot_loader=self.loader)
        budget.record_receipt(self.path, host_dispatch_id="host-one", agent_id="synthetic-agent")
        budget.record_observation(self.path, agent_id="synthetic-agent", phase="stop")
        budget.accept_result(self.path, reservation_id=attempt["reservation_id"], result_ref=ref("result"),
                             status="pass", response_ref=ref("response"),
                             baseline_sha256=self.request["baseline_sha256"])
        state = budget.read_budget(self.path)
        receipt_ref = ref(state["host_receipts"][attempt["reservation_id"]])
        with self.assertRaisesRegex(RoutingError, "NOT_FINALIZED"):
            budget.export_trace(self.path, receipt_ref)
        budget.close(self.path, outcome="PASS", evidence_ref=ref("closed-evaluation"))
        trace = budget.export_trace(self.path, receipt_ref)
        self.assertEqual(self.request["evaluation_case_ref"], trace["case_ref"])
        self.assertEqual("sha256:" + self.request["message_sha256"], trace["prompt_ref"])
        self.assertEqual(self.evaluation["protocol_ref"], trace["protocol_ref"])


if __name__ == "__main__":
    unittest.main()
