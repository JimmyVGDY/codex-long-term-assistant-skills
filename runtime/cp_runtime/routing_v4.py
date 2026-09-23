"""中文：纯函数式 V4 定位、质量收益与阶段预算选择。

English: Deterministic selection over verified snapshots. A selected candidate
is never a dispatch permit; the ledger must revalidate and reserve atomically.
"""
from __future__ import annotations

import copy
from typing import Any, Mapping

from .routing_contract import (
    ALGORITHM_ID, HOST_SURFACE, POLICY_ID, VECTOR_KEYS, RoutingError, admitted,
    assert_current_window, boolean, exact, fail, hex_digest, identifier, identity,
    integer, policy, policy_digest, profile_spec, ref, scenario, sha, strings, vector,
)
from .routing_phase_plan import capacity_after_choice, current_slot, validate_plan

REQUEST_FIELDS = {"schema_version", "task_id", "identity", "policy_digest", "scenario",
                  "execution_mode", "mode", "slot_id", "baseline_sha256", "packet_sha256",
                  "message_sha256", "evaluation_case_ref", "constraints", "evidence", "expected"}
SNAPSHOT_FIELDS = {"schema_version", "identity", "policy_digest", "execution_mode", "cards",
                   "capability", "phase_plan", "budget", "now"}
CARD_SET_FIELDS = {"schema_version", "identity", "origin", "bundle_refs", "publication_refs",
                   "qualification", "gains", "costs"}
CAPABILITY_FIELDS = {"schema_version", "host_surface", "source", "root_session_ref", "revision",
                     "available_profiles", "created_at", "expires_at", "wallclock_enforced"}
BUDGET_FIELDS = {"revision", "head_ref", "remaining", "role_capacity",
                 "phase_capacity", "parallel_available", "astra_active", "astra_parallel_available", "depth_allowed"}
EXPECTED_FIELDS = {"ledger_revision", "ledger_head_ref", "plan_revision", "plan_ref",
                   "capability_revision", "capability_ref", "cards_ref"}


def combine_cards(bundles: list[Mapping[str, Any]], publication_refs: list[str], *,
                  declared_identity: Mapping[str, str], evaluation: bool = False) -> dict[str, Any]:
    if not isinstance(bundles, list) or len(bundles) > 10 or len(publication_refs) > 10:
        fail("CARD_SET_LIMIT")
    for publication_ref in publication_refs:
        sha(publication_ref)
    if not evaluation and len(bundles) != len(publication_refs):
        fail("PRODUCTION_CARD_PUBLICATION_REQUIRED")
    result = {
        "schema_version": "verified-card-set/1", "identity": identity(dict(declared_identity)),
        "origin": "evaluation" if evaluation else ("published" if bundles else "unqualified"),
        "bundle_refs": [], "publication_refs": sorted(publication_refs),
        "qualification": [], "gains": [], "costs": [],
    }
    keys: dict[str, set[tuple]] = {"qualification": set(), "gains": set(), "costs": set()}
    for bundle in bundles:
        if bundle["identity"] != result["identity"] or bundle["policy_id"] != POLICY_ID \
                or bundle["policy_digest"] != policy_digest():
            fail("CARD_SET_IDENTITY")
        if not evaluation and bundle["origin"] != "desktop-evaluation":
            fail("PRODUCTION_CARD_ORIGIN")
        result["bundle_refs"].append(ref(bundle))
        for kind in keys:
            for card in bundle[kind]:
                key = (card["scenario_ref"], card["anchor"], card["challenger"]) if kind == "gains" \
                    else (card["scenario_ref"], card["profile_id"])
                if key in keys[kind]:
                    fail("CARD_SET_AMBIGUOUS_KEY")
                keys[kind].add(key)
                result[kind].append(copy.deepcopy(card))
    for kind in keys:
        if len(result[kind]) > policy()["limits"]["max_cards"]:
            fail("CARD_SET_LIMIT")
        result[kind].sort(key=ref)
    result["bundle_refs"].sort()
    return result


def snapshot_references(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "ledger_revision": snapshot["budget"]["revision"],
        "ledger_head_ref": snapshot["budget"]["head_ref"],
        "plan_revision": snapshot["phase_plan"]["revision"],
        "plan_ref": ref(snapshot["phase_plan"]),
        "capability_revision": snapshot["capability"]["revision"],
        "capability_ref": ref(snapshot["capability"]),
        "cards_ref": ref(snapshot["cards"]),
    }


