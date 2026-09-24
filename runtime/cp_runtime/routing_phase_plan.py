"""中文：阶段保留量的真实选项见证与有界可行性搜索。

English: Phase holds use whole feasible options, never component-wise minima.
"""
from __future__ import annotations

import copy
from typing import Any, Mapping

from .routing_contract import (
    PHASES, VECTOR_KEYS, add_vectors, exact, fail, fits, identifier, identity,
    integer, policy, ref, resource_need, role_for, scenario, sha, vector,
)

SLOT_FIELDS = {"slot_id", "scenario", "condition", "depends_on", "status", "options",
               "active_reservation_ref", "accepted_result_ref", "release_evidence_ref", "independence_required"}
OPTION_FIELDS = {"profile_id", "qualification_ref", "cost_ref", "resources"}
PLAN_FIELDS = {"schema_version", "plan_id", "revision", "identity", "slots"}
STATUSES = {"PENDING", "RESERVED", "AWAITING_RESULT", "SATISFIED", "WAIVED"}
ZERO = {key: 0 for key in VECTOR_KEYS}


def validate_plan(value: Any, *, expected_identity: Mapping[str, str] | None = None) -> dict[str, Any]:
    exact(value, PLAN_FIELDS, "PHASE_PLAN_FIELDS")
    if value["schema_version"] != "phase-plan/1":
        fail("PHASE_PLAN_VERSION")
    identifier(value["plan_id"])
    integer(value["revision"], "PHASE_PLAN_REVISION", minimum=1)
    declared_identity = identity(value["identity"])
    if expected_identity is not None and dict(expected_identity) != declared_identity:
        fail("PHASE_PLAN_IDENTITY")
    slots = value["slots"]
    if not isinstance(slots, list) or not slots or len(slots) > policy()["limits"]["max_slots"]:
        fail("PHASE_PLAN_SLOT_LIMIT")
    ids: set[str] = set()
    for slot in slots:
        exact(slot, SLOT_FIELDS, "PHASE_SLOT_FIELDS")
        name = identifier(slot["slot_id"])
        if name in ids:
            fail("PHASE_SLOT_DUPLICATE")
        ids.add(name)
        declared = scenario(slot["scenario"])
        if type(slot["independence_required"]) is not bool \
                or (declared["risk"] >= 2 and not slot["independence_required"]):
            fail("PHASE_INDEPENDENCE_REQUIREMENT")
        if slot["condition"] not in {"always", "repair-after-post"} \
                or (slot["condition"] == "repair-after-post" and declared["phase"] != "repair"):
            fail("PHASE_SLOT_CONDITION")
        if slot["status"] not in STATUSES:
            fail("PHASE_SLOT_STATUS")
        dependencies = slot["depends_on"]
        if not isinstance(dependencies, list) or len(dependencies) > len(slots) \
                or len(set(dependencies)) != len(dependencies):
            fail("PHASE_SLOT_DEPENDENCIES")
        for dependency in dependencies:
            identifier(dependency)
        for key in ("active_reservation_ref", "accepted_result_ref", "release_evidence_ref"):
            if slot[key]:
                sha(slot[key], "PHASE_SLOT_REFERENCE")
            elif not isinstance(slot[key], str):
                fail("PHASE_SLOT_REFERENCE")
        if slot["status"] in {"RESERVED", "AWAITING_RESULT"} and not slot["active_reservation_ref"]:
            fail("PHASE_SLOT_ACTIVE_REFERENCE_REQUIRED")
        if slot["status"] == "SATISFIED" and not slot["accepted_result_ref"]:
            fail("PHASE_SLOT_RESULT_REQUIRED")
        if slot["status"] == "WAIVED" and (slot["condition"] != "repair-after-post"
                                          or not slot["release_evidence_ref"]):
            fail("PHASE_SLOT_WAIVER_INVALID")
        if slot["status"] == "PENDING" and slot["active_reservation_ref"]:
            fail("PENDING_SLOT_HAS_ACTIVE_ATTEMPT")
        options = slot["options"]
        if not isinstance(options, list) or not options or len(options) > 18:
            fail("PHASE_OPTION_LIMIT")
        option_ids: set[str] = set()
        for option in options:
            exact(option, OPTION_FIELDS, "PHASE_OPTION_FIELDS")
            sha(option["qualification_ref"]); sha(option["cost_ref"])
            need = vector(option["resources"])
            if resource_need(option["profile_id"], need["units"]) != need:
                fail("PHASE_OPTION_RESOURCE_CLASS_MISMATCH")
            if option["profile_id"] in option_ids:
                fail("PHASE_OPTION_DUPLICATE")
            option_ids.add(option["profile_id"])
    dependencies_by_id = {item["slot_id"]: item["depends_on"] for item in slots}
    visited: set[str] = set()
    active: set[str] = set()

    def visit(name: str) -> None:
        if name in active:
            fail("PHASE_DEPENDENCY_CYCLE")
        if name in visited:
            return
        active.add(name)
        for dependency in dependencies_by_id[name]:
            if dependency not in ids:
                fail("PHASE_DEPENDENCY_MISSING")
            visit(dependency)
        active.remove(name)
        visited.add(name)

    for name in ids:
        visit(name)
    return copy.deepcopy(value)


