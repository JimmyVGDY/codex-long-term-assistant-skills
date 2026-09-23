"""中文：管理接口走完整合成实验链，禁止称为真实模型评测。

English: Complete management flow with synthetic host events, not model evidence.
"""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path

import test_routing_v4_context as fixtures
from cp_runtime import budget_v4, routing_evaluation_v4 as evaluation
from cp_runtime.routing_contract import RoutingError, ref, resource_need
from cp_runtime.routing_cards import build_bundle, protocol_reference
from cp_runtime.routing_context_v4 import read_evaluation, validate_evaluation_suite


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.ContextTests(methodName="runTest")
        self.fixture.setUp()
        self.root, self.ledger = self.fixture.root, self.fixture.path
        self.rubric = self.root / "rubric.txt"
        self.rubric.write_text(json.dumps("synthetic-rubric"), encoding="utf-8")
        self.cases = []
        for i in range(2):
            prompt, gold = self.root / f"prompt-{i}.txt", self.root / f"gold-{i}.txt"
            prompt.write_text(json.dumps(f"synthetic-prompt-{i}"), encoding="utf-8")
            gold.write_text(json.dumps(f"gold-{i}"), encoding="utf-8")
            self.cases.append((prompt, gold))

    def tearDown(self):
        self.fixture.tearDown()

    def make(self, case=0, profile="g6-sol-medium"):
        return evaluation.make_request(self.ledger, cwd=str(self.fixture.repo), host_session_id="desktop-session",
            slot_id="evaluation", case_id=f"case-{case}", profile_id=profile, repetition=1,
            prompt_path=self.cases[case][0])

    def test_frozen_manifest_rebuilds_from_exact_case_sources(self):
        spec = {key: self.fixture.evaluation[key] for key in evaluation.PLAN_FIELDS}
        rows = [{"case_id": f"case-{i}", "cluster_id": f"cluster-{i}", "prompt_path": str(prompt),
                 "gold_path": str(gold), "clean": i == 0, "critical": i == 1}
                for i, (prompt, gold) in enumerate(self.cases)]
        self.assertEqual(self.fixture.evaluation, evaluation.create_plan(spec, rows))
        spec["minimum_pass_bp"] = 1
        with self.assertRaisesRegex(RoutingError, "QUALITY_FLOOR"):
            evaluation.create_plan(spec, rows)

    def test_changed_case_source_or_out_of_plan_profile_never_prepares(self):
        self.cases[0][0].write_text("different prompt", encoding="utf-8")
        with self.assertRaisesRegex(RoutingError, "SOURCE_MISMATCH"):
            self.make()
        with self.assertRaisesRegex(RoutingError, "SOURCE_MISMATCH"):
            self.make(1, "g6-astra-high")

    def suite_plans(self):
        second = copy.deepcopy(self.fixture.evaluation)
        second["scenario"]["phase"] = "pre"
        second["comparisons"][0]["challenger"] = "g6-luna-high"
        for cost in second["costs"]:
            cost["scenario_ref"] = ref(second["scenario"])
            if cost["profile_id"] == "g6-sol-high":
                cost["profile_id"] = "g6-luna-high"
        for case in second["cases"]:
            case["case_id"] = "pre-" + case["case_id"]
            case["cluster_id"] = "pre-" + case["cluster_id"]
            case["case_ref"] = ref({key: value for key, value in case.items() if key != "case_ref"})
        second["case_plan"] = sorted(case["case_ref"] for case in second["cases"])
        second["protocol_ref"] = protocol_reference(second)
        return [copy.deepcopy(self.fixture.evaluation), second]

    def test_suite_keeps_pairwise_trial_count_and_rejects_ambiguous_or_foreign_cases(self):
        plans = self.suite_plans()
        suite = evaluation.create_suite(plans)
        self.assertEqual(8, suite["planned_trials"])
        with self.assertRaisesRegex(RoutingError, "TRIAL_COUNT"):
            validate_evaluation_suite({**suite, "planned_trials": 12})
        duplicate = copy.deepcopy(plans)
        duplicate[1]["cases"] = copy.deepcopy(duplicate[0]["cases"])
        duplicate[1]["case_plan"] = duplicate[0]["case_plan"]
        duplicate[1]["protocol_ref"] = protocol_reference(duplicate[1])
        with self.assertRaisesRegex(RoutingError, "CASE_AMBIGUOUS"):
            evaluation.create_suite(duplicate)
        foreign = copy.deepcopy(plans)
        foreign[1]["identity"]["project_id"] = "other-project"
        foreign[1]["protocol_ref"] = protocol_reference(foreign[1])
        with self.assertRaisesRegex(RoutingError, "SUITE_IDENTITY"):
            evaluation.create_suite(foreign)

    def test_multiple_scenarios_share_one_budget_and_keep_protocol_specific_traces(self):
        from cp_runtime.evidence import record_evidence
        from test_routing_v4_selection_phase import plan, slot
        original = budget_v4.read_budget(self.ledger)
        plans = self.suite_plans()
        suite = evaluation.create_suite(plans)
        suite_path = self.root / "suite.json"
        fixtures.write(suite_path, suite)
        sources = copy.deepcopy(original["sources"])
        sources.update(evaluation_costs=str(suite_path), evaluation_ref=ref(suite))
        evidence = self.root / "pre-evidence.json"
        record_evidence(evidence, "pre-evidence", self.fixture.project.profile_path,
            self.fixture.identity["task_id"], self.fixture.repo, "review", "Synthetic pre experiment", "valid",
            "parent-reviewed-v4-requirements", "Fixture only", ["scenario:" + ref(plans[1]["scenario"]),
                "protocol:" + plans[1]["protocol_ref"], "independent-review-required"])
        sources["evidence_paths"][evaluation.file_reference(evidence)] = str(evidence)
        self.fixture.capability["available_profiles"].append("g6-luna-high")
        fixtures.write(self.fixture.cap_path, self.fixture.capability)
        slots = []
        for i, item in enumerate(plans):
            options = [{"profile_id": cost["profile_id"], "cost_ref": ref(cost),
                "qualification_ref": ref("evaluation-only"),
                "resources": resource_need(cost["profile_id"], cost["reserve_units"])} for cost in item["costs"]]
            current = slot(f"suite-{i}", options, phase=item["scenario"]["phase"])
            current["scenario"] = item["scenario"]
            slots.append(current)
        phase_plan = plan(slots)
        phase_plan["identity"] = suite["identity"]
        path = self.root / "suite-budget.jsonl"
        init = {"declared_identity": original["identity"], "root_binding": original["root_binding"],
            "sources": sources, "execution_mode": "EVALUATION",
            "capacity": {**original["capacity"], "units": 200, "attempts": 8},
            "role_capacity": {"reviewer": 200, "worker": 0, "explorer": 0},
            "phase_capacity": {"pre": 100, "post": 100, "repair": 0},
            "phase_plan": phase_plan}
        budget_v4.initialize(path, **init)
        with self.assertRaisesRegex(RoutingError, "MISSING_OR_AMBIGUOUS"):
            read_evaluation(budget_v4.read_budget(path))
        for i, item in enumerate(plans):
            case = item["cases"][0]
            selected_profile = item["comparisons"][0]["challenger"]
            request = evaluation.make_request(path, cwd=str(self.fixture.repo), host_session_id="desktop-session",
                slot_id=f"suite-{i}", case_id=case["case_id"], profile_id=selected_profile,
                repetition=1, prompt_path=self.cases[0][0])
            selected = budget_v4.prepare(path, request, dispatch_key=f"suite-call-{i}", depth=1,
                snapshot_loader=self.fixture.loader)
            self.assertEqual("EVALUATION_SELECTED", selected["status"])
            params = selected["request_parameters"]
            attempt = budget_v4.approve_and_reserve(path, permit_id=selected["permit_id"],
                host_dispatch_id=f"suite-call-{i}", model=params["model"], effort=params["reasoning_effort"],
                agent_type=params["agent_type"], message_sha256=request["message_sha256"],
                snapshot_loader=self.fixture.loader)
            budget_v4.record_receipt(path, host_dispatch_id=f"suite-call-{i}", agent_id=f"suite-agent-{i}")
            budget_v4.record_observation(path, agent_id=f"suite-agent-{i}", phase="stop")
            response = self.root / f"suite-response-{i}.txt"
            response.write_text("Synthetic response", encoding="utf-8")
            result = evaluation.record_trial(path, cwd=str(self.fixture.repo), host_session_id="desktop-session",
                reservation_id=attempt["reservation_id"], repetition=1, response_path=response,
                gold_path=self.cases[0][1], rubric_path=self.rubric,
                grade={"passed": True, "false_block": False, "critical_failure": False, "boundary_failure": False})
            trial = json.loads(Path(result["result_path"]).read_text(encoding="utf-8"))
            self.assertEqual(item["protocol_ref"], trial["protocol_ref"])
        state = budget_v4.initialize(path, **init)
        self.assertEqual(2, state["_usage_cache"]["resources"]["attempts"])
        self.assertEqual(20, state["_usage_cache"]["resources"]["units"])
        budget_v4.close(path, outcome="PARTIAL", evidence_ref=ref("only-two-trials-exercised"))
        traces = budget_v4.export_traces(path)
        self.assertEqual({item["protocol_ref"] for item in plans}, {item["protocol_ref"] for item in traces.values()})
        suite["planned_trials"] = 1
        fixtures.write(suite_path, suite)
        with self.assertRaisesRegex(RoutingError, "PROTOCOL_BINDING"):
            budget_v4.export_traces(path)

    def test_internal_suite_entry_preregisters_exact_total(self):
        paths = []
        for i, plan in enumerate(self.suite_plans()):
            path = self.root / f"plan-{i}.json"
            fixtures.write(path, plan)
            paths.append(str(path))
        sources, output = self.root / "plans.json", self.root / "suite-output.json"
        fixtures.write(sources, {"paths": paths})
        args = [sys.executable, "-B", str(Path(__file__).resolve().parents[1] / "scripts" / "routing-v4.py"),
                "eval-suite", "--plans", str(sources), "--output", str(output)]
        result = subprocess.run(args, cwd=self.fixture.repo, capture_output=True, text=True, encoding="utf-8", timeout=20)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual(8, json.loads(result.stdout)["planned_trials"])

    def test_complete_experiment_requires_every_trial_and_keeps_quality_unqualified(self):
        revised = copy.deepcopy(budget_v4.read_budget(self.ledger)["phase_plan"])
        cost = next(row for row in self.fixture.evaluation["costs"] if row["profile_id"] == "g6-sol-high")
        revised["slots"][0]["options"].append({"profile_id": cost["profile_id"],
            "qualification_ref": ref("evaluation-only"), "cost_ref": ref(cost),
            "resources": resource_need(cost["profile_id"], cost["reserve_units"])})
        revised["revision"] += 1
        budget_v4.revise_plan(self.ledger, revised, reason_ref=ref("complete-preregistered-options"))
        sources, previous = [], None
        for i, (case, profile) in enumerate([(0, "g6-sol-medium"), (1, "g6-sol-medium"),
                                             (0, "g6-sol-high"), (1, "g6-sol-high")]):
            request = self.make(case, profile)
            transition = None
            if previous:
                budget_v4.advance_evaluation(self.ledger, slot_id="evaluation",
                    previous_result_ref=previous["result_ref"], next_packet_sha256=request["packet_sha256"])
                transition = {"prior_reservation_id": previous["reservation_id"],
                              "prior_result_ref": previous["result_ref"], "reason": "EVALUATION_NEXT"}
            selected = budget_v4.prepare(self.ledger, request, dispatch_key=f"eval-{i}", depth=1,
                snapshot_loader=self.fixture.loader, transition=transition)
            params = selected["request_parameters"]
            attempt = budget_v4.approve_and_reserve(self.ledger, permit_id=selected["permit_id"],
                host_dispatch_id=f"call-{i}", model=params["model"], effort=params["reasoning_effort"],
                agent_type=params["agent_type"], message_sha256=request["message_sha256"],
                snapshot_loader=self.fixture.loader)
            budget_v4.record_receipt(self.ledger, host_dispatch_id=f"call-{i}", agent_id=f"agent-{i}")
            budget_v4.record_observation(self.ledger, agent_id=f"agent-{i}", phase="stop")
            response = self.root / f"response-{i}.txt"
            response.write_text("Synthetic response, no actual model", encoding="utf-8")
            previous = evaluation.record_trial(self.ledger, cwd=str(self.fixture.repo),
                host_session_id="desktop-session", reservation_id=attempt["reservation_id"], repetition=1,
                response_path=response, gold_path=self.cases[case][1], rubric_path=self.rubric,
                grade={"passed": True, "false_block": False, "critical_failure": False, "boundary_failure": False})
            sources.append({"ledger": str(self.ledger), "result": previous["result_path"],
                "response": str(response), "gold": str(self.cases[case][1]), "rubric": str(self.rubric)})
            with self.assertRaisesRegex(RoutingError, "ALREADY_PREPARED"):
                self.make(case, profile)
        state = budget_v4.close(self.ledger, outcome="PASS", evidence_ref=ref("synthetic-finished"))
        self.assertEqual(4, state["_usage_cache"]["resources"]["attempts"])
        def assemble(rows):
            return evaluation.assemble_experiment(self.fixture.evaluation, rows, experiment_id="synthetic-full-flow",
                issuer_task_id=self.fixture.identity["task_id"], issuer_baseline=self.fixture.request["baseline_sha256"])
        with self.assertRaisesRegex(RoutingError, "PLANNED_TRIALS_MISSING"):
            assemble(sources[:3])
        experiment = assemble(sources)
        self.assertEqual(4, len(experiment["samples"]))
        from v4_fixtures import NOW, EXPIRES
        bundle = build_bundle(experiment, self.fixture.evaluation["costs"], bundle_id="synthetic-bundle",
                              created_at=NOW, expires_at=EXPIRES)
        self.assertFalse(any(row["qualified"] for row in bundle["qualification"]))
        Path(sources[0]["response"]).write_text("Modified capture", encoding="utf-8")
        with self.assertRaisesRegex(RoutingError, "SOURCE_BINDING"):
            assemble(sources)

    def test_internal_entry_emits_request_and_rejects_immutable_output_replacement(self):
        output = self.root / "request.json"
        args = [sys.executable, "-B", str(Path(__file__).resolve().parents[1] / "scripts" / "routing-v4.py"),
            "eval-request", "--ledger", str(self.ledger), "--host-session-id", "desktop-session",
            "--slot-id", "evaluation", "--case-id", "case-0", "--profile-id", "g6-sol-medium",
            "--prompt-file", str(self.cases[0][0]), "--output", str(output)]
        first = subprocess.run(args, cwd=self.fixture.repo, capture_output=True, text=True, encoding="utf-8", timeout=20)
        self.assertEqual(0, first.returncode, first.stdout + first.stderr)
        self.assertEqual(self.make(), json.loads(output.read_text(encoding="utf-8")))
        output.write_text('{"schema_version":"different"}', encoding="utf-8")
        second = subprocess.run(args, cwd=self.fixture.repo, capture_output=True, text=True, encoding="utf-8", timeout=20)
        self.assertEqual(2, second.returncode)
        self.assertIn("ARTIFACT_ALREADY_EXISTS", second.stdout)


if __name__ == "__main__":
    unittest.main()