def _validate(request: Any, snapshot: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    exact(request, REQUEST_FIELDS, "ROUTING_REQUEST_FIELDS")
    exact(snapshot, SNAPSHOT_FIELDS, "ROUTING_SNAPSHOT_FIELDS")
    if request["schema_version"] != "routing-request/1" or snapshot["schema_version"] != "routing-input/1" \
            or request["policy_digest"] != policy_digest() or snapshot["policy_digest"] != policy_digest():
        fail("IDENTITY_OR_POLICY_INVALID")
    expected_identity = identity(request["identity"])
    if identity(snapshot["identity"]) != expected_identity:
        fail("IDENTITY_OR_POLICY_INVALID")
    identifier(request["task_id"]); identifier(request["slot_id"])
    hex_digest(request["baseline_sha256"]); hex_digest(request["packet_sha256"])
    hex_digest(request["message_sha256"])
    if request["execution_mode"] == "EVALUATION":
        sha(request["evaluation_case_ref"])
    elif request["evaluation_case_ref"] != "":
        fail("PRODUCTION_EVALUATION_CASE_CONFLICT")
    task_scenario = scenario(request["scenario"])
    if request["mode"] not in {"economy", "balanced", "deep"} \
            or request["execution_mode"] not in {"PRODUCTION", "EVALUATION"} \
            or request["execution_mode"] != snapshot["execution_mode"]:
        fail("EXECUTION_MODE_INVALID")
    cards = exact(snapshot["cards"], CARD_SET_FIELDS, "CARD_SET_FIELDS")
    if cards["schema_version"] != "verified-card-set/1" or cards["identity"] != expected_identity:
        fail("CARD_SET_IDENTITY")
    for name in ("qualification", "gains", "costs"):
        if not isinstance(cards[name], list) or len(cards[name]) > policy()["limits"]["max_cards"]:
            fail("CARD_SET_LIMIT")
    capability = exact(snapshot["capability"], CAPABILITY_FIELDS, "CAPABILITY_FIELDS")
    if capability["schema_version"] != "desktop-capability/1" or capability["host_surface"] != HOST_SURFACE \
            or capability["source"] != "host-tool-metadata":
        fail("DESKTOP_CAPABILITY_UNAVAILABLE")
    sha(capability["root_session_ref"])
    integer(capability["revision"], "CAPABILITY_REVISION", minimum=1)
    for name in strings(capability["available_profiles"], "CAPABILITY_PROFILES", maximum=18):
        profile_spec(name)
    boolean(capability["wallclock_enforced"], "CAPABILITY_BOOLEAN")
    assert_current_window(capability, snapshot["now"])
    validate_plan(snapshot["phase_plan"], expected_identity=expected_identity)
    budget = exact(snapshot["budget"], BUDGET_FIELDS, "BUDGET_SNAPSHOT_FIELDS")
    integer(budget["revision"], "BUDGET_REVISION", minimum=1)
    sha(budget["head_ref"])
    vector(budget["remaining"])
    exact(budget["role_capacity"], {"reviewer", "worker", "explorer"}, "ROLE_CAPACITY_FIELDS")
    exact(budget["phase_capacity"], {"pre", "post", "repair"}, "PHASE_CAPACITY_FIELDS")
    for value in (*budget["role_capacity"].values(), *budget["phase_capacity"].values()):
        integer(value, "BUDGET_REMAINING")
    for name in ("parallel_available", "astra_parallel_available", "depth_allowed"):
        boolean(budget[name], "BUDGET_BOOLEAN")
    maximum = policy()["limits"]["max_astra_parallel"]
    integer(budget["astra_active"], "BUDGET_ASTRA_ACTIVE", maximum=maximum)
    if budget["astra_parallel_available"] != (budget["astra_active"] < maximum):
        fail("BUDGET_ASTRA_PARALLEL_CONFLICT")
    constraints = exact(request["constraints"], {"allowed_profiles", "deadline_ms", "strict_wallclock"},
                        "ROUTING_CONSTRAINTS")
    if constraints["allowed_profiles"] is not None:
        for name in strings(constraints["allowed_profiles"], "EXPLICIT_PROFILE_SET", maximum=18):
            profile_spec(name)
    if constraints["deadline_ms"] is not None:
        integer(constraints["deadline_ms"], "ROUTING_DEADLINE", minimum=1)
    boolean(constraints["strict_wallclock"], "ROUTING_CONSTRAINT_BOOLEAN")
    evidence = exact(request["evidence"], {"ready", "independence_required", "inline_sufficient", "refs"},
                     "ROUTING_EVIDENCE_FIELDS")
    for name in ("ready", "independence_required", "inline_sufficient"):
        boolean(evidence[name], "ROUTING_EVIDENCE_BOOLEAN")
    for evidence_ref in strings(evidence["refs"], "ROUTING_EVIDENCE_REFS"):
        sha(evidence_ref)
    exact(request["expected"], EXPECTED_FIELDS, "ROUTING_EXPECTED_FIELDS")
    if request["expected"] != snapshot_references(snapshot):
        fail("STALE_SNAPSHOT")
    normalized = copy.deepcopy(request)
    normalized["scenario"] = task_scenario
    return normalized, copy.deepcopy(snapshot)


def select(request: Mapping[str, Any], snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """中文：只选择并解释；English: never writes state or authorizes a host call."""
    try:
        request, snapshot = _validate(dict(request), dict(snapshot))
    except (RoutingError, TypeError, KeyError, ValueError) as exc:
        return {"schema_version": "selection-scorecard/2",
                "status": str(exc) if isinstance(exc, RoutingError) else "ROUTING_INPUT_INVALID"}
    current = request["scenario"]
    basis = {
        "schema_version": "selection-scorecard/2", "algorithm_id": ALGORITHM_ID,
        "policy_id": POLICY_ID, "policy_digest": policy_digest(), "identity": request["identity"],
        "task_id": request["task_id"], "slot_id": request["slot_id"],
        "baseline_sha256": request["baseline_sha256"], "packet_sha256": request["packet_sha256"],
        "scenario_ref": ref(current), "execution_mode": request["execution_mode"],
        "snapshots": snapshot_references(snapshot), "request_ref": ref(request),
    }

    def result(status: str, **extra: Any) -> dict[str, Any]:
        answer = {**basis, "status": status, **extra}
        answer["decision_ref"] = ref(answer)
        return answer

    evidence = request["evidence"]
    if not evidence["ready"] or not evidence["refs"]:
        return result("NEEDS_EVIDENCE")
    try:
        slot = current_slot(snapshot["phase_plan"], request["slot_id"])
    except RoutingError as exc:
        return result(str(exc))
    if scenario(slot["scenario"]) != current:
        return result("PHASE_SLOT_SCENARIO_MISMATCH")
    independent = evidence["independence_required"] or slot["independence_required"] or current["risk"] >= 2
    if evidence["inline_sufficient"] and not independent and request["execution_mode"] == "PRODUCTION":
        return result("INLINE", approved_profile=None, reserve_units=0, permit_ref=None)
    if request["execution_mode"] == "PRODUCTION" and (snapshot["cards"]["origin"] != "published"
                                                    or not snapshot["cards"]["publication_refs"]):
        return result("CALIBRATION_REQUIRED")
    if request["constraints"]["strict_wallclock"] and not snapshot["capability"]["wallclock_enforced"]:
        return result("DEADLINE_OR_SCOPE_UNSUPPORTED")
    pool = admitted(current["role"], request["execution_mode"])
    explicit = request["constraints"]["allowed_profiles"]
    if explicit is not None:
        pool = [name for name in pool if name in explicit]
    if request["execution_mode"] == "EVALUATION" and len(pool) != 1:
        return result("EVALUATION_REQUIRES_ONE_EXPLICIT_PROFILE")
    if not pool:
        return result("NO_ADMITTED_PROFILE")
    exclusions: dict[str, str] = {}
    available = set(snapshot["capability"]["available_profiles"])
    for name in pool:
        if name not in available:
            exclusions[name] = "DESKTOP_CAPABILITY_UNAVAILABLE"
    pool = [name for name in pool if name in available]
    if not pool:
        return result("DESKTOP_CAPABILITY_UNAVAILABLE", exclusions=exclusions)
    cards = snapshot["cards"]
    qualification = {ref(card): card for card in cards["qualification"]}
    costs = {ref(card): card for card in cards["costs"]}
    evaluation = request["execution_mode"] == "EVALUATION"

    def option_valid(other_slot: Mapping[str, Any], option: Mapping[str, Any]) -> bool:
        name = option["profile_id"]
        if name not in available or name not in admitted(other_slot["scenario"]["role"], request["execution_mode"]):
            return False
        scope = ref(scenario(other_slot["scenario"]))
        cost = costs.get(option["cost_ref"])
        if not cost or cost["profile_id"] != name or cost["scenario_ref"] != scope \
                or cost["reserve_units"] != option["resources"]["units"]:
            return False
        if evaluation:
            return True
        quality = qualification.get(option["qualification_ref"])
        return bool(quality and quality["profile_id"] == name and quality["scenario_ref"] == scope
                    and quality["qualified"] is True
                    and quality["independent_cases"] >= policy()["thresholds"]["min_independent_cases"])

    candidates = []
    deadline = request["constraints"]["deadline_ms"]
    capacity = dict(snapshot["budget"]["remaining"])
    search_remaining = policy()["limits"]["max_search_states"]
    for name in pool:
        option = next((item for item in slot["options"] if item["profile_id"] == name), None)
        if not option or not option_valid(slot, option):
            exclusions[name] = "NO_QUALIFIED_PROFILE" if not evaluation else "COST_BASIS_REQUIRED"
            continue
        cost = costs[option["cost_ref"]]
        if deadline is not None and cost["latency_ms"] > deadline:
            exclusions[name] = "DEADLINE_OR_SCOPE_UNSUPPORTED"
            continue
        if not snapshot["budget"]["parallel_available"] or not snapshot["budget"]["depth_allowed"]:
            exclusions[name] = "BUDGET_OR_PHASE_HOLD_BLOCKED"
            continue
        if profile_spec(name)["resource_group"] == "astra" and not snapshot["budget"]["astra_parallel_available"]:
            exclusions[name] = "ASTRA_PARALLEL_LIMIT"
            continue
        if search_remaining <= 0:
            return result("PHASE_PLAN_SEARCH_LIMIT", exclusions=exclusions)
        witness = capacity_after_choice(
            snapshot["phase_plan"], request["slot_id"], name, capacity, option_filter=option_valid,
            role_capacity=snapshot["budget"]["role_capacity"],
            phase_capacity=snapshot["budget"]["phase_capacity"], max_states=search_remaining)
        search_remaining -= witness.get("states", 0)
        if witness["status"] == "SEARCH_LIMIT":
            return result("PHASE_PLAN_SEARCH_LIMIT", exclusions=exclusions)
        if witness["status"] != "FEASIBLE":
            exclusions[name] = "BUDGET_OR_PHASE_HOLD_BLOCKED"
            continue
        candidates.append({"profile_id": name, "cost": cost, "option": option, "witness": witness})
    if not candidates:
        reasons = set(exclusions.values())
        priority = ("BUDGET_OR_PHASE_HOLD_BLOCKED", "ASTRA_PARALLEL_LIMIT", "DEADLINE_OR_SCOPE_UNSUPPORTED",
                    "COST_BASIS_REQUIRED", "NO_QUALIFIED_PROFILE", "DESKTOP_CAPABILITY_UNAVAILABLE")
        return result(next((reason for reason in priority if reason in reasons), "NO_QUALIFIED_PROFILE"),
                      exclusions=exclusions)
    if len({item["cost"]["cost_basis"] for item in candidates}) != 1:
        return result("COST_BASIS_REQUIRED", exclusions=exclusions)
    rank = lambda item: (item["cost"]["plan_cost"], item["cost"]["latency_ms"], item["profile_id"])
    anchor = min(candidates, key=rank)
    selected = anchor
    mode = "deep" if current["risk"] == 3 else request["mode"]
    improvements = []
    thresholds = policy()["thresholds"]
    if mode != "economy" and not evaluation:
        for candidate in candidates:
            if candidate is anchor:
                continue
            comparisons = [item for item in cards["gains"] if item["anchor"] == anchor["profile_id"]
                           and item["challenger"] == candidate["profile_id"]
                           and item["scenario_ref"] == ref(current)]
            if len(comparisons) != 1:
                continue
            comparison = comparisons[0]
            gain = comparison["quality"]["lower_delta_bp"]
            if gain < thresholds["material_quality_gain_bp"] or comparison["critical_failures"] \
                    or comparison["quality"]["n"] < thresholds["min_independent_cases"] \
                    or not comparison["false_blocks"] \
                    or comparison["false_blocks"]["upper_delta_bp"] > thresholds["false_block_margin_bp"]:
                continue
            if mode == "balanced":
                cost_n, cost_d = thresholds["balanced_cost_ratio"]
                time_n, time_d = thresholds["balanced_latency_ratio"]
                if candidate["cost"]["plan_cost"] * cost_d > anchor["cost"]["plan_cost"] * cost_n \
                        or candidate["cost"]["latency_ms"] * time_d > anchor["cost"]["latency_ms"] * time_n:
                    continue
            improvements.append((candidate, gain, ref(comparison)))
    if improvements:
        highest = max(gain for _, gain, _ in improvements)
        selected = min((item for item, gain, _ in improvements
                        if gain >= highest - thresholds["near_best_gain_bp"]), key=rank)
    gain_ref = next((proof for item, _, proof in improvements if item is selected), "")
    spec = profile_spec(selected["profile_id"])
    return result(
        "EVALUATION_SELECTED" if evaluation else "CANDIDATE_SELECTED",
        effective_mode=mode, anchor_profile=anchor["profile_id"], approved_profile=selected["profile_id"],
        request_parameters={"model": spec["model"], "reasoning_effort": spec["effort"], "agent_type": current["role"]},
        reserve_units=selected["cost"]["reserve_units"], cost_basis=selected["cost"]["cost_basis"],
        cost_ref=ref(selected["cost"]), qualification_ref=selected["option"]["qualification_ref"],
        gain_ref=gain_ref, future_witness=selected["witness"], exclusions=dict(sorted(exclusions.items())),
        candidate_profiles=sorted(item["profile_id"] for item in candidates),
    )
