"""Append-only execution feedback for later human-reviewed cost/routing optimization."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from .common import append_jsonl, utc_now, validate_identifier


def record_feedback(path: Path, payload: Dict[str, Any]) -> Dict[str, Any]:
    record = {
        "schema_version": 1,
        "task_id": validate_identifier(str(payload.get("task_id", "")), "task_id"),
        "project_id": validate_identifier(str(payload.get("project_id", "")), "project_id"),
        "complexity": payload.get("complexity", "L1"),
        "recommended_model": payload.get("recommended_model", ""),
        "actual_model": payload.get("actual_model", ""),
        "recommended_reviewers": int(payload.get("recommended_reviewers", 0)),
        "actual_reviewers": int(payload.get("actual_reviewers", 0)),
        "blocking_findings": int(payload.get("blocking_findings", 0)),
        "nonblocking_findings": int(payload.get("nonblocking_findings", 0)),
        "repair_rounds": int(payload.get("repair_rounds", 0)),
        "routing_deviation": payload.get("routing_deviation", "NONE"),
        "quality_outcome": payload.get("quality_outcome", "unknown"),
        "evidence_level": payload.get("evidence_level", "unverified"),
        "recorded_at": utc_now(),
        "limitations": "反馈仅用于人工评估，不自动修改模型、预算或路由规则",
    }
    append_jsonl(path, record)
    return record
