"""中文：独立于授权的 Evidence 记录与时效检查。

English: Evidence records and freshness checks independent from authorization.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .common import (
    RuntimeContractError,
    append_jsonl,
    atomic_write_json,
    read_json,
    repo_snapshot,
    require_external_state,
    utc_now,
    validate_identifier,
)
from .contracts import EvidenceCheckResult, EvidenceFreshness
from .project import load_profile

SCHEMA = 1
STATUSES = {"valid", "failed", "blocked", "unknown"}
KINDS = {"validation", "review", "commit", "push", "deployment", "restart", "readback", "effect", "other"}


def record_evidence(
    output: Path,
    evidence_id: str,
    profile_path: Path,
    task_id: str,
    repo_path: Path,
    kind: str,
    subject: str,
    status: str,
    source: str,
    summary: str,
    scope_refs: Iterable[str] = (),
    confidence: str = "L2",
) -> Dict[str, Any]:
    normalized_kind = kind.strip().lower()
    normalized_status = status.strip().lower()
    if normalized_kind not in KINDS:
        raise RuntimeContractError("非法 Evidence kind")
    if normalized_status not in STATUSES:
        raise RuntimeContractError("非法 Evidence status")
    profile = load_profile(profile_path)
    snapshot = repo_snapshot(repo_path)
    require_external_state(output.expanduser().resolve(), Path(snapshot["repo_path"]))
    expected_repo = Path(profile["identity"]["repo_path"]).expanduser().resolve()
    if expected_repo != Path(snapshot["repo_path"]).resolve():
        raise RuntimeContractError("Evidence 仓库与 Project Profile 不一致")
    record: Dict[str, Any] = {
        "schema_version": SCHEMA,
        "evidence_id": validate_identifier(evidence_id, "evidence_id"),
        "project_id": str(profile["project_id"]),
        "task_id": validate_identifier(task_id, "task_id"),
        "kind": normalized_kind,
        "subject": subject.strip(),
        "status": normalized_status,
        "source": source.strip(),
        "summary": summary.strip(),
        "scope_refs": sorted({item.strip() for item in scope_refs if item.strip()}),
        "baseline": snapshot,
        "freshness": EvidenceFreshness.CURRENT.value,
        "confidence": confidence,
        "recorded_at": utc_now(),
        "limitations": [
            "Evidence 只证明记录范围内的观察，不授予 commit/push/deploy/restart/data-write 权限",
            "仓库指纹变化后必须重新判断 freshness",
        ],
    }
    sealed = atomic_write_json(output, record, seal=True)
    append_jsonl(profile_path.parent / "evidence-ledger.jsonl", {
        "evidence_id": sealed["evidence_id"],
        "path": str(output.expanduser().resolve()),
        "project_id": sealed["project_id"],
        "task_id": sealed["task_id"],
        "kind": sealed["kind"],
        "status": sealed["status"],
        "baseline_sha256": snapshot["sha256"],
        "recorded_at": sealed["recorded_at"],
    })
    return sealed


def load_evidence(path: Path) -> Dict[str, Any]:
    value = read_json(path, verify=True, label="Evidence")
    if value.get("schema_version") != SCHEMA:
        raise RuntimeContractError("不支持的 Evidence schema_version")
    return value


def check_evidence(
    evidence_path: Path,
    repo_path: Optional[Path] = None,
    project_id: Optional[str] = None,
    task_id: Optional[str] = None,
) -> EvidenceCheckResult:
    record = load_evidence(evidence_path)
    reasons: List[str] = []
    freshness = EvidenceFreshness.NOT_CAPTURED
    if project_id and record.get("project_id") != project_id:
        reasons.append("project-id-mismatch")
    if task_id and record.get("task_id") != task_id:
        reasons.append("task-id-mismatch")
    baseline = record.get("baseline")
    if repo_path is not None and isinstance(baseline, dict) and baseline.get("sha256"):
        current = repo_snapshot(repo_path)
        freshness = EvidenceFreshness.CURRENT if current["sha256"] == baseline["sha256"] else EvidenceFreshness.STALE
        if freshness is EvidenceFreshness.STALE:
            reasons.append("repository-baseline-changed")
    else:
        reasons.append("repository-freshness-not-checked")
    if record.get("status") != "valid":
        reasons.append("evidence-status-not-valid")
    return EvidenceCheckResult(
        valid=not reasons and freshness is EvidenceFreshness.CURRENT,
        freshness=freshness,
        reasons=tuple(reasons),
        evidence_id=str(record.get("evidence_id", "")),
    )
