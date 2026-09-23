"""中文：预登记桌面实验、固定案例与主协调者判定的管理接口。

English: Preregistered Desktop experiments and parent-graded native trials.
Only artifact digests and structured grades enter the budget/result records.
"""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path
from typing import Any, Mapping

from . import budget_v4
from .common import atomic_write_json, parse_iso, repo_snapshot, require_external_state
from .routing_cards import protocol_reference, validate_experiment
from .routing_context_v4 import (current_evidence_refs, read_evaluation, validate_evaluation,
                                 validate_evaluation_suite, verify_root)
from .routing_contract import boolean, exact, fail, identifier, integer, policy, policy_digest, read_document, ref, sha

PLAN_FIELDS = {"identity", "scenario", "rubric_ref", "minimum_pass_bp", "baseline_profile",
               "comparisons", "repetitions", "costs"}
GRADE_FIELDS = {"passed", "false_block", "critical_failure", "boundary_failure"}
TRIAL_FIELDS = {"schema_version", "identity", "reservation_id", "protocol_ref", "case_ref", "profile_id",
                "repetition", "response_ref", "gold_ref", "rubric_ref", "grade", "finalizer"}


def file_reference(path: Path, *, prompt: bool = False) -> str:
    maximum = policy()["limits"]["max_experiment_bytes"]
    with path.open("rb") as stream:
        raw = stream.read(maximum + 1)
    if not raw or len(raw) > maximum:
        fail("EVALUATION_ARTIFACT_SIZE")
    if prompt:
        raw = raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def create_plan(specification: Mapping[str, Any], cases: list[Mapping[str, Any]]) -> dict[str, Any]:
    exact(dict(specification), PLAN_FIELDS, "EVALUATION_PLAN_SPEC_FIELDS")
    if not isinstance(cases, list) or not cases or len(cases) > 10000:
        fail("EVALUATION_CASE_LIMIT")
    rows = []
    for case in cases:
        exact(dict(case), {"case_id", "cluster_id", "prompt_path", "gold_path", "clean", "critical"},
              "EVALUATION_CASE_SOURCE_FIELDS")
        value = {key: case[key] for key in ("case_id", "cluster_id", "clean", "critical")}
        value.update(prompt_ref=file_reference(Path(case["prompt_path"]), prompt=True),
                     gold_ref=file_reference(Path(case["gold_path"])))
        value["case_ref"] = ref(value)
        rows.append(value)
    value = {"schema_version": "routing-evaluation/1", **copy.deepcopy(dict(specification)),
             "family_intervals": 4 * len(specification["comparisons"]), "cases": rows,
             "case_plan": sorted(row["case_ref"] for row in rows), "protocol_ref": ""}
    value["protocol_ref"] = protocol_reference(value)
    return validate_evaluation(value)


def trial_packet(case_ref: str, profile_id: str, repetition: int) -> str:
    return ref({"case_ref": case_ref, "profile_id": profile_id, "repetition": repetition})[7:]


def create_suite(plans: list[Mapping[str, Any]]) -> dict[str, Any]:
    if not isinstance(plans, list) or not plans or len(plans) > policy()["limits"]["max_slots"]:
        fail("EVALUATION_SUITE_LIMIT")
    items = [validate_evaluation(item) for item in plans]
    total = sum(len(item["cases"]) * item["repetitions"] * len({
        name for pair in item["comparisons"] for name in pair.values()}) for item in items)
    return validate_evaluation_suite({"schema_version": "routing-evaluation-suite/1",
        "identity": items[0]["identity"], "evaluations": items, "planned_trials": total})


