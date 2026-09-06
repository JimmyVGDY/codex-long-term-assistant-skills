"""中文：跨账本校准、持久恢复与回归候选的集成验收。

English: Integration acceptance for cross-ledger calibration, durable recovery, and regression candidates.
"""
from __future__ import annotations

import json
import base64
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from tests.test_v75_evolution import EvolutionProjectCase, EvolutionHealthTests, ROOT
from cp_runtime.delegation_budget import initialize_budget, record_decision, reserve_budget, mark_started, mark_completed, DelegationBudgetError
from cp_runtime.delegation_calibration import build_pending_sample, finalize_sample, append_sample, offline_replay_many
from cp_runtime.evolution.artifacts import ArtifactError, load
from cp_runtime.evolution.calibration_sources import register_source, project_calibration
from cp_runtime.evolution.service import ControlledEvolutionService
from cp_runtime.evolution.contracts import to_primitive
from cp_runtime.evolution.incremental import run_incremental, configure_automation, automation_tick, LAST_RESULT
from cp_runtime.evolution.regression_assets import create_candidates, verify_candidate
from cp_runtime.evolution.task_feedback import run_validation, finalize_feedback
from cp_runtime.event_v3 import append_event, OwnerTokenLock


class CrossLedgerTests(EvolutionProjectCase):
    def test_duplicate_raw_input_still_obeys_work_limit(self):
        import itertools
        sample, entry = self.sample(1, "luna-low")
        with self.assertRaisesRegex(DelegationBudgetError, "CALIBRATION_SAMPLE_LIMIT"):
            offline_replay_many(itertools.repeat(sample, 10001), ledger_paths=dict([entry]))

    def test_task_interval_uses_conservative_small_sample_critical_values(self):
        import copy, math
        from statistics import mean, stdev
        from cp_runtime.delegation_calibration import compare_scenarios, _score
        sample, _ = self.sample(1, "luna-low")
        for count, critical in ((4, 3.183), (6, 2.777), (11, 2.263), (30, 2.046)):
            rows = []
            for index in range(count):
                row = copy.deepcopy(sample)
                row.update(record_id="DCS_" + str(index).zfill(64), task_id="TASK-" + str(index))
                row["metrics"]["accepted_findings"] = 10 + index
                row["value_score"] = _score(row["role"], row["metrics"])
                rows.append(row)
            result = compare_scenarios(rows)[0]
            values = [row["value_score"] / row["cost_basis_units"] for row in rows]
            self.assertAlmostEqual(mean(values) + critical * stdev(values) / math.sqrt(count), result["lower_yield_interval_95"][1])

    def sample(self, index, profile, *, task=None, difficulty="HIGH", missed=0):
        budget_id = "BUDGET-" + str(index)
        ledger = self.project / "calibration" / (budget_id + ".jsonl")
        samples = self.project / "calibration" / (budget_id + "-samples.jsonl")
        initialize_budget(ledger, budget_id=budget_id, task_id=task or "TASK-" + str(index), project_id=self.project.name,
                          repo_fingerprint=self.event["repo_fingerprint"], budget_class="STRICT", default_dispatch_profile=profile)
        record_decision(ledger, dispatch_key="review", decision="DELEGATE", role="reviewer", approved_profile=profile,
                        reason_code="SEMANTIC_COMPLEXITY", responsibility="schema", difficulty=difficulty,
                        risk_domain="DATA", context_size="MEDIUM")
        reservation = reserve_budget(ledger, dispatch_key="review", host_dispatch_id="dispatch-" + str(index),
                                     approved_profile=profile, approval_basis="explicit-request", role="reviewer")
        mark_started(ledger, reservation_id=reservation["reservation_id"], agent_id="agent-" + str(index))
        mark_completed(ledger, reservation_id=reservation["reservation_id"], outcome="PASS")
        pending = build_pending_sample(ledger, reservation["reservation_id"],
                                       {"accepted_findings": 1, "repaired_findings": 1, "duplicate_findings": 0,
                                        "missed_findings": missed, "regressions_prevented": 0})
        final = finalize_sample(pending, finalized_by="parent:root", evidence_refs=[pending["reservation_completion_ref"]])
        append_sample(samples, final, ledger_path=ledger)
        register_source(self.project, ledger.relative_to(self.project).as_posix(), samples.relative_to(self.project).as_posix())
        return final, (budget_id, ledger)

    def test_distinct_ledgers_share_comparison_with_global_observer(self):
        pairs = [self.sample(index, "luna-low" if index < 5 else "luna-medium") for index in range(10)]
        samples = [pair[0] for pair in pairs]
        direct = offline_replay_many(samples, ledger_paths=dict(pair[1] for pair in pairs))
        comparison = direct["comparisons"][0]
        self.assertEqual(5, comparison["lower_independent_tasks"])
        self.assertEqual("luna-low", comparison["recommendation"])
        self.assertEqual("NONE", direct["execution_authorization"])
        EvolutionHealthTests.populate(self)
        snapshot = ControlledEvolutionService(self.project.parent, self.project.name).observe()
        observed = to_primitive(snapshot.metrics["dispatch_profile_value_comparisons"][0])
        observed.pop("scenario_key")
        self.assertEqual(comparison, observed)
        self.assertEqual(10, project_calibration(self.project)[1]["sample_count"])

    def test_repeated_root_tasks_and_incomparable_difficulty_are_ineligible(self):
        pairs = [self.sample(index, "luna-low" if index < 3 else "luna-medium", task="SAME") for index in range(6)]
        result = offline_replay_many([pair[0] for pair in pairs], ledger_paths=dict(pair[1] for pair in pairs))
        self.assertFalse(result["comparisons"][0]["eligible"])
        self.assertEqual(1, result["comparisons"][0]["higher_independent_tasks"])
        other, entry = self.sample(7, "luna-medium", difficulty="LOW")
        result = offline_replay_many([pairs[0][0], other], ledger_paths=dict([pairs[0][1], entry]),
                                     minimum_samples_per_profile=1, minimum_tasks_per_profile=1)
        self.assertTrue(all(not item["eligible"] for item in result["comparisons"]))

    def test_wrong_ledger_or_mutated_sample_fails_closed(self):
        first, entry = self.sample(1, "luna-low")
        _, other = self.sample(2, "luna-medium")
        with self.assertRaises(DelegationBudgetError):
            offline_replay_many([first], ledger_paths={entry[0]: other[1]})
        first["metrics"]["accepted_findings"] = 100
        with self.assertRaises(DelegationBudgetError):
            offline_replay_many([first], ledger_paths=dict([entry]))


