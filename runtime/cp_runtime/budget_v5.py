"""中文：V5 根预算、追加事件与可恢复的阶段保留量。

English: V5 root budget, append-only logical history and recoverable phase holds.
The physical rewrite is atomic; one event consumes a permit and reserves units.
"""
from __future__ import annotations

import copy
import hashlib
import json
import secrets
import re
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Callable, Mapping

from .common import atomic_write_bytes, canonical_json, require_external_state, utc_now, parse_iso
from .event_v2 import OwnerTokenLock
from .routing_contract import (
    ALGORITHM_ID, POLICY_ID, RoutingError, VECTOR_KEYS, exact, fail, identifier,
    identity, integer, policy, policy_digest, profile_spec, ref, resource_need, role_for,
    sha, vector, hex_digest, admitted,
)
from .routing_phase_plan import (
    current_slot, feasible_witness, validate_plan, validate_revision,
)
from .routing_v4 import snapshot_references
from .routing_context_contract import select, validate_request

SCHEMA = "5.0"
ZERO_HASH = "0" * 64
NATIVE_PREFIX = "CP_REVIEW_DISPATCH/2 "
FRAME_FIELDS = {"schema_version", "sequence", "event_id", "event_type", "recorded_at",
                "previous_hash", "record_hash", "identity", "data"}
EVENT_FIELDS = {
    "INITIALIZED": {"root_binding", "sources", "execution_mode", "capacity", "role_capacity",
                    "phase_capacity", "max_parallel", "max_depth", "phase_plan", "witness"},
    "PREPARED": {"permit_id", "nonce_ref", "dispatch_ref", "request", "selection",
                 "role", "slot_id", "attempt_no", "depth", "transition", "review_binding"},
    "PREPARE_REVOKED": {"permit_id", "reason_ref"},
    "ROOT_HOST_BOUND": {"session_ref", "repo_ref", "host_call_ref"},
    "DISPATCH_RESERVED": {"reservation_id", "permit_id", "host_dispatch_ref", "selection_ref", "transport_audit_sha256"},
    "HOST_RECEIPT": {"reservation_id", "agent_ref", "disposition", "proof_ref"},
    "HOST_IDENTITY_LINKED": {"reservation_id", "task_path_ref", "agent_ref", "dispatch_ref", "role", "proof_ref"},
    "CONTEXT_READ_STARTED": {"reservation_id", "agent_ref", "call_ref", "bundle_ref", "output_ref", "nonce_ref", "command_ref"},
    "CONTEXT_WIRE_DELIVERED": {"reservation_id","call_ref","raw_output_ref","wire_output_ref","raw_bytes","wire_bytes","delivery_contract"},
    "CONTEXT_DELIVERED": {"reservation_id", "call_ref", "output_ref"},
    "CONTEXT_RECOVERY": {"reservation_id", "agent_ref", "call_ref", "command_ref", "action", "reason"},
    "CONTEXT_READ_RECOVERED": {"reservation_id", "agent_ref", "call_ref", "bundle_ref", "output_ref", "nonce_ref", "command_ref"},
    "CONTEXT_NOTIFY_ATTESTED": {"reservation_id","agent_ref","delivery_ref","response_ref","visible_proof"},
    "CONTEXT_FINAL_ATTESTED": {"reservation_id", "agent_ref", "header_ref", "header_link_ref", "turn_ref", "response_ref", "delivery_ref", "semantic_ref", "semantic_status"},
    "CONTEXT_RAW_FINAL_ATTESTED": {"reservation_id", "agent_ref", "header_ref", "header_link_ref", "turn_ref", "response_ref", "delivery_ref"},
    "ORDINARY_FINAL_ATTESTED": {"reservation_id","agent_ref","header_ref","header_link_ref","turn_ref","response_ref"},
    "ORDINARY_RESULT_ACCEPTED": {"reservation_id","response_ref","validation_ref","after_baseline_sha256","result_ref","status","supersedes"},
    "HOST_OBSERVED": {"agent_ref", "phase", "outcome"},
    "HOST_TERMINAL_ERROR_RECOVERED": {"reservation_id", "agent_ref", "task_path_ref",
                                      "transcript_bytes_sha256", "file_binding_ref",
                                      "error_code", "evidence_ref", "evidence_path"},
    "HISTORICAL_ATTEMPT_CARRIED": {"slot_id", "trial_ref", "profile_id", "scenario_ref",
                                     "source_ledger_path", "source_ledger_head_hash",
                                     "source_project_id", "source_repo_fingerprint", "source_task_id",
                                     "source_reservation_id", "source_result_ref",
                                     "source_grade_ref", "source_evidence_ref",
                                     "carry_evidence_ref", "carry_evidence_path", "disposition"},
    "NOT_STARTED_RELEASED": {"reservation_id", "proof_ref"},
    "RESULT_ACCEPTED": {"reservation_id", "result_ref", "status", "response_ref", "baseline_sha256", "supersedes"},
    "SLOT_WAIVED": {"slot_id", "post_result_ref", "evidence_ref"},
    "PLAN_REVISED": {"plan", "witness", "reason_ref"},
    "EVIDENCE_ADDED": {"evidence_paths"},
    "EVALUATION_ADVANCED": {"slot_id", "previous_result_ref", "next_packet_sha256"},
    "EVALUATION_UNGRADED_SEALED": {"slot_id", "trial_ref", "reservation_id",
                                    "accepted_result_ref", "evidence_ref", "evidence_path", "reason_code"},
    "INLINE_SATISFIED": {"slot_id", "request", "selection"},
    "CLOSED": {"outcome", "evidence_ref"},
}
IDENTITY_FIELDS = {"budget_id", "task_id", "project_id", "repo_fingerprint"}
ROOT_FIELDS = {"schema_version", "repo_path", "profile_path", "profile_binding_sha256",
               "envelope_identity_ref", "host_session_ref", "policy_id", "policy_digest", "context_runtime"}
SELECTED = {"CANDIDATE_SELECTED", "EVALUATION_SELECTED"}
SnapshotLoader = Callable[[Mapping[str, Any], Mapping[str, Any], str], dict[str, Any]]


def _ordinary(state,role):
    from .ordinary_routing_v5 import enabled
    return enabled(state['root_binding']['context_runtime'],role)


def _allowed(state,role):
    return admitted(role,'PRODUCTION' if _ordinary(state,role) else state['execution_mode'])


def _select(state,request,snapshot):
    return select(request,snapshot,ordinary_contract=state['root_binding']['context_runtime'].get('ordinary_contract'))


def isolated_phase_evaluation(state):
    from .routing_context_contract import ISOLATED_PHASES,ISOLATED_PHASES_V2
    return state['execution_mode']=='EVALUATION' and state['root_binding']['context_runtime'].get('evaluation_contract') in {ISOLATED_PHASES,ISOLATED_PHASES_V2}


def isolated_trial_completion(state):
    from .routing_context_contract import ISOLATED_PHASES_V2
    return state['execution_mode']=='EVALUATION' and state['root_binding']['context_runtime'].get('evaluation_contract')==ISOLATED_PHASES_V2


def _stable(prefix: str, *values: str) -> str:
    return prefix + hashlib.sha256("\0".join(values).encode()).hexdigest()


def _agent_identifier(value: str) -> str:
    if isinstance(value, str) and re.fullmatch(r"/root(?:/[a-z0-9_]{1,64}){1,3}", value):
        return value
    return identifier(value, "V5_AGENT_IDENTIFIER")


def _identity(value: Any) -> dict[str, str]:
    exact(value, IDENTITY_FIELDS, "BUDGET_IDENTITY_FIELDS")
    identity({key: value[key] for key in ("project_id", "repo_fingerprint")})
    identifier(value["budget_id"]); identifier(value["task_id"])
    return dict(value)


def _path(value: Any, *, optional: bool = False) -> str:
    if optional and value == "":
        return value
    if not isinstance(value, str) or not value or len(value) > 4096 or "\0" in value \
            or not (PureWindowsPath(value).is_absolute() or PurePosixPath(value).is_absolute()):
        fail("V5_SOURCE_PATH_INVALID")
    return value


def validate_sources(value: Any) -> dict[str, Any]:
    exact(value, {"root_envelope", "capability", "card_sets", "evaluation_costs", "evaluation_ref", "evidence_paths"},
          "V5_SOURCE_FIELDS")
    _path(value["root_envelope"]); _path(value["capability"])
    _path(value["evaluation_costs"], optional=True)
    if value["evaluation_ref"]:
        sha(value["evaluation_ref"])
    elif value["evaluation_ref"] != "":
        fail("V5_EVALUATION_REFERENCE")
    if not isinstance(value["card_sets"], list) or len(value["card_sets"]) > 10 \
            or not isinstance(value["evidence_paths"], dict) or len(value["evidence_paths"]) > 24:
        fail("V5_SOURCE_LIMIT")
    for item in value["card_sets"]:
        exact(item, {"bundle", "experiment", "publication", "trace_ledgers", "bundle_ref",
                     "experiment_ref", "publication_ref", "publication_revision"}, "V5_CARD_SOURCE_FIELDS")
        for key in ("bundle", "experiment", "publication"):
            _path(item[key])
        for key in ("bundle_ref", "experiment_ref", "publication_ref"):
            sha(item[key])
        integer(item["publication_revision"], "V5_PUBLICATION_REVISION", minimum=1)
        if not isinstance(item["trace_ledgers"], list) or len(item["trace_ledgers"]) > 100:
            fail("V5_TRACE_SOURCE_LIMIT")
        for source in item["trace_ledgers"]:
            _path(source)
    for evidence_ref, source in value["evidence_paths"].items():
        sha(evidence_ref); _path(source)
    return copy.deepcopy(value)


def _event(state: Mapping[str, Any] | None, declared_identity: Mapping[str, Any],
           kind: str, data: Mapping[str, Any]) -> dict[str, Any]:
    exact(dict(data), EVENT_FIELDS[kind], "BUDGET_EVENT_DATA_FIELDS")
    item = {"schema_version": SCHEMA, "sequence": 1 if state is None else state["sequence"] + 1,
            "event_id": "DB5_" + secrets.token_hex(16), "event_type": kind, "recorded_at": utc_now(),
            "previous_hash": ZERO_HASH if state is None else state["head_hash"],
            "identity": dict(declared_identity), "data": copy.deepcopy(dict(data))}
    item["record_hash"] = ref(item)[7:]
    return item


def _read_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    maximum = policy()["limits"]["max_ledger_bytes"]
    with path.open("rb") as stream:
        raw = stream.read(maximum + 1)
    if len(raw) > maximum:
        fail("V5_LEDGER_TOO_LARGE")
    if raw and not raw.endswith(b"\n"):
        fail("V5_LEDGER_PARTIAL_TAIL")
    lines = raw.splitlines()
    if len(lines) > policy()["limits"]["max_ledger_records"]:
        fail("V5_LEDGER_RECORD_LIMIT")
    from .routing_contract import _object, _constant
    try:
        return [json.loads(line, object_pairs_hook=_object, parse_constant=_constant) for line in lines]
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise RoutingError("V5_LEDGER_INVALID_JSON") from exc


def _slot(state: dict[str, Any], slot_id: str) -> dict[str, Any]:
    for item in state["phase_plan"]["slots"]:
        if item["slot_id"] == slot_id:
            return item
    fail("PHASE_SLOT_UNKNOWN")