def current_slot(plan: Mapping[str, Any], slot_id: str) -> dict[str, Any]:
    match = next((slot for slot in plan["slots"] if slot["slot_id"] == slot_id), None)
    if match is None:
        fail("PHASE_SLOT_UNKNOWN")
    return copy.deepcopy(match)


def slot_ready(plan: Mapping[str, Any], slot_id: str) -> bool:
    slot = current_slot(plan, slot_id)
    return slot["status"] == "PENDING" and all(
        current_slot(plan, dependency)["status"] in {"SATISFIED", "WAIVED"}
        for dependency in slot["depends_on"])


def feasible_witness(plan: Mapping[str, Any], capacity: Mapping[str, int], *,
                     exclude_slot: str = "", max_states: int | None = None,
                     option_filter: Any = None, role_capacity: Mapping[str, int] | None = None,
                     phase_capacity: Mapping[str, int] | None = None) -> dict[str, Any]:
    """中文：返回完整分配、无解或搜索上限，三种结果不混用。

    English: Return a whole assignment, infeasibility or bounded-search unknown.
    """
    plan = validate_plan(dict(plan))
    capacity = vector(dict(capacity))
    role_capacity = dict(role_capacity or {name: capacity["units"] for name in ("reviewer", "worker", "explorer")})
    phase_capacity = dict(phase_capacity or {name: capacity["units"] for name in ("pre", "post", "repair")})
    exact(role_capacity, {"reviewer", "worker", "explorer"}, "ROLE_CAPACITY_FIELDS")
    exact(phase_capacity, {"pre", "post", "repair"}, "PHASE_CAPACITY_FIELDS")
    for number in (*role_capacity.values(), *phase_capacity.values()):
        integer(number, "LOCAL_CAPACITY")
    limit = policy()["limits"]["max_search_states"] if max_states is None else integer(
        max_states, "PHASE_SEARCH_LIMIT", minimum=1, maximum=50000)
    pending = []
    for slot in plan["slots"]:
        if slot["slot_id"] == exclude_slot or slot["status"] != "PENDING":
            continue
        options = [option for option in slot["options"] if option_filter is None or option_filter(slot, option)]
        options.sort(key=lambda option: (tuple(option["resources"][key] for key in VECTOR_KEYS),
                                         option["profile_id"]))
        if not options:
            return {"status": "INFEASIBLE", "reason": "PHASE_OPTIONS_INVALIDATED", "states": 0}
        pending.append((slot["slot_id"], options, role_for(slot["scenario"]["role"]), slot["scenario"]["phase"]))
    pending.sort(key=lambda item: (len(item[1]), item[0]))
    explored = 0
    memo: set[tuple] = set()
    exhausted = False

    def search(index: int, remaining: dict[str, int], roles: dict[str, int],
               phases: dict[str, int], selected: list[dict]) -> list[dict] | None:
        nonlocal explored, exhausted
        if explored >= limit:
            exhausted = True
            return None
        explored += 1
        if index == len(pending):
            return selected
        state = (index, *(remaining[key] for key in VECTOR_KEYS),
                 *(roles[key] for key in sorted(roles)), *(phases[key] for key in sorted(phases)))
        if state in memo:
            return None
        slot_id, options, role, phase = pending[index]
        for option in options:
            need = option["resources"]
            if fits(need, remaining) and need["units"] <= min(roles[role], phases[phase]):
                result = search(index + 1, {key: remaining[key] - need[key] for key in VECTOR_KEYS},
                                {**roles, role: roles[role] - need["units"]},
                                {**phases, phase: phases[phase] - need["units"]},
                                selected + [{"slot_id": slot_id, **option}])
                if result is not None:
                    return result
                if exhausted:
                    return None
        memo.add(state)
        return None

    selected = search(0, dict(capacity), dict(role_capacity), dict(phase_capacity), [])
    if selected is None:
        return {"status": "SEARCH_LIMIT" if exhausted else "INFEASIBLE", "states": explored}
    resources = add_vectors(*(item["resources"] for item in selected)) if selected else dict(ZERO)
    result = {"status": "FEASIBLE", "states": explored, "plan_ref": ref(plan),
              "assignments": selected, "resources": resources}
    result["witness_ref"] = ref(result)
    return result