class IncrementalRecoveryTests(EvolutionProjectCase):
    def test_changed_failure_signal_for_existing_tasks_bypasses_threshold_and_cooldown(self):
        EvolutionHealthTests.populate(self)
        service = ControlledEvolutionService(self.project.parent, self.project.name)
        self.assertEqual("ANALYZED", run_incremental(service)["status"])
        with (self.project / "feedback/late-findings.jsonl").open("w", encoding="utf-8") as handle:
            for index in range(5):
                handle.write(json.dumps({"project_id": self.project.name, "repo_fingerprint": self.event["repo_fingerprint"],
                                         "record_id": f"LATE-{index}", "task_id": f"TASK{index}",
                                         "failure_code": "CONFIRMED-LATE-FAILURE", "terminal_outcome": "FAILED"}) + "\n")
        result = run_incremental(service, minimum_new_tasks=100, cooldown_seconds=3600)
        self.assertEqual("ANALYZED", result["status"])
        self.assertEqual(0, result["new_independent_tasks"])
        self.assertTrue(result["signal_changed"])
        self.assertEqual("NO_CHANGE", run_incremental(service)["status"])

    def test_service_run_cannot_bypass_missing_or_damaged_identity(self):
        EvolutionHealthTests.populate(self)
        service = ControlledEvolutionService(self.project.parent, self.project.name)
        (self.project / "project-profile.json").unlink()
        result = service.run()
        self.assertEqual("IDENTITY_UNAVAILABLE", result["health"]["status"])
        self.assertEqual(0, result["proposal_count"])
        self.assertFalse(service.evolution_root.exists())
        (self.project / "project-profile.json").write_text("{}")
        self.assertEqual("DATA_DAMAGED", service.run()["health"]["status"])

    def test_concurrent_ticks_commit_one_transaction(self):
        EvolutionHealthTests.populate(self)
        service = ControlledEvolutionService(self.project.parent, self.project.name)

        def attempt(_):
            try:
                return run_incremental(service)["status"]
            except TimeoutError:
                return "LOCK_TIMEOUT"

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(attempt, range(2)))
        self.assertEqual(1, results.count("ANALYZED"))
        self.assertLessEqual(results.count("LOCK_TIMEOUT"), 1)
        results = [run_incremental(service)["status"] if result == "LOCK_TIMEOUT" else result
                   for result in results]
        self.assertEqual(["ANALYZED", "NO_CHANGE"], sorted(results))
        self.assertEqual(1, len(list((self.project / "evolution/transactions").glob("*.json"))))

    def test_lock_timeout_preserves_watermark_and_worker_retry_is_idempotent(self):
        from cp_runtime.evolution.incremental import RECEIPT
        EvolutionHealthTests.populate(self)
        configure_automation(self.project, enabled=True)
        service = ControlledEvolutionService(self.project.parent, self.project.name)
        with OwnerTokenLock(self.project / "evolution/incremental.guard"):
            with self.assertRaises(TimeoutError):
                run_incremental(service)
            self.assertFalse((self.project / RECEIPT).exists())
            self.assertFalse(list((self.project / "evolution/transactions").glob("*.json")))
            first, second = automation_tick(self.project), automation_tick(self.project)
            self.assertEqual("RETRY_REQUIRED", first["status"])
            self.assertEqual("RETRY_REQUIRED", second["status"])
            self.assertTrue(first["notification_required"])
            self.assertFalse(second["notification_required"])
            self.assertFalse((self.project / RECEIPT).exists())
        self.assertEqual("ANALYZED", automation_tick(self.project)["status"])
        self.assertEqual("NO_CHANGE", run_incremental(service)["status"])
        self.assertEqual(1, len(list((self.project / "evolution/transactions").glob("*.json"))))

    def test_worker_failure_is_durable_quiet_on_repeat_and_retryable(self):
        EvolutionHealthTests.populate(self)
        configure_automation(self.project, enabled=True)
        with patch("cp_runtime.evolution.incremental.run_incremental", side_effect=RuntimeError("private error")):
            self.assertTrue(automation_tick(self.project)["notification_required"])
            self.assertFalse(automation_tick(self.project)["notification_required"])
        state = load(self.project, LAST_RESULT)
        self.assertEqual("RETRY_REQUIRED", state["status"])
        self.assertNotIn("private error", json.dumps(state))
        self.assertEqual("ANALYZED", automation_tick(self.project)["status"])

    def test_no_change_still_checks_persisted_output_integrity(self):
        EvolutionHealthTests.populate(self)
        service = ControlledEvolutionService(self.project.parent, self.project.name)
        first = run_incremental(service)
        (self.project / first["observation_reference"]["path"]).write_text("{}")
        with self.assertRaises(ArtifactError):
            run_incremental(service)


