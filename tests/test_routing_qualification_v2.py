"""中文：合成证明与资格回归，不构成真实模型资格。

English: Synthetic proof/qualification regressions; never real model qualification.
"""
from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
from cp_runtime import budget_v5 as budget, review_v5 as review, routing_evaluation_v5 as evaluation
from cp_runtime.routing_cards import (build_bundle, derived_cards, validate_bundle,
                                     validate_context_experiment, validate_experiment)
from cp_runtime.routing_context_contract import create_bundle
from cp_runtime.routing_contract import RoutingError, policy_digest, ref
from cp_runtime.routing_evaluation_v4 import trial_packet
from cp_runtime.routing_qualification_plan import zero_discordance_plan
import v4_fixtures as fx
import test_routing_context_transport_v2 as transport


def context_experiment(n=253):
    experiment = fx.experiment(n, profiles=("g56-sol-medium", "g6-sol-medium"), origin="desktop-evaluation")
    experiment["schema_version"] = "routing-experiment/2"
    experiment["qualification_source"]={"study":{"path":str(Path(tempfile.gettempdir())/"absent-synthetic-study.json"),
        "sha256":ref("synthetic-study")},"trials":{"path":str(Path(tempfile.gettempdir())/"absent-synthetic-trials.json"),
        "sha256":ref("synthetic-trials")},"audit_ref":ref("synthetic-audit")}
    old_loader = fx.trace_loader(experiment)
    traces = {}
    for row in experiment["samples"]:
        trace = old_loader(row["receipt_ref"])
        trace.update(schema_version="desktop-evaluation-trace/3", transport_mode="desktop-authoritative-context/2",
                     context_delivery_ref=ref("delivery-" + row["sample_id"]),
                     native_final_ref=ref("final-" + row["sample_id"]), recovery_ref=ref("recovery-" + row["sample_id"]),
                     result_status="pass", native_response_verified=True)
        traces[row["receipt_ref"]] = trace
    return experiment, traces


class QualificationPlanTests(unittest.TestCase):
    def test_current_exact_bound_planning(self):
        for comparisons, clean, quality in ((1,252,99),(2,286,113),(3,306,121),(6,340,134),(9,360,142)):
            with self.subTest(comparisons=comparisons):
                plan = zero_discordance_plan(comparisons)
                self.assertEqual(clean, plan["independent_clean_cases"])
                self.assertEqual(quality, plan["independent_quality_cases"])
                self.assertEqual(policy_digest(), plan["policy_digest"])
                self.assertFalse(plan["qualification_granted"])

    def test_planning_rejects_invalid_families(self):
        for value in (0, -1, True, 154, "1"):
            with self.subTest(value=value), self.assertRaises(RoutingError):
                zero_discordance_plan(value)