def _usage(state: Mapping[str, Any]) -> dict[str, Any]:
    if "_usage_cache" in state:
        return state["_usage_cache"]
    total = {key: 0 for key in VECTOR_KEYS}
    roles = {key: 0 for key in ("reviewer", "worker", "explorer")}
    phases = {key: 0 for key in ("pre", "post", "repair")}
    active = astra_active = 0
    for attempt in state["reservations"].values():
        prepared = state["permits"][attempt["permit_id"]]
        need = resource_need(prepared["selection"]["approved_profile"], prepared["selection"]["reserve_units"])
        for key in VECTOR_KEYS:
            # 中文：可信未启动证明只释放单位，不恢复尝试次数。
            # English: A trusted not-started proof releases units, never attempt counters.
            if key != "units" or attempt["state"] != "NOT_STARTED_RELEASED":
                total[key] += need[key]
        if attempt["state"] != "NOT_STARTED_RELEASED":
            roles[role_for(prepared["role"])] += need["units"]
            phases[prepared["request"]["scenario"]["phase"]] += need["units"]
        inflight = attempt["state"] in {"RESERVED", "STARTED"}
        active += inflight
        astra_active += int(inflight) * need["astra_attempts"]
    return {"resources": total, "role_units": roles, "phase_units": phases,
            "active": active, "astra_active": astra_active}


def snapshot_budget(state: Mapping[str, Any]) -> dict[str, Any]:
    usage = _usage(state)
    return {
        "revision": state["resource_revision"], "head_ref": state["resource_ref"],
        "remaining": {key: state["capacity"][key] - usage["resources"][key] for key in VECTOR_KEYS},
        "role_capacity": {key: state["role_capacity"][key] - usage["role_units"][key] for key in state["role_capacity"]},
        "phase_capacity": {key: state["phase_capacity"][key] - usage["phase_units"][key] for key in state["phase_capacity"]},
        "parallel_available": usage["active"] < state["max_parallel"], "depth_allowed": True,
        "astra_active": usage["astra_active"],
        "astra_parallel_available": usage["astra_active"] < policy()["limits"]["max_astra_parallel"],
    }


def _economic_projection(state: Mapping[str, Any]) -> dict[str, Any]:
    return {"usage": _usage(state), "phase_plan": state["phase_plan"], "closed": state["closed"],
            "capacity": state["capacity"], "role_capacity": state["role_capacity"],
            "phase_capacity": state["phase_capacity"], "max_parallel": state["max_parallel"],
            "sources_ref": ref(state["sources"])}


def _project_host(state: dict[str, Any], reservation_id: str) -> None:
    attempt = state["reservations"][reservation_id]
    receipt = state["host_receipts"].get(reservation_id)
    if not receipt or receipt["disposition"] != "created":
        return
    observations = state["host_observations"].get(effective_agent_ref(state, reservation_id), {})
    slot = _slot(state, state["permits"][attempt["permit_id"]]["slot_id"])
    if "stop" in observations:
        if attempt["state"] in {"RESERVED", "STARTED"}:
            state["_usage_cache"]["active"] -= 1
            selected = state["permits"][attempt["permit_id"]]["selection"]["approved_profile"]
            state["_usage_cache"]["astra_active"] -= int(profile_spec(selected)["resource_group"] == "astra")
        attempt["state"] = "COMPLETED"
        attempt["outcome"] = observations["stop"]
        if slot["status"] == "RESERVED":
            slot["status"] = "AWAITING_RESULT"
    elif "start" in observations and attempt["state"] == "RESERVED":
        attempt["state"] = "STARTED"


def effective_agent_ref(state: Mapping[str, Any], reservation_id: str) -> str:
    link = state["host_identity_links"].get(reservation_id)
    return link["agent_ref"] if link else state["host_receipts"][reservation_id]["agent_ref"]