class RegressionCandidateTests(EvolutionProjectCase):
    def test_confirmed_routing_root_generates_idempotent_candidates_with_verified_sources(self):
        EvolutionHealthTests.populate(self, outcome="FAILED")
        for index in range(5):
            task = "ROOT-" + str(index)
            validation = run_validation(self.project, task, task, task, [sys.executable, "-c", "raise SystemExit(1)"])
            finalize_feedback(self.project, task, task, task, actor="parent:" + task, outcome="FAILED",
                              failure_category="ROUTING", routing_deviation="WRONG_DOMAIN", repair_rounds=1,
                              evidence_paths=[validation["reference"]["path"]], root_cause_id="WRONG-SKILL", root_cause_confirmed=True)
            for event_type in ("TURN_OPENED", "TASK_COMPLETED", "SESSION_ENDED"):
                append_event(self.project / "feedback/task-outcome-v3.jsonl",
                             {**self.event, "session_id": task, "task_id": task, "turn_id": task, "event_type": event_type})
        service = ControlledEvolutionService(self.project.parent, self.project.name)
        snapshot = service.observe()
        proposal = next(item for item in service.propose(snapshot, service.analyze(snapshot))
                        if item.hypothesis["scope"]["metric_target"] == "root_cause_id:wrong-skill")
        references = create_candidates(self.project, proposal)
        self.assertEqual(2, len(references))
        self.assertEqual(references, create_candidates(self.project, proposal))
        candidate = verify_candidate(self.project, references[0], proposal)
        self.assertEqual("PENDING_REVIEW", candidate["status"])
        self.assertFalse(candidate["automatic_application"])
        self.assertEqual("NONE", candidate["execution_authorization"])
        (self.project / candidate["source_refs"][0]["path"]).write_text("{}")
        with self.assertRaises(ArtifactError):
            verify_candidate(self.project, references[0], proposal)


