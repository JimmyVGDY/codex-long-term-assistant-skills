"""中文：原生 context/2 资格取证。English: grades never replace model results.

These records feed the explicit experiment/2 consumer. Building an experiment is
not publication; whole-study accounting and activation remain separate gates.
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Mapping

from . import budget_v5 as budget
from .common import atomic_write_json, parse_iso, repo_snapshot, require_external_state, utc_now
from .context_semantics_v2 import expand_semantics
from .event_v2 import OwnerTokenLock
from .routing_cards import validate_context_experiment
from .routing_context_contract import MODE_V2
from .routing_context_v4 import read_evaluation, validate_evaluation
from .routing_context_v5 import verify_root
from .routing_contract import boolean, exact, fail, identifier, integer, policy, read_document, ref
from .routing_evaluation_v4 import GRADE_FIELDS, file_reference, trial_packet

TRIAL_FIELDS = {"schema_version", "identity", "reservation_id", "accepted_result_ref", "protocol_ref",
                "case_ref", "profile_id", "repetition", "response_ref", "gold_ref", "rubric_ref",
                "grade", "finalizer", "tool_surface_ref"}
SOURCE_FIELDS = {"ledger", "result", "response", "gold", "rubric", "transcript"}


def _grade(value: Mapping[str, Any], case: Mapping[str, Any]) -> dict[str, bool]:
    exact(dict(value), GRADE_FIELDS, "EVALUATION_GRADE_FIELDS")
    for flag in value.values():
        boolean(flag, "EVALUATION_GRADE_BOOLEAN")
    if (value["passed"] and any(value[key] for key in GRADE_FIELDS - {"passed"})) \
            or (value["false_block"] and not case["clean"]) \
            or (value["critical_failure"] and not case["critical"]):
        fail("EVALUATION_GRADE_CONTRADICTION")
    return dict(value)


def _native(state: Mapping[str, Any], reservation_id: str, response_path: Path,
            gold_path: Path, rubric_path: Path, repetition: int) -> tuple[dict, dict, dict]:
    from .research_bootstrap import deny_statistics
    deny_statistics(state)
    if state["execution_mode"] != "EVALUATION" \
            or state["root_binding"]["context_runtime"]["transport_mode"] != MODE_V2:
        fail("CONTEXT_EVALUATION_V2_ROOT_REQUIRED")
    from .review_vector_transport import enabled
    if enabled(state):fail("VECTOR_LEGACY_QUALIFICATION_DENIED")
    attempt = state["reservations"].get(reservation_id)
    accepted = state["accepted_results"].get(reservation_id)
    final = state["context_finals"].get(reservation_id)
    raw_final = state.get("context_raw_finals",{}).get(reservation_id)
    delivery = state["context_deliveries"].get(reservation_id)
    recovery = state["context_recovery"].get(reservation_id)
    receipt = state["host_receipts"].get(reservation_id)
    if not attempt or attempt["state"] != "COMPLETED" or not receipt \
            or receipt["disposition"] != "created" or not accepted or not (final or raw_final) or not delivery \
            or not recovery or recovery["status"] != "DELIVERED" \
            or accepted["status"] not in {"pass", "nonblocking", "blocking", "incomplete"} \
            or attempt["outcome"] in {"FAILED", "CANCELLED", "PARTIAL", "BLOCKED"}:
        fail("CONTEXT_EVALUATION_NATIVE_COMPLETION_REQUIRED")
    agent_ref = budget.effective_agent_ref(state, reservation_id)
    if not state["root_host_binding"] or set(state["host_observations"].get(agent_ref, {})) != {"start", "stop"}:
        fail("CONTEXT_EVALUATION_NATIVE_LIFECYCLE_REQUIRED")
    permit = state["permits"][attempt["permit_id"]]
    request = permit["request"]
    evaluation = read_evaluation(state, case_ref=request["evaluation_case_ref"])
    case = next(row for row in evaluation["cases"] if row["case_ref"] == request["evaluation_case_ref"])
    integer(repetition, "EVALUATION_REPETITION", minimum=1, maximum=evaluation["repetitions"])
    response_ref=file_reference(response_path)
    if final:
        response, _ = read_document(response_path)
        from .notify_delivery import semantic_payload
        semantic = expand_semantics(semantic_payload(state, response))
        if response_ref != accepted["response_ref"] or response_ref != final["response_ref"] \
                or ref(semantic) != final["semantic_ref"] or semantic["status"] != accepted["status"] \
                or final["semantic_status"] != accepted["status"] or final["delivery_ref"] != ref(delivery) \
                or final["agent_ref"] != agent_ref:
            fail("CONTEXT_EVALUATION_FINAL_BINDING")
    elif response_ref != raw_final["response_ref"] or accepted["status"] != "incomplete" \
            or raw_final["delivery_ref"] != ref(delivery) or raw_final["agent_ref"] != agent_ref:
        fail("CONTEXT_EVALUATION_RAW_FINAL_BINDING")
    profile = permit["selection"]["approved_profile"]
    if request["packet_sha256"] != trial_packet(case["case_ref"], profile, repetition) \
            or request["business_prompt_sha256"] != case["prompt_ref"][7:] \
            or file_reference(gold_path) != case["gold_ref"] \
            or file_reference(rubric_path) != evaluation["rubric_ref"]:
        fail("CONTEXT_EVALUATION_PROTOCOL_BINDING")
    return evaluation, case, budget._trace_from_state(state, reservation_id, evaluation)


def record_trial(ledger_path: Path, *, cwd: str, host_session_id: str, reservation_id: str,
                 repetition: int, response_path: Path, gold_path: Path, rubric_path: Path,
                 transcript_path: Path, grade: Mapping[str, Any]) -> dict[str, Any]:
    """中文：持久化一份不可变父级评分，绝不重写 RESULT_ACCEPTED。
    
    English: Persist one immutable parent grade; never rewrite RESULT_ACCEPTED.
    """
    state = budget.read_budget(ledger_path)
    from .research_bootstrap import deny_statistics
    deny_statistics(state)
    verify_root(state, cwd=cwd, host_session_id=host_session_id)
    evaluation, case, trace = _native(state, reservation_id, response_path, gold_path, rubric_path, repetition)
    from .context_tool_surface import verify_trial_surface
    surface = verify_trial_surface(ledger_path,state,reservation_id,transcript_path)
    if trace["result_status"] in {"incomplete","invalid"} and grade.get("passed") is not False:
        fail("EVALUATION_GRADE_CONTRADICTS_NATIVE_INCOMPLETE")
    permit = state["permits"][state["reservations"][reservation_id]["permit_id"]]
    if repo_snapshot(Path(cwd))["sha256"] != permit["request"]["baseline_sha256"]:
        fail("EVALUATION_GRADE_SOURCE_CHANGED")
    value = {
        "schema_version": "routing-trial-result/2", "identity": copy.deepcopy(state["identity"]),
        "reservation_id": reservation_id, "accepted_result_ref": state["accepted_results"][reservation_id]["result_ref"],
        "protocol_ref": evaluation["protocol_ref"], "case_ref": case["case_ref"],
        "profile_id": trace["profile_id"], "repetition": repetition, "response_ref": trace["response_ref"],
        "gold_ref": case["gold_ref"], "rubric_ref": evaluation["rubric_ref"],
        "grade": _grade(grade, case), "finalizer": "parent:" + state["identity"]["task_id"],
        "tool_surface_ref":ref(surface),
    }
    key = ref({"identity": state["identity"], "reservation_id": reservation_id})[7:]
    output = ledger_path.parent / "qualification-grades" / (key + ".json")
    require_external_state(output.resolve(), Path(cwd).resolve())
    output.parent.mkdir(parents=True, exist_ok=True)
    with OwnerTokenLock(output, timeout=2):
        if output.exists():
            if read_document(output)[0] != value:
                fail("CONTEXT_EVALUATION_GRADE_IMMUTABLE")
        else:
            atomic_write_json(output, value)
    return {"result_path": str(output.resolve()), "result_ref": file_reference(output),
            "model_passed": value["grade"]["passed"], "reservation_id": reservation_id}


def read_trial(source: Mapping[str, Any], *, cache: dict | None = None) -> tuple[dict, dict, dict]:
    exact(dict(source), SOURCE_FIELDS, "EVALUATION_TRIAL_SOURCE_FIELDS")
    path = Path(source["ledger"])
    key = str(path.resolve())
    # 中文：缓存只在一次组装内有效，且只接收密封终态账本。
    # English: A cache lives only for one assembly. Only sealed terminal ledgers enter it.
    if cache is not None and key in cache:
        events, state = cache[key]
    else:
        events = budget._read_events(path)
        state = budget.replay(events)
        if not state["closed"]:
            fail("EVALUATION_TRACE_NOT_FINALIZED")
        if cache is not None:
            cache[key] = events, state
    trial, _ = read_document(Path(source["result"]))
    if trial.get('schema_version')=='routing-trial-result/3':
        from .research_negative import read_negative
        return read_negative(source,state,trial,events)
    exact(trial, TRIAL_FIELDS, "EVALUATION_TRIAL_FIELDS")
    if trial["schema_version"] != "routing-trial-result/2" or trial["identity"] != state["identity"] \
            or trial["finalizer"] != "parent:" + state["identity"]["task_id"]:
        fail("CONTEXT_EVALUATION_PARENT_BINDING")
    rid = trial["reservation_id"]
    evaluation, case, trace = _native(state, rid, Path(source["response"]), Path(source["gold"]),
                                     Path(source["rubric"]), trial["repetition"])
    from .context_tool_surface import verify_trial_surface
    if ref(verify_trial_surface(path,state,rid,Path(source["transcript"]))) != trial["tool_surface_ref"]:
        fail("STUDY_TOOL_SURFACE_CHANGED")
    accepted = state["accepted_results"][rid]
    if trial["accepted_result_ref"] != accepted["result_ref"] \
            or any(trial[k] != trace[k] for k in ("protocol_ref", "case_ref", "profile_id", "response_ref")) \
            or trial["gold_ref"] != case["gold_ref"] or trial["rubric_ref"] != evaluation["rubric_ref"]:
        fail("CONTEXT_EVALUATION_TRIAL_SOURCE_BINDING")
    grade = _grade(trial["grade"], case)
    if trace["result_status"] in {"incomplete","invalid"} and grade["passed"]:
        fail("EVALUATION_GRADE_CONTRADICTS_NATIVE_INCOMPLETE")
    permit = state["permits"][state["reservations"][rid]["permit_id"]]
    starts = [event["recorded_at"] for event in events if event["event_type"] == "DISPATCH_RESERVED"
              and event["data"]["reservation_id"] == rid]
    stops = [event["recorded_at"] for event in events if event["event_type"] == "HOST_OBSERVED"
             and event["data"]["agent_ref"] == trace["task_ref"] and event["data"]["phase"] == "stop"]
    if len(starts) != 1 or len(stops) != 1:
        fail("CONTEXT_EVALUATION_TIMING_BINDING")
    latency = round((parse_iso(stops[0]) - parse_iso(starts[0])).total_seconds() * 1000)
    integer(latency, "EVALUATION_NATIVE_DURATION", maximum=604800000)
    sample = {"sample_id": "trial-" + ref({"receipt": trace["receipt_ref"], "identity": state["identity"]})[7:],
              **case, **grade, "repetition": trial["repetition"],
              **{k: trace[k] for k in ("task_ref", "call_ref", "receipt_ref", "response_ref", "profile_id")},
              "cost_units": permit["selection"]["reserve_units"], "latency_ms": latency}
    return sample, trace, evaluation


def assemble_experiment(evaluation: Mapping[str, Any], sources: list[Mapping[str, Any]], *,
                        experiment_id: str, issuer_task_id: str, issuer_baseline: str,
                        qualification_source: Mapping[str, Any]) -> dict[str, Any]:
    from .qualification_study import load_study_sources, require_experiment_study
    evaluation = validate_evaluation(evaluation)
    if not isinstance(sources, list) or not sources or len(sources) > policy()["limits"]["max_cases"]:
        fail("EVALUATION_TRIAL_LIMIT")
    _, registered_sources, _ = load_study_sources(qualification_source, now=utc_now())
    if sources != registered_sources:
        fail("STUDY_ASSEMBLY_SOURCE_SUBSET")
    samples, traces, cache = [], {}, {}
    for source in sources:
        sample, trace, frozen = read_trial(source, cache=cache)
        if frozen["protocol_ref"] != evaluation["protocol_ref"]:
            continue
        if frozen != evaluation:
            fail("EVALUATION_TRIAL_FOREIGN_PLAN")
        if trace["receipt_ref"] in traces:
            fail("SAMPLE_NATIVE_TRIAL_REUSED")
        samples.append(sample)
        traces[trace["receipt_ref"]] = trace
    value = {"schema_version": "routing-experiment/2", "experiment_id": identifier(experiment_id),
             "origin": "desktop-evaluation", "issuer": {"task_id": issuer_task_id, "baseline_sha256": issuer_baseline},
             **{k: copy.deepcopy(evaluation[k]) for k in
                ("identity", "scenario", "rubric_ref", "minimum_pass_bp", "baseline_profile", "comparisons",
                 "family_intervals", "case_plan", "repetitions", "protocol_ref")},
             "samples": samples, "finalizer": "parent:" + issuer_task_id,
             "qualification_source":copy.deepcopy(dict(qualification_source))}
    value = validate_context_experiment(value, trace_loader=traces.__getitem__, require_native=True)
    require_experiment_study(value,now=utc_now())
    return value