def capacity_after_choice(plan: Mapping[str, Any], slot_id: str, profile_id: str,
                          capacity: Mapping[str, int], *, option_filter: Any = None,
                          role_capacity: Mapping[str, int] | None = None,
                          phase_capacity: Mapping[str, int] | None = None,
                          max_states: int | None = None) -> dict[str, Any]:
    if not slot_ready(plan, slot_id):
        return {"status": "SLOT_NOT_READY"}
    slot = current_slot(plan, slot_id)
    option = next((item for item in slot["options"] if item["profile_id"] == profile_id), None)
    if option is None or (option_filter is not None and not option_filter(slot, option)):
        return {"status": "OPTION_INVALID"}
    if not fits(option["resources"], capacity):
        return {"status": "INFEASIBLE"}
    roles = dict(role_capacity or {name: capacity["units"] for name in ("reviewer", "worker", "explorer")})
    phases = dict(phase_capacity or {name: capacity["units"] for name in ("pre", "post", "repair")})
    role, phase = role_for(slot["scenario"]["role"]), slot["scenario"]["phase"]
    if option["resources"]["units"] > min(roles[role], phases[phase]):
        return {"status": "INFEASIBLE"}
    roles[role] -= option["resources"]["units"]
    phases[phase] -= option["resources"]["units"]
    remaining = {key: capacity[key] - option["resources"][key] for key in VECTOR_KEYS}
    return feasible_witness(plan, remaining, exclude_slot=slot_id, option_filter=option_filter,
                            role_capacity=roles, phase_capacity=phases, max_states=max_states)


def validate_revision(previous: Mapping[str, Any], revised: Mapping[str, Any]) -> dict[str, Any]:
    revised = validate_plan(dict(revised), expected_identity=previous["identity"])
    if revised["plan_id"] != previous["plan_id"] or revised["revision"] != previous["revision"] + 1:
        fail("PHASE_PLAN_REVISION_CONFLICT")
    old = {slot["slot_id"]: slot for slot in previous["slots"]}
    new = {slot["slot_id"]: slot for slot in revised["slots"]}
    if not set(old).issubset(new):
        fail("PHASE_SLOT_REMOVAL_DENIED")
    for name, before in old.items():
        after = new[name]
        if before["status"] != after["status"] or any(before[key] != after[key] for key in
                ("condition", "active_reservation_ref", "accepted_result_ref", "release_evidence_ref")):
            fail("PHASE_REVISION_CANNOT_CHANGE_LIFECYCLE")
        if before["independence_required"] and not after["independence_required"]:
            fail("PHASE_INDEPENDENCE_DOWNGRADE_DENIED")
        if before["status"] != "PENDING" and before != after:
            fail("ACTIVE_OR_FINISHED_SLOT_IMMUTABLE")
        if not set(before["depends_on"]).issubset(after["depends_on"]):
            fail("PHASE_DEPENDENCY_REMOVAL_DENIED")
        a, b = before["scenario"], after["scenario"]
        if any(a[key] != b[key] for key in
               ("role", "phase", "tools_profile", "speed_mode", "prompt_sha256", "context_bucket")) \
                or any(b[key] < a[key] for key in ("semantic", "reasoning", "risk")) \
                or not set(a["tags"]).issubset(b["tags"]):
            fail("PHASE_QUALITY_DOWNGRADE_DENIED")
    return revised
