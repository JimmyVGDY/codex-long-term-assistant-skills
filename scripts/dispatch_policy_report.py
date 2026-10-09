"""中文：严格验证当前合成派发报告，不将其提升为原生验收证明。

English: Validate current synthetic dispatch reports without promoting them to native acceptance evidence.
"""
from __future__ import annotations

from typing import Any, Mapping

from cp_runtime.dispatch_policy import policy as legacy_policy
from cp_runtime.g6_flexible_policy import POLICY_ID, PROFILES

SCHEMA = "4.0"
FIELDS = {"ok", "schema_version", "policy_id", "evidence_scope", "native_model_calls",
          "dispatch_policy_status", "automatic_ceiling_profile", "registered_reviewer_ceiling_profile",
          "current_case_count", "legacy_case_count", "case_count", "cases", "legacy_policy_id",
          "legacy_cases", "legacy_evidence_scope", "test_state_isolation", "privacy"}


def expected_cases() -> tuple[dict[str, str], dict[str, str]]:
    """中文：完整组合与拒绝边界来自版本化策略，不能由报告自行声明覆盖范围。

    English: Versioned policy defines complete combinations and denial boundaries, not the submitted report.
    """
    current = {role + "-" + profile: "allow"
               for role in ("cp_review_data_contract", "worker", "explorer") for profile in PROFILES}
    current["missing-evidence-default"] = "allow"
    negative = {"deny-" + value: "deny" for value in ("xhigh", "max", "ultra", "unknown-role",
                                                    "implicit-review", "unknown-model")}
    current.update(negative)
    current["deny-legacy-default"] = "deny"
    old = legacy_policy("reviewer-matrix-v3")
    legacy = {role + "-" + name: "allow" if name in old["role_profiles"][role] else "deny"
              for role in ("reviewer", "worker", "explorer") for name in old["profiles"]}
    legacy.update(negative)
    return current, legacy


def _rows(rows: Any, expected: Mapping[str, str], *, native_shape: bool) -> None:
    if not isinstance(rows, list) or len(rows) != len(expected):
        raise ValueError("dispatch evidence coverage is incomplete")
    required = {"case_id", "expected", "observed", "pass"} | ({"exit_code"} if native_shape else set())
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != required:
            raise ValueError("dispatch evidence case fields are invalid")
        case_id = row["case_id"]
        if not isinstance(case_id, str) or case_id in seen or case_id not in expected:
            raise ValueError("dispatch evidence case identity is invalid")
        if row["expected"] != expected[case_id] or row["observed"] != expected[case_id] or row["pass"] is not True:
            raise ValueError("dispatch evidence case did not pass its required behavior")
        if native_shape and (type(row["exit_code"]) is not int or row["exit_code"] != 0):
            raise ValueError("dispatch evidence Hook did not exit successfully")
        seen.add(case_id)


def validate_current_report(report: Mapping[str, Any]) -> dict[str, Any]:
    """中文：保持严格范围、数量和隐私声明，旧版报告交给原解释器。

    English: Enforce scope, counts and privacy exactly; historical reports retain their original readers.
    """
    if not isinstance(report, Mapping) or set(report) != FIELDS:
        raise ValueError("dispatch evidence fields are invalid")
    if (report["schema_version"] != SCHEMA or report["policy_id"] != POLICY_ID
            or report["evidence_scope"] != "synthetic-policy-only" or report["ok"] is not True
            or report["dispatch_policy_status"] != "PASS"
            or report["automatic_ceiling_profile"] != "g6-astra-high"
            or report["registered_reviewer_ceiling_profile"] != "g6-astra-high"
            or type(report["native_model_calls"]) is not int or report["native_model_calls"] != 0
            or report["legacy_policy_id"] != "reviewer-matrix-v3"
            or report["legacy_evidence_scope"] != "frozen-tuple-admission-only; lifecycle replay tested separately"
            or report["test_state_isolation"] != "temporary CODEX_HOME and CP_ASSISTANT_DATA"):
        raise ValueError("dispatch evidence scope or policy is invalid")
    current, legacy = expected_cases()
    for field, count in (("current_case_count", len(current)), ("legacy_case_count", len(legacy)),
                         ("case_count", len(current) + len(legacy))):
        if type(report[field]) is not int or report[field] != count:
            raise ValueError("dispatch evidence counts are invalid")
    _rows(report["cases"], current, native_shape=True)
    _rows(report["legacy_cases"], legacy, native_shape=False)
    privacy = report["privacy"]
    if (not isinstance(privacy, dict)
            or set(privacy) != {"host_model_information_collected", "host_model_information_exported"}
            or any(value is not False for value in privacy.values())):
        raise ValueError("dispatch evidence privacy declaration is invalid")
    return {"schema_version": SCHEMA, "evidence_scope": "synthetic-policy-only",
            "automatic_ceiling_profile": "g6-astra-high", "required_cases": len(current) + len(legacy)}
