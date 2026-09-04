"""中文：V7.4.3 模型身份隐私与旧链兼容合同测试。

English: V7.4.3 model-identity privacy and legacy-chain compatibility contracts.
"""

from __future__ import annotations

import hashlib
import hmac
import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from runtime.cp_runtime import delegation_budget as budget
from runtime.cp_runtime import event_v2 as events
from runtime.cp_runtime.event_archive import health_overview


REPO = "sha256:" + "a" * 64


class V743PrivacyContractsTests(unittest.TestCase):
    @staticmethod
    def _legacy_event(payload: dict, key: str = "") -> dict:
        validated = events._make_legacy_event_v2(payload)
        envelope = dict(validated)
        envelope["previous_hash"] = events.ZERO_HASH
        envelope["record_hash"] = events.sha256_hex(
            events.ZERO_HASH + "\n" + events.canonical_json(validated)
        )
        if key:
            envelope["record_hmac_sha256"] = hmac.new(
                key.encode("utf-8"), events.canonical_json(envelope).encode("utf-8"), hashlib.sha256,
            ).hexdigest()
        return envelope

    def test_v3_recursively_drops_host_model_identity(self) -> None:
        raw = events.make_event({
            "event_type": "SUBAGENT_STOPPED",
            "project_id": "project-1",
            "repo_fingerprint": REPO,
            "task_id": "task-1",
            "approved_dispatch_profile": "luna-medium",
            "reserved_units": 2,
            "actual_model": "gpt-5.6-terra",
            "metadata": {
                "safe": "kept",
                "actual_model": "gpt-5.6-terra",
                "nested": [{"runtime_model": "gpt-5.6-sol", "value": 1}],
            },
        })

        encoded = events.canonical_json(raw)
        self.assertEqual(raw["metadata"]["safe"], "kept")
        self.assertNotIn("actual_model", encoded)
        self.assertNotIn("runtime_model", encoded)
        self.assertNotIn("gpt-5.6-terra", encoded)
        self.assertNotIn("gpt-5.6-sol", encoded)

    def test_legacy_event_v2_is_verified_then_safely_projected(self) -> None:
        key = "test-only-hmac-key"
        envelope = self._legacy_event({
            "event_id": "EVT_legacy",
            "event_type": "SUBAGENT_STOPPED",
            "captured_at": "2026-09-04T00:00:00.000+00:00",
            "project_id": "project-1",
            "repo_fingerprint": REPO,
            "task_id": "task-1",
            "terminal_outcome": "PASS",
            "terminal_outcome_source": "hook-payload",
            "recommended_model": "gpt-5.6-luna",
            "actual_model": "gpt-5.6-terra",
            "actual_reasoning_effort": "high",
            "actual_model_source": "host-attested-hook-payload",
            "actual_reasoning_effort_source": "host-attested-hook-payload",
            "metadata": {"actual_model": "gpt-5.6-sol", "safe": "kept"},
        }, key)

        with tempfile.TemporaryDirectory() as directory:
            chain = Path(directory) / "legacy-v2.jsonl"
            chain.write_text(events.canonical_json(envelope) + "\n", encoding="utf-8")
            result = events.read_event_chain(chain, hmac_key=key)
            projected = result["events"][0]
            self.assertEqual(result["schema_version"], "2.0")
            self.assertEqual(projected["source_schema_version"], "2.0")
            self.assertEqual(projected["metadata"], {"safe": "kept"})
            encoded = events.canonical_json(projected)
            self.assertNotIn("actual_model", encoded)
            self.assertNotIn("reasoning_effort", encoded)
            with self.assertRaises(events.EventContractError):
                events.append_event(chain, events.make_event({
                    "event_type": "TASK_COMPLETED",
                    "project_id": "project-1",
                    "repo_fingerprint": REPO,
                }))

    def test_legacy_budget_v1_is_read_only_and_safely_projected(self) -> None:
        identity = {
            "budget_id": "budget-1",
            "task_id": "task-1",
            "project_id": "project-1",
            "repo_fingerprint": REPO,
        }
        limits = dict(budget.BUDGET_CLASSES["LIGHT"])
        data = {
            "decision_kind": "budget-initialized",
            "budget_class": "LIGHT",
            "default_model_profile": "luna-medium",
            "limits": limits,
            "role_limits": {
                role: {"max_units": limits["max_units"], "max_dispatches": limits["max_dispatches"]}
                for role in sorted(budget.ROLES)
            },
            "cost_formula_version": "profile-weight-v1",
            "association_mode": "explicit-dispatch-permit",
        }
        unsigned = {
            "schema_version": budget.LEGACY_SCHEMA_VERSION,
            "event_id": "DBE_legacy",
            "event_type": "DECISION_RECORDED",
            "captured_at": "2026-09-04T00:00:00.000+00:00",
            "sequence": 1,
            **identity,
            "data": data,
        }
        record = {
            **unsigned,
            "previous_hash": budget.ZERO_HASH,
            "record_hash": budget._record_hash(budget.ZERO_HASH, unsigned),
        }

        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "legacy-v1.jsonl"
            ledger.write_text(budget.canonical_json(record) + "\n", encoding="utf-8")
            state = budget.read_budget(ledger)
            self.assertTrue(state["read_only"])
            self.assertEqual(state["default_dispatch_profile"], "luna-medium")
            encoded = budget.canonical_json(state)
            self.assertNotIn("actual_profile", encoded)
            self.assertNotIn("runtime_evidence", encoded)
            self.assertNotIn("top_up", encoded)
            with self.assertRaises(budget.DelegationBudgetError):
                budget.initialize_budget(
                    ledger,
                    budget_id="budget-1",
                    task_id="task-1",
                    project_id="project-1",
                    repo_fingerprint=REPO,
                    budget_class="LIGHT",
                    default_dispatch_profile="luna-medium",
                )

    def test_legacy_budget_rejects_hash_valid_invalid_state_transition(self) -> None:
        identity = {
            "budget_id": "budget-1", "task_id": "task-1", "project_id": "project-1",
            "repo_fingerprint": REPO,
        }
        limits = dict(budget.BUDGET_CLASSES["LIGHT"])
        init_data = {
            "decision_kind": "budget-initialized", "budget_class": "LIGHT",
            "default_model_profile": "luna-medium", "limits": limits,
            "role_limits": {role: {"max_units": limits["max_units"], "max_dispatches": limits["max_dispatches"]}
                            for role in sorted(budget.ROLES)},
            "cost_formula_version": "profile-weight-v1", "association_mode": "explicit-dispatch-permit",
        }
        unsigned_init = {
            "schema_version": budget.LEGACY_SCHEMA_VERSION, "event_id": "DBE_init",
            "event_type": "DECISION_RECORDED", "captured_at": "2026-09-04T00:00:00.000+00:00",
            "sequence": 1, **identity, "data": init_data,
        }
        init = {**unsigned_init, "previous_hash": budget.ZERO_HASH,
                "record_hash": budget._record_hash(budget.ZERO_HASH, unsigned_init)}
        invalid_data = {
            "reservation_id": "missing-reservation", "agent_ref": "sha256:" + "b" * 64,
            "actual_profile": "", "runtime_evidence": "unavailable", "top_up_units": 0,
            "association": "reservation-id",
        }
        unsigned_invalid = {
            "schema_version": budget.LEGACY_SCHEMA_VERSION, "event_id": "DBE_invalid",
            "event_type": "AGENT_STARTED", "captured_at": "2026-09-04T00:00:01.000+00:00",
            "sequence": 2, **identity, "data": invalid_data,
        }
        invalid = {**unsigned_invalid, "previous_hash": init["record_hash"],
                   "record_hash": budget._record_hash(init["record_hash"], unsigned_invalid)}
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "legacy-v1.jsonl"
            ledger.write_text("\n".join(budget.canonical_json(row) for row in (init, invalid)) + "\n",
                              encoding="utf-8")
            with self.assertRaisesRegex(budget.DelegationBudgetError, "状态转换"):
                budget.read_budget(ledger)

    def test_health_accepts_independent_v2_and_v3_chains(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            feedback = root / "project-1" / "feedback"
            current = feedback / "task-outcome-v3.jsonl"
            legacy = feedback / "task-outcome-v2.jsonl"
            events.append_event(current, events.make_event({
                "event_id": "EVT_current", "event_type": "TURN_OPENED",
                "captured_at": "2026-09-04T00:00:01.000+00:00",
                "project_id": "project-1", "repo_fingerprint": REPO,
            }))
            legacy.parent.mkdir(parents=True, exist_ok=True)
            legacy.write_text(events.canonical_json(self._legacy_event({
                "event_id": "EVT_legacy", "event_type": "TURN_OPENED",
                "captured_at": "2026-09-04T00:00:00.000+00:00",
                "project_id": "project-1", "repo_fingerprint": REPO,
            })) + "\n", encoding="utf-8")
            for queue_name in ("seal-queue-v3", "seal-queue"):
                pending = feedback / queue_name / "pending"
                pending.mkdir(parents=True)
                (pending / ("job-%s.json" % queue_name)).write_text("{}\n", encoding="utf-8")
            result = health_overview(root)
            self.assertTrue(result["ok"])
            project = result["projects"][0]
            self.assertEqual("VALID", project["chain_status"])
            self.assertEqual(2, project["event_count"])
            self.assertEqual(2, project["pending_jobs"])
            self.assertEqual("PENDING", project["queue_status"])
            self.assertEqual({1}, {item["pending_jobs"] for item in project["event_chains"]})
            self.assertEqual({"current", "legacy-readonly"},
                             {item["role"] for item in project["event_chains"]})

    def test_privacy_lint_only_exempts_delimited_legacy_reader_lines(self) -> None:
        script = Path(__file__).resolve().parents[1] / "scripts" / "privacy-boundary-lint.py"
        spec = importlib.util.spec_from_file_location("privacy_boundary_lint", script)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader
        spec.loader.exec_module(module)
        sample = "\n".join([
            "# 中文：PRIVACY_LEGACY_READER_BEGIN；English: begin.", "actual_model = legacy",
            "# 中文：PRIVACY_LEGACY_READER_END；English: end.",
            "actual_model = active",
        ])
        active = list(module.active_lines(Path("runtime/cp_runtime/event_v2.py"), sample))
        self.assertEqual([(4, "actual_model = active")], active)

    def test_legacy_budget_binding_makes_existing_review_state_read_only(self) -> None:
        script = (Path(__file__).resolve().parents[1] / "skills" / "multi-agent-independent-review" /
                  "scripts" / "review_controller.py")
        spec = importlib.util.spec_from_file_location("review_controller_v743", script)
        controller = importlib.util.module_from_spec(spec)
        assert spec.loader
        spec.loader.exec_module(controller)
        with tempfile.TemporaryDirectory() as directory:
            review_dir = Path(directory)
            state = {
                "schema_version": 7, "boundary_id": "boundary-1", "task_id": "task-1",
                "delegation_budget": {"ledger_path": str(review_dir / "budget.jsonl"),
                                      "budget_id": "budget-1", "accounting_owner": "delegation-budget-v2"},
                "routing_decisions": {"pre": [], "post": []},
                "phases": {"pre": {"current_round": 0, "rounds": {}},
                           "post": {"current_round": 0, "rounds": {}}},
                "limits": dict(controller.DEFAULT_LIMITS),
                "counters": {"total_reviewers": 0, "repair_rounds": 0, "terra_high_reviewers": 0},
                "isolation": controller.default_isolation(), "notes": [],
            }
            (review_dir / controller.STATE_FILE).write_text(json.dumps(state), encoding="utf-8")
            with mock.patch.object(controller, "read_budget", return_value={"read_only": True}):
                loaded = controller.load_state(review_dir)
            self.assertEqual("delegation-budget-v1-readonly",
                             loaded["delegation_budget"]["accounting_owner"])
            with redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
                controller.ensure_state_mutable(loaded)


if __name__ == "__main__":
    unittest.main()