def _apply(state: dict[str, Any] | None, event: Mapping[str, Any]) -> dict[str, Any]:
    kind, data = event["event_type"], event["data"]
    if kind == "INITIALIZED":
        if state is not None:
            fail("V5_DUPLICATE_INITIALIZATION")
        root = data["root_binding"]
        exact(root, ROOT_FIELDS, "V5_ROOT_BINDING_FIELDS")
        if root["schema_version"] != "dispatch-root/3" or root.get("policy_id") != POLICY_ID \
                or root.get("policy_digest") != policy_digest():
            fail("V5_ROOT_BINDING_POLICY")
        _path(root["repo_path"]); _path(root["profile_path"])
        hex_digest(root["profile_binding_sha256"]); sha(root["envelope_identity_ref"])
        sha(root.get("host_session_ref"))
        from .routing_context_contract import validate_runtime
        validate_runtime(root["context_runtime"])
        validate_sources(data["sources"])
        capacity = vector(data["capacity"])
        if capacity["units"] < 1 or capacity["attempts"] < 1:
            fail("V5_EMPTY_CAPACITY")
        for key, keys in (("role_capacity", {"reviewer", "worker", "explorer"}),
                          ("phase_capacity", {"pre", "post", "repair"})):
            exact(data[key], keys, "V5_LOCAL_CAPACITY_FIELDS")
            for limit in data[key].values():
                integer(limit, "V5_LOCAL_CAPACITY")
        integer(data["max_parallel"], "V5_MAX_PARALLEL", minimum=1, maximum=3)
        integer(data["max_depth"], "V5_MAX_DEPTH", minimum=1, maximum=3)
        if data["execution_mode"] not in {"PRODUCTION", "EVALUATION"}:
            fail("EXECUTION_MODE_INVALID")
        if root['context_runtime'].get('research_contract') and data['execution_mode']!='EVALUATION':fail('RESEARCH_EVALUATION_ONLY')
        if root['context_runtime'].get('bootstrap_contract') and (data['execution_mode']!='EVALUATION' or data['sources']['evaluation_costs'] or data['sources']['evaluation_ref'] or data['sources']['card_sets']):
            fail('BOOTSTRAP_NO_STATISTICAL_SOURCES')
        if root['context_runtime'].get('review_contract') and data['execution_mode']!='EVALUATION':
            fail('VECTOR_DEVELOPMENT_ONLY')
        if root['context_runtime'].get('evaluation_contract') and data['execution_mode']!='EVALUATION':
            fail('V5_PHASE_EVALUATION_ONLY')
        plan = validate_plan(data["phase_plan"], expected_identity={
            key: event["identity"][key] for key in ("project_id", "repo_fingerprint")})
        if root['context_runtime'].get('evaluation_contract') and any(
                slot['condition']!='always' or slot['depends_on'] or role_for(slot['scenario']['role'])!='reviewer'
                for slot in plan['slots']):
            fail('V5_PHASE_EVALUATION_REQUIRES_ISOLATED_REVIEW_SLOTS')
        if root['context_runtime'].get('review_contract') and any(
                role_for(slot['scenario']['role'])!='reviewer' for slot in plan['slots']):
            fail('VECTOR_REVIEWER_SLOTS_REQUIRED')
        if root['context_runtime'].get('bootstrap_contract') and any(slot['scenario']['role'] not in policy()['reviewer_roles'] or slot['condition']!='always' or slot['depends_on'] for slot in plan['slots']):
            fail('BOOTSTRAP_REVIEWER_SLOTS_ONLY')
        witness = feasible_witness(plan, capacity, role_capacity=data["role_capacity"],
                                   phase_capacity=data["phase_capacity"])
        if witness["status"] != "FEASIBLE" or witness != data["witness"]:
            fail("V5_INITIAL_PLAN_NOT_FEASIBLE")
        state = {
            "schema_version": SCHEMA, "identity": dict(event["identity"]), "policy_id": POLICY_ID,
            "policy_digest": policy_digest(), "root_binding": copy.deepcopy(root),
            "sources": copy.deepcopy(data["sources"]), "execution_mode": data["execution_mode"],
            "capacity": capacity, "role_capacity": dict(data["role_capacity"]),
            "phase_capacity": dict(data["phase_capacity"]), "max_parallel": data["max_parallel"],
            "max_depth": data["max_depth"], "phase_plan": plan, "phase_witness": witness,
            "permits": {}, "reservations": {}, "host_dispatches": {}, "host_receipts": {},
            "host_observations": {}, "accepted_results": {}, "ungraded_seals": {}, "closed": False, "outcome": "UNKNOWN",
            "host_identity_links": {}, "context_reads": {}, "context_deliveries": {},
            "root_host_binding": {},
            "resource_revision": 1, "resource_ref": "",
            "_usage_cache": {"resources": {key: 0 for key in VECTOR_KEYS},
                             "role_units": {key: 0 for key in ("reviewer", "worker", "explorer")},
                             "phase_units": {key: 0 for key in ("pre", "post", "repair")},
                             "active": 0, "astra_active": 0},
        }
        if root["context_runtime"]["transport_mode"] == "desktop-authoritative-context/2":
            state.update(context_recovery={}, context_recovery_bindings={}, context_read_history={}, context_finals={}, context_raw_finals={})
        if root['context_runtime'].get('ordinary_contract'):
            state.update(ordinary_finals={},ordinary_results={})
    else:
        if state is None:
            fail("V5_INITIALIZATION_MISSING")
        if state["closed"]:
            fail("V5_BUDGET_CLOSED")
        before = ref(_economic_projection(state))
        if kind == "ROOT_HOST_BOUND":
            for value in data.values():
                sha(value)
            if state["root_host_binding"] or data["session_ref"] != state["root_binding"]["host_session_ref"] \
                    or data["repo_ref"] != ref(state["root_binding"]["repo_path"]):
                fail("V5_NATIVE_ROOT_BINDING")
            state["root_host_binding"] = copy.deepcopy(data)
        elif kind == "PREPARED":
            identifier(data["permit_id"]); sha(data["nonce_ref"]); sha(data["dispatch_ref"])
            integer(data["attempt_no"], "V5_ATTEMPT_NUMBER", minimum=1)
            integer(data["depth"], "V5_DEPTH", minimum=1, maximum=state["max_depth"])
            if data["permit_id"] in state["permits"] or any(
                item["nonce_ref"] == data["nonce_ref"] or item["dispatch_ref"] == data["dispatch_ref"]
                for item in state["permits"].values()):
                fail("V5_PREPARE_COLLISION")
            validate_request(data["request"])
            choice = data["selection"]
            if choice.get("status") not in SELECTED or choice.get("decision_ref") != ref({
                key: value for key, value in choice.items() if key != "decision_ref"}):
                fail("V5_SELECTION_INTEGRITY")
            spec = profile_spec(choice.get("approved_profile"))
            if choice["approved_profile"] not in _allowed(state,data["role"]) \
                    or choice["request_parameters"] != {
                        "model": spec["model"], "reasoning_effort": spec["effort"], "agent_type": data["role"]}:
                fail("V5_SELECTION_TUPLE_MISMATCH")
            if data["request"]["identity"] != {key: state["identity"][key] for key in ("project_id", "repo_fingerprint")} \
                    or data["request"]["task_id"] != state["identity"]["task_id"] \
                    or data["request"]["execution_mode"] != state["execution_mode"] \
                    or data["request"]["scenario"]["role"] != data["role"] \
                    or data["request"]["slot_id"] != data["slot_id"]:
                fail("V5_PREPARE_IDENTITY")
            if choice["snapshots"]["ledger_revision"] != state["resource_revision"] \
                    or choice["snapshots"]["ledger_head_ref"] != state["resource_ref"]:
                fail("STALE_SNAPSHOT")
            if _slot(state, data["slot_id"])["status"] != "PENDING":
                fail("PHASE_SLOT_NOT_PENDING")
            if data["review_binding"]:
                if _ordinary(state, data['role']):
                    fail('ORDINARY_REVIEW_BINDING_DENIED')
                binding = exact(data["review_binding"], {"review_state_ref", "boundary_id", "reviewer"},
                                "V5_REVIEW_BINDING_FIELDS")
                sha(binding["review_state_ref"]); identifier(binding["boundary_id"]); identifier(binding["reviewer"])
                if binding["reviewer"] != data["role"]:
                    fail("V5_REVIEW_ROLE_BINDING")
            for previous_binding in state["permits"].values():
                if previous_binding["slot_id"] == data["slot_id"] \
                        and previous_binding["review_binding"] != data["review_binding"]:
                    fail("V5_REVIEW_OWNER_CONFLICT")
            prior = [item for item in state["permits"].values()
                     if item["slot_id"] == data["slot_id"] and item["status"] == "CONSUMED"]
            if prior:
                transition = exact(data["transition"], {"prior_reservation_id", "prior_result_ref", "reason"},
                                   "V5_TRANSITION_FIELDS")
                previous = state["reservations"].get(transition["prior_reservation_id"])
                if not previous or previous["state"] not in {"COMPLETED", "NOT_STARTED_RELEASED"} \
                        or state["permits"][previous["permit_id"]]["slot_id"] != data["slot_id"]:
                    fail("PRIOR_ATTEMPT_UNRESOLVED")
                previous_permit = state["permits"][previous["permit_id"]]
                if previous_permit["attempt_no"] != max(item["attempt_no"] for item in prior):
                    fail("V5_TRANSITION_NOT_LATEST")
                if previous["state"] == "NOT_STARTED_RELEASED":
                    if transition["reason"] != "HOST_UNAVAILABLE" or transition["prior_result_ref"]:
                        fail("V5_TRANSITION_RELEASE_PROOF")
                else:
                    old_result = state["accepted_results"].get(transition["prior_reservation_id"]) or state.get('ordinary_results',{}).get(transition['prior_reservation_id'])
                    if not old_result or old_result["result_ref"] != transition["prior_result_ref"]:
                        fail("V5_TRANSITION_RESULT_BINDING")
                    changed = any(data["request"][key] != previous_permit["request"][key]
                                  for key in ("baseline_sha256", "packet_sha256", "evidence"))
                    if not changed or transition["reason"] not in {
                        "NEW_EVIDENCE", "BASELINE_CHANGED", "TARGETED_REPAIR", "EVALUATION_NEXT"}:
                        fail("V5_REPEAT_REQUIRES_NEW_EVIDENCE")
                    if transition["reason"] == "EVALUATION_NEXT" and state["execution_mode"] != "EVALUATION":
                        fail("V5_EVALUATION_TRANSITION_IN_PRODUCTION")
            elif data["request"]["scenario"]["phase"] == "repair" and not isolated_phase_evaluation(state):
                transition = exact(data["transition"], {"prior_reservation_id", "prior_result_ref", "reason"},
                                   "V5_REPAIR_TRANSITION_REQUIRED")
                previous = state["reservations"].get(transition["prior_reservation_id"])
                old_result = state["accepted_results"].get(transition["prior_reservation_id"])
                old_permit = state["permits"].get(previous["permit_id"]) if previous else None
                if not previous or previous["state"] != "COMPLETED" or not old_result or not old_permit \
                        or old_result["result_ref"] != transition["prior_result_ref"] \
                        or old_result["status"] != "blocking" or transition["reason"] != "TARGETED_REPAIR" \
                        or old_permit["slot_id"] not in _slot(state, data["slot_id"])["depends_on"] \
                        or old_permit["request"]["scenario"]["phase"] != "post" \
                        or any(row["slot_id"] == old_permit["slot_id"] and row["status"] == "CONSUMED"
                               and row["attempt_no"] > old_permit["attempt_no"] for row in state["permits"].values()):
                    fail("V5_REPAIR_PARENT_MISMATCH")
            elif data["transition"]:
                fail("V5_TRANSITION_WITHOUT_PRIOR")
            selected_option = next((item for item in _slot(state, data["slot_id"])["options"]
                                    if item["profile_id"] == choice["approved_profile"]), None)
            if not selected_option or choice["reserve_units"] != selected_option["resources"]["units"] \
                    or choice["cost_ref"] != selected_option["cost_ref"] \
                    or choice["qualification_ref"] != selected_option["qualification_ref"]:
                fail("V5_SELECTION_OPTION_MISMATCH")
            if _ordinary(state,data['role']):
                from .ordinary_routing_v5 import CONTRACT,option
                if choice.get('selection_basis')!=CONTRACT or selected_option!=option(choice['approved_profile'],data['request']['scenario']):
                    fail('ORDINARY_FIXED_COST_REQUIRED')
            state["permits"][data["permit_id"]] = {**copy.deepcopy(data), "status": "PREPARED"}
        elif kind == "PREPARE_REVOKED":
            sha(data["reason_ref"])
            permit = state["permits"].get(data["permit_id"])
            if not permit or permit["status"] != "PREPARED":
                fail("V5_PREPARE_REVOCATION_CONFLICT")
            permit["status"] = "REVOKED"
        elif kind == "DISPATCH_RESERVED":
            identifier(data["reservation_id"]); sha(data["host_dispatch_ref"]); sha(data["selection_ref"])
            hex_digest(data["transport_audit_sha256"])
            permit = state["permits"].get(data["permit_id"])
            if not permit or permit["status"] != "PREPARED":
                fail("PERMIT_ALREADY_CONSUMED")
            if not state["root_host_binding"]:
                fail("V5_NATIVE_ROOT_REQUIRED")
            if data["reservation_id"] in state["reservations"] or data["host_dispatch_ref"] in state["host_dispatches"]:
                fail("HOST_DISPATCH_COLLISION")
            choice = permit["selection"]
            if choice["decision_ref"] != data["selection_ref"] \
                    or choice["snapshots"]["ledger_revision"] != state["resource_revision"] \
                    or choice["snapshots"]["ledger_head_ref"] != state["resource_ref"]:
                fail("STALE_SNAPSHOT")
            slot = _slot(state, permit["slot_id"])
            if slot["status"] != "PENDING":
                fail("PHASE_SLOT_NOT_PENDING")
            permit["status"] = "CONSUMED"
            state["reservations"][data["reservation_id"]] = {
                **copy.deepcopy(data), "state": "RESERVED", "outcome": "UNKNOWN"}
            state["host_dispatches"][data["host_dispatch_ref"]] = data["reservation_id"]
            need = resource_need(choice["approved_profile"], choice["reserve_units"])
            for key in VECTOR_KEYS:
                state["_usage_cache"]["resources"][key] += need[key]
            state["_usage_cache"]["role_units"][role_for(permit["role"])] += need["units"]
            state["_usage_cache"]["phase_units"][permit["request"]["scenario"]["phase"]] += need["units"]
            state["_usage_cache"]["active"] += 1
            state["_usage_cache"]["astra_active"] += need["astra_attempts"]
            slot["status"] = "RESERVED"
            slot["active_reservation_ref"] = ref(data["reservation_id"])
        elif kind == "HOST_RECEIPT":
            attempt = state["reservations"].get(data["reservation_id"])
            if not attempt or data["reservation_id"] in state["host_receipts"]:
                fail("V5_RECEIPT_COLLISION")
            if data["disposition"] not in {"created", "not-started"}:
                fail("V5_RECEIPT_DISPOSITION")
            sha(data["proof_ref"])
            if data["disposition"] == "created":
                sha(data["agent_ref"])
                if any(row["agent_ref"] == data["agent_ref"] or effective_agent_ref(state, rid) == data["agent_ref"]
                       for rid, row in state["host_receipts"].items()):
                    fail("V5_AGENT_RECEIPT_COLLISION")
            elif data["agent_ref"]:
                fail("V5_NOT_STARTED_AGENT_CONFLICT")
            link = state["host_identity_links"].get(data["reservation_id"])
            if link and (data["disposition"] != "created" or
                         data["agent_ref"] not in {link["task_path_ref"], link["agent_ref"]}):
                fail("V5_RECEIPT_IDENTITY_LINK_CONFLICT")
            state["host_receipts"][data["reservation_id"]] = copy.deepcopy(data)
            _project_host(state, data["reservation_id"])
        elif kind == "HOST_IDENTITY_LINKED":
            for key in ("task_path_ref", "agent_ref", "dispatch_ref", "proof_ref"):
                sha(data[key])
            attempt = state["reservations"].get(data["reservation_id"])
            if not attempt or attempt["state"] == "NOT_STARTED_RELEASED":
                fail("V5_IDENTITY_LINK_WITHOUT_ATTEMPT")
            permit = state["permits"][attempt["permit_id"]]
            if data["dispatch_ref"] != permit["dispatch_ref"] or data["role"] != permit["role"] \
                    or data["reservation_id"] in state["host_identity_links"] \
                    or any(link["agent_ref"] == data["agent_ref"] for link in state["host_identity_links"].values()):
                fail("V5_IDENTITY_LINK_CONFLICT")
            receipt = state["host_receipts"].get(data["reservation_id"])
            if receipt and (receipt["disposition"] != "created" or
                            receipt["agent_ref"] not in {data["task_path_ref"], data["agent_ref"]}):
                fail("V5_RECEIPT_IDENTITY_LINK_CONFLICT")
            if receipt and receipt["agent_ref"] != data["agent_ref"] \
                    and "stop" in state["host_observations"].get(receipt["agent_ref"], {}):
                fail("V5_IDENTITY_LINK_AFTER_TERMINAL")
            if any(rid != data["reservation_id"] and row["agent_ref"] == data["agent_ref"]
                   for rid, row in state["host_receipts"].items()):
                fail("V5_IDENTITY_LINK_CONFLICT")
            state["host_identity_links"][data["reservation_id"]] = copy.deepcopy(data)
            _project_host(state, data["reservation_id"])
        elif kind == "CONTEXT_RECOVERY":
            from .context_recovery_v2 import MODE, transition, deadline_for_runtime
            if state["root_binding"]["context_runtime"]["transport_mode"] != MODE:
                fail("CONTEXT_V2_MODE_REQUIRED")
            rid = data["reservation_id"]
            attempt = state["reservations"].get(rid)
            link = state["host_identity_links"].get(rid)
            if not attempt or attempt["state"] not in {"RESERVED", "STARTED"} or not link \
                    or data["agent_ref"] != link["agent_ref"]:
                fail("CONTEXT_V2_RECOVERY_BINDING")
            sha(data["command_ref"]); sha(data["call_ref"])
            binding = {name: data[name] for name in ("agent_ref", "command_ref")}
            if state["context_recovery_bindings"].get(rid, binding) != binding or any(
                    data["call_ref"] in item["calls"] for key, item in state["context_recovery"].items() if key != rid):
                fail("CONTEXT_V2_RECOVERY_CONFLICT")
            state["context_recovery"][rid] = transition(state["context_recovery"].get(rid), event=data["action"],
                call_ref=data["call_ref"], now_ms=int(parse_iso(event["recorded_at"]).timestamp() * 1000),
                reason=data["reason"], max_elapsed_ms=deadline_for_runtime(state["root_binding"]["context_runtime"]))
            state["context_recovery_bindings"][rid] = binding
        elif kind in {"CONTEXT_READ_STARTED", "CONTEXT_READ_RECOVERED"}:
            for name in ("agent_ref", "call_ref", "bundle_ref", "output_ref", "nonce_ref", "command_ref"):
                sha(data[name])
            rid = data["reservation_id"]
            attempt = state["reservations"].get(rid)
            link = state["host_identity_links"].get(rid)
            receipt = state["host_receipts"].get(rid)
            old = state["context_reads"].get(rid)
            if kind == "CONTEXT_READ_RECOVERED":
                if state["root_binding"]["context_runtime"]["transport_mode"] != "desktop-authoritative-context/2" \
                        or not old or any(old[key] != data[key] for key in data if key != "call_ref"):
                    fail("CONTEXT_V2_RECOVERED_READ_BINDING")
            elif old:
                fail("V5_CONTEXT_READ_BINDING")
            if not attempt or attempt["state"] not in {"RESERVED", "STARTED"} or not link or not receipt \
                    or receipt["disposition"] != "created" or link["agent_ref"] != data["agent_ref"] \
                    or any(row["call_ref"] == data["call_ref"]
                        for row in state["context_reads"].values()):
                fail("V5_CONTEXT_READ_BINDING")
            if state["root_binding"]["context_runtime"]["transport_mode"] == "desktop-authoritative-context/2":
                recovery = state["context_recovery"].get(rid, {})
                if recovery.get("status") != "ADMITTED" or recovery.get("active_call") != data["call_ref"] \
                        or state["context_recovery_bindings"][rid]["command_ref"] != data["command_ref"]:
                    fail("CONTEXT_V2_READ_ADMISSION_REQUIRED")
                state["context_read_history"].setdefault(rid, []).append(copy.deepcopy(data))
            request = state["permits"][attempt["permit_id"]]["request"]
            if request["context_bundle"]["sha256"] != data["bundle_ref"]:
                fail("V5_CONTEXT_BUNDLE_BINDING")
            state["context_reads"][rid] = copy.deepcopy(data)
        elif kind == "CONTEXT_DELIVERED":
            from . import notify_wire
            if notify_wire.enabled(state):fail('WIRE_ATOMIC_EVENT_REQUIRED')
            rid = data["reservation_id"]
            started = state["context_reads"].get(rid)
            attempt = state["reservations"].get(rid)
            if not started or not attempt or attempt["state"] not in {"RESERVED", "STARTED"} \
                    or rid in state["context_deliveries"] or any(started[name] != data[name]
                        for name in ("call_ref", "output_ref")):
                fail("V5_CONTEXT_DELIVERY_BINDING")
            state["context_deliveries"][rid] = copy.deepcopy(data)
        elif kind == "CONTEXT_WIRE_DELIVERED":
            from . import notify_wire
            if not notify_wire.enabled(state) or data['delivery_contract']!=notify_wire.CONTRACT:fail('WIRE_OPT_IN_REQUIRED')
            rid=data['reservation_id'];started=state['context_reads'].get(rid);attempt=state['reservations'].get(rid)
            sha(data['raw_output_ref']);sha(data['wire_output_ref']);integer(data['raw_bytes'],'WIRE_RAW_BYTES',minimum=1,maximum=65536);integer(data['wire_bytes'],'WIRE_BYTES',minimum=1,maximum=notify_wire.MAX_WIRE)
            if not started or not attempt or attempt['state'] not in {'RESERVED','STARTED'} or rid in state['context_deliveries'] or started['call_ref']!=data['call_ref'] or started['output_ref']!=data['raw_output_ref']:fail('WIRE_DELIVERY_BINDING')
            state['context_deliveries'][rid]={'reservation_id':rid,'call_ref':data['call_ref'],'output_ref':data['raw_output_ref']}
            state.setdefault('context_wire_deliveries',{})[rid]=copy.deepcopy(data)
        elif kind == "CONTEXT_RAW_FINAL_ATTESTED":
            if state["root_binding"]["context_runtime"]["transport_mode"] != "desktop-authoritative-context/2":
                fail("CONTEXT_V2_MODE_REQUIRED")
            for key,value in data.items():
                if key != "reservation_id":
                    sha(value)
            rid=data["reservation_id"]
            link=state["host_identity_links"].get(rid,{})
            if rid in state["context_raw_finals"] or state["context_recovery"].get(rid,{}).get("status") != "DELIVERED" \
                    or rid not in state["context_deliveries"] or data["delivery_ref"] != ref(state["context_deliveries"][rid]) \
                    or data["agent_ref"] != link.get("agent_ref") or data["header_link_ref"] != link.get("proof_ref"):
                fail("CONTEXT_V2_RAW_FINAL_BINDING")
            state["context_raw_finals"][rid]=copy.deepcopy(data)
        elif kind == 'CONTEXT_NOTIFY_ATTESTED':
            from .notify_delivery import enabled,validate_proof
            if not enabled(state):fail('NOTIFY_OPT_IN_REQUIRED')
            rid=data['reservation_id'];native=state['context_raw_finals'].get(rid)
            from . import notify_wire
            proof=notify_wire.validate_proof(data['visible_proof']) if notify_wire.enabled(state) else validate_proof(data['visible_proof'])
            if notify_wire.enabled(state):
                delivery=state.get('context_wire_deliveries',{}).get(rid,{})
                if proof['wire_output_ref']!=delivery.get('wire_output_ref') or proof['wire_bytes']!=delivery.get('wire_bytes'):fail('WIRE_ATTESTATION_BINDING')
            if not native or data['agent_ref']!=native['agent_ref'] or data['response_ref']!=native['response_ref'] or data['delivery_ref']!=native['delivery_ref'] or proof['raw_output_ref']!=state['context_deliveries'][rid]['output_ref'] or rid in state.setdefault('context_notify_finals',{}):fail('NOTIFY_ATTESTATION_BINDING')
            state['context_notify_finals'][rid]=copy.deepcopy(data)
        elif kind == "CONTEXT_FINAL_ATTESTED":
            if state["root_binding"]["context_runtime"]["transport_mode"] != "desktop-authoritative-context/2":
                fail("CONTEXT_V2_MODE_REQUIRED")
            for key, value in data.items():
                if key not in {"reservation_id", "semantic_status"}:
                    sha(value)
            rid = data["reservation_id"]
            link = state["host_identity_links"].get(rid, {})
            if data["semantic_status"] not in {"pass", "nonblocking", "blocking", "incomplete"} \
                    or rid in state["context_finals"] or state["context_recovery"].get(rid, {}).get("status") != "DELIVERED" \
                    or rid not in state["context_deliveries"] or data["delivery_ref"] != ref(state["context_deliveries"][rid]) \
                    or data["agent_ref"] != link.get("agent_ref") or data["header_link_ref"] != link.get("proof_ref"):
                fail("CONTEXT_V2_FINAL_BINDING")
            raw_final=state["context_raw_finals"].get(rid)
            if raw_final and any(raw_final[key] != data[key] for key in raw_final):
                fail("CONTEXT_V2_FINAL_RAW_CONFLICT")
            from .notify_delivery import enabled
            if enabled(state) and (rid not in state.get('context_notify_finals',{}) or state['context_notify_finals'][rid]['response_ref']!=data['response_ref']):fail('NOTIFY_FINAL_PROOF_REQUIRED')
            state["context_finals"][rid] = copy.deepcopy(data)
        elif kind == "HOST_OBSERVED":
            sha(data["agent_ref"])
            if data["phase"] not in {"start", "stop"} or data["outcome"] not in {
                "PASS", "BLOCKED", "FAILED", "CANCELLED", "PARTIAL", "UNKNOWN"}:
                fail("V5_HOST_OBSERVATION")
            observations = state["host_observations"].setdefault(data["agent_ref"], {})
            if data["phase"] == "stop" and any(
                    recovered["agent_ref"] == data["agent_ref"]
                    for recovered in state.get("host_terminal_recoveries", {}).values()):
                fail("V5_RECOVERED_HOST_STOP_CONFLICT")
            if data["phase"] in observations:
                fail("V5_DUPLICATE_OBSERVATION_EVENT")
            if data["phase"] == "start" and data["outcome"] != "UNKNOWN":
                fail("V5_START_OUTCOME_INVALID")
            observations[data["phase"]] = data["outcome"]
            for rid, receipt in state["host_receipts"].items():
                if effective_agent_ref(state, rid) == data["agent_ref"]:
                    _project_host(state, rid)
        elif kind == "HOST_TERMINAL_ERROR_RECOVERED":
            rid = data["reservation_id"]
            for key in ("agent_ref", "task_path_ref", "file_binding_ref", "evidence_ref"):
                sha(data[key])
            _path(data["evidence_path"])
            hex_digest(data["transcript_bytes_sha256"])
            attempt = state["reservations"].get(rid)
            receipt = state["host_receipts"].get(rid)
            link = state["host_identity_links"].get(rid)
            observed = state["host_observations"].get(data["agent_ref"], {})
            if (state["execution_mode"] != "EVALUATION" or
                    state["root_binding"]["context_runtime"].get("research_contract") not in {"desktop-research-campaign/1", "desktop-research-campaign/2"} or
                    data["error_code"] != "server_overloaded" or
                    not attempt or attempt["state"] != "STARTED" or
                    not receipt or receipt["disposition"] != "created" or not link or
                    not state["root_host_binding"] or
                    effective_agent_ref(state, rid) != data["agent_ref"] or
                    link["task_path_ref"] != data["task_path_ref"] or
                    observed != {"start": "UNKNOWN"} or
                    rid in state.get("host_terminal_recoveries", {}) or
                    rid in state["context_reads"] or rid in state["context_deliveries"] or
                    rid in state.get("context_recovery", {}) or
                    rid in state.get("context_wire_deliveries", {}) or
                    rid in state.get("context_notify_finals", {}) or
                    rid in state.get("context_finals", {}) or
                    rid in state.get("context_raw_finals", {}) or
                    rid in state["accepted_results"]):
                fail("V5_HOST_TERMINAL_RECOVERY_DENIED")
            slot = _slot(state, state["permits"][attempt["permit_id"]]["slot_id"])
            if slot["status"] != "RESERVED":
                fail("V5_HOST_TERMINAL_RECOVERY_SLOT")
            state.setdefault("host_terminal_recoveries", {})[rid] = copy.deepcopy(data)
            attempt["state"], attempt["outcome"] = "COMPLETED", "FAILED"
            state["_usage_cache"]["active"] -= 1
            selected = state["permits"][attempt["permit_id"]]["selection"]["approved_profile"]
            state["_usage_cache"]["astra_active"] -= int(profile_spec(selected)["resource_group"] == "astra")
            slot["status"] = "AWAITING_RESULT"
        elif kind == "HISTORICAL_ATTEMPT_CARRIED":
            for key in ("trial_ref", "scenario_ref", "source_result_ref", "source_evidence_ref",
                        "carry_evidence_ref"):
                sha(data[key])
            if data["source_grade_ref"]:
                sha(data["source_grade_ref"])
            _path(data["source_ledger_path"])
            _path(data["carry_evidence_path"])
            hex_digest(data["source_ledger_head_hash"])
            sha(data["source_repo_fingerprint"])
            identifier(data["source_project_id"])
            identifier(data["source_task_id"])
            identifier(data["source_reservation_id"])
            profile_spec(data["profile_id"])
            slot = _slot(state, data["slot_id"])
            if (state["execution_mode"] != "EVALUATION" or
                    state["root_binding"]["context_runtime"].get("research_contract") not in {"desktop-research-campaign/1", "desktop-research-campaign/2"} or
                    slot["status"] != "PENDING" or slot["active_reservation_ref"] or
                    data["slot_id"] != "trial_" + data["trial_ref"][7:59] or
                    data["scenario_ref"] != ref(slot["scenario"]) or
                    not any(option["profile_id"] == data["profile_id"] for option in slot["options"]) or
                    data["source_project_id"] != state["identity"]["project_id"] or
                    data["source_repo_fingerprint"] != state["identity"]["repo_fingerprint"] or
                    data["source_task_id"] == state["identity"]["task_id"] or
                    data["slot_id"] in state.get("historical_carries", {}) or
                    any(carry["source_reservation_id"] == data["source_reservation_id"]
                        for carry in state.get("historical_carries", {}).values()) or
                    any(permit["slot_id"] == data["slot_id"] for permit in state["permits"].values()) or
                    data["disposition"] not in {"MODEL_GRADED", "HOST_INFRA_UNGRADED", "READER_PROTOCOL_UNGRADED"} or
                    (data["disposition"] == "MODEL_GRADED") != bool(data["source_grade_ref"])):
                fail("V5_HISTORICAL_CARRY_DENIED")
            state.setdefault("historical_carries", {})[data["slot_id"]] = copy.deepcopy(data)
            slot["status"] = "SATISFIED"
            slot["accepted_result_ref"] = data["source_result_ref"]
        elif kind == "NOT_STARTED_RELEASED":
            attempt = state["reservations"].get(data["reservation_id"])
            receipt = state["host_receipts"].get(data["reservation_id"])
            if not attempt or attempt["state"] != "RESERVED" or not receipt \
                    or receipt["disposition"] != "not-started" or receipt["proof_ref"] != data["proof_ref"]:
                fail("V5_RELEASE_REQUIRES_NOT_STARTED_PROOF")
            attempt["state"] = "NOT_STARTED_RELEASED"
            permit = state["permits"][attempt["permit_id"]]
            units = permit["selection"]["reserve_units"]
            state["_usage_cache"]["resources"]["units"] -= units
            state["_usage_cache"]["role_units"][role_for(permit["role"])] -= units
            state["_usage_cache"]["phase_units"][permit["request"]["scenario"]["phase"]] -= units
            state["_usage_cache"]["active"] -= 1
            selected = permit["selection"]["approved_profile"]
            state["_usage_cache"]["astra_active"] -= int(profile_spec(selected)["resource_group"] == "astra")
            slot = _slot(state, permit["slot_id"])
            slot["status"] = "PENDING"
            slot["active_reservation_ref"] = ""
        elif kind == 'ORDINARY_FINAL_ATTESTED':
            rid=data['reservation_id'];attempt=state['reservations'].get(rid)
            if not attempt or attempt['state'] not in {'RESERVED','STARTED','COMPLETED'} \
                    or not _ordinary(state,state['permits'][attempt['permit_id']]['role']):
                fail('ORDINARY_FINAL_ROLE')
            for key in ('agent_ref','header_ref','header_link_ref','turn_ref','response_ref'):sha(data[key])
            if rid in state['ordinary_finals'] or data['agent_ref']!=effective_agent_ref(state,rid) \
                    or data['header_link_ref']!=state['host_identity_links'].get(rid,{}).get('proof_ref'):
                fail('ORDINARY_FINAL_BINDING')
            state['ordinary_finals'][rid]=copy.deepcopy(data)
        elif kind == 'ORDINARY_RESULT_ACCEPTED':
            rid=data['reservation_id'];attempt=state['reservations'].get(rid)
            if not attempt or attempt['state']!='COMPLETED' or not _ordinary(state,state['permits'][attempt['permit_id']]['role']):
                fail('ORDINARY_RESULT_TERMINAL')
            for key in ('response_ref','validation_ref','result_ref'):sha(data[key])
            hex_digest(data['after_baseline_sha256'])
            if rid in state['ordinary_results'] or state['ordinary_finals'].get(rid,{}).get('response_ref')!=data['response_ref'] \
                    or state['host_receipts'].get(rid,{}).get('disposition')!='created' \
                    or data['status'] not in {'pass','incomplete'}:
                fail('ORDINARY_RESULT_BINDING')
            if data['status']=='pass' and attempt['outcome'] in {'FAILED','CANCELLED','PARTIAL','BLOCKED'}:
                fail('ORDINARY_RESULT_HOST_CONFLICT')
            permit=state['permits'][attempt['permit_id']]
            expected_supersedes=[r['result_ref'] for previous,r in state['ordinary_results'].items()
                if state['permits'][state['reservations'][previous]['permit_id']]['slot_id']==permit['slot_id'] and r['status']=='incomplete'
                and r['result_ref'] not in {x for result in state['ordinary_results'].values() for x in result['supersedes']}]
            if data['supersedes']!=expected_supersedes:fail('ORDINARY_RESULT_SUPERSESSION')
            slot=_slot(state,permit['slot_id'])
            if slot['status']!='AWAITING_RESULT':fail('ORDINARY_RESULT_SLOT')
            if data['result_ref']!=ref({k:v for k,v in data.items() if k!='result_ref'}):fail('ORDINARY_RESULT_INTEGRITY')
            state['ordinary_results'][rid]=copy.deepcopy(data)
            slot['active_reservation_ref']=''
            slot['status']='SATISFIED' if data['status']=='pass' else 'PENDING'
            if data['status']=='pass':slot['accepted_result_ref']=data['result_ref']
        elif kind == "RESULT_ACCEPTED":
            sha(data["result_ref"]); sha(data["response_ref"])
            attempt = state["reservations"].get(data["reservation_id"])
            if attempt and _ordinary(state, state['permits'][attempt['permit_id']]['role']):
                fail('ORDINARY_REVIEW_RESULT_DENIED')
            if not attempt or attempt["state"] != "COMPLETED" or data["reservation_id"] in state["accepted_results"]:
                fail("V5_RESULT_REQUIRES_COMPLETED_ATTEMPT")
            permit = state["permits"][attempt["permit_id"]]
            if data["supersedes"] != result_supersedes(state, permit, data["status"]):
                fail("V5_RESULT_SUPERSESSION_MISMATCH")
            if data["baseline_sha256"] != permit["request"]["baseline_sha256"] \
                    or data["status"] not in {"pass", "nonblocking", "blocking", "incomplete"}:
                fail("V5_RESULT_BINDING")
            if data["status"] != "incomplete" and data["reservation_id"] not in state["context_deliveries"]:
                fail("V5_CONTEXT_DELIVERY_REQUIRED")
            if state["root_binding"]["context_runtime"]["transport_mode"] == "desktop-authoritative-context/2" \
                    and data["status"] != "incomplete":
                rid = data["reservation_id"]
                if state["context_recovery"].get(rid, {}).get("status") != "DELIVERED" \
                        or state["context_finals"].get(rid, {}).get("response_ref") != data["response_ref"] \
                        or state["context_finals"][rid]["semantic_status"] != data["status"]:
                    fail("CONTEXT_V2_NATIVE_FINAL_REQUIRED")
            # 中文：已知的未完成终态不能被结果覆盖；UNKNOWN 仍需独立核验结果。
            # English: A known unsuccessful stop cannot be overridden by a completed
            # review. UNKNOWN never supplies a verdict; result validation is separate.
            if attempt["outcome"] in {"CANCELLED", "FAILED", "PARTIAL", "BLOCKED"} \
                    and data["status"] != "incomplete":
                fail("V5_RESULT_CONFLICTS_WITH_HOST_OUTCOME")
            slot = _slot(state, permit["slot_id"])
            if slot["status"] != "AWAITING_RESULT":
                fail("V5_RESULT_SLOT_STATE")
            state["accepted_results"][data["reservation_id"]] = copy.deepcopy(data)
            if not isinstance(data["supersedes"], list) or len(data["supersedes"]) > 10 \
                    or len(set(data["supersedes"])) != len(data["supersedes"]):
                fail("V5_SUPERSEDES_FIELDS")
            for previous_ref in data["supersedes"]:
                sha(previous_ref)
                old = next((item for rid, item in state["accepted_results"].items()
                            if rid != data["reservation_id"] and item["result_ref"] == previous_ref), None)
                if not old or data["status"] not in {"pass", "nonblocking"} \
                        or old["status"] not in {"blocking", "incomplete"}:
                    fail("V5_SUPERSEDES_INVALID")
                old_permit = state["permits"][state["reservations"][old["reservation_id"]]["permit_id"]]
                if old_permit["slot_id"] != permit["slot_id"] and old_permit["slot_id"] not in slot["depends_on"]:
                    fail("V5_SUPERSEDES_SCOPE_MISMATCH")
            if data["status"] == "incomplete" or (
                data["status"] == "blocking" and permit["request"]["scenario"]["phase"] in {"pre", "repair"}
                and not isolated_trial_completion(state)):
                slot["status"] = "PENDING"
                slot["active_reservation_ref"] = ""
            else:
                slot["status"] = "SATISFIED"
                slot["accepted_result_ref"] = data["result_ref"]
                slot["active_reservation_ref"] = ""
        elif kind == "SLOT_WAIVED":
            sha(data["post_result_ref"]); sha(data["evidence_ref"])
            slot = _slot(state, data["slot_id"])
            parents = [item for item in state["accepted_results"].values()
                       if item["result_ref"] == data["post_result_ref"] and item["status"] in {"pass", "nonblocking"}]
            if slot["condition"] != "repair-after-post" or slot["status"] != "PENDING" or len(parents) != 1:
                fail("V5_REPAIR_WAIVER_NOT_PROVEN")
            parent = state["permits"][state["reservations"][parents[0]["reservation_id"]]["permit_id"]]
            if parent["request"]["scenario"]["phase"] != "post" or parent["slot_id"] not in slot["depends_on"]:
                fail("V5_REPAIR_WAIVER_PARENT_MISMATCH")
            slot["status"] = "WAIVED"
            slot["release_evidence_ref"] = data["evidence_ref"]
        elif kind == "EVIDENCE_ADDED":
            additions = data["evidence_paths"]
            if not isinstance(additions, dict) or not additions:
                fail("V5_EVIDENCE_ADDITIONS_REQUIRED")
            previous = state["sources"]["evidence_paths"]
            if any(key in previous and previous[key] != value for key, value in additions.items()):
                fail("V5_EVIDENCE_SOURCE_REPLACEMENT")
            sources = {**state["sources"], "evidence_paths": {**previous, **additions}}
            state["sources"] = validate_sources(sources)
        elif kind == "PLAN_REVISED":
            sha(data["reason_ref"])
            revised = validate_revision(state["phase_plan"], data["plan"])
            budget = snapshot_budget(state)
            witness = feasible_witness(revised, budget["remaining"], role_capacity=budget["role_capacity"],
                                       phase_capacity=budget["phase_capacity"])
            if witness["status"] != "FEASIBLE" or witness != data["witness"]:
                fail("V5_REVISED_PLAN_NOT_FEASIBLE")
            state["phase_plan"], state["phase_witness"] = revised, witness
        elif kind == "EVALUATION_ADVANCED":
            if state["execution_mode"] != "EVALUATION":
                fail("V5_EVALUATION_TRANSITION_IN_PRODUCTION")
            hex_digest(data["next_packet_sha256"])
            slot = _slot(state, data["slot_id"])
            if slot["status"] != "SATISFIED" or slot["accepted_result_ref"] != data["previous_result_ref"]:
                fail("V5_EVALUATION_ADVANCE_BINDING")
            previous = next(item for item in state["accepted_results"].values()
                            if item["result_ref"] == data["previous_result_ref"])
            previous_request = state["permits"][state["reservations"][previous["reservation_id"]]["permit_id"]]["request"]
            if previous_request["packet_sha256"] == data["next_packet_sha256"]:
                fail("V5_EVALUATION_CASE_REUSE")
            slot["status"], slot["active_reservation_ref"] = "PENDING", ""
        elif kind == "EVALUATION_UNGRADED_SEALED":
            for key in ("trial_ref", "accepted_result_ref", "evidence_ref"):
                sha(data[key])
            _path(data["evidence_path"])
            rid = data["reservation_id"]
            attempt = state["reservations"].get(rid)
            accepted = state["accepted_results"].get(rid)
            permit = state["permits"].get(attempt["permit_id"]) if attempt else None
            slot = _slot(state, data["slot_id"])
            runtime = state["root_binding"]["context_runtime"]
            if (state["execution_mode"] != "EVALUATION" or
                    runtime.get("research_contract") != "desktop-research-campaign/2" or
                    not attempt or attempt["state"] != "COMPLETED" or
                    not permit or permit["slot_id"] != data["slot_id"] or
                    state["host_receipts"].get(rid, {}).get("disposition") != "created" or
                    not accepted or accepted["status"] != "incomplete" or
                    accepted["result_ref"] != data["accepted_result_ref"] or
                    accepted["supersedes"] or rid in state["ungraded_seals"] or
                    slot["status"] != "PENDING" or slot["active_reservation_ref"] or
                    slot["condition"] != "always" or slot["depends_on"] or
                    data["slot_id"] != "trial_" + data["trial_ref"][7:59] or
                    data["reason_code"] not in {"READER_PROTOCOL_DENIED", "HOST_CAPACITY_ERROR"}):
                fail("RESEARCH_UNGRADED_SEAL_DENIED")
            if data["reason_code"] == "READER_PROTOCOL_DENIED":
                if (state["context_recovery"].get(rid, {}).get("status") != "DENIED" or
                        rid not in state["context_reads"] or
                        rid in state["context_deliveries"] or
                        rid in state.get("context_wire_deliveries", {}) or
                        rid in state["context_finals"] or
                        rid in state["context_raw_finals"]):
                    fail("RESEARCH_UNGRADED_READER_SOURCE")
            elif (rid not in state.get("host_terminal_recoveries", {}) or
                  attempt["outcome"] != "FAILED" or rid in state["context_reads"]):
                fail("RESEARCH_UNGRADED_HOST_SOURCE")
            state["ungraded_seals"][rid] = copy.deepcopy(data)
            slot["status"] = "UNGRADABLE"
            slot["accepted_result_ref"] = accepted["result_ref"]
            slot["release_evidence_ref"] = data["evidence_ref"]
        elif kind == "INLINE_SATISFIED":
            slot = _slot(state, data["slot_id"])
            selection, request = data["selection"], data["request"]
            if state["execution_mode"] != "PRODUCTION" or slot["status"] != "PENDING" \
                    or slot["independence_required"] or slot["scenario"]["risk"] >= 2 \
                    or request["scenario"] != slot["scenario"] \
                    or not request["evidence"]["ready"] or not request["evidence"]["inline_sufficient"] \
                    or request["evidence"]["independence_required"] \
                    or selection.get("status") != "INLINE" \
                    or selection.get("request_ref") != ref(request) \
                    or selection.get("decision_ref") != ref({key: item for key, item in selection.items()
                                                              if key != "decision_ref"}):
                fail("V5_INLINE_SCOPE_NOT_PROVEN")
            slot["status"] = "SATISFIED"
            slot["accepted_result_ref"] = selection["decision_ref"]
        elif kind == "CLOSED":
            sha(data["evidence_ref"])
            if data["outcome"] not in {"PASS", "BLOCKED", "FAILED", "CANCELLED", "PARTIAL", "UNKNOWN"}:
                fail("V5_CLOSE_OUTCOME")
            if _usage(state)["active"]:
                fail("V5_CLOSE_ACTIVE_ATTEMPTS")
            if data["outcome"] == "PASS" and any(slot["status"] not in {"SATISFIED", "WAIVED"}
                                                for slot in state["phase_plan"]["slots"]):
                fail("V5_CLOSE_UNFULFILLED_SCOPE")
            if data["outcome"] == "PASS" and any(
                    carry["disposition"] in {"HOST_INFRA_UNGRADED", "READER_PROTOCOL_UNGRADED"}
                    for carry in state.get("historical_carries", {}).values()):
                fail("V5_CLOSE_HISTORICAL_INFRA_FAILURE")
            resolved = {reference for item in state["accepted_results"].values()
                        for reference in item["supersedes"]}
            if data["outcome"] == "PASS" and any(item["status"] in {"blocking", "incomplete"}
                    and item["result_ref"] not in resolved for item in state["accepted_results"].values()):
                fail("V5_CLOSE_UNRESOLVED_RESULTS")
            ordinary_resolved={x for r in state.get('ordinary_results',{}).values() for x in r['supersedes']}
            if data['outcome']=='PASS' and any(r['status']=='incomplete' and r['result_ref'] not in ordinary_resolved
                                               for r in state.get('ordinary_results',{}).values()):
                fail('ORDINARY_CLOSE_UNRESOLVED_RESULTS')
            state["closed"], state["outcome"] = True, data["outcome"]
        if ref(_economic_projection(state)) != before:
            state["resource_revision"] += 1
    state["sequence"], state["head_hash"] = event["sequence"], event["record_hash"]
    state["resource_ref"] = ref(_economic_projection(state))
    usage = _usage(state)
    if usage["astra_active"] > policy()["limits"]["max_astra_parallel"]:
        fail("V5_ASTRA_PARALLEL_LIMIT")
    if any(usage["resources"][key] > state["capacity"][key] for key in VECTOR_KEYS) \
            or any(usage["role_units"][key] > state["role_capacity"][key] for key in state["role_capacity"]) \
            or any(usage["phase_units"][key] > state["phase_capacity"][key] for key in state["phase_capacity"]) \
            or usage["active"] > state["max_parallel"]:
        fail("V5_CAPACITY_EXCEEDED")
    return state


