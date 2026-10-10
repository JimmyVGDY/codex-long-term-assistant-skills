"""中文：冻结派发策略的门禁投影；实际入口清单见 gate_contract。

English: Frozen dispatch-policy gate projection; gate_contract owns actual entrypoints.
"""
from __future__ import annotations

from typing import Any, Mapping

from .routing_contract import exact, fail, sha

# 中文：每项由脚本选择器、预算控制器或 Hook 消费；旧 V3/V4/V5 回放保留原门禁语义。
# English: Each entry is consumed by the script decision, budget controller, or Hook.
# Old V3/V4/V5 replay keeps its original gate semantics.
CATALOG: dict[str, dict[str, Any]] = {
    "identity_scope": {"entrypoint": "g6_budget_v1.initialize/prepare; cp_hook._guard",
        "consumers": ["g6_budget_v1", "g6_hook_v1"],
        "normal_rule": "Bind project, repository, task, host session and authorized scope.",
        "missing_evidence_default": "Continue bounded classification with UNKNOWN; retain identity fields already known.",
        "known_violation_action": "Restrict the conflicting write or dispatch.",
        "next_action": "continue_local_or_dispatch_if_bound"},
    "pre_review": {"entrypoint": "g6_flexible_policy.decide",
        "consumers": ["g6_budget_v1.prepare", "g6_hook_v1.pretool"],
        "normal_rule": "Use a source-linked pre-review result for affected scope.",
        "missing_evidence_default": "Use baseline plan and mark independent pre-review unverified.",
        "known_violation_action": "Restrict only the affected hazardous operation.",
        "next_action": "continue_reversible_preparation"},
    "model_selection": {"entrypoint": "g6_flexible_policy.decide",
        "consumers": ["g6_default_activation.resolve", "g6_budget_v1.prepare", "g6_hook_v1._pretool"],
        "normal_rule": "Choose an available authorized GPT-6 tuple from policy and budget.",
        "missing_evidence_default": "Use Sol/medium or a bounded capability fallback.",
        "known_violation_action": "Do not call an unavailable or unauthorized tuple.",
        "next_action": "dispatch_or_continue_local"},
    "budget_initialization": {"entrypoint": "g6_budget_v1.initialize",
        "consumers": ["g6_budget_v1.prepare", "g6_hook_v1.pretool"],
        "normal_rule": "Create or read a bound hash-chain journal from an existing authorization template.",
        "missing_evidence_default": "Use authorized STANDARD template; no historical cost card is needed.",
        "known_violation_action": "Do not bypass corruption, identity conflict or actual exhausted budget.",
        "next_action": "prepare_or_continue_local"},
    "future_hold": {"entrypoint": "g6_budget_v1._usage/snapshot",
        "consumers": ["g6_flexible_policy.decide", "g6_budget_v1.approve_and_reserve"],
        "normal_rule": "Reserve only explicitly required slots at allowed profile cost.",
        "missing_evidence_default": "Use each slot's stated baseline assumption; do not assume Luna minimum.",
        "known_violation_action": "Do not spend held units on optional calls.",
        "next_action": "dispatch_affordable_or_continue_local"},
    "context_readiness": {"entrypoint": "g6_hook_v1._facts; routing_context_contract.load_bundle",
        "consumers": ["g6_budget_v1.prepare", "g6_hook_v1._pretool"],
        "normal_rule": "Read bounded, source-verified materials and record missing items.",
        "missing_evidence_default": "Deliver available scoped context and mark omissions; offer bounded follow-up read.",
        "known_violation_action": "Restrict confirmed foreign or sensitive source access.",
        "next_action": "continue_with_limited_context"},
    "dispatch_permit": {"entrypoint": "g6_budget_v1.prepare/approve_and_reserve",
        "consumers": ["g6_hook_v1.pretool", "cp_hook._guard"],
        "normal_rule": "Recheck exact current permit, host identity, parameters and atomic budget.",
        "missing_evidence_default": "Reissue a bounded default decision if optional evidence is missing.",
        "known_violation_action": "Deny forged, stale or overspending call parameters.",
        "next_action": "spawn_or_reprepare"},
    "post_review": {"entrypoint": "g6_hook_v1._terminal; g6_review_receipt_v1.ingest",
        "consumers": ["g6_review_receipt_v1.project_delivery", "g6_delivery_v1.evaluate_delivery"],
        "normal_rule": "Keep native task terminal separate from source-linked independent review findings.",
        "missing_evidence_default": "Keep independent review unverified; continue safe implementation and targeted checks.",
        "known_violation_action": "Restrict release of confirmed blocking defect.",
        "next_action": "continue_local_with_unverified_status"},
    "repair_review": {"entrypoint": "g6_review_receipt_v1.ingest/project_delivery",
        "consumers": ["g6_delivery_v1.evaluate_delivery"],
        "normal_rule": "Recheck changed baseline after adopted findings are repaired.",
        "missing_evidence_default": "Keep repair review unverified; continue targeted validation.",
        "known_violation_action": "Restrict only the affected release action for confirmed defect.",
        "next_action": "continue_targeted_validation"},
    "validation": {"entrypoint": "g6_delivery_v1.evaluate_delivery",
        "consumers": ["g6_review_receipt_v1.project_delivery", "package_manager.g6_install_delivery_report"],
        "normal_rule": "Read necessary check exit codes and baseline references.",
        "missing_evidence_default": "Optional checks stay unverified; deliver the scoped local result.",
        "known_violation_action": "Restrict corresponding publish/install action when a required safety check fails.",
        "next_action": "deliver_local_or_run_needed_check"},
    "package_installation": {"entrypoint": "package_manager.install_user/verify",
        "consumers": ["package_manager.g6_install_delivery_report", "package_manager.verify"],
        "normal_rule": "Verify package digest, target, transaction and installed readback.",
        "missing_evidence_default": "Skip empirical qualification; if runtime readback is absent, keep effect unverified and probe safely.",
        "known_violation_action": "Do not overwrite on hash, target or transaction conflict.",
        "next_action": "install_or_verify_existing"},
    "same_chat_handoff": {"entrypoint": "g6_handoff_provenance.verify_stop_checkpoint",
        "consumers": ["g6_hook_v1.registered_path", "cp_hook._budget_path"],
        "normal_rule": "Bind old stopped root, unresolved child and new root without rewriting history.",
        "missing_evidence_default": "Continue code and local checks; obtain bounded old-root evidence before native dispatch.",
        "known_violation_action": "Do not dispatch into a known active old root or misroute late events.",
        "next_action": "continue_local_until_safe_handoff"},
}