def make_request(ledger_path: Path, *, cwd: str, host_session_id: str, slot_id: str,
                 case_id: str, profile_id: str, repetition: int, prompt_path: Path) -> dict[str, Any]:
    state = budget_v4.read_budget(ledger_path)
    verify_root(state, cwd=cwd, host_session_id=host_session_id)
    if state["execution_mode"] != "EVALUATION" or state["closed"]:
        fail("EVALUATION_ROOT_NOT_OPEN")
    evaluation = read_evaluation(state, case_id=case_id)
    integer(repetition, "EVALUATION_REPETITION", minimum=1, maximum=evaluation["repetitions"])
    matches = [case for case in evaluation["cases"] if case["case_id"] == case_id]
    if len(matches) != 1:
        fail("EVALUATION_CASE_MISSING_OR_AMBIGUOUS")
    case = matches[0]
    profiles = {name for pair in evaluation["comparisons"] for name in pair.values()}
    if profile_id not in profiles or file_reference(prompt_path, prompt=True) != case["prompt_ref"]:
        fail("EVALUATION_REQUEST_SOURCE_MISMATCH")
    packet = trial_packet(case["case_ref"], profile_id, repetition)
    if any(permit["request"]["packet_sha256"] == packet and permit["status"] != "REVOKED"
           for permit in state["permits"].values()):
        fail("EVALUATION_TRIAL_ALREADY_PREPARED")
    evidence_refs = current_evidence_refs(state, scenario_ref=ref(evaluation["scenario"]),
                                           scope_ref="protocol:" + evaluation["protocol_ref"])
    return {"schema_version": "routing-request/1", "task_id": state["identity"]["task_id"],
            "identity": evaluation["identity"], "policy_digest": policy_digest(), "scenario": evaluation["scenario"],
            "execution_mode": "EVALUATION", "mode": "economy", "slot_id": identifier(slot_id),
            "baseline_sha256": repo_snapshot(Path(cwd))["sha256"], "packet_sha256": packet,
            "message_sha256": case["prompt_ref"][7:], "evaluation_case_ref": case["case_ref"],
            "constraints": {"allowed_profiles": [profile_id], "deadline_ms": None, "strict_wallclock": False},
            "evidence": {"ready": bool(evidence_refs), "independence_required": True, "inline_sufficient": False,
                         "refs": evidence_refs}, "expected": {}}


def record_trial(ledger_path: Path, *, cwd: str, host_session_id: str, reservation_id: str,
                 repetition: int, response_path: Path, gold_path: Path, rubric_path: Path,
                 grade: Mapping[str, Any]) -> dict[str, Any]:
    state = budget_v4.read_budget(ledger_path)
    verify_root(state, cwd=cwd, host_session_id=host_session_id)
    if state["execution_mode"] != "EVALUATION" or state["closed"]:
        fail("EVALUATION_ROOT_NOT_OPEN")
    attempt = state["reservations"].get(reservation_id)
    if not attempt or attempt["state"] != "COMPLETED":
        fail("EVALUATION_NATIVE_COMPLETION_REQUIRED")
    permit = state["permits"][attempt["permit_id"]]
    request, selected = permit["request"], permit["selection"]
    evaluation = read_evaluation(state, case_ref=request["evaluation_case_ref"])
    case = next(item for item in evaluation["cases"] if item["case_ref"] == request["evaluation_case_ref"])
    integer(repetition, "EVALUATION_REPETITION", minimum=1, maximum=evaluation["repetitions"])
    if request["packet_sha256"] != trial_packet(case["case_ref"], selected["approved_profile"], repetition) \
            or request["baseline_sha256"] != repo_snapshot(Path(cwd))["sha256"] \
            or file_reference(gold_path) != case["gold_ref"] \
            or file_reference(rubric_path) != evaluation["rubric_ref"]:
        fail("EVALUATION_GRADE_SOURCE_CHANGED")
    exact(dict(grade), GRADE_FIELDS, "EVALUATION_GRADE_FIELDS")
    for flag in grade.values():
        boolean(flag, "EVALUATION_GRADE_BOOLEAN")
    if (grade["passed"] and any(grade[key] for key in GRADE_FIELDS - {"passed"})) \
            or (grade["false_block"] and not case["clean"]) \
            or (grade["critical_failure"] and not case["critical"]):
        fail("EVALUATION_GRADE_CONTRADICTION")
    value = {"schema_version": "routing-trial-result/1", "identity": state["identity"],
             "reservation_id": reservation_id, "protocol_ref": evaluation["protocol_ref"],
             "case_ref": case["case_ref"], "profile_id": selected["approved_profile"], "repetition": repetition,
             "response_ref": file_reference(response_path), "gold_ref": case["gold_ref"],
             "rubric_ref": evaluation["rubric_ref"], "grade": dict(grade),
             "finalizer": "parent:" + state["identity"]["task_id"]}
    output = ledger_path.parent / "evaluation-results" / (ref(value)[7:] + ".json")
    require_external_state(output.resolve(), Path(cwd).resolve())
    if output.exists():
        if read_document(output)[0] != value:
            fail("EVALUATION_IMMUTABLE_RESULT_COLLISION")
    else:
        atomic_write_json(output, value)
    _, result_ref = read_document(output)
    # 中文：此处 PASS 仅表示试验已采集并判定，模型正确性保存在 grade。
    # English: PASS here means a completed, graded trial. Model correctness is in grade.
    budget_v4.accept_result(ledger_path, reservation_id=reservation_id, result_ref=result_ref,
                             status="pass", response_ref=value["response_ref"],
                             baseline_sha256=request["baseline_sha256"])
    return {"result_path": str(output.resolve()), "result_ref": result_ref,
            "model_passed": grade["passed"], "reservation_id": reservation_id}