def replay(events: list[dict[str, Any]]) -> dict[str, Any]:
    state = None
    previous, bound_identity = ZERO_HASH, None
    seen: set[str] = set()
    for sequence, event in enumerate(events, 1):
        exact(event, FRAME_FIELDS, "V5_EVENT_FIELDS")
        integer(event["sequence"], "V5_EVENT_SEQUENCE", minimum=1,
                maximum=policy()["limits"]["max_ledger_records"])
        identifier(event["event_id"]); hex_digest(event["record_hash"]); hex_digest(event["previous_hash"])
        _identity(event["identity"])
        if event["schema_version"] != SCHEMA or event["sequence"] != sequence \
                or event["previous_hash"] != previous or event["event_id"] in seen:
            fail("V5_EVENT_CHAIN_INVALID")
        kind = event["event_type"]
        if kind not in EVENT_FIELDS:
            fail("V5_EVENT_TYPE")
        exact(event["data"], EVENT_FIELDS[kind], "V5_EVENT_DATA_FIELDS")
        if ref({key: value for key, value in event.items() if key != "record_hash"})[7:] != event["record_hash"]:
            fail("V5_EVENT_HASH_MISMATCH")
        if bound_identity is not None and event["identity"] != bound_identity:
            fail("V5_LEDGER_IDENTITY_CHANGED")
        bound_identity = event["identity"]
        seen.add(event["event_id"])
        state = _apply(state, event)
        previous = event["record_hash"]
    if state is None:
        fail("V5_LEDGER_EMPTY")
    return state


