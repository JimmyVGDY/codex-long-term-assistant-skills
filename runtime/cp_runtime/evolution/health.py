"""中文：分析前的只读健康门禁，区分无信号与无法观察。

English: Read-only pre-analysis health gates distinguishing no signal from unavailable observation.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from .artifacts import ArtifactError, project_identity
from .contracts import EvolutionPolicy, SelfObservationSnapshot, parse_iso_datetime, sha256_hex, utc_now_iso, to_primitive
from .observation import observe_project


def inspect_health(project_dir: Path, project_id: str, policy: EvolutionPolicy, *,
                   explicit_sources: Sequence[str] | None = None, observed_at: str | None = None,
                   max_age_days: int = 30) -> tuple[dict[str, Any], SelfObservationSnapshot | None]:
    if type(max_age_days) is not int or not 1 <= max_age_days <= 365:
        raise ArtifactError("INVALID_FRESHNESS_LIMIT")
    now = observed_at or utc_now_iso()
    timestamp = parse_iso_datetime(now, "observed_at")
    result: dict[str, Any] = {
        "schema_version": "evolution-health/1", "project_id": project_id, "checked_at": now,
        "policy_version": policy.policy_version, "policy_digest": sha256_hex(policy),
        "status": "IDENTITY_UNAVAILABLE", "reason_codes": [], "analysis_allowed": False,
        "execution_authorization": "NONE", "checks": {},
    }
    try:
        identity = project_identity(project_dir)
        if identity["project_id"] != project_id:
            raise ArtifactError("PROJECT_IDENTITY_MISMATCH")
        result["repo_fingerprint"] = identity["repo_fingerprint"]
        result["checks"]["identity"] = "PASS"
    except Exception as exc:
        code = str(exc)
        status = "IDENTITY_MISMATCH" if "MISMATCH" in code else "DATA_DAMAGED" if (project_dir / "project-profile.json").exists() else "IDENTITY_UNAVAILABLE"
        result.update(status=status, reason_codes=[status])
        return result, None
    try:
        snapshot = observe_project(project_id, project_dir, policy, explicit_sources, now)
    except Exception as exc:
        status = getattr(exc, "code", "DATA_DAMAGED")
        result.update(status=status, reason_codes=[status])
        return result, None
    metrics = snapshot.metrics
    lifecycle = metrics.get("lifecycle", {})
    checks = result["checks"]
    checks.update(integrity="PASS", task_count=snapshot.task_count,
                  known_terminal_outcome_coverage=metrics.get("known_terminal_outcome_coverage", 0),
                  lifecycle_completeness_rate=lifecycle.get("lifecycle_completeness_rate", 0),
                  session_end_coverage=lifecycle.get("session_end_coverage", 0),
                  reviewer_cost_coverage=metrics.get("reviewer_cost_coverage", 0),
                  reviewer_attribution_coverage={key: value.get("attribution_coverage", 0)
                                                 for key, value in metrics.get("reviewer_stats", {}).items()},
                  signal_eligibility=to_primitive(metrics.get("signal_eligibility", {})))
    if snapshot.window_end is None:
        result.update(status="INSUFFICIENT_DATA", reason_codes=["NO_TIMESTAMPED_TASKS"])
        return result, snapshot
    end = parse_iso_datetime(snapshot.window_end, "window_end")
    age = (timestamp - end).total_seconds()
    checks["newest_record_age_seconds"] = age
    if age < -300:
        result.update(status="DATA_DAMAGED", reason_codes=["FUTURE_DATED_INPUT"])
        return result, snapshot
    if age > max_age_days * 86400:
        result.update(status="STALE_DATA", reason_codes=["STALE_OBSERVATION_WINDOW"])
        return result, snapshot
    if not metrics.get("evidence_sufficient"):
        result.update(status="INSUFFICIENT_DATA", reason_codes=["SIGNAL_EVIDENCE_GATES_NOT_MET"])
        return result, snapshot
    result.update(status="READY" if snapshot.signals else "HEALTHY_NO_SIGNAL", analysis_allowed=True)
    blocked = [key for key, gate in metrics.get("signal_eligibility", {}).items() if not gate["eligible"]]
    if blocked:
        result["reason_codes"] = ["PARTIAL_SIGNAL_COVERAGE"]
        result["blocked_signals"] = blocked
    return result, snapshot
