from __future__ import annotations

import json
import sys
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from runtime.cp_runtime.evolution import (  # noqa: E402
    ControlledEvolutionService,
    DecisionType,
    EvolutionPolicy,
    ExecutionAuthorization,
    ProposalAction,
    ProposalRegistry,
    ProposalStatus,
)
from runtime.cp_runtime.evolution.contracts import ContractError  # noqa: E402
from runtime.cp_runtime.evolution.observation import ObservationError  # noqa: E402
from runtime.cp_runtime.evolution.redaction import redact  # noqa: E402
from runtime.cp_runtime.evolution.storage import StorageError  # noqa: E402


class ControlledEvolutionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="codex-v51-")
        self.context_root = Path(self.temp.name) / "project-context"
        self.project_id = "project-alpha"
        self.project_dir = self.context_root / self.project_id
        self.project_dir.mkdir(parents=True)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _write_jsonl(self, relative: str, records: list) -> Path:
        path = self.project_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="\n") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        return path

    def _failure_records(self, count: int = 6, start: Optional[datetime] = None) -> list:
        start = start or datetime(2026, 7, 1, tzinfo=timezone.utc)
        records = []
        for index in range(count):
            records.append({
                "record_id": "feedback-%d" % index,
                "task_id": "TASK-%03d" % index,
                "timestamp": (start + timedelta(days=index * 2)).isoformat(),
                "recommended_model": "luna-medium",
                "actual_model": "terra-medium",
                "recommended_reviewers": 1,
                "actual_reviewers": 2,
                "routing_deviation": "MODEL_ESCALATION",
                "blocking_findings": 1,
                "nonblocking_findings": 0,
                "repair_rounds": 2,
                "failure_code": "E_TIMEOUT",
                "quality_outcome": "failed",
                "skill": "problem-troubleshooting",
                "reviewer_results": [{
                    "reviewer": "correctness-reviewer",
                    "result_id": "review-result-%d" % index,
                    "blocking_findings": 1,
                    "nonblocking_findings": 0,
                }],
            })
        return records

    def test_insufficient_records_only_observes(self) -> None:
        self._write_jsonl("feedback/execution-feedback.jsonl", self._failure_records(2))
        result = ControlledEvolutionService(self.context_root, self.project_id).run(dry_run=True)
        self.assertEqual(0, result["assessment_count"])
        self.assertEqual(0, result["proposal_count"])
        self.assertEqual("NONE", result["execution_authorization"])
        self.assertFalse(result["automatic_execution"])

    def test_repeated_failures_generate_controlled_proposals(self) -> None:
        self._write_jsonl("feedback/execution-feedback.jsonl", self._failure_records(6))
        result = ControlledEvolutionService(self.context_root, self.project_id).run(dry_run=True)
        self.assertGreaterEqual(result["proposal_count"], 3)
        actions = {item["action_type"] for item in result["proposals"]}
        self.assertIn("MODIFY", actions)
        for proposal in result["proposals"]:
            self.assertEqual("NONE", proposal["execution_authorization"])
            self.assertEqual("PENDING_REVIEW", proposal["status"])
            self.assertTrue(proposal["rollback_plan"])
            self.assertTrue(proposal["validation_plan"])
            self.assertTrue(proposal["evidence"])

    def test_registry_deduplicates_and_requires_explicit_decision(self) -> None:
        self._write_jsonl("feedback/execution-feedback.jsonl", self._failure_records(6))
        service = ControlledEvolutionService(self.context_root, self.project_id)
        first = service.run(dry_run=False)
        second = service.run(dry_run=False)
        self.assertGreater(first["proposal_count"], 0)
        self.assertTrue(any(item["created"] for item in first["registered"]))
        self.assertTrue(all(not item["created"] for item in second["registered"]))

        registry = ProposalRegistry(self.project_dir / "evolution", self.project_id)
        view = registry.list()[0]
        with self.assertRaises(ContractError):
            registry.decide(view.proposal.proposal_id, DecisionType.ACCEPT, "AI", "too short")
        accepted = registry.decide(
            view.proposal.proposal_id,
            DecisionType.ACCEPT,
            "actor-1",
            "已确认问题与证据匹配，但实施仍需单独任务、审批和回归验证。",
        )
        self.assertEqual(ProposalStatus.ACCEPTED, accepted.current_status)
        self.assertEqual(ExecutionAuthorization.NONE, accepted.proposal.execution_authorization)
        with self.assertRaises(Exception):
            registry.decide(
                view.proposal.proposal_id,
                DecisionType.REJECT,
                "actor-1",
                "不得覆盖已经接受的终态决策，保留原始审计链路。",
            )

    def test_hash_chain_tamper_fails_closed(self) -> None:
        self._write_jsonl("feedback/execution-feedback.jsonl", self._failure_records(6))
        ControlledEvolutionService(self.context_root, self.project_id).run(dry_run=False)
        proposals = self.project_dir / "evolution" / "proposals.jsonl"
        lines = proposals.read_text(encoding="utf-8").splitlines()
        first = json.loads(lines[0])
        first["payload"]["target_resource"] = "tampered-resource"
        lines[0] = json.dumps(first, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        proposals.write_text("\n".join(lines) + "\n", encoding="utf-8")
        registry = ProposalRegistry(self.project_dir / "evolution", self.project_id)
        with self.assertRaises(StorageError):
            registry.validate()

    def test_malformed_source_fails_closed(self) -> None:
        path = self.project_dir / "feedback" / "execution-feedback.jsonl"
        path.parent.mkdir(parents=True)
        path.write_text('{"task_id":"TASK-1"}\n{broken-json}\n', encoding="utf-8")
        with self.assertRaises(StorageError):
            ControlledEvolutionService(self.context_root, self.project_id).run(dry_run=True)

    def test_explicit_source_cannot_escape_project_context(self) -> None:
        outside = self.context_root / "outside.jsonl"
        outside.write_text("{}\n", encoding="utf-8")
        service = ControlledEvolutionService(self.context_root, self.project_id)
        with self.assertRaises(StorageError):
            service.run(explicit_sources=["../outside.jsonl"], dry_run=True)

    def test_sensitive_fields_are_redacted(self) -> None:
        value = redact({
            "api_key": "sk-" + "abcdefghijklmnopqrstuvwxyz",
            "nested": {"authorization": "Bearer " + "abcdefghijklmnopqrstuvwxyz"},
            "message": "connect " + "mysql://" + "root:password@127.0.0.1/db",
        })
        self.assertEqual("[REDACTED]", value["api_key"])
        self.assertEqual("[REDACTED]", value["nested"]["authorization"])
        self.assertIn("[REDACTED]", value["message"])
        self.assertNotIn("password@", value["message"])

    def test_proposal_contract_is_frozen(self) -> None:
        self._write_jsonl("feedback/execution-feedback.jsonl", self._failure_records(6))
        result = ControlledEvolutionService(self.context_root, self.project_id).run(dry_run=True)
        self.assertTrue(result["proposals"])
        snapshot = ControlledEvolutionService(self.context_root, self.project_id).observe()
        assessments = ControlledEvolutionService(self.context_root, self.project_id).analyze(snapshot)
        proposals = ControlledEvolutionService(self.context_root, self.project_id).propose(snapshot, assessments)
        with self.assertRaises(FrozenInstanceError):
            proposals[0].status = ProposalStatus.ACCEPTED

    def test_deprecation_is_only_a_high_confidence_candidate(self) -> None:
        start = datetime(2026, 5, 1, tzinfo=timezone.utc)
        records_a = []
        records_b = []
        for index in range(24):
            record = {
                "record_id": "review-%d" % index,
                "task_id": "TASK-R-%03d" % index,
                "timestamp": (start + timedelta(days=index * 2)).isoformat(),
                "quality_outcome": "accepted",
                "reviewer_results": [{
                    "reviewer": "low-yield-reviewer",
                    "result_id": "review-result-%d" % index,
                    "blocking_findings": 0,
                    "nonblocking_findings": 0,
                    "rejected": 1,
                    "cost_units": 1,
                }],
            }
            (records_a if index % 2 == 0 else records_b).append(record)
        self._write_jsonl("review/review-results-a.jsonl", records_a)
        self._write_jsonl("audit/review-results-b.jsonl", records_b)
        result = ControlledEvolutionService(self.context_root, self.project_id).run(dry_run=True)
        candidates = [item for item in result["proposals"] if item["target_resource"] == "reviewer:low-yield-reviewer"]
        self.assertEqual(1, len(candidates))
        self.assertEqual(ProposalAction.DEPRECATE.value, candidates[0]["action_type"])
        self.assertEqual("NONE", candidates[0]["execution_authorization"])
        self.assertTrue(any("观察期" in step for step in [candidates[0]["recommendation"]]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
