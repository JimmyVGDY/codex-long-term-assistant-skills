"""中文：不含宿主模型身份的追加式执行反馈。

English: Append-only execution feedback for later human-reviewed cost and routing optimization.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from .common import RuntimeContractError, append_jsonl, utc_now, validate_identifier

APPROVED_PROFILES = {"", "luna-low", "luna-medium", "terra-medium", "terra-high"}


def record_feedback(path: Path, payload: Dict[str, Any]) -> Dict[str, Any]:
    profile = str(payload.get("approved_dispatch_profile") or "").strip().lower()
    if profile not in APPROVED_PROFILES:
        raise RuntimeContractError("approved_dispatch_profile 非法")
    reserved_units = int(payload.get("reserved_units") or 0)
    if reserved_units < 0:
        raise RuntimeContractError("reserved_units 不能为负数")
    record = {
        "schema_version": 2,
        "task_id": validate_identifier(str(payload.get("task_id", "")), "task_id"),
        "project_id": validate_identifier(str(payload.get("project_id", "")), "project_id"),
        "complexity": payload.get("complexity", "L1"),
        "approved_dispatch_profile": profile,
        "reserved_units": reserved_units,
        "recommended_reviewers": int(payload.get("recommended_reviewers", 0)),
        "actual_reviewers": int(payload.get("actual_reviewers", 0)),
        "blocking_findings": int(payload.get("blocking_findings", 0)),
        "nonblocking_findings": int(payload.get("nonblocking_findings", 0)),
        "repair_rounds": int(payload.get("repair_rounds", 0)),
        "routing_deviation": payload.get("routing_deviation", "NONE"),
        "quality_outcome": payload.get("quality_outcome", "unknown"),
        "evidence_level": payload.get("evidence_level", "unverified"),
        "recorded_at": utc_now(),
        "limitations": "反馈不包含宿主模型身份，仅用于人工评估且不自动修改预算或路由规则",
    }
    append_jsonl(path, record)
    return record
