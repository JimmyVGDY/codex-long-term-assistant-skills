"""中文：桌面实际入口的门禁决策；与冻结的模型评分回放分离。

English: Decisions for actual Desktop gates, separate from frozen routing replay.
"""
from __future__ import annotations

import re
from typing import Any, Mapping


# 中文：登记真实处理器和事件；测试从安装器产物读回，不能仅遍历本表自证完整。
# English: Register real handlers/events; tests read installer output rather than
# proving coverage by iterating this table alone.
HOOK_ENTRYPOINTS = {
    "cp_gate.py": {"PreToolUse", "PostToolUse"},
    "cp_context.py": {"PreToolUse", "PostToolUse"},
    "cp_hook.py": {"UserPromptSubmit", "PreToolUse", "PostToolUse", "SubagentStart",
                   "SubagentStop", "Stop", "Interrupt", "SessionEnd"},
}
COMMAND_ENTRYPOINTS = {
    "execution_guard.transition": "workflow_stage",
    "execution_guard.validate": "workflow_validation",
    "execution_guard.finalize": "delivery_claim",
    "OperationWorkflow.prepare": "write_preparation",
    "OperationWorkflow.finish": "write_result",
    "g6_hook_v1._pretool": "dispatch",
    "g6_hook_v1._terminal": "dispatch_reconciliation",
    "package_manager._require_plugin_host": "installation_compatibility",
    "evolution.health.inspect_health": "observation_analysis",
}
DECISIONS = {"CONTINUE_DEFAULT", "CONTINUE_DEGRADED", "REPREPARE", "RETRY_BOUNDED",
             "WAIT_RECONCILE", "STOP_AFFECTED_ACTION"}


def result(*, gate_id: str, entrypoint: str, reason_code: str, decision: str,
           affected_action: str, next_action: str,
           exact_parameters: Mapping[str, Any] | None = None,
           evidence_state: str = "UNVERIFIED", retry_budget: int = 0) -> dict[str, Any]:
    """中文：继续与通过独立记录；不生成授权、宿主身份或成功回执。

    English: Keep continuation separate from verification; never mint authority,
    host identity, or success receipts.
    """
    if (decision not in DECISIONS or type(retry_budget) is not int
            or not 0 <= retry_budget <= 2
            or not re.fullmatch(r"[A-Z0-9_]{1,96}", reason_code)
            or evidence_state not in {"VERIFIED", "UNVERIFIED", "CONFIRMED_CONFLICT"}):
        raise ValueError("GATE_DECISION_INVALID")
    return {"schema_version": "desktop-gate-decision/1", "gate_id": gate_id,
            "entrypoint": entrypoint, "reason_code": reason_code,
            "evidence_state": evidence_state, "affected_action": affected_action,
            "decision": decision, "next_action": next_action,
            "exact_parameters": dict(exact_parameters or {}), "retry_budget": retry_budget,
            "verification_state": "VERIFIED" if evidence_state == "VERIFIED" else "UNVERIFIED"}


def write_failure(reason: str) -> dict[str, Any]:
    code = reason if re.fullmatch(r"[A-Z0-9_]{1,96}", reason) else "GATE_INPUT_UNAVAILABLE"
    retryable = code in {"GATE_HOST_DEADLINE", "GATE_WORKER_FAILED", "GATE_LOCK_BUSY",
                         "PATH_UNREADABLE", "OP_SCOPE_UNREADABLE", "GATE_INPUT_UNAVAILABLE"}
    refresh = code.startswith("INTENT_STALE_") or code in {
        "OP_SCOPE_CHANGED", "OP_REVISION_CONFLICT", "OP_POLICY_CHANGED", "OP_NOT_PREPARING"}
    conflict = any(part in code for part in (
        "IDENTITY_MISMATCH", "IDENTITY_CONFLICT", "PATH_ESCAPE", "SENSITIVE_PATH",
        "LINK_REJECTED", "HASH", "OP_INTENT_MISMATCH", "OP_POSTTOOL_CONFLICT"))
    action = "retry_same_operation" if retryable else "prepare_current_intent" if refresh else (
        "resolve_confirmed_conflict" if conflict else "adapt_supported_native_input")
    return result(gate_id="write_safety", entrypoint="cp_gate.py", reason_code=code,
                  decision="STOP_AFFECTED_ACTION" if conflict else
                           "RETRY_BOUNDED" if retryable else "REPREPARE",
                  affected_action="write", next_action=action,
                  evidence_state="CONFIRMED_CONFLICT" if conflict else "UNVERIFIED",
                  retry_budget=1 if retryable else 0)


def registration_inventory(hooks: Mapping[str, Any], *, source: str = "installer") -> list[dict[str, Any]]:
    """中文：检查受管安装结果；未知第三方处理器显式记为范围外。

    English: Inspect managed installation output and mark third-party handlers
    explicitly outside this package's coverage.
    """
    if source not in {"installer", "account"}:
        raise ValueError("GATE_INVENTORY_SOURCE")
    rows = []
    for event, groups in hooks.items():
        for group in groups:
            for hook in group.get("hooks", []):
                command = str(hook.get("command", ""))
                managed = (source == "installer" or "cp-assistant-hooks" in command
                           or "codex-cross-project-engineering-assistant" in command)
                names = re.findall(r"(?:^|[/\\\s\"])(cp_[a-z_]+\.py)(?=[\s\"]|$)", command)
                if not managed:
                    rows.append({"event": event, "scope": "external", "covered": False})
                    continue
                if len(names) != 1 or event not in HOOK_ENTRYPOINTS.get(names[0], set()):
                    raise ValueError("UNMAPPED_MANAGED_GATE_ENTRYPOINT")
                rows.append({"event": event, "entrypoint": names[0], "scope": "managed",
                             "matcher": group.get("matcher", "ALL"), "covered": True})
    return rows
