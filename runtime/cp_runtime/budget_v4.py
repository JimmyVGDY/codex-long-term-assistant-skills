"""中文：V4 根预算、追加事件与可恢复的阶段保留量。

English: V4 root budget, append-only logical history and recoverable phase holds.
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

from .common import atomic_write_bytes, canonical_json, require_external_state, utc_now
from .event_v2 import OwnerTokenLock
from .routing_contract import (
    ALGORITHM_ID, POLICY_ID, RoutingError, VECTOR_KEYS, exact, fail, identifier,
    identity, integer, policy, policy_digest, profile_spec, ref, resource_need, role_for,
    sha, vector, hex_digest, admitted,
)
from .routing_phase_plan import (
    current_slot, feasible_witness, validate_plan, validate_revision,
)
from .routing_v4 import select, snapshot_references

SCHEMA = "4.0"
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
    "DISPATCH_RESERVED": {"reservation_id", "permit_id", "host_dispatch_ref", "selection_ref"},
    "HOST_RECEIPT": {"reservation_id", "agent_ref", "disposition", "proof_ref"},
    "HOST_IDENTITY_LINKED": {"reservation_id", "task_path_ref", "agent_ref", "dispatch_ref", "role", "proof_ref"},
    "HOST_OBSERVED": {"agent_ref", "phase", "outcome"},
    "NOT_STARTED_RELEASED": {"reservation_id", "proof_ref"},
    "RESULT_ACCEPTED": {"reservation_id", "result_ref", "status", "response_ref", "baseline_sha256", "supersedes"},
    "SLOT_WAIVED": {"slot_id", "post_result_ref", "evidence_ref"},
    "PLAN_REVISED": {"plan", "witness", "reason_ref"},
    "EVIDENCE_ADDED": {"evidence_paths"},
    "EVALUATION_ADVANCED": {"slot_id", "previous_result_ref", "next_packet_sha256"},
    "INLINE_SATISFIED": {"slot_id", "request", "selection"},
    "CLOSED": {"outcome", "evidence_ref"},
}
IDENTITY_FIELDS = {"budget_id", "task_id", "project_id", "repo_fingerprint"}
ROOT_FIELDS = {"schema_version", "repo_path", "profile_path", "profile_binding_sha256",
               "envelope_identity_ref", "host_session_ref", "policy_id", "policy_digest"}
SELECTED = {"CANDIDATE_SELECTED", "EVALUATION_SELECTED"}
SnapshotLoader = Callable[[Mapping[str, Any], Mapping[str, Any], str], dict[str, Any]]


def _stable(prefix: str, *values: str) -> str:
    return prefix + hashlib.sha256("\0".join(values).encode()).hexdigest()


def _agent_identifier(value: str) -> str:
    if isinstance(value, str) and re.fullmatch(r"/root(?:/[a-z0-9_]{1,64}){1,3}", value):
        return value
    return identifier(value, "V4_AGENT_IDENTIFIER")


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
        fail("V4_SOURCE_PATH_INVALID")
    return value


def validate_sources(value: Any) -> dict[str, Any]:
    exact(value, {"root_envelope", "capability", "card_sets", "evaluation_costs", "evaluation_ref", "evidence_paths"},
          "V4_SOURCE_FIELDS")
    _path(value["root_envelope"]); _path(value["capability"])
    _path(value["evaluation_costs"], optional=True)
    if value["evaluation_ref"]:
        sha(value["evaluation_ref"])
    elif value["evaluation_ref"] != "":
        fail("V4_EVALUATION_REFERENCE")
    if not isinstance(value["card_sets"], list) or len(value["card_sets"]) > 10 \
            or not isinstance(value["evidence_paths"], dict) or len(value["evidence_paths"]) > 24:
        fail("V4_SOURCE_LIMIT")
    for item in value["card_sets"]:
        exact(item, {"bundle", "experiment", "publication", "trace_ledgers", "bundle_ref",
                     "experiment_ref", "publication_ref", "publication_revision"}, "V4_CARD_SOURCE_FIELDS")
        for key in ("bundle", "experiment", "publication"):
            _path(item[key])
        for key in ("bundle_ref", "experiment_ref", "publication_ref"):
            sha(item[key])
        integer(item["publication_revision"], "V4_PUBLICATION_REVISION", minimum=1)
        if not isinstance(item["trace_ledgers"], list) or len(item["trace_ledgers"]) > 100:
            fail("V4_TRACE_SOURCE_LIMIT")
        for source in item["trace_ledgers"]:
            _path(source)
    for evidence_ref, source in value["evidence_paths"].items():
        sha(evidence_ref); _path(source)
    return copy.deepcopy(value)


def _event(state: Mapping[str, Any] | None, declared_identity: Mapping[str, Any],
           kind: str, data: Mapping[str, Any]) -> dict[str, Any]:
    exact(dict(data), EVENT_FIELDS[kind], "BUDGET_EVENT_DATA_FIELDS")
    item = {"schema_version": SCHEMA, "sequence": 1 if state is None else state["sequence"] + 1,
            "event_id": "DB4_" + secrets.token_hex(16), "event_type": kind, "recorded_at": utc_now(),
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
        fail("V4_LEDGER_TOO_LARGE")
    if raw and not raw.endswith(b"\n"):
        fail("V4_LEDGER_PARTIAL_TAIL")
    lines = raw.splitlines()
    if len(lines) > policy()["limits"]["max_ledger_records"]:
        fail("V4_LEDGER_RECORD_LIMIT")
    from .routing_contract import _object, _constant
    try:
        return [json.loads(line, object_pairs_hook=_object, parse_constant=_constant) for line in lines]
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise RoutingError("V4_LEDGER_INVALID_JSON") from exc


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
            fail("V4_DUPLICATE_INITIALIZATION")
        root = data["root_binding"]
        exact(root, ROOT_FIELDS, "V4_ROOT_BINDING_FIELDS")
        if root["schema_version"] != "dispatch-root/2" or root.get("policy_id") != POLICY_ID \
                or root.get("policy_digest") != policy_digest():
            fail("V4_ROOT_BINDING_POLICY")
        _path(root["repo_path"]); _path(root["profile_path"])
        hex_digest(root["profile_binding_sha256"]); sha(root["envelope_identity_ref"])
        sha(root.get("host_session_ref"))
        validate_sources(data["sources"])
        capacity = vector(data["capacity"])
        if capacity["units"] < 1 or capacity["attempts"] < 1:
            fail("V4_EMPTY_CAPACITY")
        for key, keys in (("role_capacity", {"reviewer", "worker", "explorer"}),
                          ("phase_capacity", {"pre", "post", "repair"})):
            exact(data[key], keys, "V4_LOCAL_CAPACITY_FIELDS")
            for limit in data[key].values():
                integer(limit, "V4_LOCAL_CAPACITY")
        integer(data["max_parallel"], "V4_MAX_PARALLEL", minimum=1, maximum=3)
        integer(data["max_depth"], "V4_MAX_DEPTH", minimum=1, maximum=3)
        if data["execution_mode"] not in {"PRODUCTION", "EVALUATION"}:
            fail("EXECUTION_MODE_INVALID")
        plan = validate_plan(data["phase_plan"], expected_identity={
            key: event["identity"][key] for key in ("project_id", "repo_fingerprint")})
        witness = feasible_witness(plan, capacity, role_capacity=data["role_capacity"],
                                   phase_capacity=data["phase_capacity"])
        if witness["status"] != "FEASIBLE" or witness != data["witness"]:
            fail("V4_INITIAL_PLAN_NOT_FEASIBLE")
        state = {
            "schema_version": SCHEMA, "identity": dict(event["identity"]), "policy_id": POLICY_ID,
            "policy_digest": policy_digest(), "root_binding": copy.deepcopy(root),
            "sources": copy.deepcopy(data["sources"]), "execution_mode": data["execution_mode"],
            "capacity": capacity, "role_capacity": dict(data["role_capacity"]),
            "phase_capacity": dict(data["phase_capacity"]), "max_parallel": data["max_parallel"],
            "max_depth": data["max_depth"], "phase_plan": plan, "phase_witness": witness,
            "permits": {}, "reservations": {}, "host_dispatches": {}, "host_receipts": {},
            "host_observations": {}, "accepted_results": {}, "closed": False, "outcome": "UNKNOWN",
            "host_identity_links": {},
            "resource_revision": 1, "resource_ref": "",
            "_usage_cache": {"resources": {key: 0 for key in VECTOR_KEYS},
                             "role_units": {key: 0 for key in ("reviewer", "worker", "explorer")},
                             "phase_units": {key: 0 for key in ("pre", "post", "repair")},
                             "active": 0, "astra_active": 0},
        }
    else:
        if state is None:
            fail("V4_INITIALIZATION_MISSING")
        if state["closed"]:
            fail("V4_BUDGET_CLOSED")
        before = ref(_economic_projection(state))
        if kind == "PREPARED":
            identifier(data["permit_id"]); sha(data["nonce_ref"]); sha(data["dispatch_ref"])
            integer(data["attempt_no"], "V4_ATTEMPT_NUMBER", minimum=1)
            integer(data["depth"], "V4_DEPTH", minimum=1, maximum=state["max_depth"])
            if data["permit_id"] in state["permits"] or any(
                item["nonce_ref"] == data["nonce_ref"] or item["dispatch_ref"] == data["dispatch_ref"]
                for item in state["permits"].values()):
                fail("V4_PREPARE_COLLISION")
            choice = data["selection"]
            if choice.get("status") not in SELECTED or choice.get("decision_ref") != ref({
                key: value for key, value in choice.items() if key != "decision_ref"}):
                fail("V4_SELECTION_INTEGRITY")
            spec = profile_spec(choice.get("approved_profile"))
            if choice["approved_profile"] not in admitted(data["role"], state["execution_mode"]) \
                    or choice["request_parameters"] != {
                        "model": spec["model"], "reasoning_effort": spec["effort"], "agent_type": data["role"]}:
                fail("V4_SELECTION_TUPLE_MISMATCH")
            if data["request"]["identity"] != {key: state["identity"][key] for key in ("project_id", "repo_fingerprint")} \
                    or data["request"]["task_id"] != state["identity"]["task_id"] \
                    or data["request"]["execution_mode"] != state["execution_mode"] \
                    or data["request"]["scenario"]["role"] != data["role"] \
                    or data["request"]["slot_id"] != data["slot_id"]:
                fail("V4_PREPARE_IDENTITY")
            if choice["snapshots"]["ledger_revision"] != state["resource_revision"] \
                    or choice["snapshots"]["ledger_head_ref"] != state["resource_ref"]:
                fail("STALE_SNAPSHOT")
            if _slot(state, data["slot_id"])["status"] != "PENDING":
                fail("PHASE_SLOT_NOT_PENDING")
            if data["review_binding"]:
                binding = exact(data["review_binding"], {"review_state_ref", "boundary_id", "reviewer"},
                                "V4_REVIEW_BINDING_FIELDS")
                sha(binding["review_state_ref"]); identifier(binding["boundary_id"]); identifier(binding["reviewer"])
                if binding["reviewer"] != data["role"]:
                    fail("V4_REVIEW_ROLE_BINDING")
            for previous_binding in state["permits"].values():
                if previous_binding["slot_id"] == data["slot_id"] \
                        and previous_binding["review_binding"] != data["review_binding"]:
                    fail("V4_REVIEW_OWNER_CONFLICT")
            prior = [item for item in state["permits"].values()
                     if item["slot_id"] == data["slot_id"] and item["status"] == "CONSUMED"]
            if prior:
                transition = exact(data["transition"], {"prior_reservation_id", "prior_result_ref", "reason"},
                                   "V4_TRANSITION_FIELDS")
                previous = state["reservations"].get(transition["prior_reservation_id"])
                if not previous or previous["state"] not in {"COMPLETED", "NOT_STARTED_RELEASED"} \
                        or state["permits"][previous["permit_id"]]["slot_id"] != data["slot_id"]:
                    fail("PRIOR_ATTEMPT_UNRESOLVED")
                previous_permit = state["permits"][previous["permit_id"]]
                if previous_permit["attempt_no"] != max(item["attempt_no"] for item in prior):
                    fail("V4_TRANSITION_NOT_LATEST")
                if previous["state"] == "NOT_STARTED_RELEASED":
                    if transition["reason"] != "HOST_UNAVAILABLE" or transition["prior_result_ref"]:
                        fail("V4_TRANSITION_RELEASE_PROOF")
                else:
                    old_result = state["accepted_results"].get(transition["prior_reservation_id"])
                    if not old_result or old_result["result_ref"] != transition["prior_result_ref"]:
                        fail("V4_TRANSITION_RESULT_BINDING")
                    changed = any(data["request"][key] != previous_permit["request"][key]
                                  for key in ("baseline_sha256", "packet_sha256", "evidence"))
                    if not changed or transition["reason"] not in {
                        "NEW_EVIDENCE", "BASELINE_CHANGED", "TARGETED_REPAIR", "EVALUATION_NEXT"}:
                        fail("V4_REPEAT_REQUIRES_NEW_EVIDENCE")
                    if transition["reason"] == "EVALUATION_NEXT" and state["execution_mode"] != "EVALUATION":
                        fail("V4_EVALUATION_TRANSITION_IN_PRODUCTION")
            elif data["transition"]:
                fail("V4_TRANSITION_WITHOUT_PRIOR")
            selected_option = next((item for item in _slot(state, data["slot_id"])["options"]
                                    if item["profile_id"] == choice["approved_profile"]), None)
            if not selected_option or choice["reserve_units"] != selected_option["resources"]["units"] \
                    or choice["cost_ref"] != selected_option["cost_ref"] \
                    or choice["qualification_ref"] != selected_option["qualification_ref"]:
                fail("V4_SELECTION_OPTION_MISMATCH")
            state["permits"][data["permit_id"]] = {**copy.deepcopy(data), "status": "PREPARED"}
        elif kind == "PREPARE_REVOKED":
            sha(data["reason_ref"])
            permit = state["permits"].get(data["permit_id"])
            if not permit or permit["status"] != "PREPARED":
                fail("V4_PREPARE_REVOCATION_CONFLICT")
            permit["status"] = "REVOKED"
        elif kind == "DISPATCH_RESERVED":
            identifier(data["reservation_id"]); sha(data["host_dispatch_ref"]); sha(data["selection_ref"])
            permit = state["permits"].get(data["permit_id"])
            if not permit or permit["status"] != "PREPARED":
                fail("PERMIT_ALREADY_CONSUMED")
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
                fail("V4_RECEIPT_COLLISION")
            if data["disposition"] not in {"created", "not-started"}:
                fail("V4_RECEIPT_DISPOSITION")
            sha(data["proof_ref"])
            if data["disposition"] == "created":
                sha(data["agent_ref"])
                if any(row["agent_ref"] == data["agent_ref"] or effective_agent_ref(state, rid) == data["agent_ref"]
                       for rid, row in state["host_receipts"].items()):
                    fail("V4_AGENT_RECEIPT_COLLISION")
            elif data["agent_ref"]:
                fail("V4_NOT_STARTED_AGENT_CONFLICT")
            link = state["host_identity_links"].get(data["reservation_id"])
            if link and (data["disposition"] != "created" or
                         data["agent_ref"] not in {link["task_path_ref"], link["agent_ref"]}):
                fail("V4_RECEIPT_IDENTITY_LINK_CONFLICT")
            state["host_receipts"][data["reservation_id"]] = copy.deepcopy(data)
            _project_host(state, data["reservation_id"])
        elif kind == "HOST_IDENTITY_LINKED":
            for key in ("task_path_ref", "agent_ref", "dispatch_ref", "proof_ref"):
                sha(data[key])
            attempt = state["reservations"].get(data["reservation_id"])
            if not attempt or attempt["state"] == "NOT_STARTED_RELEASED":
                fail("V4_IDENTITY_LINK_WITHOUT_ATTEMPT")
            permit = state["permits"][attempt["permit_id"]]
            if data["dispatch_ref"] != permit["dispatch_ref"] or data["role"] != permit["role"] \
                    or data["reservation_id"] in state["host_identity_links"] \
                    or any(link["agent_ref"] == data["agent_ref"] for link in state["host_identity_links"].values()):
                fail("V4_IDENTITY_LINK_CONFLICT")
            receipt = state["host_receipts"].get(data["reservation_id"])
            if receipt and (receipt["disposition"] != "created" or
                            receipt["agent_ref"] not in {data["task_path_ref"], data["agent_ref"]}):
                fail("V4_RECEIPT_IDENTITY_LINK_CONFLICT")
            if receipt and receipt["agent_ref"] != data["agent_ref"] \
                    and "stop" in state["host_observations"].get(receipt["agent_ref"], {}):
                fail("V4_IDENTITY_LINK_AFTER_TERMINAL")
            if any(rid != data["reservation_id"] and row["agent_ref"] == data["agent_ref"]
                   for rid, row in state["host_receipts"].items()):
                fail("V4_IDENTITY_LINK_CONFLICT")
            state["host_identity_links"][data["reservation_id"]] = copy.deepcopy(data)
            _project_host(state, data["reservation_id"])
        elif kind == "HOST_OBSERVED":
            sha(data["agent_ref"])
            if data["phase"] not in {"start", "stop"} or data["outcome"] not in {
                "PASS", "BLOCKED", "FAILED", "CANCELLED", "PARTIAL", "UNKNOWN"}:
                fail("V4_HOST_OBSERVATION")
            observations = state["host_observations"].setdefault(data["agent_ref"], {})
            if data["phase"] in observations:
                fail("V4_DUPLICATE_OBSERVATION_EVENT")
            if data["phase"] == "start" and data["outcome"] != "UNKNOWN":
                fail("V4_START_OUTCOME_INVALID")
            observations[data["phase"]] = data["outcome"]
            for rid, receipt in state["host_receipts"].items():
                if effective_agent_ref(state, rid) == data["agent_ref"]:
                    _project_host(state, rid)
        elif kind == "NOT_STARTED_RELEASED":
            attempt = state["reservations"].get(data["reservation_id"])
            receipt = state["host_receipts"].get(data["reservation_id"])
            if not attempt or attempt["state"] != "RESERVED" or not receipt \
                    or receipt["disposition"] != "not-started" or receipt["proof_ref"] != data["proof_ref"]:
                fail("V4_RELEASE_REQUIRES_NOT_STARTED_PROOF")
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
        elif kind == "RESULT_ACCEPTED":
            sha(data["result_ref"]); sha(data["response_ref"])
            attempt = state["reservations"].get(data["reservation_id"])
            if not attempt or attempt["state"] != "COMPLETED" or data["reservation_id"] in state["accepted_results"]:
                fail("V4_RESULT_REQUIRES_COMPLETED_ATTEMPT")
            permit = state["permits"][attempt["permit_id"]]
            if data["baseline_sha256"] != permit["request"]["baseline_sha256"] \
                    or data["status"] not in {"pass", "nonblocking", "blocking", "incomplete"}:
                fail("V4_RESULT_BINDING")
            # 中文：已知的未完成终态不能被结果覆盖；UNKNOWN 仍需独立核验结果。
            # English: A known unsuccessful stop cannot be overridden by a completed
            # review. UNKNOWN never supplies a verdict; result validation is separate.
            if attempt["outcome"] in {"CANCELLED", "FAILED", "PARTIAL", "BLOCKED"} \
                    and data["status"] != "incomplete":
                fail("V4_RESULT_CONFLICTS_WITH_HOST_OUTCOME")
            slot = _slot(state, permit["slot_id"])
            if slot["status"] != "AWAITING_RESULT":
                fail("V4_RESULT_SLOT_STATE")
            state["accepted_results"][data["reservation_id"]] = copy.deepcopy(data)
            if not isinstance(data["supersedes"], list) or len(data["supersedes"]) > 10 \
                    or len(set(data["supersedes"])) != len(data["supersedes"]):
                fail("V4_SUPERSEDES_FIELDS")
            for previous_ref in data["supersedes"]:
                sha(previous_ref)
                old = next((item for rid, item in state["accepted_results"].items()
                            if rid != data["reservation_id"] and item["result_ref"] == previous_ref), None)
                if not old or data["status"] not in {"pass", "nonblocking"} \
                        or old["status"] not in {"blocking", "incomplete"}:
                    fail("V4_SUPERSEDES_INVALID")
                old_permit = state["permits"][state["reservations"][old["reservation_id"]]["permit_id"]]
                if old_permit["slot_id"] != permit["slot_id"] and old_permit["slot_id"] not in slot["depends_on"]:
                    fail("V4_SUPERSEDES_SCOPE_MISMATCH")
            if data["status"] == "incomplete" or (
                data["status"] == "blocking" and permit["request"]["scenario"]["phase"] in {"pre", "repair"}):
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
                fail("V4_REPAIR_WAIVER_NOT_PROVEN")
            parent = state["permits"][state["reservations"][parents[0]["reservation_id"]]["permit_id"]]
            if parent["request"]["scenario"]["phase"] != "post" or parent["slot_id"] not in slot["depends_on"]:
                fail("V4_REPAIR_WAIVER_PARENT_MISMATCH")
            slot["status"] = "WAIVED"
            slot["release_evidence_ref"] = data["evidence_ref"]
        elif kind == "EVIDENCE_ADDED":
            additions = data["evidence_paths"]
            if not isinstance(additions, dict) or not additions:
                fail("V4_EVIDENCE_ADDITIONS_REQUIRED")
            previous = state["sources"]["evidence_paths"]
            if any(key in previous and previous[key] != value for key, value in additions.items()):
                fail("V4_EVIDENCE_SOURCE_REPLACEMENT")
            sources = {**state["sources"], "evidence_paths": {**previous, **additions}}
            state["sources"] = validate_sources(sources)
        elif kind == "PLAN_REVISED":
            sha(data["reason_ref"])
            revised = validate_revision(state["phase_plan"], data["plan"])
            budget = snapshot_budget(state)
            witness = feasible_witness(revised, budget["remaining"], role_capacity=budget["role_capacity"],
                                       phase_capacity=budget["phase_capacity"])
            if witness["status"] != "FEASIBLE" or witness != data["witness"]:
                fail("V4_REVISED_PLAN_NOT_FEASIBLE")
            state["phase_plan"], state["phase_witness"] = revised, witness
        elif kind == "EVALUATION_ADVANCED":
            if state["execution_mode"] != "EVALUATION":
                fail("V4_EVALUATION_TRANSITION_IN_PRODUCTION")
            hex_digest(data["next_packet_sha256"])
            slot = _slot(state, data["slot_id"])
            if slot["status"] != "SATISFIED" or slot["accepted_result_ref"] != data["previous_result_ref"]:
                fail("V4_EVALUATION_ADVANCE_BINDING")
            previous = next(item for item in state["accepted_results"].values()
                            if item["result_ref"] == data["previous_result_ref"])
            previous_request = state["permits"][state["reservations"][previous["reservation_id"]]["permit_id"]]["request"]
            if previous_request["packet_sha256"] == data["next_packet_sha256"]:
                fail("V4_EVALUATION_CASE_REUSE")
            slot["status"], slot["active_reservation_ref"] = "PENDING", ""
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
                fail("V4_INLINE_SCOPE_NOT_PROVEN")
            slot["status"] = "SATISFIED"
            slot["accepted_result_ref"] = selection["decision_ref"]
        elif kind == "CLOSED":
            sha(data["evidence_ref"])
            if data["outcome"] not in {"PASS", "BLOCKED", "FAILED", "CANCELLED", "PARTIAL", "UNKNOWN"}:
                fail("V4_CLOSE_OUTCOME")
            if _usage(state)["active"]:
                fail("V4_CLOSE_ACTIVE_ATTEMPTS")
            if data["outcome"] == "PASS" and any(slot["status"] not in {"SATISFIED", "WAIVED"}
                                                for slot in state["phase_plan"]["slots"]):
                fail("V4_CLOSE_UNFULFILLED_SCOPE")
            resolved = {reference for item in state["accepted_results"].values()
                        for reference in item["supersedes"]}
            if data["outcome"] == "PASS" and any(item["status"] in {"blocking", "incomplete"}
                    and item["result_ref"] not in resolved for item in state["accepted_results"].values()):
                fail("V4_CLOSE_UNRESOLVED_RESULTS")
            state["closed"], state["outcome"] = True, data["outcome"]
        if ref(_economic_projection(state)) != before:
            state["resource_revision"] += 1
    state["sequence"], state["head_hash"] = event["sequence"], event["record_hash"]
    state["resource_ref"] = ref(_economic_projection(state))
    usage = _usage(state)
    if usage["astra_active"] > policy()["limits"]["max_astra_parallel"]:
        fail("V4_ASTRA_PARALLEL_LIMIT")
    if any(usage["resources"][key] > state["capacity"][key] for key in VECTOR_KEYS) \
            or any(usage["role_units"][key] > state["role_capacity"][key] for key in state["role_capacity"]) \
            or any(usage["phase_units"][key] > state["phase_capacity"][key] for key in state["phase_capacity"]) \
            or usage["active"] > state["max_parallel"]:
        fail("V4_CAPACITY_EXCEEDED")
    return state


def replay(events: list[dict[str, Any]]) -> dict[str, Any]:
    state = None
    previous, bound_identity = ZERO_HASH, None
    seen: set[str] = set()
    for sequence, event in enumerate(events, 1):
        exact(event, FRAME_FIELDS, "V4_EVENT_FIELDS")
        integer(event["sequence"], "V4_EVENT_SEQUENCE", minimum=1,
                maximum=policy()["limits"]["max_ledger_records"])
        identifier(event["event_id"]); hex_digest(event["record_hash"]); hex_digest(event["previous_hash"])
        _identity(event["identity"])
        if event["schema_version"] != SCHEMA or event["sequence"] != sequence \
                or event["previous_hash"] != previous or event["event_id"] in seen:
            fail("V4_EVENT_CHAIN_INVALID")
        kind = event["event_type"]
        if kind not in EVENT_FIELDS:
            fail("V4_EVENT_TYPE")
        exact(event["data"], EVENT_FIELDS[kind], "V4_EVENT_DATA_FIELDS")
        if ref({key: value for key, value in event.items() if key != "record_hash"})[7:] != event["record_hash"]:
            fail("V4_EVENT_HASH_MISMATCH")
        if bound_identity is not None and event["identity"] != bound_identity:
            fail("V4_LEDGER_IDENTITY_CHANGED")
        bound_identity = event["identity"]
        seen.add(event["event_id"])
        state = _apply(state, event)
        previous = event["record_hash"]
    if state is None:
        fail("V4_LEDGER_EMPTY")
    return state


def _append(path: Path, events: list[dict[str, Any]], event: dict[str, Any]) -> dict[str, Any]:
    complete = events + [event]
    if len(complete) > policy()["limits"]["max_ledger_records"]:
        fail("V4_LEDGER_RECORD_LIMIT")
    state = replay(complete)
    raw = "".join(canonical_json(item) + "\n" for item in complete).encode("utf-8")
    if len(raw) > policy()["limits"]["max_ledger_bytes"]:
        fail("V4_LEDGER_TOO_LARGE")
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
    exact(dict(root_binding), ROOT_FIELDS, "V4_ROOT_BINDING_FIELDS")
    require_external_state(path.resolve(), Path(root_binding["repo_path"]).resolve())
    witness = feasible_witness(phase_plan, capacity, role_capacity=role_capacity, phase_capacity=phase_capacity)
    if witness["status"] != "FEASIBLE":
        fail("V4_INITIAL_PLAN_" + witness["status"])
    data = {"root_binding": dict(root_binding), "sources": dict(sources), "execution_mode": execution_mode,
            "capacity": dict(capacity), "role_capacity": dict(role_capacity), "phase_capacity": dict(phase_capacity),
            "max_parallel": max_parallel, "max_depth": max_depth, "phase_plan": dict(phase_plan), "witness": witness}
    with OwnerTokenLock(path, timeout=2):
        events = _read_events(path)
        if events:
            if events[0]["identity"] != declared_identity or events[0]["data"] != data:
                fail("V4_INITIALIZATION_CONFLICT")
            return replay(events)
        return _append(path, [], _event(None, declared_identity, "INITIALIZED", data))


def prepare(path: Path, request: Mapping[str, Any], *, dispatch_key: str, depth: int,
            snapshot_loader: SnapshotLoader, transition: Mapping[str, Any] | None = None,
            review_binding: Mapping[str, Any] | None = None) -> dict[str, Any]:
    identifier(dispatch_key)
    with OwnerTokenLock(path, timeout=2):
        events = _read_events(path)
        state = replay(events)
        snapshot = snapshot_loader(state, request, utc_now())
        request = copy.deepcopy(dict(request))
        request["expected"] = snapshot_references(snapshot)
        choice = select(request, snapshot)
        if choice["status"] == "INLINE":
            _append(path, events, _event(state, state["identity"], "INLINE_SATISFIED",
                                         {"slot_id": request["slot_id"], "request": request, "selection": choice}))
            return choice
        if choice["status"] not in SELECTED:
            return choice
        if any(item["dispatch_ref"] == ref(dispatch_key) for item in state["permits"].values()):
            fail("V4_DISPATCH_KEY_REUSE")
        attempt_no = 1 + sum(item["slot_id"] == request["slot_id"] for item in state["permits"].values())
        nonce = secrets.token_hex(32)
        permit_id = _stable("DP4_", state["identity"]["budget_id"], choice["decision_ref"], str(attempt_no), ref(nonce))
        data = {"permit_id": permit_id, "nonce_ref": ref(nonce), "dispatch_ref": ref(dispatch_key),
                "request": request, "selection": choice, "role": request["scenario"]["role"],
                "slot_id": request["slot_id"], "attempt_no": attempt_no, "depth": depth,
                "transition": dict(transition or {}), "review_binding": dict(review_binding or {})}
        _append(path, events, _event(state, state["identity"], "PREPARED", data))
        return {**choice, "permit_id": permit_id, "native_message_prefix": NATIVE_PREFIX + nonce + "\n\n"}


def approve_and_reserve(path: Path, *, permit_id: str, host_dispatch_id: str,
                        model: str, effort: str, agent_type: str, snapshot_loader: SnapshotLoader,
                        message_sha256: str, nonce: str = "") -> dict[str, Any]:
    identifier(host_dispatch_id)
    with OwnerTokenLock(path, timeout=2):
        events = _read_events(path)
        state = replay(events)
        permit = state["permits"].get(permit_id)
        if not permit:
            fail("V4_PERMIT_UNKNOWN")
        requested = permit["selection"]["request_parameters"]
        if (model, effort, agent_type) != (requested["model"], requested["reasoning_effort"], requested["agent_type"]):
            fail("V4_PERMIT_REQUEST_MISMATCH")
        if hex_digest(message_sha256) != permit["request"]["message_sha256"]:
            fail("V4_REQUEST_MESSAGE_MISMATCH")
        if nonce and ref(nonce) != permit["nonce_ref"]:
            fail("V4_NONCE_MISMATCH")
        host_ref = ref(host_dispatch_id)
        existing_id = state["host_dispatches"].get(host_ref)
        if existing_id:
            existing = state["reservations"][existing_id]
            if existing["permit_id"] != permit_id:
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
        choice = select(permit["request"], snapshot)
        if choice["status"] not in SELECTED or choice["decision_ref"] != permit["selection"]["decision_ref"]:
            fail("STALE_SNAPSHOT")
        rid = _stable("DBR4_", state["identity"]["budget_id"], host_ref)
        data = {"reservation_id": rid, "permit_id": permit_id, "host_dispatch_ref": host_ref,
                "selection_ref": choice["decision_ref"]}
        updated = _append(path, events, _event(state, state["identity"], "DISPATCH_RESERVED", data))
        return {**updated["reservations"][rid], "idempotent": False}


def _mutate(path: Path, kind: str, data: Mapping[str, Any],
            before: Callable[[dict[str, Any]], dict[str, Any] | None] | None = None) -> dict[str, Any]:
    with OwnerTokenLock(path, timeout=2):
        events = _read_events(path)
        state = replay(events)
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
        rid = state["host_dispatches"].get(ref(identifier(host_dispatch_id)))
        if not rid:
            fail("V4_RECEIPT_WITHOUT_RESERVATION")
        if disposition == "created":
            _agent_identifier(agent_id)
            proof = ref({"source": "native-post-tool", "root": state["root_binding"]["host_session_ref"],
                         "call": ref(host_dispatch_id), "agent": ref(agent_id)})
        else:
            proof = sha(not_started_proof, "V4_NOT_STARTED_PROOF_REQUIRED")
        data = {"reservation_id": rid, "agent_ref": ref(agent_id) if agent_id else "",
                "disposition": disposition, "proof_ref": proof}
        existing = state["host_receipts"].get(rid)
        if existing:
            if existing != data:
                fail("V4_RECEIPT_CONFLICT")
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
                fail("V4_OBSERVATION_CONFLICT")
            return {"idempotent": True}
        return None
    return _mutate(path, "HOST_OBSERVED", data, previous)


def link_host_identity(path: Path, *, reservation_id: str, task_path: str, agent_id: str,
                       dispatch_key: str, role: str, proof_ref: str,
                       verified_proof_aliases: tuple[str, ...] = ()) -> dict[str, Any]:
    _agent_identifier(task_path); _agent_identifier(agent_id); identifier(dispatch_key)
    if task_path != "/root/" + dispatch_key:
        fail("V4_IDENTITY_LINK_TASK_MISMATCH")
    # 中文：适配器最多提供两个已核验文件表示；旧摘要的选择在账本锁内完成。
    # English: At most two verified file spellings are offered; reuse is decided under the ledger lock.
    if not isinstance(verified_proof_aliases, tuple) or len(verified_proof_aliases) > 2:
        fail("V4_IDENTITY_PROOF_ALIASES")
    for alias in verified_proof_aliases:
        sha(alias)
    if verified_proof_aliases and proof_ref not in verified_proof_aliases:
        fail("V4_IDENTITY_PROOF_ALIASES")
    accepted_proofs = {proof_ref, *verified_proof_aliases}
    data = {"reservation_id": reservation_id, "task_path_ref": ref(task_path), "agent_ref": ref(agent_id),
            "dispatch_ref": ref(dispatch_key), "role": role, "proof_ref": proof_ref}
    def previous(state):
        old = state["host_identity_links"].get(reservation_id)
        if old is not None:
            if ({key: value for key, value in old.items() if key != "proof_ref"}
                    != {key: value for key, value in data.items() if key != "proof_ref"}
                    or old["proof_ref"] not in accepted_proofs):
                fail("V4_IDENTITY_LINK_CONFLICT")
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
                fail("V4_RESULT_CONFLICT")
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


def close(path: Path, *, outcome: str, evidence_ref: str) -> dict[str, Any]:
    return _mutate(path, "CLOSED", {"outcome": outcome, "evidence_ref": evidence_ref})


def export_trace(path: Path, receipt_ref: str) -> dict[str, Any]:
    """中文：只读取已关闭实验账本，避免消费根与发行根的交叉锁。

    English: Read an immutable closed evaluation journal without cross-root locks.
    """
    sha(receipt_ref)
    state = replay(_read_events(path))
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
    if state["execution_mode"] != "EVALUATION" or not state["closed"]:
        fail("EVALUATION_TRACE_NOT_FINALIZED")
    from .routing_context_v4 import read_evaluations, choose_evaluation
    evaluations = read_evaluations(state)
    return {ref(receipt): _trace_from_state(state, rid, choose_evaluation(evaluations, case_ref=
                state["permits"][state["reservations"][rid]["permit_id"]]["request"]["evaluation_case_ref"]))
            for rid, receipt in state["host_receipts"].items()
            if receipt["disposition"] == "created" and rid in state["accepted_results"]}


def _trace_from_state(state: Mapping[str, Any], rid: str, evaluation: Mapping[str, Any]) -> dict[str, Any]:
    receipt = state["host_receipts"][rid]
    receipt_ref = ref(receipt)
    result = state["accepted_results"].get(rid)
    attempt = state["reservations"][rid]
    if receipt["disposition"] != "created" or attempt["state"] != "COMPLETED" or not result:
        fail("EVALUATION_RESPONSE_NOT_CAPTURED")
    permit = state["permits"][attempt["permit_id"]]
    request = permit["request"]
    return {
        "schema_version": "desktop-evaluation-trace/1", "host_surface": "codex-desktop",
        "identity": {key: state["identity"][key] for key in ("project_id", "repo_fingerprint")},
        "task_ref": effective_agent_ref(state, rid), "call_ref": attempt["host_dispatch_ref"],
        "receipt_ref": receipt_ref, "response_ref": result["response_ref"],
        "profile_id": permit["selection"]["approved_profile"], "outcome": "COMPLETED",
        "source": "verified-host-receipt", "prompt_ref": "sha256:" + request["message_sha256"],
        "case_ref": request["evaluation_case_ref"], "scenario_ref": ref(request["scenario"]),
        "protocol_ref": evaluation["protocol_ref"],
    }
