"""中文：演进闭环的身份、策略与跨模块回归测试。

English: Cross-module identity, policy, and evolution-loop regression tests.
"""
from __future__ import annotations

import hashlib
import os
import json
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))

from cp_runtime.event_v3 import append_event, stable_repo_fingerprint
from cp_runtime.evolution.contracts import EvolutionPolicy, to_primitive
from cp_runtime.evolution.observation import ObservationError, _expected_repo_fingerprint, observe_project
from cp_runtime.evolution.service import load_policy
from cp_runtime.common import seal_record
from cp_runtime.evolution.artifacts import ArtifactError
from cp_runtime.evolution.task_feedback import consume_for_hook, finalize_feedback, run_validation
from cp_runtime.evolution.health import inspect_health
from cp_runtime.evolution.service import ControlledEvolutionService
from cp_runtime.evolution.incremental import RECEIPT, automation_tick, configure_automation, run_incremental
from cp_runtime.evolution.registry import ProposalRegistry, _proposal
from cp_runtime.evolution.contracts import DecisionType, ProposalStatus
from cp_runtime.evolution.snapshots import persist_snapshot


class EvolutionFoundationTests(unittest.TestCase):
    def test_profile_and_hook_share_historical_raw_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = Path(folder) / "repo"
            (repo / ".git").mkdir(parents=True)
            remote = "https://example.invalid/team/project.git"
            (repo / ".git" / "config").write_text('[remote "origin"]\nurl = ' + remote + '\n', encoding="utf-8")
            context = Path(folder) / "context" / "project-alpha"
            context.mkdir(parents=True)
            (context / "project-profile.json").write_text(json.dumps({
                "project_id": "project-alpha",
                "identity": {"repo_path": str(repo), "remote_origin": remote},
            }), encoding="utf-8")
            expected = "sha256:" + hashlib.sha256((str(repo.resolve()) + "\n" + remote).encode()).hexdigest()
            self.assertEqual(expected, stable_repo_fingerprint(str(repo)))
            self.assertEqual(expected, _expected_repo_fingerprint(context))
            event_file = context / "feedback" / "task-outcome-v3.jsonl"
            append_event(event_file, {
                "event_type": "TASK_COMPLETED", "session_id": "S1", "turn_id": "T1", "task_id": "T1",
                "project_id": "project-alpha", "repo_fingerprint": expected, "terminal_outcome": "PASS",
            })
            before = event_file.read_bytes()
            self.assertEqual(1, observe_project("project-alpha", context).task_count)
            self.assertEqual(before, event_file.read_bytes())
            profile = json.loads((context / "project-profile.json").read_text())
            profile["identity"]["remote_origin"] = remote + "-other"
            (context / "project-profile.json").write_text(json.dumps(profile), encoding="utf-8")
            with self.assertRaises(ObservationError):
                observe_project("project-alpha", context)

    def test_default_and_explicit_policy_have_identical_content(self):
        explicit = load_policy(ROOT / "config" / "evolution-policy.json")
        self.assertEqual(to_primitive(EvolutionPolicy()), to_primitive(explicit))
        self.assertEqual(to_primitive(load_policy()), to_primitive(explicit))


class EvolutionProjectCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / "repo"
        self.repo.mkdir()
        for command in (["init", "-q"], ["config", "user.email", "test@example.invalid"],
                        ["config", "user.name", "Test"], ["commit", "--allow-empty", "-qm", "initial"]):
            subprocess.run(["git", *command], cwd=self.repo, check=True, capture_output=True)
        self.project = Path(self.tmp.name) / "context" / "project-alpha"
        self.project.mkdir(parents=True)
        profile = seal_record({"project_id": self.project.name, "identity": {"repo_path": str(self.repo), "remote_origin": ""}})
        (self.project / "project-profile.json").write_text(json.dumps(profile), encoding="utf-8")
        self.event = {"project_id": self.project.name, "repo_fingerprint": stable_repo_fingerprint(str(self.repo)),
                      "session_id": "S1", "turn_id": "T1", "task_id": "TASK1", "event_type": "TASK_COMPLETED"}

    def validation(self, code=0):
        return run_validation(self.project, "S1", "T1", "TASK1", [sys.executable, "-c", f"raise SystemExit({code})"])

    def finalize(self, validation, **changes):
        options = dict(actor="parent:TASK1", outcome="PASS", failure_category="NONE", routing_deviation="MATCHED",
                       repair_rounds=0, evidence_paths=[validation["reference"]["path"]])
        options.update(changes)
        return finalize_feedback(self.project, "S1", "T1", "TASK1", **options)


