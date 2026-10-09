"""中文：依据具体检查和门禁证据生成有界的交付与读回状态。

English: Bounded delivery/readback status from concrete checks and gate evidence.
"""
from __future__ import annotations

from typing import Any, Mapping

from .g6_gate_catalog import stage_decision
from .routing_contract import exact, fail, hex_digest, ref, sha

CHECK_FIELDS = {"check_id", "required", "exit_code", "source_ref", "baseline_sha256"}


def evaluate_delivery(*, checks: list[Mapping[str, Any]], baseline_sha256: str | None,
                      post_review: Mapping[str, Any] | None = None,
                      repair_review: Mapping[str, Any] | None = None,
                      installed: bool = False, installed_readback_ref: str | None = None,
                      action: str = "install") -> dict[str, Any]:
    """中文：缺少可选证明时保持 UNKNOWN；必要检查明确失败时限制发布。
    
    English: Missing optional proof remains UNKNOWN; required failed checks restrict release.
    """
    if action not in {"install", "publish", "write"} or type(installed) is not bool:
        fail("G6_DELIVERY_ACTION")
    if baseline_sha256 is not None:
        hex_digest(baseline_sha256)
    if installed_readback_ref is not None:
        sha(installed_readback_ref)
    if not isinstance(checks, list) or len(checks) > 64:
        fail("G6_DELIVERY_CHECK_LIMIT")
    seen = set()
    projected = []
    for raw in checks:
        check = exact(dict(raw), CHECK_FIELDS, "G6_DELIVERY_CHECK_FIELDS")
        name = check["check_id"]
        if not isinstance(name, str) or not name or len(name) > 100 or name in seen:
            fail("G6_DELIVERY_CHECK_ID")
        seen.add(name)
        if type(check["required"]) is not bool:
            fail("G6_DELIVERY_REQUIRED_TYPE")
        if check["exit_code"] is not None and (type(check["exit_code"]) is not int
                                               or not -255 <= check["exit_code"] <= 255):
            fail("G6_DELIVERY_EXIT_CODE")
        if check["source_ref"] is not None:
            sha(check["source_ref"])
        if check["baseline_sha256"] is not None:
            hex_digest(check["baseline_sha256"])
        if baseline_sha256 is not None and check["baseline_sha256"] is not None \
                and check["baseline_sha256"] != baseline_sha256:
            projected.append({**check, "status": "STALE_BASELINE"})
        elif check["exit_code"] is None or check["source_ref"] is None:
            projected.append({**check, "status": "UNVERIFIED"})
        else:
            projected.append({**check, "status": "PASS" if check["exit_code"] == 0 else "FAILED"})
    failed_required = [row for row in projected if row["required"] and row["status"] == "FAILED"]
    unresolved_required = [row for row in projected if row["required"] and row["status"] in {
        "UNVERIFIED", "STALE_BASELINE"}]
    optional_unverified = any(not row["required"] and row["status"] in {
        "UNVERIFIED", "STALE_BASELINE", "FAILED"} for row in projected)
    if failed_required:
        validation = {"gate_id": "validation", "state": "VERIFIED_HARD_VIOLATION",
                      "affected_action": action, "source_ref": ref(failed_required)}
    elif unresolved_required or not projected:
        validation = None
    else:
        validation = {"gate_id": "validation", "state": "PASS",
                      "affected_action": "none", "source_ref": ref(projected)}
    validation_decision = stage_decision("validation", validation, action=action)
    review_decision = stage_decision("post_review", post_review, action=action)
    repair_decision = stage_decision("repair_review", repair_review, action=action)
    install_gate = ({"gate_id": "package_installation", "state": "PASS",
                     "affected_action": "none", "source_ref": installed_readback_ref}
                    if installed and installed_readback_ref else None)
    install_decision = stage_decision("package_installation", install_gate, action=action)
    gate_decisions = [validation_decision, review_decision, repair_decision, install_decision]
    blocked = [item for item in gate_decisions if item["decision"] == "STOP_ACTION"]
    if blocked:
        status, next_action = "ACTION_RESTRICTED", "resolve_confirmed_violation_or_continue_unaffected_work"
    elif unresolved_required or not projected:
        status, next_action = "LOCAL_RESULT_UNVERIFIED", "run_required_check_or_deliver_local"
    elif installed and installed_readback_ref is None:
        status, next_action = "INSTALLED_EFFECT_UNVERIFIED", "probe_installed_runtime"
    elif installed:
        status = "INSTALLED_PARTIAL_UNVERIFIED" if optional_unverified else "INSTALLED_READBACK_VERIFIED"
        next_action = "report_distinct_runtime_effect"
    else:
        status = "LOCAL_RESULT_PARTIAL_UNVERIFIED" if optional_unverified else "LOCAL_CHECKS_VERIFIED"
        next_action = "continue_authorized_delivery"
    return {"schema_version": "g6-delivery-status/1", "status": status,
            "next_action": next_action, "checks": projected,
            "gate_decisions": gate_decisions,
            "restricted_action": action if blocked else None,
            "independent_review_verified": review_decision["gate_state"] == "PASS",
            "repair_review_verified": repair_decision["gate_state"] == "PASS",
            "installed": installed, "installed_readback_verified": installed_readback_ref is not None}
