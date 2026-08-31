"""Explicit workflow-level approval records bound to project, task and baseline."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .common import (
    RuntimeContractError,
    atomic_write_json,
    normalize_environment,
    parse_iso,
    read_json,
    repo_snapshot,
    require_external_state,
    utc_now,
    validate_identifier,
)
from .contracts import ApprovalCheckResult
from .project import load_profile

SCHEMA = 1
PROTECTED_OPERATIONS = {
    "commit", "push", "deploy", "restart", "data-write", "production-operation", "make-effective"
}


def _approval_payload(
    approval_id: str,
    project_id: str,
    task_id: str,
    operations: Iterable[str],
    environment: str,
    baseline_sha256: str,
    expires_at: str,
    approved_by: str,
    note: str,
    one_time: bool,
) -> Dict[str, Any]:
    normalized_operations = sorted({item.strip().lower() for item in operations if item.strip()})
    if not normalized_operations:
        raise RuntimeContractError("approval operations 不能为空")
    unsupported = sorted(set(normalized_operations) - PROTECTED_OPERATIONS)
    if unsupported:
        raise RuntimeContractError("不支持的 Approval operation: " + ",".join(unsupported))
    expires = parse_iso(expires_at)
    if expires <= parse_iso(utc_now()):
        raise RuntimeContractError("Approval 过期时间必须晚于当前时间")
    return {
        "schema_version": SCHEMA,
        "approval_id": validate_identifier(approval_id, "approval_id"),
        "project_id": validate_identifier(project_id, "project_id"),
        "task_id": validate_identifier(task_id, "task_id"),
        "operations": normalized_operations,
        "environment": normalize_environment(environment),
        "baseline_sha256": baseline_sha256,
        "approved_by": approved_by.strip() or "explicit-user-approval",
        "note": note.strip(),
        "one_time": bool(one_time),
        "issued_at": utc_now(),
        "expires_at": expires.isoformat(),
        "consumed_at": None,
        "status": "active",
        "limitations": [
            "这是工作流级授权记录，不是 Codex 平台或操作系统权限边界",
            "Evidence 不会自动创建 Approval",
            "基线、项目、任务、环境或操作不一致时必须失败关闭",
        ],
    }


def issue_approval(
    output: Path,
    approval_id: str,
    profile_path: Path,
    task_id: str,
    operations: Iterable[str],
    environment: str,
    repo_path: Path,
    expires_at: str,
    approved_by: str = "explicit-user-approval",
    note: str = "",
    one_time: bool = True,
) -> Dict[str, Any]:
    profile = load_profile(profile_path)
    snapshot = repo_snapshot(repo_path)
    require_external_state(output.expanduser().resolve(), Path(snapshot["repo_path"]))
    expected_repo = Path(profile["identity"]["repo_path"]).expanduser().resolve()
    if expected_repo != Path(snapshot["repo_path"]).resolve():
        raise RuntimeContractError("Approval 仓库与 Project Profile 不一致")
    payload = _approval_payload(
        approval_id, str(profile["project_id"]), task_id, operations,
        environment, snapshot["sha256"], expires_at, approved_by, note, one_time,
    )
    return atomic_write_json(output, payload, seal=True)


def load_approval(path: Path) -> Dict[str, Any]:
    value = read_json(path, verify=True, label="Approval")
    if value.get("schema_version") != SCHEMA:
        raise RuntimeContractError("不支持的 Approval schema_version")
    return value


def check_approval(
    approval_path: Path,
    project_id: str,
    task_id: str,
    operation: str,
    environment: str,
    baseline_sha256: str,
) -> ApprovalCheckResult:
    record = load_approval(approval_path)
    reasons: List[str] = []
    normalized_operation = operation.strip().lower()
    normalized_environment = normalize_environment(environment)
    if record.get("status") != "active":
        reasons.append("approval-status-not-active")
    if record.get("project_id") != project_id:
        reasons.append("project-id-mismatch")
    if record.get("task_id") != task_id:
        reasons.append("task-id-mismatch")
    if normalized_operation not in record.get("operations", []):
        reasons.append("operation-not-approved")
    if record.get("environment") != normalized_environment:
        reasons.append("environment-mismatch")
    if record.get("baseline_sha256") != baseline_sha256:
        reasons.append("baseline-mismatch")
    if parse_iso(record["expires_at"]) <= parse_iso(utc_now()):
        reasons.append("approval-expired")
    consumed = bool(record.get("consumed_at"))
    if record.get("one_time") and consumed:
        reasons.append("approval-already-consumed")
    return ApprovalCheckResult(
        valid=not reasons,
        reasons=tuple(reasons),
        approval_id=str(record.get("approval_id", "")),
        operation=normalized_operation,
        environment=normalized_environment,
        consumed=consumed,
    )


def consume_approval(
    approval_path: Path,
    project_id: str,
    task_id: str,
    operation: str,
    environment: str,
    baseline_sha256: str,
) -> Dict[str, Any]:
    result = check_approval(
        approval_path, project_id, task_id, operation, environment, baseline_sha256
    )
    if not result.valid:
        raise RuntimeContractError("Approval 无效: " + ",".join(result.reasons))
    record = load_approval(approval_path)
    if record.get("one_time"):
        record["consumed_at"] = utc_now()
        record["status"] = "consumed"
        record["consumed_operation"] = operation.strip().lower()
        atomic_write_json(approval_path, record, seal=True)
    return record