def read_trial(source: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    exact(dict(source), {"ledger", "result", "response", "gold", "rubric"}, "EVALUATION_TRIAL_SOURCE_FIELDS")
    path = Path(source["ledger"])
    events = budget_v4._read_events(path)
    state = budget_v4.replay(events)
    if state["execution_mode"] != "EVALUATION" or not state["closed"]:
        fail("EVALUATION_TRACE_NOT_FINALIZED")
    trial, result_ref = read_document(Path(source["result"]))
    exact(trial, TRIAL_FIELDS, "EVALUATION_TRIAL_FIELDS")
    accepted = state["accepted_results"].get(trial["reservation_id"])
    if trial["schema_version"] != "routing-trial-result/1" or trial["identity"] != state["identity"] \
            or trial["finalizer"] != "parent:" + state["identity"]["task_id"] \
            or not accepted or accepted["result_ref"] != result_ref \
            or accepted["response_ref"] != trial["response_ref"] \
            or any(file_reference(Path(source[key])) != trial[key + "_ref"] for key in ("response", "gold", "rubric")):
        fail("EVALUATION_TRIAL_SOURCE_BINDING")
    rid = trial["reservation_id"]
    receipt = state["host_receipts"][rid]
    trace = budget_v4.export_trace(path, ref(receipt))
    evaluation = read_evaluation(state, case_ref=trace["case_ref"])
    case = next(item for item in evaluation["cases"] if item["case_ref"] == trace["case_ref"])
    permit = state["permits"][state["reservations"][rid]["permit_id"]]
    if trial["protocol_ref"] != trace["protocol_ref"] or trial["case_ref"] != trace["case_ref"] \
            or trial["profile_id"] != trace["profile_id"] or trial["gold_ref"] != case["gold_ref"] \
            or trial["rubric_ref"] != evaluation["rubric_ref"] \
            or permit["request"]["packet_sha256"] != trial_packet(case["case_ref"], trial["profile_id"], trial["repetition"]):
        fail("EVALUATION_TRIAL_PROTOCOL_BINDING")
    starts = [event["recorded_at"] for event in events if event["event_type"] == "DISPATCH_RESERVED"
              and event["data"]["reservation_id"] == rid]
    stops = [event["recorded_at"] for event in events if event["event_type"] == "HOST_OBSERVED"
             and event["data"]["agent_ref"] == budget_v4.effective_agent_ref(state, rid)
             and event["data"]["phase"] == "stop"]
    latency = round((parse_iso(stops[0]) - parse_iso(starts[0])).total_seconds() * 1000)
    integer(latency, "EVALUATION_NATIVE_DURATION", maximum=604800000)
    sample = {"sample_id": "trial-" + ref({"receipt": ref(receipt), "identity": state["identity"]})[7:],
              **case, **trial["grade"], "repetition": trial["repetition"],
              **{key: trace[key] for key in ("task_ref", "call_ref", "receipt_ref", "response_ref", "profile_id")},
              "cost_units": permit["selection"]["reserve_units"], "latency_ms": latency}
    return sample, trace, evaluation


def assemble_experiment(evaluation: Mapping[str, Any], sources: list[Mapping[str, Any]], *,
                        experiment_id: str, issuer_task_id: str, issuer_baseline: str) -> dict[str, Any]:
    evaluation = validate_evaluation(evaluation)
    if not isinstance(sources, list) or len(sources) > policy()["limits"]["max_cases"]:
        fail("EVALUATION_TRIAL_LIMIT")
    samples, traces = [], {}
    for source in sources:
        sample, trace, frozen = read_trial(source)
        if frozen != evaluation:
            fail("EVALUATION_TRIAL_FOREIGN_PLAN")
        samples.append(sample)
        traces[trace["receipt_ref"]] = trace
    value = {"schema_version": "routing-experiment/1", "experiment_id": identifier(experiment_id),
             "origin": "desktop-evaluation", "issuer": {"task_id": issuer_task_id, "baseline_sha256": issuer_baseline},
             **{key: copy.deepcopy(evaluation[key]) for key in
                ("identity", "scenario", "rubric_ref", "minimum_pass_bp", "baseline_profile", "comparisons",
                 "family_intervals", "case_plan", "repetitions", "protocol_ref")},
             "samples": samples, "finalizer": "parent:" + issuer_task_id}
    return validate_experiment(value, trace_loader=traces.__getitem__, require_native=True)
