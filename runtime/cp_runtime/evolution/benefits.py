"""中文：实施验证与观察收益分离，重放时重新核验全部引用。

English: Separate implementation validation from observed benefit, rechecking references on replay.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from .artifacts import ArtifactError, load, persist, project_identity, seal
from .contracts import OptimizationProposal, parse_iso_datetime, sha256_hex, to_primitive, utc_now_iso
from .hypothesis import metric_value
from .snapshots import load_snapshot
from .task_feedback import VALIDATION_SCHEMA


def implementation_evidence(project_dir: Path, task_id: str, commit: str,
                            paths: Sequence[str]) -> list[dict[str, str]]:
    if not re.fullmatch(r"[0-9a-f]{40,64}", commit) or not 1 <= len(paths) <= 100:
        raise ArtifactError("IMPLEMENTATION_EVIDENCE_REQUIRED")
    identity = project_identity(project_dir, verify_live=False)
    references = []
    for path in paths:
        value = load(project_dir, path, schema=VALIDATION_SCHEMA)
        if value["subject"]["task_id"] != task_id or any(value["subject"].get(key) != item for key, item in identity.items()):
            raise ArtifactError("IMPLEMENTATION_IDENTITY_MISMATCH")
        if value.get("commit") != commit or value.get("exit_code") != 0 or value.get("workspace_unchanged") is not True:
            raise ArtifactError("IMPLEMENTATION_VALIDATION_NOT_PASSED")
        references.append({"path": path, "content_hash": value["content_hash"]})
    if len({ref["path"] for ref in references}) != len(references):
        raise ArtifactError("IMPLEMENTATION_EVIDENCE_DUPLICATE")
    return references


def evaluate_benefit(project_dir: Path, proposal: OptimizationProposal, *, implementation_task_id: str,
                     git_baseline: str, implementation_commit: str, validation_refs: Sequence[Mapping[str, str]],
                     before_ref: Mapping[str, str], after_ref: Mapping[str, str]) -> dict[str, Any]:
    hypothesis = proposal.hypothesis
    if hypothesis is None:
        raise ArtifactError("LEGACY_PROPOSAL_HAS_NO_BENEFIT_HYPOTHESIS")
    before = load_snapshot(project_dir, before_ref)
    after = load_snapshot(project_dir, after_ref)
    if before.content_hash != hypothesis["baseline_snapshot_hash"] or before.snapshot_id != hypothesis["baseline_snapshot_id"]:
        raise ArtifactError("BENEFIT_BASELINE_MISMATCH")
    if before.metrics.get("policy_digest") != after.metrics.get("policy_digest"):
        raise ArtifactError("BENEFIT_POLICY_MISMATCH")
    for snapshot in (before, after):
        if parse_iso_datetime(snapshot.observed_at, "observed_at") > parse_iso_datetime(utc_now_iso(), "now"):
            raise ArtifactError("BENEFIT_FUTURE_INPUT")
        if snapshot.project_id != proposal.project_id or snapshot.metrics.get("repo_fingerprint") != hypothesis["scope"]["repo_fingerprint"]:
            raise ArtifactError("BENEFIT_SCOPE_MISMATCH")
    actual_refs = implementation_evidence(project_dir, implementation_task_id, implementation_commit,
                                          [ref["path"] for ref in validation_refs])
    if actual_refs != [dict(ref) for ref in validation_refs]:
        raise ArtifactError("IMPLEMENTATION_REFERENCE_CHANGED")
    validation_times = [parse_iso_datetime(load(project_dir, ref["path"], ref["content_hash"])["observed_at"], "observed_at")
                        for ref in validation_refs]
    reasons = []
    before_tasks = set(before.metrics.get("independent_task_ids", []))
    after_tasks = set(after.metrics.get("independent_task_ids", []))
    if implementation_task_id in before_tasks | after_tasks:
        raise ArtifactError("BENEFIT_IMPLEMENTATION_IN_COHORT")
    if before_tasks & after_tasks:
        raise ArtifactError("BENEFIT_COHORT_OVERLAP")
    minimum = hypothesis["minimum_independent_tasks"]
    if len(before_tasks) < minimum or len(after_tasks) < minimum:
        reasons.append("INSUFFICIENT_INDEPENDENT_TASKS")
    if not before.window_end or not after.window_start or not after.window_end:
        reasons.append("INSUFFICIENT_OBSERVATION_WINDOW")
    else:
        before_end = parse_iso_datetime(before.window_end, "window_end")
        after_start = parse_iso_datetime(after.window_start, "window_start")
        after_end = parse_iso_datetime(after.window_end, "window_end")
        if after_start <= before_end or after_start < max(validation_times):
            raise ArtifactError("BENEFIT_WINDOW_PRECEDES_IMPLEMENTATION")
        if after_end > parse_iso_datetime(after.observed_at, "observed_at"):
            raise ArtifactError("BENEFIT_FUTURE_INPUT")
        if (after_end - after_start).total_seconds() < hypothesis["minimum_window_days"] * 86400:
            reasons.append("INSUFFICIENT_OBSERVATION_WINDOW")
    metric = hypothesis["metric"]
    target_resource = hypothesis["scope"]["metric_target"]
    baseline = metric_value(before.metrics, metric, target_resource)
    observed = metric_value(after.metrics, metric, target_resource)
    if baseline != hypothesis["baseline"]:
        raise ArtifactError("BENEFIT_BASELINE_VALUE_MISMATCH")
    if observed is None or baseline is None or hypothesis["target"] is None:
        reasons.append("METRIC_UNAVAILABLE")
    coverage = after.metrics.get("known_terminal_outcome_coverage", 0)
    if coverage < hypothesis["guardrails"]["minimum_known_terminal_outcome_coverage"]:
        reasons.append("INSUFFICIENT_OUTCOME_COVERAGE")
    regression = after.metrics.get("negative_outcome_rate", 1) > hypothesis["guardrails"]["maximum_negative_outcome_rate"]
    if reasons:
        status = "INSUFFICIENT"
    elif regression:
        status = "REGRESSED"
    else:
        supported = observed <= hypothesis["target"] if hypothesis["direction"] == "decrease" else observed >= hypothesis["target"]
        status = "SUPPORTED" if supported else "NOT_SUPPORTED"
    return {
        "schema_version": "benefit-report/1", "proposal_id": proposal.proposal_id,
        "proposal_hash": proposal.content_hash, "project_id": proposal.project_id,
        "repo_fingerprint": hypothesis["scope"]["repo_fingerprint"], "implementation_task_id": implementation_task_id,
        "git_baseline": git_baseline, "implementation_commit": implementation_commit,
        "validation_refs": [dict(ref) for ref in validation_refs], "before_ref": dict(before_ref), "after_ref": dict(after_ref),
        "implementation_status": "PASS", "benefit_status": status, "reason_codes": reasons,
        "metric": metric, "baseline": baseline, "observed": observed, "target": hypothesis["target"],
        "independent_after_tasks": len(after_tasks), "observed_at": after.observed_at,
        "execution_authorization": "NONE",
    }


def persist_benefit(project_dir: Path, report: Mapping[str, Any]) -> dict[str, str]:
    value = seal(report)
    return persist(project_dir, "evolution/benefit-reports/" + value["content_hash"] + ".json", value)


def verify_benefit(project_dir: Path, reference: Mapping[str, str], proposal: OptimizationProposal,
                   implementation_task_id: str, git_baseline: str, implementation_commit: str) -> dict[str, Any]:
    report = load(project_dir, reference["path"], reference["content_hash"], "benefit-report/1")
    if report["implementation_task_id"] != implementation_task_id or report["git_baseline"] != git_baseline or report["implementation_commit"] != implementation_commit:
        raise ArtifactError("BENEFIT_IMPLEMENTATION_MISMATCH")
    rebuilt = evaluate_benefit(project_dir, proposal, implementation_task_id=implementation_task_id,
                               git_baseline=git_baseline, implementation_commit=implementation_commit,
                               validation_refs=report["validation_refs"], before_ref=report["before_ref"], after_ref=report["after_ref"])
    if seal(rebuilt) != report:
        raise ArtifactError("BENEFIT_RECOMPUTATION_MISMATCH")
    return report