class VersionedConsumerTests(unittest.TestCase):
    def test_consumers_do_not_silently_upgrade_or_downgrade(self):
        new, traces = context_experiment(3)
        self.assertEqual(new, validate_context_experiment(new, trace_loader=traces.__getitem__, require_native=True))
        with self.assertRaisesRegex(RoutingError, "EXPERIMENT_(VERSION|FIELDS)"):
            validate_experiment(new, trace_loader=traces.__getitem__, require_native=True)
        old = copy.deepcopy(new)
        old["schema_version"] = "routing-experiment/1"
        old.pop("qualification_source")
        with self.assertRaisesRegex(RoutingError, "NATIVE_TRACE_FIELDS"):
            validate_experiment(old, trace_loader=traces.__getitem__, require_native=True)
        with self.assertRaisesRegex(RoutingError, "EXPERIMENT_(VERSION|FIELDS)"):
            validate_context_experiment(old)
        with self.assertRaisesRegex(RoutingError, "NATIVE_TRACE_FIELDS"):
            validate_context_experiment(new, trace_loader=fx.trace_loader(new), require_native=True)

    def test_invalid_final_proof_and_failure_accounting_never_qualify(self):
        experiment, original = context_experiment(3)
        receipt = experiment["samples"][0]["receipt_ref"]
        for field, value in (("native_response_verified",False),("result_status","incomplete"),
                             ("native_final_ref",""),("recovery_ref",""),
                             ("transport_mode","desktop-authoritative-context/1")):
            traces = copy.deepcopy(original)
            traces[receipt][field] = value
            with self.subTest(field=field), self.assertRaises(RoutingError):
                validate_context_experiment(experiment, trace_loader=traces.__getitem__, require_native=True)

    def test_missing_plan_units_duplicate_calls_and_foreign_profiles_reject(self):
        original, traces = context_experiment(3)
        missing = copy.deepcopy(original)
        missing["samples"].pop()
        with self.assertRaisesRegex(RoutingError, "PLANNED_TRIALS_MISSING"):
            validate_context_experiment(missing, trace_loader=traces.__getitem__, require_native=True)
        duplicate = copy.deepcopy(original)
        duplicate["samples"][1]["call_ref"] = duplicate["samples"][0]["call_ref"]
        with self.assertRaisesRegex(RoutingError, "NATIVE_TRIAL_REUSED"):
            validate_context_experiment(duplicate)
        traces[original["samples"][0]["receipt_ref"]]["profile_id"] = "g6-luna-low"
        with self.assertRaisesRegex(RoutingError, "BINDING_MISMATCH"):
            validate_context_experiment(original, trace_loader=traces.__getitem__, require_native=True)

    def test_equal_answer_bytes_are_not_duplicate_native_calls(self):
        experiment, traces = context_experiment(3)
        shared = ref("same independently produced answer")
        for row in experiment["samples"]:
            row["response_ref"] = shared
            traces[row["receipt_ref"]]["response_ref"] = shared
        validate_context_experiment(experiment, trace_loader=traces.__getitem__, require_native=True)

    def test_statistics_are_unchanged_and_publication_still_needs_whole_study(self):
        experiment, traces = context_experiment()
        qualification, _ = derived_cards(experiment)
        self.assertTrue(all(card["qualified"] for card in qualification))
        too_small, _ = context_experiment(31)
        card = next(c for c in derived_cards(too_small)[0] if c["profile_id"] == "g6-sol-medium")
        self.assertIn("FALSE_BLOCK_MARGIN_NOT_ESTABLISHED", card["reasons"])
        bundle = build_bundle(experiment, fx.costs(experiment), bundle_id="synthetic-context2",
                              created_at=fx.NOW, expires_at=fx.EXPIRES)
        self.assertEqual("routing-card-bundle/2", bundle["schema_version"])
        validate_bundle(bundle, experiment, now=fx.NOW, production=False)
        with self.assertRaisesRegex(RoutingError, "CONTEXT_QUALIFICATION_STUDY_UNAVAILABLE"):
            validate_bundle(bundle, experiment, now=fx.NOW, trace_loader=traces.__getitem__)