class EvolutionFeedbackTests(EvolutionProjectCase):
    @unittest.skipUnless(os.name == "nt", "Windows short-path aliases")
    def test_finalized_report_enumeration_accepts_real_windows_short_path(self):
        import ctypes
        from cp_runtime.evolution.task_feedback import finalized_reports
        final = self.finalize(self.validation())
        buffer = ctypes.create_unicode_buffer(32768)
        length = ctypes.windll.kernel32.GetShortPathNameW(str(self.project), buffer, len(buffer))
        if not length or Path(buffer.value) == self.project:
            self.skipTest("Volume does not expose a distinct short-path alias")
        short = Path(buffer.value)
        self.assertEqual(self.project.resolve(), short.resolve())
        self.assertEqual([(final["reference"]["path"], final["report"])], finalized_reports(short))

    def test_worktree_change_requires_new_turn_after_finalization(self):
        self.finalize(self.validation())
        (self.repo / "change.txt").write_text("new baseline")
        with self.assertRaisesRegex(ArtifactError, "FEEDBACK_FINALIZATION_CONFLICT"):
            self.finalize(self.validation())
        validation = run_validation(self.project, "S1", "T2", "TASK1", [sys.executable, "-c", "pass"])
        final = finalize_feedback(self.project, "S1", "T2", "TASK1", actor="parent:TASK1", outcome="PASS",
                                  failure_category="NONE", routing_deviation="MATCHED", repair_rounds=0,
                                  evidence_paths=[validation["reference"]["path"]])
        self.assertEqual("T2", final["report"]["subject"]["turn_id"])

    def test_linked_worktree_identity_and_profile_agree(self):
        from cp_runtime.event_v2 import repo_fingerprint_for_identity, project_id_for
        from cp_runtime.evolution.artifacts import project_identity
        remote = "https://example.invalid/team/repo.git"
        subprocess.run(["git", "remote", "add", "origin", remote], cwd=self.repo, check=True)
        worktree = self.repo.parent / "linked"
        subprocess.run(["git", "worktree", "add", "--detach", str(worktree)], cwd=self.repo, check=True, capture_output=True)
        for root in (self.repo, worktree):
            profile = seal_record({"project_id": self.project.name, "identity": {"repo_path": str(root), "remote_origin": remote}})
            (self.project / "project-profile.json").write_text(json.dumps(profile))
            expected = repo_fingerprint_for_identity(str(root), remote)
            self.assertEqual(expected, stable_repo_fingerprint(str(root)))
            self.assertEqual(expected, _expected_repo_fingerprint(self.project))
            self.assertEqual(expected, project_identity(self.project)["repo_fingerprint"])
            with patch.dict("os.environ", {"CP_PROJECT_ID": ""}):
                self.assertTrue(project_id_for(expected, str(root)).endswith(hashlib.sha256(remote.encode()).hexdigest()[:10]))

    def test_feedback_automatic_counts_idempotence_and_one_task_aggregation(self):
        validation = self.validation()
        report = self.finalize(validation)
        self.assertEqual(1, report["report"]["validation_passed"])
        self.assertEqual(report, self.finalize(validation))
        self.assertEqual(report["report"], consume_for_hook(self.project, self.event, str(self.repo)))
        event_file = self.project / "feedback" / "task-outcome-v3.jsonl"
        append_event(event_file, {**self.event, "event_type": "TURN_OPENED"})
        append_event(event_file, {**self.event, "metadata": {"finalized_feedback_hash": report["report"]["content_hash"]}})
        snapshot = observe_project(self.project.name, self.project)
        self.assertEqual(1, snapshot.task_count)
        self.assertEqual(1, snapshot.metrics["known_outcome_count"])
        self.assertEqual(1, snapshot.metrics["finalized_feedback_count"])

    def test_failed_validation_cannot_be_finalized_pass(self):
        validation = self.validation(3)
        with self.assertRaises(ArtifactError):
            self.finalize(validation)
        report = self.finalize(validation, outcome="FAILED", failure_category="VALIDATION")
        self.assertEqual(1, report["report"]["validation_failed"])

    def test_feedback_rejects_child_conflict_tamper_and_stale_worktree(self):
        validation = self.validation()
        with self.assertRaises(ArtifactError):
            self.finalize(validation, actor="child:TASK1")
        self.finalize(validation)
        with self.assertRaises(ArtifactError):
            self.finalize(validation, repair_rounds=1)
        evidence_file = self.project / validation["reference"]["path"]
        original = evidence_file.read_text()
        evidence_file.write_text(original.replace('"exit_code": 0', '"exit_code": 1'))
        with self.assertRaises(ArtifactError):
            consume_for_hook(self.project, self.event, str(self.repo))
        evidence_file.write_text(original)
        (self.repo / "changed.txt").write_text("changed")
        with self.assertRaises(ArtifactError):
            consume_for_hook(self.project, self.event, str(self.repo))

    def test_other_sessions_turns_and_tasks_cannot_consume_feedback(self):
        self.finalize(self.validation())
        for key in ("session_id", "turn_id", "task_id"):
            self.assertIsNone(consume_for_hook(self.project, {**self.event, key: "OTHER"}, str(self.repo)))

    def test_validation_retains_no_command_or_output_body(self):
        marker = "private-output-canary"
        result = run_validation(self.project, "S1", "T1", "TASK1", [sys.executable, "-c", f"print('{marker}')"])
        self.assertNotIn(marker, (self.project / result["reference"]["path"]).read_text())