GATE_FIELDS = {"gate_id", "state", "affected_action", "source_ref"}


def complete_gates(observed: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """中文：规范化每个活动门禁，显式展示缺证据状态，不伪造 PASS。
    
    English: Normalize every active gate; absent evidence is visible, never fake PASS.
    """
    if not isinstance(observed, list) or len(observed) > len(CATALOG):
        fail("G6_GATE_OBSERVATIONS")
    result: dict[str, dict[str, Any]] = {}
    for raw in observed:
        gate = exact(dict(raw), GATE_FIELDS, "G6_GATE_FIELDS")
        name = gate["gate_id"]
        if name not in CATALOG or name in result:
            fail("G6_GATE_ID")
        if gate["state"] not in {"PASS", "MISSING_EVIDENCE", "VERIFIED_HARD_VIOLATION"}:
            fail("G6_GATE_STATE")
        if gate["affected_action"] not in {"spawn_agent", "write", "install", "publish", "all", "none"}:
            fail("G6_GATE_ACTION")
        if gate["state"] == "PASS" and gate["source_ref"] is None:
            gate = {**gate, "state": "MISSING_EVIDENCE"}
        if gate["state"] == "VERIFIED_HARD_VIOLATION":
            sha(gate["source_ref"])
        elif gate["source_ref"] is not None:
            sha(gate["source_ref"])
        result[name] = gate
    for name in CATALOG:
        result.setdefault(name, {"gate_id": name, "state": "MISSING_EVIDENCE",
                                 "affected_action": "none", "source_ref": None})
    return [result[name] for name in CATALOG]


def stage_decision(gate_id: str, observed: Mapping[str, Any] | None,
                   *, action: str) -> dict[str, Any]:
    """中文：为流程阶段返回明确下一步，不把 UNKNOWN 变成 PASS。
    
    English: One next action for a workflow stage, without turning UNKNOWN into PASS.
    """
    if gate_id not in CATALOG or action not in {"spawn_agent", "write", "install", "publish"}:
        fail("G6_STAGE_OR_ACTION")
    gate = next(item for item in complete_gates([observed] if observed is not None else [])
                if item["gate_id"] == gate_id)
    if gate["state"] == "PASS" and gate["source_ref"] is None:
        gate = {**gate, "state": "MISSING_EVIDENCE"}
    hard = gate["state"] == "VERIFIED_HARD_VIOLATION" and gate["affected_action"] in {
        "all", action}
    if hard:
        status = "STOP_ACTION"
        next_action = "continue_unaffected_work"
    elif gate["state"] == "MISSING_EVIDENCE":
        status = "CONTINUE_DEGRADED"
        next_action = CATALOG[gate_id]["next_action"]
    else:
        status = "CONTINUE_DEFAULT"
        next_action = "execute_authorized_action"
    return {"gate_id": gate_id, "gate_state": gate["state"], "decision": status,
            "affected_action": action if hard else None, "next_action": next_action,
            "evidence_ref": gate["source_ref"]}