def _append(path: Path, events: list[dict[str, Any]], event: dict[str, Any]) -> dict[str, Any]:
    complete = events + [event]
    if len(complete) > policy()["limits"]["max_ledger_records"]:
        fail("V5_LEDGER_RECORD_LIMIT")
    state = replay(complete)
    raw = "".join(canonical_json(item) + "\n" for item in complete).encode("utf-8")
    if len(raw) > policy()["limits"]["max_ledger_bytes"]:
        fail("V5_LEDGER_TOO_LARGE")
    atomic_write_bytes(path, raw)
    return state


def read_budget(path: Path) -> dict[str, Any]:
    with OwnerTokenLock(path, timeout=2):
        return replay(_read_events(path))


def initialize(path: Path, *, declared_identity: Mapping[str, Any], root_binding: Mapping[str, Any],
               sources: Mapping[str, Any], execution_mode: str, capacity: Mapping[str, int],
               role_capacity: Mapping[str, int], phase_capacity: Mapping[str, int],
               phase_plan: Mapping[str, Any], max_parallel: int = 3, max_depth: int = 2) -> dict[str, Any]:
    declared_identity = _identity(dict(declared_identity))
    exact(dict(root_binding), ROOT_FIELDS, "V5_ROOT_BINDING_FIELDS")
    if any(slot.get("status") == "UNGRADABLE" for slot in phase_plan.get("slots", [])):
        fail("RESEARCH_UNGRADABLE_CANNOT_INITIALIZE")
    require_external_state(path.resolve(), Path(root_binding["repo_path"]).resolve())
    witness = feasible_witness(phase_plan, capacity, role_capacity=role_capacity, phase_capacity=phase_capacity)
    if witness["status"] != "FEASIBLE":
        fail("V5_INITIAL_PLAN_" + witness["status"])
    data = {"root_binding": dict(root_binding), "sources": dict(sources), "execution_mode": execution_mode,
            "capacity": dict(capacity), "role_capacity": dict(role_capacity), "phase_capacity": dict(phase_capacity),
            "max_parallel": max_parallel, "max_depth": max_depth, "phase_plan": dict(phase_plan), "witness": witness}
    with OwnerTokenLock(path, timeout=2):
        events = _read_events(path)
        if events:
            if events[0]["identity"] != declared_identity or events[0]["data"] != data:
                fail("V5_INITIALIZATION_CONFLICT")
            return replay(events)
        return _append(path, [], _event(None, declared_identity, "INITIALIZED", data))