class HookFeedbackIntegrationTests(EvolutionProjectCase):
    def test_seal_worker_runs_opted_in_analysis_after_current_seal(self):
        from cp_runtime.integrity import init_keyring, verify_event_seals
        EvolutionHealthTests.populate(self)
        configure_automation(self.project, enabled=True)
        keyring = self.project.parent / "keyring.json"
        init_keyring(keyring)
        terminal = {**self.event, "event_type": "SESSION_ENDED", "metadata": {"seal_required": True}}
        encoded = base64.urlsafe_b64encode(json.dumps(terminal).encode()).decode()
        env = {**os.environ, "CP_ASSISTANT_DATA": str(self.project.parent), "CP_ASSISTANT_KEYRING_PATH": str(keyring)}
        command = [sys.executable, "-B", str(ROOT / "hooks/seal_worker.py"),
                   "--queue", str(self.project / "feedback/seal-queue-v3"), "--keyring", str(keyring),
                   "--bootstrap-event-b64", encoded]
        result = subprocess.run(command, text=True, capture_output=True, env=env, timeout=15)
        self.assertEqual(0, result.returncode, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual("ANALYZED", report["evolution"]["status"])
        self.assertEqual("SEALED_CURRENT", verify_event_seals(self.project / "feedback/task-outcome-v3.jsonl", keyring_path=keyring)["seal_status"])
        second = subprocess.run(command, text=True, capture_output=True, env=env, timeout=15)
        self.assertEqual(0, second.returncode, second.stderr)
        self.assertEqual(1, len(list((self.project / "evolution/transactions").glob("*.json"))))

    def test_host_prompt_binding_validation_cli_and_stop_consume_same_feedback(self):
        env = {**os.environ, "PLUGIN_ROOT": str(ROOT), "CP_PROJECT_ID": self.project.name,
               "CP_ASSISTANT_DATA": str(self.project.parent), "CODEX_HOME": str(self.project.parent / "codex")}
        common = ["--context-root", str(self.project.parent), "--project-id", self.project.name,
                  "--session-id", "S1", "--turn-id", "T1", "--task-id", "TASK1"]
        payload = {**self.event, "cwd": str(self.repo), "hook_event_name": "UserPromptSubmit"}
        prompt = subprocess.run([sys.executable, "-B", str(ROOT / "hooks/cp_hook.py"), "UserPromptSubmit"],
                                input=json.dumps(payload), text=True, capture_output=True, env=env, timeout=5)
        self.assertEqual(0, prompt.returncode, prompt.stderr)
        self.assertIn('"task_id": "TASK1"', json.loads(prompt.stdout)["hookSpecificOutput"]["additionalContext"])
        command = [sys.executable, "-B", str(ROOT / "scripts/evolution.py"), "validate-task", *common,
                   "--", sys.executable, "-c", "raise SystemExit(1)"]
        failed = subprocess.run(command, text=True, capture_output=True, env=env, timeout=8)
        self.assertEqual(1, failed.returncode, failed.stderr)
        command[-1] = "pass"
        validated = subprocess.run(command, text=True, capture_output=True, env=env, timeout=8)
        self.assertEqual(0, validated.returncode, validated.stderr)
        reference = json.loads(validated.stdout)["result"]["reference"]
        finalized = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/evolution.py"), "finalize-task", *common,
                                    "--actor", "parent:TASK1", "--outcome", "PASS", "--failure-category", "NONE",
                                    "--routing-deviation", "MATCHED", "--repair-rounds", "1", "--evidence", reference["path"]],
                                   text=True, capture_output=True, env=env, timeout=8)
        self.assertEqual(0, finalized.returncode, finalized.stderr)
        payload["hook_event_name"] = "Stop"
        stopped = subprocess.run([sys.executable, "-B", str(ROOT / "hooks/cp_hook.py"), "Stop"], input=json.dumps(payload),
                                 text=True, capture_output=True, env=env, timeout=5)
        self.assertEqual("{}", stopped.stdout.strip())
        from cp_runtime.event_v3 import read_event_chain
        terminal = read_event_chain(self.project / "feedback/task-outcome-v3.jsonl")["events"][-1]
        self.assertEqual("UNKNOWN", terminal["terminal_outcome"])
        self.assertEqual("VERIFIED", terminal["metadata"]["feedback_status"])
        snapshot = ControlledEvolutionService(self.project.parent, self.project.name).observe()
        self.assertEqual(1, snapshot.metrics["accepted_count"])
        self.assertEqual(1, snapshot.task_count)
