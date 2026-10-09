"""中文：GPT-6 Desktop 决策核心由脚本控制；语义建议始终标为建议。

English: Script-owned GPT-6 Desktop decision core; semantic advice stays labeled advice.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from .common import parse_iso
from .g6_gate_catalog import complete_gates
from .routing_contract import exact, fail, hex_digest, identity, integer, ref, role_for, sha

POLICY_ID = "desktop-g6-deterministic-v1"
POLICY_SHA256 = "1593b5136a133b62b6a8973f1c5a29b798189a3ef2fe424a5aaed0fc87cdf70f"
DESIGN_SOURCE_SHA256 = "5270c4644a428e5716bebb8d64a7e8b983ee85e19b12fbcaee68e18e393e6abc"
POLICY_PATH = Path(__file__).parent / "data" / "desktop-g6-flexible-policy-v1.json"
FAMILIES = ("luna", "sol", "astra")
EFFORTS = ("low", "medium", "high")
PROFILES = tuple(f"g6-{family}-{effort}" for family in FAMILIES for effort in EFFORTS)
TASK_NAME = re.compile(r"[a-z0-9_]{1,64}\Z")
FACT_FIELDS = {"schema_version", "identity", "task_id", "work_item_id", "baseline_sha256",
               "scope_ref", "task_kind", "task_kind_source", "source_refs", "missing_evidence"}
BUDGET_FIELDS = {"schema_version", "ledger_head", "capacity_class", "capacity_units",
                 "capacity_attempts", "completed_charged_units", "completed_charged_attempts",
                 "inflight_reserved_units", "inflight_reserved_attempts", "future_required_hold_units",
                 "future_required_hold_attempts", "parallel_limit", "active_calls", "depth_limit",
                 "depth", "astra_active", "upward_adjustments_used"}
CAPABILITY_FIELDS = {"schema_version", "available_profiles", "source_ref"}
GATE_FIELDS = {"gate_id", "state", "affected_action", "source_ref"}
ADJUSTMENT_FIELDS = {"requested_profile", "source", "reason", "source_ref"}
TASK_KINDS = {"lookup", "extraction", "mechanical", "ordinary", "cross_domain_adjudication", "unknown"}
TASK_SOURCES = {"user_direct", "script_verified", "semantic_proposal", "unknown"}
GATE_STATES = {"PASS", "MISSING_EVIDENCE", "VERIFIED_HARD_VIOLATION"}


def policy() -> dict[str, Any]:
    raw = POLICY_PATH.read_bytes()
    if hashlib.sha256(raw).hexdigest() != POLICY_SHA256:
        fail("G6_POLICY_HASH_MISMATCH")
    value = json.loads(raw)
    if (value.get("schema_version") != "g6-runtime-policy/1"
            or value.get("policy_id") != POLICY_ID
            or value.get("host_surface") != "codex-desktop"
            or value.get("design_source_sha256") != DESIGN_SOURCE_SHA256
            or value.get("profiles") != list(PROFILES)):
        fail("G6_POLICY_CONTRACT")
    return value


def profile_spec(profile_id: str) -> dict[str, Any]:
    if profile_id not in PROFILES:
        fail("G6_PROFILE_UNKNOWN")
    _, family, effort = profile_id.split("-")
    rule = policy()
    return {"profile_id": profile_id, "model": f"gpt-6-{family}", "effort": effort,
            "family": family, "planning_units":
            rule["family_weights"][family] * rule["effort_weights"][effort]}


def _facts(value: Mapping[str, Any]) -> dict[str, Any]:
    result = exact(dict(value), FACT_FIELDS, "G6_FACT_FIELDS")
    if result["schema_version"] != "g6-task-facts/1":
        fail("G6_FACT_VERSION")
    identity(result["identity"])
    for key in ("task_id", "work_item_id"):
        if not isinstance(result[key], str) or not result[key] or len(result[key]) > 160:
            fail("G6_FACT_TASK")
    if result["baseline_sha256"] is not None:
        hex_digest(result["baseline_sha256"])
    sha(result["scope_ref"])
    if result["task_kind"] not in TASK_KINDS or result["task_kind_source"] not in TASK_SOURCES:
        fail("G6_FACT_KIND")
    for key in ("source_refs", "missing_evidence"):
        values = result[key]
        if (not isinstance(values, list) or len(values) > 64
                or any(not isinstance(item, str) or not item or len(item) > 160 for item in values)
                or len(values) != len(set(values))):
            fail("G6_FACT_LIST")
    for source in result["source_refs"]:
        sha(source)
    return result


def _budget(value: Mapping[str, Any]) -> dict[str, Any]:
    result = exact(dict(value), BUDGET_FIELDS, "G6_BUDGET_FIELDS")
    if result["schema_version"] != "g6-budget-snapshot/1":
        fail("G6_BUDGET_VERSION")
    hex_digest(result["ledger_head"])
    rule = policy()
    name = result["capacity_class"]
    templates = rule["budget_templates"]
    parallel = rule["concurrency_defaults"]
    if (name not in templates or result["capacity_units"] != templates[name]["units"]
            or result["capacity_attempts"] != templates[name]["attempts"]
            or result["parallel_limit"] != parallel[name]["parallel"]
            or result["depth_limit"] != parallel[name]["depth"]):
        fail("G6_BUDGET_TEMPLATE")
    for key in BUDGET_FIELDS - {"schema_version", "ledger_head", "capacity_class"}:
        integer(result[key], "G6_BUDGET_VALUE", maximum=1_000_000)
    if (result["active_calls"] > result["parallel_limit"]
            or result["astra_active"] > parallel["astra_parallel"]
            or result["depth"] > result["depth_limit"]
            or result["completed_charged_units"] + result["inflight_reserved_units"]
            + result["future_required_hold_units"] > result["capacity_units"]
            or result["completed_charged_attempts"] + result["inflight_reserved_attempts"]
            + result["future_required_hold_attempts"] > result["capacity_attempts"]):
        fail("G6_BUDGET_INCONSISTENT")
    return result


def _capability(value: Mapping[str, Any]) -> dict[str, Any]:
    result = exact(dict(value), CAPABILITY_FIELDS, "G6_CAPABILITY_FIELDS")
    if result["schema_version"] != "g6-desktop-capability/1":
        fail("G6_CAPABILITY_VERSION")
    if result["source_ref"] is not None:
        sha(result["source_ref"])
    available = result["available_profiles"]
    if available is not None and (not isinstance(available, list)
                                  or len(available) != len(set(available))
                                  or any(item not in PROFILES for item in available)):
        fail("G6_CAPABILITY_LIST")
    return result


def _gates(values: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return complete_gates(values)


def _preferred(facts: Mapping[str, Any]) -> str:
    # 中文：刻意不使用范围指标作为难度证明。
    # English: Scope metrics are deliberately absent: they are not difficulty proof.
    if facts["source_refs"] and facts["task_kind_source"] in {"user_direct", "script_verified"}:
        if facts["task_kind"] in {"lookup", "extraction", "mechanical"}:
            return "g6-luna-low"
        if facts["task_kind"] == "cross_domain_adjudication":
            return "g6-astra-medium"
    return "g6-sol-medium"


def _fallback_key(name: str, preferred: str) -> tuple:
    current = profile_spec(preferred)
    other = profile_spec(name)
    return (other["family"] != current["family"],
            abs(EFFORTS.index(other["effort"]) - EFFORTS.index(current["effort"])),
            other["planning_units"], name)


def is_upward_adjustment(current: str, requested: str) -> bool:
    """中文：更便宜或降级型号的回退不消耗升档次数。
    
    English: A cheaper/lower-family fallback never consumes an upward adjustment.
    """
    before, after = profile_spec(current), profile_spec(requested)
    return (after["planning_units"] > before["planning_units"]
            or FAMILIES.index(after["family"]) > FAMILIES.index(before["family"]))


def decide(*, facts: Mapping[str, Any], budget: Mapping[str, Any],
           capability: Mapping[str, Any], gates: list[Mapping[str, Any]],
           agent_type: str, task_name: str, message: str, decision_time: str,
           adjustment: Mapping[str, Any] | None = None,
           explicit_user_profile: str | None = None) -> dict[str, Any]:
    """中文：本函数只计算决策；账本与 Hook 仍须预占并再次核验。
    
    English: Pure decision; the journal and Hook must still reserve and recheck it.
    """
    rule = policy()
    facts = _facts(facts)
    budget = _budget(budget)
    capability = _capability(capability)
    gates = _gates(gates)
    role_for(agent_type)
    if not TASK_NAME.fullmatch(task_name) or not isinstance(message, str) or not message:
        fail("G6_DISPATCH_INPUT")
    when = parse_iso(decision_time)
    if when.tzinfo is None:
        fail("G6_DECISION_TIME")
    if explicit_user_profile is not None and explicit_user_profile not in PROFILES:
        fail("G6_EXPLICIT_PROFILE")
    if adjustment is not None:
        adjustment = exact(dict(adjustment), ADJUSTMENT_FIELDS, "G6_ADJUSTMENT_FIELDS")
        if (adjustment["requested_profile"] not in PROFILES
                or adjustment["source"] not in {"model_semantic", "user_direct"}
                or not isinstance(adjustment["reason"], str)
                or len(adjustment["reason"]) > 500):
            fail("G6_ADJUSTMENT_INPUT")
        if adjustment["source_ref"] is not None:
            sha(adjustment["source_ref"])
    preferred = explicit_user_profile or _preferred(facts)
    remaining_units = (budget["capacity_units"] - budget["completed_charged_units"]
                       - budget["inflight_reserved_units"] - budget["future_required_hold_units"])
    remaining_attempts = (budget["capacity_attempts"] - budget["completed_charged_attempts"]
                          - budget["inflight_reserved_attempts"] - budget["future_required_hold_attempts"])
    hard = [gate for gate in gates if gate["state"] == "VERIFIED_HARD_VIOLATION"
            and gate["affected_action"] in {"all", "spawn_agent"}]
    missing = sorted(set(facts["missing_evidence"])
                     | {gate["gate_id"] for gate in gates if gate["state"] == "MISSING_EVIDENCE"})
    if facts["baseline_sha256"] is None:
        missing.append("baseline_sha256")
    reasons = ["MISSING_EVIDENCE_CONTINUE"] if missing else []
    decision = "CONTINUE_DEFAULT"
    chosen = None
    candidates: list[str] = []
    available = capability["available_profiles"]
    if available is None:
        available = list(PROFILES)
        missing.append("available_profiles")
        reasons.append("CAPABILITY_UNVERIFIED_BOUNDED_ATTEMPT")
    if hard:
        decision = "STOP_ACTION"
        reasons.append("VERIFIED_HARD_VIOLATION")
    elif budget["depth"] >= budget["depth_limit"]:
        decision = "CONTINUE_LOCAL"
        reasons.append("DEPTH_LIMIT")
    elif budget["active_calls"] >= budget["parallel_limit"]:
        decision = "QUEUE"
        reasons.append("PARALLEL_CAPACITY_FULL")
    elif remaining_units < 1 or remaining_attempts < 1:
        decision = "CONTINUE_LOCAL"
        reasons.append("BUDGET_EXHAUSTED")
    else:
        candidates = sorted((name for name in available
                             if profile_spec(name)["planning_units"] <= remaining_units
                             and (not name.startswith("g6-astra-") or not budget["astra_active"])))
        if explicit_user_profile is not None:
            if explicit_user_profile in candidates:
                chosen = explicit_user_profile
            else:
                decision = "CONTINUE_LOCAL"
                reasons.append("EXPLICIT_USER_PROFILE_UNAVAILABLE_OR_UNAFFORDABLE")
        elif preferred in candidates:
            chosen = preferred
        else:
            at_most = [name for name in candidates
                       if profile_spec(name)["planning_units"] <= profile_spec(preferred)["planning_units"]]
            if at_most:
                chosen = min(at_most, key=lambda name: _fallback_key(name, preferred))
                decision = "CONTINUE_DEGRADED"
                reasons.append("CAPABILITY_OR_BUDGET_FALLBACK")
            elif candidates:
                chosen = min(candidates, key=lambda name: (profile_spec(name)["planning_units"], name))
                decision = "CONTINUE_DEGRADED"
                reasons.append("CAPABILITY_FALLBACK_HIGHER_WEIGHT")
            else:
                decision = "CONTINUE_LOCAL"
                reasons.append("NO_AFFORDABLE_G6_PROFILE")
        if (chosen is not None and adjustment is not None and explicit_user_profile is None
                and adjustment["source"] != "user_direct"):
            requested = adjustment["requested_profile"]
            base_units = profile_spec(chosen)["planning_units"]
            request_units = profile_spec(requested)["planning_units"]
            maximum_ratio = rule["elasticity"]["max_weight_ratio_per_ordinary_adjustment"]
            upward = is_upward_adjustment(chosen, requested)
            within_ratio = request_units * maximum_ratio[1] <= base_units * maximum_ratio[0]
            within_count = (not upward or budget["upward_adjustments_used"] <
                            rule["elasticity"]["max_automatic_upward_adjustments_per_work_item"])
            if requested in candidates and within_ratio and within_count:
                chosen = requested
                decision = "CONTINUE_DEGRADED" if requested != preferred else "CONTINUE_DEFAULT"
                reasons.append("SCRIPT_APPROVED_SEMANTIC_ADJUSTMENT")
            else:
                reasons.append("ADJUSTMENT_NOT_APPROVED_KEEP_DEFAULT")
        elif (chosen is not None and adjustment is not None and explicit_user_profile is None
              and adjustment["source"] == "user_direct"):
            requested = adjustment["requested_profile"]
            if requested in candidates:
                chosen = requested
                reasons.append("USER_PROFILE_SELECTED")
            else:
                decision = "CONTINUE_LOCAL"
                chosen = None
                reasons.append("USER_PROFILE_UNAVAILABLE_OR_UNAFFORDABLE")
    if available == [] and not hard:
        decision = "CONTINUE_LOCAL"
        reasons.append("NO_DESKTOP_G6_PROFILE_AVAILABLE")
    missing = sorted(set(missing))
    if missing and "MISSING_EVIDENCE_CONTINUE" not in reasons:
        reasons.append("MISSING_EVIDENCE_CONTINUE")
    selected = profile_spec(chosen) if chosen else None
    allowed_adjustments = []
    if selected:
        max_ratio = rule["elasticity"]["max_weight_ratio_per_ordinary_adjustment"]
        allowed_adjustments = [name for name in candidates
                               if profile_spec(name)["planning_units"] * max_ratio[1]
                               <= selected["planning_units"] * max_ratio[0]
                               and (budget["upward_adjustments_used"] <
                                    rule["elasticity"]["max_automatic_upward_adjustments_per_work_item"]
                                    or not is_upward_adjustment(chosen, name))]
    expiry = (when.astimezone(timezone.utc) +
              timedelta(seconds=rule["decision_ttl_seconds"])).isoformat().replace("+00:00", "Z")
    params = ({"task_name": task_name, "agent_type": agent_type, "model": selected["model"],
               "reasoning_effort": selected["effort"], "fork_turns": "none", "message": message}
              if selected else None)
    result = {"schema_version": "g6-dispatch-decision/1", "policy_id": POLICY_ID,
              "policy_digest": "sha256:" + POLICY_SHA256, "facts_ref": ref(facts),
              "ledger_head": budget["ledger_head"], "capability_ref": ref(capability),
              "gate_results": gates, "decision": decision, "preferred_profile": preferred,
              "approved_profile": chosen, "allowed_adjustment_profiles": allowed_adjustments,
              "planning_units": selected["planning_units"] if selected else 0,
              "remaining_units_before_dispatch": remaining_units,
              "remaining_attempts_before_dispatch": remaining_attempts,
              "future_hold": {"units": budget["future_required_hold_units"],
                              "attempts": budget["future_required_hold_attempts"]},
              "missing_evidence": missing, "reason_codes": sorted(set(reasons)),
              "next_action": "spawn_agent" if selected else
              "wait_for_capacity" if decision == "QUEUE" else
              "stop_affected_action" if decision == "STOP_ACTION" else "continue_local",
              "expires_at": expiry,
              "tool_parameters_ref": ref({"task_name": task_name, "agent_type": agent_type,
                                          "model": selected["model"], "reasoning_effort": selected["effort"],
                                          "fork_turns": "none", "message_sha256":
                                          hashlib.sha256(message.encode("utf-8")).hexdigest()}) if selected else None}
    result["decision_ref"] = ref(result)
    result["exact_tool_parameters"] = params
    return result
