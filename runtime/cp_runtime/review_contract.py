"""中文：Reviewer V5 结果契约，引用冻结评分，不包含宿主型号自述。

English: Reviewer V5 result contracts bind the approved scorecard and one review owner.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Mapping

from .dispatch_policy import DispatchPolicyError, canonical_json, digest, policy, validate_scorecard

RESULT_SCHEMA_VERSION = 5
REVIEW_STATE_SCHEMA_VERSION = 8
RESULT_FIELDS = {
    "schema_version", "result_id", "reviewer", "task_id", "review_phase", "review_round",
    "boundary_id", "packet_sha256", "status", "isolation_level", "dispatch_assignment",
    "task_difficulty", "duration_ms", "estimated_cost_units", "cost_formula_version",
    "calibration_finalized", "accepted", "rejected", "duplicate", "repaired", "regressions_prevented",
    "checked_scope", "findings", "unverified_items", "summary",
}
ASSIGNMENT_FIELDS = {
    "approved_profile", "acceptable_profiles", "policy_id", "policy_digest", "selection_ref",
    "earned_budget", "dispatch_permit_ref", "review_state_ref", "policy_status", "cost_basis_units",
}
FINDING_FIELDS = {
    "id", "dimension", "severity", "evidence_level", "blocking", "summary", "location", "root_cause_group",
    "required_validation", "disposition", "adoption_reason", "repaired", "regression_prevented", "regression_evidence",
}
DISPOSITIONS = {"PENDING", "ACCEPTED", "REPAIRED", "REGRESSION_PREVENTED", "REJECTED", "DEFERRED",
                "OUT_OF_SCOPE", "DUPLICATE", "INSUFFICIENT_EVIDENCE"}
ADOPTION_REASONS = {"CORRECTNESS", "SECURITY", "COMPATIBILITY", "PERFORMANCE", "DATA_CONTRACT",
                    "REGRESSION_PREVENTION", "OUT_OF_SCOPE", "DUPLICATE", "INSUFFICIENT_EVIDENCE",
                    "DEFERRED", "REJECTED", "UNSPECIFIED"}
ISOLATION_LEVELS = {"system-readonly", "logical-readonly", "tool-restricted", "self-review", "unknown"}
STATUSES = {"pass", "nonblocking", "blocking", "incomplete"}
DIFFICULTIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL", "UNKNOWN"}
REF = re.compile(r"^sha256:[a-f0-9]{64}$")
HEX = re.compile(r"^[a-f0-9]{64}$")


def _strings(value: Any, name: str) -> list[str]:
    if not isinstance(value, list) or len(value) > 256 or any(not isinstance(item, str) for item in value):
        raise DispatchPolicyError("REVIEW_STRING_LIST_INVALID:" + name)
    return value


def assignment_from_score(selection: Mapping[str, Any], acceptable_profiles: list[str], *,
                          review_state_ref: str, permit_ref: str = "") -> dict[str, Any]:
    score = validate_scorecard(selection)
    value = {
        "approved_profile": score["approved_profile"], "acceptable_profiles": sorted(acceptable_profiles),
        "policy_id": score["policy_id"], "policy_digest": score["policy_digest"], "selection_ref": digest(score),
        "earned_budget": score["earned_budget"], "dispatch_permit_ref": permit_ref,
        "review_state_ref": review_state_ref, "policy_status": "approved" if permit_ref else "policy-only",
        "cost_basis_units": score["cost_basis_units"],
    }
    validate_assignment(value)
    if not set(acceptable_profiles).issubset(score["requirement_profiles"]):
        raise DispatchPolicyError("REVIEW_ACCEPTABLE_SET_OUTSIDE_REQUIREMENT")
    return value


def validate_assignment(value: Mapping[str, Any]) -> None:
    if not isinstance(value, Mapping) or set(value) != ASSIGNMENT_FIELDS:
        raise DispatchPolicyError("REVIEW_ASSIGNMENT_FIELDS")
    if any(not isinstance(value[key], str) for key in ("policy_id", "policy_digest", "approved_profile")):
        raise DispatchPolicyError("REVIEW_ASSIGNMENT_TYPES")
    contract = policy(value["policy_id"], value["policy_digest"])
    if "scoring" not in contract:
        raise DispatchPolicyError("REVIEW_V5_REQUIRES_SCORED_POLICY")
    profile = value["approved_profile"]
    if profile not in contract["role_profiles"]["reviewer"]:
        raise DispatchPolicyError("REVIEW_APPROVED_PROFILE_UNKNOWN")
    acceptable = _strings(value["acceptable_profiles"], "acceptable_profiles")
    if not acceptable or len(acceptable) != len(set(acceptable)) or profile not in acceptable \
            or not set(acceptable).issubset(contract["role_profiles"]["reviewer"]):
        raise DispatchPolicyError("REVIEW_ACCEPTABLE_SET_INVALID")
    for key in ("selection_ref", "review_state_ref"):
        if not isinstance(value[key], str) or not REF.fullmatch(value[key]):
            raise DispatchPolicyError("REVIEW_ASSIGNMENT_REFERENCE_INVALID")
    permit = value["dispatch_permit_ref"]
    if not isinstance(permit, str) or (permit and not REF.fullmatch(permit)) \
            or value["policy_status"] != ("approved" if permit else "policy-only"):
        raise DispatchPolicyError("REVIEW_PERMIT_STATUS_MISMATCH")
    units = contract["profiles"][profile]["units"]
    if type(value["cost_basis_units"]) is not int or value["cost_basis_units"] != units \
            or type(value["earned_budget"]) is not int or not units <= value["earned_budget"] <= contract["scoring"]["max_units"]:
        raise DispatchPolicyError("REVIEW_SCORE_COST_INVALID")


def result_id(*, boundary_id: str, task_id: str, phase: str, round_number: int, reviewer: str,
              packet_sha256: str, assignment: Mapping[str, Any]) -> str:
    identity = "|".join(map(str, (boundary_id, task_id, phase, round_number, reviewer, packet_sha256,
                                 assignment["review_state_ref"], assignment["dispatch_permit_ref"], assignment["selection_ref"])))
    return "RVR_" + hashlib.sha256(identity.encode("utf-8")).hexdigest()


def result_template(*, boundary_id: str, task_id: str, phase: str, round_number: int, reviewer: str,
                    packet_sha256: str, assignment: Mapping[str, Any], difficulty: str = "UNKNOWN") -> dict[str, Any]:
    validate_assignment(assignment)
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "result_id": result_id(boundary_id=boundary_id, task_id=task_id, phase=phase, round_number=round_number,
                               reviewer=reviewer, packet_sha256=packet_sha256, assignment=assignment),
        "reviewer": reviewer, "task_id": task_id, "review_phase": phase, "review_round": round_number,
        "boundary_id": boundary_id, "packet_sha256": packet_sha256, "status": "incomplete", "isolation_level": "unknown",
        "dispatch_assignment": dict(assignment), "task_difficulty": difficulty, "duration_ms": 0,
        "estimated_cost_units": assignment["cost_basis_units"],
        "cost_formula_version": policy(assignment["policy_id"])["cost_formula_version"], "calibration_finalized": False,
        "accepted": 0, "rejected": 0, "duplicate": 0, "repaired": 0, "regressions_prevented": 0,
        "checked_scope": [], "findings": [], "unverified_items": [], "summary": "",
    }


def validate_result(value: Mapping[str, Any], *, expected_assignment: Mapping[str, Any] | None = None,
                    expected_identity: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != RESULT_FIELDS or type(value["schema_version"]) is not int \
            or value["schema_version"] != RESULT_SCHEMA_VERSION:
        raise DispatchPolicyError("REVIEW_RESULT_SCHEMA_OR_FIELDS")
    assignment = value["dispatch_assignment"]
    validate_assignment(assignment)
    if expected_assignment is not None and canonical_json(assignment) != canonical_json(expected_assignment):
        raise DispatchPolicyError("REVIEW_RESULT_ASSIGNMENT_MISMATCH")
    if expected_identity is not None and any(value.get(key) != item for key, item in expected_identity.items()):
        raise DispatchPolicyError("REVIEW_RESULT_IDENTITY_MISMATCH")
    for key in ("reviewer", "task_id", "boundary_id"):
        if not isinstance(value[key], str) or not value[key] or len(value[key]) > 160:
            raise DispatchPolicyError("REVIEW_RESULT_IDENTITY_INVALID")
    if value["review_phase"] not in {"pre", "post"} or type(value["review_round"]) is not int or value["review_round"] < 1 \
            or not isinstance(value["packet_sha256"], str) or not HEX.fullmatch(value["packet_sha256"]):
        raise DispatchPolicyError("REVIEW_RESULT_PHASE_OR_PACKET")
    expected_id = result_id(boundary_id=value["boundary_id"], task_id=value["task_id"], phase=value["review_phase"],
                            round_number=value["review_round"], reviewer=value["reviewer"],
                            packet_sha256=value["packet_sha256"], assignment=assignment)
    if value["result_id"] != expected_id:
        raise DispatchPolicyError("REVIEW_RESULT_ID_MISMATCH")
    if value["status"] not in STATUSES or value["isolation_level"] not in ISOLATION_LEVELS \
            or value["task_difficulty"] not in DIFFICULTIES or not isinstance(value["summary"], str):
        raise DispatchPolicyError("REVIEW_RESULT_ENUM_INVALID")
    if value["calibration_finalized"] is not False:
        raise DispatchPolicyError("REVIEWER_CANNOT_FINALIZE_CALIBRATION")
    for key in ("duration_ms", "accepted", "rejected", "duplicate", "repaired", "regressions_prevented"):
        if type(value[key]) is not int or value[key] < 0:
            raise DispatchPolicyError("REVIEW_RESULT_COUNT_INVALID:" + key)
    if type(value["estimated_cost_units"]) is not int or value["estimated_cost_units"] != assignment["cost_basis_units"] \
            or value["cost_formula_version"] != policy(assignment["policy_id"])["cost_formula_version"]:
        raise DispatchPolicyError("REVIEW_RESULT_COST_MISMATCH")
    _strings(value["checked_scope"], "checked_scope")
    _strings(value["unverified_items"], "unverified_items")
    validate_findings(value["findings"], value["status"])
    return dict(value)


def validate_findings(findings: Any, status: str) -> None:
    """中文：新旧结果共用 Finding 语义，独立保留外层版本契约。

    English: Share finding semantics without reinterpreting versioned envelopes.
    """
    if not isinstance(findings, list) or len(findings) > 64:
        raise DispatchPolicyError("REVIEW_FINDING_LIMIT")
    ids: set[str] = set()
    for finding in findings:
        if not isinstance(finding, dict) or set(finding) != FINDING_FIELDS:
            raise DispatchPolicyError("REVIEW_FINDING_FIELDS")
        if any(not isinstance(finding[key], str) or not finding[key] for key in
               ("id", "dimension", "summary", "location", "root_cause_group")) or finding["id"] in ids:
            raise DispatchPolicyError("REVIEW_FINDING_IDENTITY")
        ids.add(finding["id"])
        if finding["severity"] not in {"blocking", "high", "medium", "low", "suggestion"} \
                or finding["evidence_level"] not in {"confirmed", "high-probability", "inference", "unverified"} \
                or finding["disposition"] not in DISPOSITIONS or finding["adoption_reason"] not in ADOPTION_REASONS:
            raise DispatchPolicyError("REVIEW_FINDING_ENUM")
        if any(type(finding[key]) is not bool for key in ("blocking", "repaired", "regression_prevented")):
            raise DispatchPolicyError("REVIEW_FINDING_BOOLEAN")
        _strings(finding["required_validation"], "required_validation")
        _strings(finding["regression_evidence"], "regression_evidence")
    if status == "pass" and findings:
        raise DispatchPolicyError("REVIEW_PASS_WITH_FINDINGS")
    if any(item["blocking"] for item in findings) and status not in {"blocking", "incomplete"}:
        raise DispatchPolicyError("REVIEW_BLOCKING_STATUS_MISMATCH")


def default_isolation() -> dict[str, Any]:
    return {"review_mode": "unknown", "parent_sandbox": "unknown", "declared_sandbox": "read-only",
            "probe_result": "not-run", "agent_config_confirmed": False, "runtime_agent_confirmed": False,
            "isolation_level": "unknown", "strict_readonly_eligible": False, "evidence": "", "verified_at": ""}


def derive_isolation(value: Mapping[str, Any]) -> tuple[str, bool]:
    if value.get("review_mode") == "self-review":
        return "self-review", False
    if value.get("probe_result") == "write-succeeded":
        return "logical-readonly", False
    if value.get("probe_result") == "sandbox-denied":
        confirmed = bool(value.get("runtime_agent_confirmed"))
        return ("system-readonly", True) if confirmed else ("unknown", False)
    if value.get("parent_sandbox") in {"workspace-write", "danger-full-access"}:
        return "logical-readonly", False
    if value.get("parent_sandbox") == "read-only":
        confirmed = bool(value.get("runtime_agent_confirmed")) and bool(value.get("agent_config_confirmed"))
        return ("system-readonly", True) if confirmed else ("unknown", False)
    return "unknown", False