class NativeGradeTests(unittest.TestCase):
    def setUp(self):
        self.fixture = transport.TransportV2Tests(methodName="runTest")
        original_prepare = review.prepare

        def prepare(directory, request, **kwargs):
            profile = request["constraints"]["allowed_profiles"][0]
            request["packet_sha256"] = trial_packet(request["evaluation_case_ref"], profile, 1)
            root = Path(directory).parent
            request["context_bundle"] = create_bundle(root/"qualification-bundle.json", repo=root/"repo",
                business_prompt=root/"prompt.txt", packet_sha256=request["packet_sha256"],
                baseline_sha256=request["baseline_sha256"], artifacts={})
            return original_prepare(directory, request, **kwargs)

        with patch.object(review, "prepare", prepare):
            self.fixture.setUp()
        self.path = self.fixture.path
        self.root = self.fixture.f.f.root
        original_final=self.fixture.final
        def final(payload=None,outcome="UNKNOWN",stop=True):
            from cp_runtime.context_tool_surface import reader_program
            result=original_final(payload,outcome,stop=False)
            holder=self.fixture.f
            state=budget.read_budget(self.path)
            request=state["permits"][holder.pid]["request"]
            program=reader_program(self.path,state,request,"desktop-session",holder.child)
            from cp_runtime.routing_hook_v5 import _grant_path
            grant=json.loads(_grant_path(self.path,"desktop-session",holder.child).read_text(encoding="utf8"))
            visible=[{"type":"input_text","text":"Script completed\nWall time 0.1 seconds\nOutput:\n"},
                     {"type":"input_text","text":json.dumps({"exit_code":0,"output":grant["output"]})}]
            events=[json.loads(line) for line in holder.transcript.read_text(encoding="utf8").splitlines()]
            call_id="program-"+holder.parent["tool_use_id"]
            events[2:2]=[
                {"type":"response_item","payload":{"type":"custom_tool_call","name":"exec",
                    "call_id":call_id,"input":program}},
                {"type":"response_item","payload":{"type":"custom_tool_call_output","call_id":call_id,
                    "output":visible}}]
            holder.transcript.write_text("\n".join(json.dumps(e) for e in events)+"\n",encoding="utf8")
            if stop:holder.stop(outcome)
            return result
        self.fixture.final=final
        self.gold = self.root/"gold.json"
        self.rubric = self.root/"rubric.json"
        self.gold.write_text(json.dumps("gold-0"), encoding="utf8")
        self.rubric.write_text(json.dumps("synthetic-rubric"), encoding="utf8")

    def tearDown(self):
        self.fixture.tearDown()

    def complete(self):
        self.fixture.begin()
        self.fixture.read()
        self.fixture.final()
        review.record_semantic(self.fixture.f.review_dir, self.fixture.f.pid, self.fixture.response)
        self.rid = next(iter(budget.read_budget(self.path)["reservations"]))

    def record(self, **flags):
        return evaluation.record_trial(self.path, cwd=str(self.fixture.f.f.repo), host_session_id="desktop-session",
            reservation_id=self.rid, repetition=1, response_path=self.fixture.response,
            gold_path=self.gold, rubric_path=self.rubric,
            transcript_path=self.fixture.f.transcript,
            grade={"passed":True,"false_block":False,"critical_failure":False,"boundary_failure":False,**flags})

    def test_grade_is_idempotent_and_cannot_overwrite_model_result(self):
        self.complete()
        before = self.path.read_bytes()
        recorded = self.record()
        self.assertEqual(recorded, self.record())
        self.assertEqual(before, self.path.read_bytes())
        with self.assertRaisesRegex(RoutingError, "GRADE_IMMUTABLE"):
            self.record(passed=False)

    def test_source_reconstruction_requires_closed_and_exact_native_answer(self):
        self.complete()
        recorded = self.record()
        source = dict(ledger=str(self.path), result=recorded["result_path"], response=str(self.fixture.response),
                      gold=str(self.gold), rubric=str(self.rubric),transcript=str(self.fixture.f.transcript))
        with self.assertRaisesRegex(RoutingError, "NOT_FINALIZED"):
            evaluation.read_trial(source)
        review.close(self.fixture.f.review_dir, conclusion="PASS")
        budget.close(self.path, outcome="PASS", evidence_ref=ref("synthetic-test-only"))
        sample, trace, plan = evaluation.read_trial(source)
        self.assertTrue(sample["passed"])
        self.assertEqual("desktop-evaluation-trace/4", trace["schema_version"])
        self.assertTrue(trace["native_response_verified"])
        self.assertEqual(plan["protocol_ref"], trace["protocol_ref"])
        self.fixture.response.write_text(self.fixture.response.read_text(encoding="utf8").replace("reviewed", "changed"),encoding="utf8")
        with self.assertRaisesRegex(RoutingError, "FINAL_BINDING"):
            evaluation.read_trial(source)

    def test_changed_gold_or_rubric_is_rejected_before_grading(self):
        self.complete()
        for path in (self.gold, self.rubric):
            old = path.read_bytes()
            path.write_text('"changed"',encoding="utf8")
            with self.subTest(path=path.name), self.assertRaisesRegex(RoutingError, "PROTOCOL_BINDING"):
                self.record()
            path.write_bytes(old)

    def test_two_native_calls_can_accept_identical_answers_without_overwrite(self):
        self.complete()
        first_state = budget.read_budget(self.path)
        first_result = first_state["accepted_results"][self.rid]
        first_bytes = self.fixture.response.read_bytes()
        holder = self.fixture.f
        request = copy.deepcopy(holder.request)
        case = holder.f.evaluation["cases"][1]
        request["evaluation_case_ref"] = case["case_ref"]
        request["business_prompt_sha256"] = case["prompt_ref"][7:]
        request["packet_sha256"] = trial_packet(case["case_ref"], "g6-sol-medium", 1)
        second_prompt = self.root/"second-prompt.txt"
        second_prompt.write_text(json.dumps("synthetic-prompt-1"),encoding="utf8")
        request["context_bundle"] = create_bundle(self.root/"second-qualification-bundle.json", repo=holder.f.repo,
            business_prompt=second_prompt, packet_sha256=request["packet_sha256"],
            baseline_sha256=request["baseline_sha256"], artifacts={})
        request["expected"] = {}
        budget.advance_evaluation(self.path, slot_id=request["slot_id"],
            previous_result_ref=first_result["result_ref"], next_packet_sha256=request["packet_sha256"])
        selected = review.prepare(holder.review_dir, request, dispatch_key="eval_two", depth=1,
            snapshot_loader=holder.loader, transition={"reason":"EVALUATION_NEXT",
                "prior_reservation_id":self.rid,"prior_result_ref":first_result["result_ref"]})
        self.assertEqual("EVALUATION_SELECTED", selected["status"])
        holder.pid = selected["permit_id"]
        holder.parent["tool_use_id"] = "spawn-two"
        holder.parent["tool_input"] = {**selected["request_parameters"], "task_name":"eval_two",
                                        "fork_turns":"none", "message":"opaque-data"}
        holder.child = "12345678-1234-1234-1234-123456789013"
        holder.transcript = holder.transcript.with_name("rollout-"+holder.child+".jsonl")
        holder.header["payload"]["id"] = holder.child
        holder.header["payload"]["source"]["subagent"]["thread_spawn"]["agent_path"] = "/root/eval_two"
        holder.transcript.write_text(json.dumps(holder.header)+"\n",encoding="utf8")
        holder.child_data.update(agent_id=holder.child,transcript_path=str(holder.transcript))
        self.fixture.begin()
        self.fixture.read()
        self.fixture.final()
        self.assertEqual(first_bytes, self.fixture.response.read_bytes())
        review.record_semantic(holder.review_dir, holder.pid, self.fixture.response)
        final_state = budget.read_budget(self.path)
        accepted = list(final_state["accepted_results"].values())
        self.assertEqual(2, len(accepted))
        self.assertEqual(1, len({item["response_ref"] for item in accepted}))
        self.assertEqual(2, len({item["result_ref"] for item in accepted}))
        self.assertEqual(2, final_state["_usage_cache"]["resources"]["attempts"])
        self.assertEqual(first_result, final_state["accepted_results"][self.rid])

    def test_incomplete_native_answer_cannot_be_relabelled_by_parent(self):
        self.fixture.begin()
        self.fixture.read()
        self.fixture.final({"status":"incomplete","findings":[],"checked_scope":[],
                            "unverified_items":["required material"],"summary":"Incomplete review."})
        review.record_semantic(self.fixture.f.review_dir, self.fixture.f.pid, self.fixture.response)
        self.rid = next(iter(budget.read_budget(self.path)["reservations"]))
        with self.assertRaisesRegex(RoutingError, "GRADE_CONTRADICTS_NATIVE_INCOMPLETE"):
            self.record()
        recorded = self.record(passed=False)
        self.assertFalse(recorded["model_passed"])

    def test_malformed_but_native_answer_is_preserved_as_a_failed_model_sample(self):
        self.fixture.begin()
        self.fixture.read()
        with self.assertRaises(ValueError):
            self.fixture.final("Malformed structured response from the model")
        state=budget.read_budget(self.path)
        self.rid=next(iter(state["reservations"]))
        self.assertTrue(state["context_raw_finals"])
        self.assertFalse(state["context_finals"])
        before=self.fixture.response.read_bytes()
        review.record_failure_accounting(self.fixture.f.review_dir,self.fixture.f.pid,
            evidence_ref=state["context_raw_finals"][self.rid]["response_ref"])
        with self.assertRaisesRegex(RoutingError,"GRADE_CONTRADICTS_NATIVE_INCOMPLETE"):
            self.record()
        saved=self.record(passed=False)
        self.assertEqual(before,self.fixture.response.read_bytes())
        review.close(self.fixture.f.review_dir,conclusion="PARTIAL")
        budget.close(self.path,outcome="PARTIAL",evidence_ref=ref("synthetic-malformed-model-result"))
        source=dict(ledger=str(self.path),result=saved["result_path"],response=str(self.fixture.response),
            gold=str(self.gold),rubric=str(self.rubric),transcript=str(self.fixture.f.transcript))
        sample,trace,_=evaluation.read_trial(source)
        self.assertFalse(sample["passed"])
        self.assertEqual("invalid",trace["result_status"])
        self.assertEqual("incomplete",trace["accounted_status"])
        self.assertTrue(trace["native_response_verified"])


if __name__ == "__main__":
    unittest.main()