def prepare(path: Path, request: Mapping[str, Any], *, dispatch_key: str, depth: int,
            snapshot_loader: SnapshotLoader, transition: Mapping[str, Any] | None = None,
            review_binding: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if not re.fullmatch(r"[a-z0-9_]{1,64}", dispatch_key):
        fail("V5_NAMED_DISPATCH_REQUIRED")
    if depth != 1:
        fail("V5_DEPTH_ONE_REQUIRED")
    validate_request(dict(request))
    with OwnerTokenLock(path, timeout=2):
        events = _read_events(path)
        state = replay(events)
        snapshot = snapshot_loader(state, request, utc_now())
        request = copy.deepcopy(dict(request))
        request["expected"] = snapshot_references(snapshot)
        choice = _select(state,request,snapshot)
        if choice["status"] == "INLINE":
            _append(path, events, _event(state, state["identity"], "INLINE_SATISFIED",
                                         {"slot_id": request["slot_id"], "request": request, "selection": choice}))
            return choice
        if choice["status"] not in SELECTED:
            return choice
        if any(item["dispatch_ref"] == ref(dispatch_key) for item in state["permits"].values()):
            fail("V5_DISPATCH_KEY_REUSE")
        attempt_no = 1 + sum(item["slot_id"] == request["slot_id"] for item in state["permits"].values())
        nonce = secrets.token_hex(32)
        permit_id = _stable("DP5_", state["identity"]["budget_id"], choice["decision_ref"], str(attempt_no), ref(nonce))
        data = {"permit_id": permit_id, "nonce_ref": ref(nonce), "dispatch_ref": ref(dispatch_key),
                "request": request, "selection": choice, "role": request["scenario"]["role"],
                "slot_id": request["slot_id"], "attempt_no": attempt_no, "depth": depth,
                "transition": dict(transition or {}), "review_binding": dict(review_binding or {})}
        _append(path, events, _event(state, state["identity"], "PREPARED", data))
        return {**choice, "permit_id": permit_id}


def approve_and_reserve(path: Path, *, permit_id: str, host_dispatch_id: str,
                        model: str, effort: str, agent_type: str, snapshot_loader: SnapshotLoader,
                        transport_audit_sha256: str, binding_guard: Callable | None = None) -> dict[str, Any]:
    identifier(host_dispatch_id)
    with OwnerTokenLock(path, timeout=2):
        events = _read_events(path)
        state = replay(events)
        if binding_guard is None or not state["root_host_binding"]:
            fail("V5_ACTIVE_REGISTRATION_REQUIRED")
        binding_guard(state)
        permit = state["permits"].get(permit_id)
        if not permit:
            fail("V5_PERMIT_UNKNOWN")
        requested = permit["selection"]["request_parameters"]
        if (model, effort, agent_type) != (requested["model"], requested["reasoning_effort"], requested["agent_type"]):
            fail("V5_PERMIT_REQUEST_MISMATCH")
        hex_digest(transport_audit_sha256)
        # 中文：密文仅作审计；业务字节由上下文适配器重新校验。
        # English: Opaque transport is audit data, never a plaintext equality claim.
        host_ref = ref(host_dispatch_id)
        existing_id = state["host_dispatches"].get(host_ref)
        if existing_id:
            existing = state["reservations"][existing_id]
            if existing["permit_id"] != permit_id or existing["transport_audit_sha256"] != transport_audit_sha256:
                fail("HOST_DISPATCH_COLLISION")
            if existing["state"] == "NOT_STARTED_RELEASED":
                fail("RELEASED_ATTEMPT_REUSE")
            if existing["state"] != "RESERVED" or existing_id in state["host_receipts"]:
                fail("ATTEMPT_ALREADY_STARTED")
            # 中文：同一宿主调用重试也要核对当前状态。
            # English: Revalidate live state even when the same host call retries.
            current = snapshot_loader(state, permit["request"], utc_now())
            live = snapshot_references(current)
            expected = permit["selection"]["snapshots"]
            if any(live[key] != expected[key] for key in
                   ("plan_revision", "capability_revision", "capability_ref", "cards_ref")) \
                    or permit["selection"]["approved_profile"] not in current["capability"]["available_profiles"]:
                fail("STALE_SNAPSHOT")
            return {**existing, "idempotent": True}
        if permit["status"] != "PREPARED":
            fail("PERMIT_ALREADY_CONSUMED")
        snapshot = snapshot_loader(state, permit["request"], utc_now())
        choice = _select(state,permit['request'],snapshot)
        if choice["status"] not in SELECTED or choice["decision_ref"] != permit["selection"]["decision_ref"]:
            fail("STALE_SNAPSHOT")
        rid = _stable("DBR5_", state["identity"]["budget_id"], host_ref)
        data = {"reservation_id": rid, "permit_id": permit_id, "host_dispatch_ref": host_ref,
                "selection_ref": choice["decision_ref"], "transport_audit_sha256": transport_audit_sha256}
        updated = _append(path, events, _event(state, state["identity"], "DISPATCH_RESERVED", data))
        return {**updated["reservations"][rid], "idempotent": False}


def _mutate(path: Path, kind: str, data: Mapping[str, Any],
            before: Callable[[dict[str, Any]], dict[str, Any] | None] | None = None) -> dict[str, Any]:
    with OwnerTokenLock(path, timeout=2):
        events = _read_events(path)
        state = replay(events)
        if state["closed"]:
            fail("V5_BUDGET_CLOSED")
        if before:
            existing = before(state)
            if existing is not None:
                return existing
        return _append(path, events, _event(state, state["identity"], kind, data))


def record_receipt(path: Path, *, host_dispatch_id: str, agent_id: str = "",
                   disposition: str = "created", not_started_proof: str = "") -> dict[str, Any]:
    with OwnerTokenLock(path, timeout=2):
        events = _read_events(path)
        state = replay(events)
        if state["closed"]:
            fail("V5_BUDGET_CLOSED")
        rid = state["host_dispatches"].get(ref(identifier(host_dispatch_id)))
        if not rid:
            fail("V5_RECEIPT_WITHOUT_RESERVATION")
        if disposition == "created":
            _agent_identifier(agent_id)
            proof = ref({"source": "native-post-tool", "root": state["root_binding"]["host_session_ref"],
                         "call": ref(host_dispatch_id), "agent": ref(agent_id)})
        else:
            proof = sha(not_started_proof, "V5_NOT_STARTED_PROOF_REQUIRED")
        data = {"reservation_id": rid, "agent_ref": ref(agent_id) if agent_id else "",
                "disposition": disposition, "proof_ref": proof}
        existing = state["host_receipts"].get(rid)
        if existing:
            if existing != data:
                fail("V5_RECEIPT_CONFLICT")
            return {"reservation_id": rid, "idempotent": True}
        updated = _append(path, events, _event(state, state["identity"], "HOST_RECEIPT", data))
        return {"reservation_id": rid, "state": updated["reservations"][rid]["state"], "idempotent": False}


def record_observation(path: Path, *, agent_id: str, phase: str, outcome: str = "UNKNOWN") -> dict[str, Any]:
    _agent_identifier(agent_id)
    data = {"agent_ref": ref(agent_id), "phase": phase, "outcome": outcome}
    def previous(state):
        item = state["host_observations"].get(data["agent_ref"], {})
        if phase in item:
            if item[phase] != outcome:
                fail("V5_OBSERVATION_CONFLICT")
            return {"idempotent": True}
        return None
    return _mutate(path, "HOST_OBSERVED", data, previous)


def link_host_identity(path: Path, *, reservation_id: str, task_path: str, agent_id: str,
                       dispatch_key: str, role: str, proof_ref: str,
                       verified_proof_aliases: tuple[str, ...] = ()) -> dict[str, Any]:
    _agent_identifier(task_path); _agent_identifier(agent_id); identifier(dispatch_key)
    if task_path != "/root/" + dispatch_key:
        fail("V5_IDENTITY_LINK_TASK_MISMATCH")
    # 中文：适配器最多提供两个已核验文件表示；旧摘要的选择在账本锁内完成。
    # English: At most two verified file spellings are offered; reuse is decided under the ledger lock.
    if not isinstance(verified_proof_aliases, tuple) or len(verified_proof_aliases) > 2:
        fail("V5_IDENTITY_PROOF_ALIASES")
    for alias in verified_proof_aliases:
        sha(alias)
    if verified_proof_aliases and proof_ref not in verified_proof_aliases:
        fail("V5_IDENTITY_PROOF_ALIASES")
    accepted_proofs = {proof_ref, *verified_proof_aliases}
    data = {"reservation_id": reservation_id, "task_path_ref": ref(task_path), "agent_ref": ref(agent_id),
            "dispatch_ref": ref(dispatch_key), "role": role, "proof_ref": proof_ref}
    def previous(state):
        old = state["host_identity_links"].get(reservation_id)
        if old is not None:
            if ({key: value for key, value in old.items() if key != "proof_ref"}
                    != {key: value for key, value in data.items() if key != "proof_ref"}
                    or old["proof_ref"] not in accepted_proofs):
                fail("V5_IDENTITY_LINK_CONFLICT")
            return state
        return None
    return _mutate(path, "HOST_IDENTITY_LINKED", data, previous)


def release_not_started(path: Path, *, reservation_id: str, proof_ref: str) -> dict[str, Any]:
    return _mutate(path, "NOT_STARTED_RELEASED", {"reservation_id": reservation_id, "proof_ref": proof_ref})


def accept_result(path: Path, *, reservation_id: str, result_ref: str, status: str,
                  response_ref: str, baseline_sha256: str,
                  supersedes: list[str] | None = None) -> dict[str, Any]:
    data = {
        "reservation_id": reservation_id, "result_ref": result_ref, "status": status,
        "response_ref": response_ref, "baseline_sha256": baseline_sha256, "supersedes": list(supersedes or [])}
    def previous(state):
        old = state["accepted_results"].get(reservation_id)
        if old is not None:
            if old != data:
                fail("V5_RESULT_CONFLICT")
            return state
        return None
    return _mutate(path, "RESULT_ACCEPTED", data, previous)


def waive_repair(path: Path, *, slot_id: str, post_result_ref: str, evidence_ref: str) -> dict[str, Any]:
    return _mutate(path, "SLOT_WAIVED", {"slot_id": slot_id, "post_result_ref": post_result_ref,
                                      "evidence_ref": evidence_ref})


def revise_plan(path: Path, new_plan: Mapping[str, Any], *, reason_ref: str) -> dict[str, Any]:
    with OwnerTokenLock(path, timeout=2):
        events = _read_events(path)
        state = replay(events)
        revised = validate_revision(state["phase_plan"], new_plan)
        available = snapshot_budget(state)
        witness = feasible_witness(revised, available["remaining"], role_capacity=available["role_capacity"],
                                   phase_capacity=available["phase_capacity"])
        return _append(path, events, _event(state, state["identity"], "PLAN_REVISED",
                                            {"plan": revised, "witness": witness, "reason_ref": reason_ref}))


def revoke_prepare(path: Path, *, permit_id: str, reason_ref: str) -> dict[str, Any]:
    return _mutate(path, "PREPARE_REVOKED", {"permit_id": permit_id, "reason_ref": reason_ref})


def add_evidence_paths(path: Path, evidence_paths: Mapping[str, str]) -> dict[str, Any]:
    def previous(state):
        known = state["sources"]["evidence_paths"]
        if evidence_paths and all(known.get(key) == value for key, value in evidence_paths.items()):
            return state
        return None
    return _mutate(path, "EVIDENCE_ADDED", {"evidence_paths": dict(evidence_paths)}, previous)


def advance_evaluation(path: Path, *, slot_id: str, previous_result_ref: str,
                       next_packet_sha256: str) -> dict[str, Any]:
    return _mutate(path, "EVALUATION_ADVANCED", {"slot_id": slot_id,
                   "previous_result_ref": previous_result_ref, "next_packet_sha256": next_packet_sha256})


def seal_ungraded_evaluation(path: Path, data: Mapping[str, Any]) -> dict[str, Any]:
    """中文：封存已核实的终态缺口，保留尝试费用，不生成评分。
    
    English: Seal a verified terminal gap without refunding its attempt or creating a grade.
    """
    return _mutate(path, "EVALUATION_UNGRADED_SEALED", dict(data))


def close(path: Path, *, outcome: str, evidence_ref: str) -> dict[str, Any]:
    return _mutate(path, "CLOSED", {"outcome": outcome, "evidence_ref": evidence_ref})


def ordinary_final_attested(path: Path,data: Mapping[str,Any]) -> dict[str,Any]:
    def previous(state):
        old=state.get('ordinary_finals',{}).get(data['reservation_id'])
        if old:
            if old!=dict(data):fail('ORDINARY_FINAL_CONFLICT')
            return state
        return None
    return _mutate(path,'ORDINARY_FINAL_ATTESTED',data,previous)


def ordinary_result_accepted(path: Path,data: Mapping[str,Any]) -> dict[str,Any]:
    def previous(state):
        old=state.get('ordinary_results',{}).get(data['reservation_id'])
        if old:
            if old!=dict(data):fail('ORDINARY_RESULT_CONFLICT')
            return state
        return None
    return _mutate(path,'ORDINARY_RESULT_ACCEPTED',data,previous)


def export_trace(path: Path, receipt_ref: str) -> dict[str, Any]:
    """中文：只读取已关闭实验账本，避免消费根与发行根的交叉锁。

    English: Read an immutable closed evaluation journal without cross-root locks.
    """
    sha(receipt_ref)
    state = replay(_read_events(path))
    from .research_bootstrap import deny_statistics
    deny_statistics(state)
    if state["execution_mode"] != "EVALUATION" or not state["closed"]:
        fail("EVALUATION_TRACE_NOT_FINALIZED")
    matches = [(rid, value) for rid, value in state["host_receipts"].items() if ref(value) == receipt_ref]
    if len(matches) != 1:
        fail("EVALUATION_RECEIPT_UNKNOWN")
    rid, receipt = matches[0]
    from .routing_context_v4 import read_evaluation
    case_ref = state["permits"][state["reservations"][rid]["permit_id"]]["request"]["evaluation_case_ref"]
    return _trace_from_state(state, rid, read_evaluation(state, case_ref=case_ref))


def export_traces(path: Path) -> dict[str, dict[str, Any]]:
    """中文：每个已关闭账本只重放一次，输出有界摘要索引。

    English: Replay each closed journal once and export a bounded trace index.
    """
    state = replay(_read_events(path))
    from .research_bootstrap import deny_statistics
    deny_statistics(state)
    if state["execution_mode"] != "EVALUATION" or not state["closed"]:
        fail("EVALUATION_TRACE_NOT_FINALIZED")
    if state['root_binding']['context_runtime'].get('ordinary_contract') and not state['accepted_results']:
        return {}
    from .routing_context_v4 import read_evaluations, choose_evaluation
    evaluations = read_evaluations(state)
    return {ref(receipt): _trace_from_state(state, rid, choose_evaluation(evaluations, case_ref=
                state["permits"][state["reservations"][rid]["permit_id"]]["request"]["evaluation_case_ref"]))
            for rid, receipt in state["host_receipts"].items()
            if receipt["disposition"] == "created" and rid in state["accepted_results"]}


def _trace_from_state(state: Mapping[str, Any], rid: str, evaluation: Mapping[str, Any]) -> dict[str, Any]:
    from .review_vector_transport import enabled
    if enabled(state):fail("VECTOR_LEGACY_QUALIFICATION_DENIED")
    receipt = state["host_receipts"][rid]
    receipt_ref = ref(receipt)
    result = state["accepted_results"].get(rid)
    attempt = state["reservations"][rid]
    if receipt["disposition"] != "created" or attempt["state"] != "COMPLETED" or not result:
        fail("EVALUATION_RESPONSE_NOT_CAPTURED")
    permit = state["permits"][attempt["permit_id"]]
    request = permit["request"]
    if rid not in state["context_deliveries"]:
        fail("V5_TRACE_CONTEXT_NOT_DELIVERED")
    trace = {
        "schema_version": "desktop-evaluation-trace/2", "host_surface": "codex-desktop",
        "identity": {key: state["identity"][key] for key in ("project_id", "repo_fingerprint")},
        "task_ref": effective_agent_ref(state, rid), "call_ref": attempt["host_dispatch_ref"],
        "receipt_ref": receipt_ref, "response_ref": result["response_ref"],
        "profile_id": permit["selection"]["approved_profile"], "outcome": "COMPLETED",
        "source": "verified-host-receipt", "prompt_ref": "sha256:" + request["business_prompt_sha256"],
        "case_ref": request["evaluation_case_ref"], "scenario_ref": ref(request["scenario"]),
        "protocol_ref": evaluation["protocol_ref"],
        "context_delivery_ref": ref(state["context_deliveries"].get(rid, {})),
        "transport_mode": state["root_binding"]["context_runtime"]["transport_mode"],
    }
    if trace["transport_mode"] == "desktop-authoritative-context/2":
        # 中文：此版本明确区别于旧资格传输；未另获生产资格前，旧卡片消费者拒绝使用。
        # English: Explicitly distinct from the old qualification transport. Legacy card
        # consumers reject this version until separate production qualification.
        trace.update(schema_version="desktop-evaluation-trace/3",
                     native_final_ref=ref(state["context_finals"][rid]) if rid in state["context_finals"] else "",
                     recovery_ref=ref(state["context_recovery"][rid]),
                     result_status=result["status"],
                     native_response_verified=state["context_finals"].get(rid, {}).get("response_ref") == result["response_ref"])
        raw=state["context_raw_finals"].get(rid)
        if raw:
            structured=state["context_finals"].get(rid,{})
            trace.update(schema_version="desktop-evaluation-trace/4",response_ref=raw["response_ref"],
                native_raw_final_ref=ref(raw),accounted_result_ref=result["result_ref"],
                accounted_status=result["status"],host_outcome=attempt["outcome"],
                native_final_ref=ref(structured) if structured else "",
                result_status=structured.get("semantic_status","invalid"),
                native_response_verified=True)
    return trace


def context_read_started(path: Path, data: Mapping[str, Any]) -> dict[str, Any]:
    def previous(state):
        old = state["context_reads"].get(data["reservation_id"])
        if state["reservations"].get(data["reservation_id"], {}).get("state") not in {"RESERVED", "STARTED"}:
            fail("V5_CONTEXT_READ_TERMINAL")
        if old is not None:
            if old != dict(data) or state["closed"]:
                fail("V5_CONTEXT_READ_CONFLICT")
            return state
        return None
    return _mutate(path, "CONTEXT_READ_STARTED", dict(data), previous)


def context_read_recovered(path: Path, data: Mapping[str, Any]) -> dict[str, Any]:
    def previous(state):
        if state["reservations"].get(data["reservation_id"], {}).get("state") not in {"RESERVED", "STARTED"}:
            fail("V5_CONTEXT_READ_TERMINAL")
        if state["context_reads"].get(data["reservation_id"]) == dict(data):
            return state
        return None
    return _mutate(path, "CONTEXT_READ_RECOVERED", dict(data), previous)


def context_recovery(path: Path, data: Mapping[str, Any]) -> dict[str, Any]:
    def previous(state):
        if state["root_binding"]["context_runtime"]["transport_mode"] != "desktop-authoritative-context/2":
            fail("CONTEXT_V2_MODE_REQUIRED")
        rid = data["reservation_id"]
        if data["action"] == "ATTEMPT" and state["reservations"].get(rid, {}).get("state") not in {"RESERVED", "STARTED"}:
            fail("V5_CONTEXT_READ_TERMINAL")
        old = state["context_recovery"].get(rid, {}).get("calls", {}).get(data["call_ref"], {}).get("events", {})
        if data["action"] in old:
            if old[data["action"]] != data["reason"] or state["context_recovery_bindings"][rid] != {
                    key: data[key] for key in ("agent_ref", "command_ref")}:
                fail("CONTEXT_V2_DUPLICATE_CONFLICT")
            return state
        return None
    return _mutate(path, "CONTEXT_RECOVERY", dict(data), previous)


def context_final_attested(path: Path, data: Mapping[str, Any]) -> dict[str, Any]:
    def previous(state):
        old = state.get("context_finals", {}).get(data["reservation_id"])
        if old:
            if old != dict(data):
                fail("CONTEXT_V2_FINAL_CONFLICT")
            return state
        return None
    return _mutate(path, "CONTEXT_FINAL_ATTESTED", dict(data), previous)


def context_raw_final_attested(path: Path, data: Mapping[str, Any]) -> dict[str, Any]:
    def previous(state):
        old=state.get("context_raw_finals",{}).get(data["reservation_id"])
        if old:
            if old != dict(data):
                fail("CONTEXT_V2_RAW_FINAL_CONFLICT")
            return state
        return None
    return _mutate(path,"CONTEXT_RAW_FINAL_ATTESTED",dict(data),previous)


def context_delivered(path: Path, *, reservation_id: str, call_ref: str, output_ref: str) -> dict[str, Any]:
    data = {"reservation_id": reservation_id, "call_ref": call_ref, "output_ref": output_ref}
    def previous(state):
        old = state["context_deliveries"].get(reservation_id)
        if old is not None:
            if old != data or state["closed"]:
                fail("V5_CONTEXT_DELIVERY_CONFLICT")
            return state
        return None
    return _mutate(path, "CONTEXT_DELIVERED", data, previous)


def bind_native_root(path: Path, *, session_ref: str, repo_ref: str, host_call_ref: str) -> dict[str, Any]:
    """中文：只由真实父 Hook 激活；English: adapter supplies the actual parent event."""
    data = {"session_ref": session_ref, "repo_ref": repo_ref, "host_call_ref": host_call_ref}
    def previous(state):
        old = state["root_host_binding"]
        if old:
            if old["session_ref"] != session_ref or old["repo_ref"] != repo_ref:
                fail("V5_NATIVE_ROOT_CONFLICT")
            return state
        return None
    return _mutate(path, "ROOT_HOST_BOUND", data, previous)


def result_supersedes(state: Mapping[str, Any], permit: Mapping[str, Any], status: str) -> list[str]:
    """中文：替代关系来自已验证转换；English: model content never chooses prior results."""
    transition = permit["transition"]
    if status not in {"pass", "nonblocking"} or not transition or not transition["prior_result_ref"]:
        return []
    prior = state["accepted_results"].get(transition["prior_reservation_id"])
    if not prior or prior["result_ref"] != transition["prior_result_ref"]:
        fail("V5_RESULT_PRIOR_BINDING")
    return [prior["result_ref"]] if prior["status"] in {"blocking", "incomplete"} else []


def context_notify_attested(path: Path, data: Mapping[str,Any]) -> dict[str,Any]:
    def previous(state):
        prior=state.get('context_notify_finals',{}).get(data['reservation_id'])
        if prior:
            if prior!=dict(data):fail('NOTIFY_ATTESTATION_CONFLICT')
            return state
        return None
    return _mutate(path,'CONTEXT_NOTIFY_ATTESTED',dict(data),previous)

def context_wire_delivered(path: Path,data: Mapping[str,Any]) -> dict[str,Any]:
    def previous(state):
        old=state.get('context_wire_deliveries',{}).get(data['reservation_id'])
        if old is not None:
            if old!=dict(data) or state['closed']:fail('WIRE_DELIVERY_CONFLICT')
            return state
        return None
    return _mutate(path,'CONTEXT_WIRE_DELIVERED',dict(data),previous)