class EvolutionHealthTests(EvolutionProjectCase):
    def populate(self, outcome="PASS"):
        path = self.project / "feedback" / "task-outcome-v3.jsonl"
        now = datetime.now(timezone.utc)
        for index, age in enumerate((9, 7, 5, 3, 1)):
            for event_type in ("TURN_OPENED", "TASK_COMPLETED", "SESSION_ENDED"):
                append_event(path, {**self.event, "event_type": event_type, "task_id": f"TASK{index}",
                                   "session_id": f"SESSION{index}", "turn_id": f"TURN{index}",
                                   "captured_at": (now - timedelta(days=age)).isoformat(),
                                   "terminal_outcome": outcome if event_type == "TASK_COMPLETED" else "UNKNOWN"})
        return path

    def test_health_distinguishes_insufficient_healthy_stale_and_corrupt(self):
        report, _ = inspect_health(self.project, self.project.name, EvolutionPolicy())
        self.assertEqual("INSUFFICIENT_DATA", report["status"])
        source = self.populate()
        before = {p.relative_to(self.project).as_posix(): p.read_bytes() for p in self.project.rglob("*") if p.is_file()}
        report, _ = inspect_health(self.project, self.project.name, EvolutionPolicy())
        self.assertEqual("HEALTHY_NO_SIGNAL", report["status"])
        self.assertTrue(report["analysis_allowed"])
        after = {p.relative_to(self.project).as_posix(): p.read_bytes() for p in self.project.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        report, _ = inspect_health(self.project, self.project.name, EvolutionPolicy(),
                                   observed_at=(datetime.now(timezone.utc) + timedelta(days=45)).isoformat())
        self.assertEqual("STALE_DATA", report["status"])
        source.write_text(source.read_text() + "{bad\n")
        report, snapshot = inspect_health(self.project, self.project.name, EvolutionPolicy())
        self.assertEqual("DATA_DAMAGED", report["status"])
        self.assertIsNone(snapshot)

    def test_health_rejects_live_identity_drift(self):
        subprocess.run(["git", "remote", "add", "origin", "https://example.invalid/other"], cwd=self.repo, check=True)
        report, _ = inspect_health(self.project, self.project.name, EvolutionPolicy())
        self.assertEqual("IDENTITY_MISMATCH", report["status"])
        self.assertFalse(report["analysis_allowed"])


class EvolutionIncrementalTests(EvolutionProjectCase):
    def setUp(self):
        super().setUp()
        EvolutionHealthTests.populate(self)
        self.service = ControlledEvolutionService(self.project.parent, self.project.name)

    def test_incremental_replay_is_quiet_and_creates_one_transaction(self):
        first = run_incremental(self.service)
        self.assertEqual("ANALYZED", first["status"])
        receipt = (self.project / RECEIPT).read_bytes()
        second = run_incremental(self.service)
        self.assertEqual("NO_CHANGE", second["status"])
        self.assertFalse(second["notification_required"])
        self.assertEqual(receipt, (self.project / RECEIPT).read_bytes())
        self.assertEqual(1, len(list((self.project / "evolution/transactions").glob("*.json"))))

    def test_crash_after_outputs_reuses_transaction_without_consuming_receipt(self):
        def crash(point):
            if point == "before_receipt":
                raise RuntimeError("simulated interruption")
        with self.assertRaises(RuntimeError):
            run_incremental(self.service, fault=crash)
        self.assertFalse((self.project / RECEIPT).exists())
        paths = list((self.project / "evolution/transactions").glob("*.json"))
        self.assertEqual(1, len(paths))
        original = paths[0].read_bytes()
        self.assertEqual("ANALYZED", run_incremental(self.service)["status"])
        self.assertEqual(original, paths[0].read_bytes())

    def test_automation_is_opt_in_and_identity_bound(self):
        self.assertEqual("DISABLED", automation_tick(self.project)["status"])
        self.assertFalse((self.project / "evolution").exists())
        configure_automation(self.project, enabled=True)
        self.assertEqual("ANALYZED", automation_tick(self.project)["status"])
        self.assertEqual("NO_CHANGE", automation_tick(self.project)["status"])
        configure_automation(self.project, enabled=False)
        self.assertEqual("DISABLED", automation_tick(self.project)["status"])

    def test_supplemental_feedback_for_seen_task_triggers_analysis(self):
        event_path = self.project / "feedback/task-outcome-v3.jsonl"
        for event_type in ("TURN_OPENED", "TASK_COMPLETED", "SESSION_ENDED"):
            append_event(event_path, {**self.event, "task_id": "SUPPLEMENT", "event_type": event_type})
        first = run_incremental(self.service, cooldown_seconds=0)
        self.assertEqual("ANALYZED", first["status"])
        validation = run_validation(self.project, "S1", "T1", "SUPPLEMENT", [sys.executable, "-c", "pass"])
        finalize_feedback(self.project, "S1", "T1", "SUPPLEMENT", actor="parent:SUPPLEMENT", outcome="PASS",
                          failure_category="NONE", routing_deviation="MATCHED", repair_rounds=0,
                          evidence_paths=[validation["reference"]["path"]])
        second = run_incremental(self.service, cooldown_seconds=0)
        self.assertEqual("ANALYZED", second["status"])
        self.assertEqual(0, second["new_independent_tasks"])
        self.assertNotEqual(first["input_key"], second["input_key"])


class EvolutionHypothesisTests(EvolutionProjectCase):
    def test_new_proposals_have_frozen_testable_hypotheses_and_stable_fingerprints(self):
        EvolutionHealthTests.populate(self, outcome="FAILED")
        service = ControlledEvolutionService(self.project.parent, self.project.name)
        first = service.run(dry_run=True)
        second = service.run(dry_run=True)
        self.assertGreater(first["proposal_count"], 0)
        raw = first["proposals"][0]
        self.assertEqual("2.0", raw["schema_version"])
        self.assertEqual(0.9, raw["hypothesis"]["target"])
        self.assertEqual(raw["fingerprint"], second["proposals"][0]["fingerprint"])
        proposal = _proposal(raw)
        proposal.verify_integrity()
        with self.assertRaises(TypeError):
            proposal.hypothesis["target"] = 0
        raw["hypothesis"]["scope"]["project_id"] = "other"
        with self.assertRaises(ArtifactError):
            _proposal(raw)


class EvolutionBenefitTests(EvolutionProjectCase):
    def setUp(self):
        super().setUp()
        now = datetime.now(timezone.utc)
        self.now = now
        path = self.project / "feedback/task-outcome-v3.jsonl"
        for group, ages, outcome in (("BEFORE", (20, 18, 16, 14, 12), "FAILED"), ("AFTER", (9, 7, 5, 3, 1), "PASS")):
            for index, age in enumerate(ages):
                for event_type in ("TURN_OPENED", "TASK_COMPLETED", "SESSION_ENDED"):
                    append_event(path, {**self.event, "event_type": event_type, "task_id": f"{group}-{index}",
                                       "session_id": f"{group}-{index}", "turn_id": f"{group}-{index}",
                                       "captured_at": (now - timedelta(days=age)).isoformat(),
                                       "terminal_outcome": outcome if event_type == "TASK_COMPLETED" else "UNKNOWN"})
        self.service = ControlledEvolutionService(self.project.parent, self.project.name)
        before = self.service.observe(window_start=(now - timedelta(days=21)).isoformat(), window_end=(now - timedelta(days=11)).isoformat())
        after = self.service.observe(window_start=(now - timedelta(days=10)).isoformat(), window_end=now.isoformat())
        self.before_ref = persist_snapshot(self.project, before)
        self.after_ref = persist_snapshot(self.project, after)
        proposals = self.service.propose(before, self.service.analyze(before))
        self.proposal = next(item for item in proposals if item.hypothesis["metric"] == "negative_outcome_rate")
        self.registry = ProposalRegistry(self.service.evolution_root, self.project.name)
        self.registry.register(self.proposal)
        self.registry.decide(self.proposal.proposal_id, DecisionType.ACCEPT, "human", "Approve an independently authorized implementation task.")
        self.commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=self.repo, text=True).strip()

    def implement(self):
        self.registry.link_implementation(self.proposal.proposal_id, "parent:TASK1", "TASK1", self.commit)
        with patch("cp_runtime.evolution.task_feedback.utc_now_iso", return_value=(self.now - timedelta(days=10)).isoformat()):
            validation = self.validation()
        self.registry.record_validation(self.proposal.proposal_id, "parent:TASK1", self.commit, [validation["reference"]["path"]])
        return validation

    def test_implementation_pass_is_not_benefit_pass_and_observations_are_append_only(self):
        self.implement()
        with self.assertRaises(ArtifactError):
            self.registry.close(self.proposal.proposal_id, "parent:TASK1", "PASS")
        short = self.service.observe(window_start=(self.now - timedelta(days=10)).isoformat(), window_end=(self.now - timedelta(days=8)).isoformat())
        short_ref = persist_snapshot(self.project, short)
        view = self.registry.observe_benefit(self.proposal.proposal_id, "parent:TASK1", self.before_ref, short_ref)
        self.assertEqual("INSUFFICIENT", view.latest_benefit["benefit_status"])
        after = self.service.observe(window_start=(self.now - timedelta(days=10)).isoformat(), window_end=self.now.isoformat())
        self.after_ref = persist_snapshot(self.project, after)
        view = self.registry.observe_benefit(self.proposal.proposal_id, "parent:TASK1", self.before_ref, self.after_ref)
        self.assertEqual("SUPPORTED", view.latest_benefit["benefit_status"])
        original = self.registry.governed.path.read_bytes()
        self.registry.observe_benefit(self.proposal.proposal_id, "parent:TASK1", self.before_ref, self.after_ref)
        self.assertEqual(original, self.registry.governed.path.read_bytes())
        view = self.registry.close(self.proposal.proposal_id, "parent:TASK1", "PASS")
        self.assertEqual(ProposalStatus.CLOSED, view.current_status)
        self.assertEqual("PASS", view.final_outcome)
        with self.assertRaises(ArtifactError):
            self.registry.observe_benefit(self.proposal.proposal_id, "parent:TASK1", self.before_ref, self.after_ref)

    def test_replay_detects_changed_evidence_and_overlapping_cohorts(self):
        self.implement()
        with self.assertRaises(ArtifactError):
            self.registry.observe_benefit(self.proposal.proposal_id, "parent:TASK1", self.before_ref, self.before_ref)
        self.registry.observe_benefit(self.proposal.proposal_id, "parent:TASK1", self.before_ref, self.after_ref)
        path = self.project / self.after_ref["path"]
        path.write_text(path.read_text().replace('"negative_outcome_rate": 0.0', '"negative_outcome_rate": 1.0'))
        with self.assertRaises(ArtifactError):
            self.registry.get(self.proposal.proposal_id)

    def test_cancellation_before_implementation_is_terminal(self):
        view = self.registry.close(self.proposal.proposal_id, "human", "CANCELLED")
        self.assertEqual("CANCELLED", view.final_outcome)
        with self.assertRaises(ArtifactError):
            self.registry.link_implementation(self.proposal.proposal_id, "human", "TASK1", self.commit)

    def test_implementation_task_is_rejected_in_either_observation_cohort(self):
        self.implement()
        from cp_runtime.evolution.benefits import evaluate_benefit
        from cp_runtime.evolution.snapshots import load_snapshot
        from types import SimpleNamespace
        before, after = load_snapshot(self.project, self.before_ref), load_snapshot(self.project, self.after_ref)
        validation = self.registry.get(self.proposal.proposal_id)
        for selected in (0, 1):
            snapshots = [before, after]
            raw = dict(vars(snapshots[selected]))
            raw["metrics"] = {**raw["metrics"], "independent_task_ids": [*raw["metrics"]["independent_task_ids"], "TASK1"]}
            snapshots[selected] = SimpleNamespace(**raw)
            with patch("cp_runtime.evolution.benefits.load_snapshot", side_effect=snapshots), \
                 patch("cp_runtime.evolution.benefits.implementation_evidence", return_value=[]):
                with self.assertRaisesRegex(ArtifactError, "BENEFIT_IMPLEMENTATION_IN_COHORT"):
                    evaluate_benefit(self.project, validation.proposal, implementation_task_id="TASK1", git_baseline=self.commit,
                                     implementation_commit=self.commit, validation_refs=[], before_ref=self.before_ref, after_ref=self.after_ref)

    def test_root_candidate_followup_recomputes_supported_insufficient_and_tampering(self):
        from cp_runtime.evolution.regression_assets import verify_followups
        from cp_runtime.evolution.artifacts import seal
        for index, age in enumerate((20, 18, 16, 14, 12)):
            task = f"BEFORE-{index}"
            when = (self.now - timedelta(days=age)).isoformat()
            with patch("cp_runtime.evolution.task_feedback.utc_now_iso", return_value=when):
                evidence = run_validation(self.project, task, task, task, [sys.executable, "-c", "raise SystemExit(1)"])
                finalize_feedback(self.project, task, task, task, actor="parent:" + task, outcome="FAILED",
                                  failure_category="ROUTING", routing_deviation="WRONG_DOMAIN", repair_rounds=1,
                                  evidence_paths=[evidence["reference"]["path"]], root_cause_id="WRONG-SKILL", root_cause_confirmed=True)
        before = self.service.observe(window_start=(self.now - timedelta(days=21)).isoformat(), window_end=(self.now - timedelta(days=11)).isoformat())
        self.before_ref = persist_snapshot(self.project, before)
        self.proposal = next(item for item in self.service.propose(before, self.service.analyze(before))
                             if item.hypothesis["scope"]["metric_target"] == "root_cause_id:wrong-skill")
        self.registry.register(self.proposal)
        self.registry.decide(self.proposal.proposal_id, DecisionType.ACCEPT, "human", "Approve independent implementation.")
        self.implement()
        short = self.service.observe(window_start=(self.now - timedelta(days=10)).isoformat(), window_end=(self.now - timedelta(days=8)).isoformat())
        self.registry.observe_benefit(self.proposal.proposal_id, "parent:TASK1", self.before_ref, persist_snapshot(self.project, short))
        after = self.service.observe(window_start=(self.now - timedelta(days=10)).isoformat(), window_end=self.now.isoformat())
        self.after_ref = persist_snapshot(self.project, after)
        self.registry.observe_benefit(self.proposal.proposal_id, "parent:TASK1", self.before_ref, self.after_ref)
        views = {view.proposal.proposal_id: view for view in self.registry.list()}
        followups = verify_followups(self.project, views)
        self.assertEqual({"SUPPORTED", "INSUFFICIENT"}, {row["status"] for row in followups})
        self.assertTrue(all(row["baseline_recurrence_rate"] == 1 and row["observed_recurrence_rate"] == 0 for row in followups))
        self.assertEqual(4, self.registry.validate()["verified_regression_followup_count"])
        path = next((self.project / "evolution/regression-followups").glob("*.json"))
        row = json.loads(path.read_text())
        row["observed_recurrence_rate"] = 1
        path.write_text(json.dumps(seal(row)))
        with self.assertRaisesRegex(ArtifactError, "REGRESSION_FOLLOWUP_RECOMPUTATION_MISMATCH"):
            self.registry.validate()

    def test_rollback_requires_validation_at_a_clean_baseline(self):
        validation = self.implement()
        with self.assertRaises(ArtifactError):
            self.registry.close(self.proposal.proposal_id, "parent:TASK1", "ROLLED_BACK")
        view = self.registry.close(self.proposal.proposal_id, "parent:TASK1", "ROLLED_BACK", [validation["reference"]["path"]])
        self.assertEqual("ROLLED_BACK", view.final_outcome)


if __name__ == "__main__":
    unittest.main()
